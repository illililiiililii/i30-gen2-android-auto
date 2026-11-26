"""Show the GD13MY guest's LCD framebuffer in a Windows desktop window."""

import argparse
from contextlib import nullcontext
from datetime import datetime
import json
from math import ceil, isfinite
from pathlib import Path
from queue import Empty, SimpleQueue
from os import fstat
import re
import struct
from threading import Event, Thread
from time import monotonic
import tkinter as tk
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_PC

import emulate_gd13my
from emulate_gd13my import KernelRun, ROM_PATH, ROOT, TIMER_HZ, ReadOnlyHsMmc
from gd13my_arm import RM, instruction, translate
from gd13my_disk_state import persistent_diska
from gd13my_guest_clock import UTC_PLACEHOLDER, utc_mailbox
from gd13my_mmio import MicomCdp, TouchController


BOOT_DIR = ROOT / 'build/gd13my-boot'
DISK_START_LBA = 131070
NAVIGATION_MENU_PACKET = b'\x60\x02\x1e\x01'
NAVIGATION_START_PACKET = b'\xe0\x02\x04\x02'
NAVIGATION_READY = b'MAIN mode ACK from APP ---Request mode: 0x0,  Current App 0x2 <-- 0x2'
NAVIGATION_MENU_ACK = b'CMAP::OnHardKey_NAVIMENU()'
USB_TEST_READY = b'i30 USB attach ready. Connect Samsung phone.'
USB_TEST_SUCCESS = b'Phone answered the Android Auto version request.\r\n'
USB_TEST_FAILURE = b'USB accessory found, but the version request failed.\r\n'
USB_AUTH_STATUS = {
    b'i30 CE TLS waiting for enrolled trust material.': '실폰 버전 확인 · 헤드유닛 인증 자료 미등록',
    b'i30 CE TLS guest UTC unavailable or invalid.': 'WinCE UTC 시각을 읽지 못했거나 시각이 유효하지 않음',
    b'i30 CE TLS trust CA missing, unreadable or invalid.': 'WinCE TLS 신뢰 CA 파일 확인 필요',
    b'i30 CE TLS peer hostname or fingerprint configuration invalid.': '폰 인증서 이름 또는 지문 설정 확인 필요',
    b'i30 CE TLS head unit certificate missing, unreadable or invalid.': '헤드유닛 인증서 파일 확인 필요',
    b'i30 CE TLS head unit certificate is not yet valid at guest UTC.': 'WinCE 시각이 헤드유닛 인증서 유효 시작일 이전임',
    b'i30 CE TLS head unit certificate expired at guest UTC.': 'WinCE 시각에서 헤드유닛 인증서가 만료됨',
    b'i30 CE TLS head unit RSA key missing, unreadable or invalid.': '헤드유닛 RSA 키 파일 확인 필요',
    b'i30 CE TLS head unit certificate and RSA key do not match.': '헤드유닛 인증서와 RSA 키 불일치',
    b'i30 CE TLS phone certificate rejected at guest UTC.': 'WinCE 시각 기준으로 폰 인증서 유효기간 검증 실패',
    b'i30 CE TLS phone certificate trust or peer identity rejected.': '폰 인증서 신뢰 체인 또는 이름·지문 검증 실패',
    b'i30 CE TLS phone certificate hostname does not match.': '등록한 폰 인증서 이름 불일치',
    b'i30 CE TLS phone certificate fingerprint does not match.': '등록한 폰 인증서 지문 불일치',
    b'i30 CE TLS phone certificate chain has no trusted anchor.': 'WinCE가 폰 인증서 체인을 신뢰하지 않음',
    b'i30 CE TLS phone rejected the head unit certificate chain (unknown CA).': '폰이 헤드유닛 인증서 발급자를 신뢰하지 않음',
    b'i30 CE TLS phone sent a fatal alert.': '폰이 TLS 연결을 종료함 · UART의 TLS 경고 코드 확인',
    b'i30 CE TLS USB read interrupted while waiting for the phone.': 'TLS 도중 폰의 USB 응답을 받지 못함',
    b'i30 CE TLS USB write interrupted.': 'TLS 메시지 USB 전송 실패',
    b'i30 CE TLS invalid Android Auto handshake frame.': 'Android Auto TLS 프레임 형식 오류',
    b'i30 CE TLS protocol version rejected.': 'TLS 프로토콜 버전 거부',
    b'i30 CE TLS cipher suite rejected.': 'TLS 암호 스위트 거부',
    b'i30 CE TLS unexpected handshake record or message.': '예상하지 않은 TLS 핸드셰이크 레코드 또는 메시지',
    b'i30 CE TLS engine stopped during handshake.': 'WinCE에서 TLS 처리 중단 · UART의 BearSSL 오류 코드 확인',
    b'i30 CE failed to set emulator UTC.': 'WinCE 가상 시계 초기화 실패',
    b'i30 CE TLS configuration rejected.': 'WinCE TLS 인증 설정을 읽거나 검증하지 못함',
    b'i30 CE TLS handshake rejected or interrupted.': 'WinCE TLS 연결 거부 또는 중단',
    b'i30 CE service discovery incomplete.': 'WinCE Android Auto 서비스 협상 중단',
    b'i30 CE authenticated service discovery completed.': 'WinCE 인증 및 서비스 탐색 완료 · 영상 출력권 대기',
    b'i30 CE projection frame presented.': 'WinCE에서 Android Auto 영상 프레임 표시',
    b'i30 CE projection yielded to the stock display.': '순정 화면 우선 · Android Auto 영상 일시 중지',
    b'i30 CE projection resumed on its authorized surface.': '순정 화면 해제 · Android Auto 영상 재개',
    b'i30 CE projection released the display.': 'WinCE Android Auto 영상 종료',
}
USB_MARKERS = (USB_TEST_READY, USB_TEST_SUCCESS, USB_TEST_FAILURE, *USB_AUTH_STATUS)
USB_TEST_EVENT = re.compile(b'|'.join(re.escape(marker) for marker in USB_MARKERS))
USB_TEST_TAIL = max(map(len, USB_MARKERS)) - 1
NAVIGATION_KEYS = {
    'position': (b'\x60\x02\x1f\x01', '현위치'),
    'destination': (b'\x60\x02\x38\x01', '목적지'),
}
VOLUME_STEPS = {'volume_down': -1, 'volume_up': 1}


class AppPartitionOverlay:
    """Read DiskA from a compact bench image and the other sectors from the full image."""

    def __init__(self, media, app):
        self.media, self.app = media, app
        media.seek(0)
        app.seek(0)
        base_mbr, app_mbr = media.read(512), app.read(512)
        if (len(base_mbr) != 512 or len(app_mbr) != 512 or base_mbr[510:] != b'\x55\xaa' or
                app_mbr[510:] != b'\x55\xaa' or base_mbr[446:462] != app_mbr[446:462] or base_mbr[450] != 0x0c):
            raise ValueError('APP overlay and full media must have the same first FAT32 partition')
        start, sectors = struct.unpack_from('<II', base_mbr, 454)
        self.start, self.end = start * 512, (start + sectors) * 512
        if (not start or not sectors or self.end > fstat(media.fileno()).st_size or
                self.end != fstat(app.fileno()).st_size or any(app_mbr[462:510])):
            raise ValueError('Expected a compact image containing only the original DiskA partition')
        self.position = 0
        self.utc_offset = None

    def enable_host_utc(self, offset):
        if offset % 512 or not self.start <= offset <= self.end - len(UTC_PLACEHOLDER):
            raise ValueError('Invalid DiskA UTC mailbox offset')
        self.app.seek(offset)
        if self.app.read(len(UTC_PLACEHOLDER)) != UTC_PLACEHOLDER:
            raise ValueError('DiskA does not contain the reserved UTC mailbox at this offset')
        self.utc_offset = offset

    def fileno(self):
        return self.media.fileno()

    def seek(self, offset):
        self.position = offset

    def read(self, size):
        start = self.position
        end = self.position + size
        chunks = []
        while self.position < end:
            if self.position < self.start:
                stream, limit = self.media, self.start
            elif self.position < self.end:
                stream, limit = self.app, self.end
            else:
                stream, limit = self.media, end
            stream.seek(self.position)
            count = min(end, limit) - self.position
            data = stream.read(count)
            chunks.append(data)
            self.position += len(data)
            if len(data) != count:
                break
        data = b''.join(chunks)
        if self.utc_offset is None:
            return data
        first = max(start, self.utc_offset)
        last = min(start + len(data), self.utc_offset + len(UTC_PLACEHOLDER))
        if first >= last:
            return data
        mailbox = utc_mailbox()
        return data[:first - start] + mailbox[first - self.utc_offset:last - self.utc_offset] + data[last - start:]


class WindowedRun(KernelRun):
    projection = None

    def __init__(self, image, card, messages, pointer, menu_button, closing, output, *, omap_public_rom=None,
                 display_mode=3, assist_navi_start=False, assist_touch_calibration=False, phone_port=None,
                 controls=None, projection=None, auto_calibrate=False, boot_trace=False, usb_clock_units=None):
        self.touch = TouchController()
        super().__init__(image, 'gd13my', 'boot', guest_exceptions=True, virtual_timer=True,
                         card=card, display=True, timer_irq=True, boot_trace=boot_trace, touch=self.touch,
                         omap_public_rom=omap_public_rom, musb=phone_port.controller if phone_port else None)
        self.phone_port = phone_port
        self.usb_clock_units = usb_clock_units
        self.projection = projection
        self.controls = controls
        uart1 = self.irq_controller.sources[72]
        self.micom = MicomCdp(uart1, display_mode=display_mode)
        uart1.peer = self.micom.receive
        self.messages = messages
        self.pointer = pointer
        self.menu_button = menu_button
        self.closing = closing
        self.output = output
        self.next_poll_units = 0
        self.boot_started = monotonic()
        self.boot_timings = {}
        self.next_frame_time = 0
        self.next_serial_time = 0
        self.serial_length = 0
        self.usb_test_offset = 0
        self.usb_auth_status = None
        self.next_touch_tick = 0
        self.held_contact = None
        self.last_frame = None
        self.assist_navi_start = assist_navi_start
        self.assist_touch_calibration = assist_touch_calibration
        self.auto_calibrate = auto_calibrate
        self.calibration_points = set()
        self.wait_for_navigation = display_mode == 2
        self.navigation_ready = False
        self.menu_sent = None
        self.menu_slow = False

    def service_menu_button(self, now):
        if self.menu_sent is not None:
            sent, offset = self.menu_sent
            if self.uart.output.find(NAVIGATION_MENU_ACK, offset) != -1:
                self.menu_sent = None
                self.messages.put(('menu', '순정 내비가 F2 입력을 처리함'))
            elif not self.menu_slow and now - sent >= 30:
                self.menu_slow = True
                self.messages.put(('menu', 'F2 전송 완료 · 순정 내비 응답이 늦음'))
        if (self.menu_sent is None or self.menu_slow) and self.navigation_ready and self.menu_button.is_set():
            self.menu_button.clear()
            self.menu_sent = (now, len(self.uart.output))
            self.menu_slow = False
            self.micom.reply(NAVIGATION_MENU_PACKET)
            self.messages.put(('menu', 'F2 전송 완료 · 순정 내비 응답 확인 중'))

    def service_panel(self):
        if self.controls is None:
            return False
        try:
            button = self.controls.get_nowait()
        except Empty:
            return False
        if button == 'usb' and self.phone_port is not None:
            if self.projection is None or not self.projection.running:
                self.phone_port.reconnect()
        elif button in VOLUME_STEPS:
            level = self.micom.set_navigation_volume(self.micom.navigation_volume + VOLUME_STEPS[button])
            self.messages.put(('menu', f'내비 볼륨 {level}/18 · MICOM 입력 전송'))
        elif button in NAVIGATION_KEYS:
            packet, name = NAVIGATION_KEYS[button]
            self.micom.reply(packet)
            self.messages.put(('menu', f'{name} · MICOM 입력 전송'))
        return True

    def service_usb_test(self):
        if self.phone_port is None or len(self.uart.output) <= self.usb_test_offset:
            return
        for event in USB_TEST_EVENT.finditer(self.uart.output, self.usb_test_offset):
            self.usb_test_offset = event.end()
            if self.projection is not None and self.projection.running:
                continue
            marker = event.group()
            if marker == USB_TEST_READY:
                self.usb_auth_status = None
                self.use_usb_clock()
                self.phone_port.reconnect()
            elif marker == USB_TEST_FAILURE:
                self.messages.put(('usb', 'CE Android Auto 버전 응답 실패'))
            elif marker in USB_AUTH_STATUS:
                self.usb_auth_status = USB_AUTH_STATUS[marker]
                self.messages.put(('usb', self.usb_auth_status))
            elif self.projection is not None:
                claimed = self.phone_port.take_projection_link()
                if claimed is not None:
                    self.projection.start(claimed)
            else:
                self.boot_timings.setdefault('android_auto_version', round(monotonic() - self.boot_started, 3))
                self.messages.put(('usb', self.usb_auth_status or 'CE Android Auto 버전 교환 완료'))
        self.usb_test_offset = max(self.usb_test_offset, len(self.uart.output) - USB_TEST_TAIL)

    def use_usb_clock(self):
        rate = getattr(self, 'usb_clock_units', None)
        if rate:
            # Rebase CPU units so the WinCE timer does not jump when the rate changes.
            ticks = self.clock_ticks()
            emulate_gd13my.VIRTUAL_CPU_UNITS_PER_SECOND = rate
            self.clock_units = (ticks * rate + TIMER_HZ - 1) // TIMER_HZ
            self.next_poll_units = self.irq_poll_at = self.clock_units
            self.usb_clock_units = None

    def start_navigation(self):
        if not self.assist_navi_start:
            return
        # Wait for AV registration and the end of the stock calibration sequence.
        if not all(marker in self.uart.output for marker in
                   (b'Complete register process -- PATH_Av', b'Calib file write BuffLen')):
            return
        self.assist_navi_start = False
        site = 0x16708

        def route_once(cpu, address, _size, _data):
            if instruction(cpu, address) != 0xe3540000:
                return
            if tuple(cpu.reg_read(RM[n]) for n in (4, 8, 6, 7)) != (0, 0xe0, 4, 2):
                return
            # The bench lacks the companion app event. Route only this matching decoded event.
            cpu.reg_write(RM[4], 1)
            cpu.hook_del(hook)
            self.output.with_suffix('.mode.log').write_text(
                f'{self.clock_ticks()} Assisted .061 NAVI start at {address:#x}\n', encoding='utf-8')

        hook = self.cpu.hook_add(UC_HOOK_CODE, route_once, begin=site, end=site)
        self.cpu.ctl_flush_tb()
        self.micom.reply(NAVIGATION_START_PACKET)

    def correct_touch_coordinates(self):
        if not self.assist_touch_calibration or b'Calib file write BuffLen' not in self.uart.output:
            return
        self.assist_touch_calibration = False
        read_point, set_points = 0xc0841368, 0xc084186c
        registers = (*RM, UC_ARM_REG_CPSR)
        saved = None

        def calibrate(cpu, address, _size, _data):
            nonlocal saved
            if instruction(cpu, address) != 0xeb0007f8 or instruction(cpu, set_points) != 0xe92d4ff0:
                return
            if saved is not None:
                if cpu.reg_read(RM[-1]) != read_point:
                    return
                physical, scratch, values = saved
                result = cpu.reg_read(RM[0])
                cpu.mem_write(physical, scratch)
                for reg, value in zip(registers, values):
                    cpu.reg_write(reg, value)
                cpu.hook_del(hook)
                self.output.with_suffix('.recalibration.log').write_text(
                    f'{self.clock_ticks()} Native GD13MY touch calibration result {result}\n', encoding='utf-8')
                return
            stack = (cpu.reg_read(RM[-2]) - 96) & ~7
            args, reserve = translate(cpu, stack), translate(cpu, stack - 0x280)
            last = translate(cpu, stack + 87)
            if not (args and reserve and last and args.physical is not None and reserve.physical is not None and
                    last.physical == args.physical + 87 and
                    self.contains_ram(args.physical, 88) and self.contains_ram(reserve.physical, 0x280)):
                return
            # The desktop coordinates are already the .061 controller's raw coordinates.
            x = (400, 160, 160, 640, 640)
            y = (240, 96, 384, 384, 96)
            saved = (args.physical, bytes(cpu.mem_read(args.physical, 88)),
                     [cpu.reg_read(reg) for reg in registers])
            cpu.mem_write(args.physical, struct.pack('<22I', stack + 68, 0, *x, *y, *x, *y))
            for reg, value in zip(RM, (5, stack + 8, stack + 28, stack + 48)):
                cpu.reg_write(reg, value)
            cpu.reg_write(RM[-2], stack)
            cpu.reg_write(RM[-1], read_point)
            cpu.reg_write(UC_ARM_REG_PC, set_points)

        hook = self.cpu.hook_add(UC_HOOK_CODE, calibrate, begin=read_point, end=read_point)
        self.cpu.ctl_flush_tb()

    def advance_clock(self, cpu, address, size, data):
        super().advance_clock(cpu, address, size, data)
        if self.clock_units < self.next_poll_units:
            return
        self.next_poll_units = self.clock_units + min(131_072, emulate_gd13my.VIRTUAL_CPU_UNITS_PER_SECOND // 125)
        if self.closing.is_set():
            cpu.emu_stop()
            return
        ticks = self.clock_ticks()
        if self.touch.pending is None and ticks >= self.next_touch_tick:
            try:
                sample = self.pointer.get_nowait()
            except Empty:
                sample = self.held_contact
            if sample is not None:
                self.submit_input(sample, ticks)
        now = monotonic()
        self.service_panel()
        if self.phone_port is not None:
            self.phone_port.poll()
        if self.menu_button.is_set() or self.menu_sent is not None:
            self.service_menu_button(now)
        if now >= self.next_serial_time:
            self.next_serial_time = now + 1
            self.service_usb_test()
            self.correct_touch_coordinates()
            self.start_navigation()
            if not self.navigation_ready and ((self.wait_for_navigation and NAVIGATION_READY in self.uart.output)
                                              or (not self.wait_for_navigation and self.last_frame is not None)):
                self.navigation_ready = True
                self.boot_timings['navigation_ready'] = round(now - self.boot_started, 3)
                if self.wait_for_navigation:
                    self.micom.report_rear_view()
                if self.projection is not None:
                    self.projection.ready.set()
                self.messages.put(('navigation_ready', None))
            self.messages.put(('heartbeat', (ticks // TIMER_HZ, self.touch.consumed)))
            self.flush_serial()
        if self.display.active is not None and now >= self.next_frame_time:
            self.publish_frame()

    def submit_input(self, sample, ticks):
        if sample == NAVIGATION_MENU_PACKET:
            self.micom.reply(NAVIGATION_MENU_PACKET)
            return
        self.touch.submit(*sample)
        self.held_contact = sample if sample[2] else None
        self.next_touch_tick = ticks + 660  # Sample a held contact every 20 ms of guest time.

    def run_window(self, seconds):
        deadline = monotonic() + seconds
        while True:
            report = self.run(instructions=0, seconds=max(1, ceil(deadline - monotonic())))
            if self.closing.is_set():
                if report['stop'] != 'guest_error':
                    report['stop'] = 'guest_stopped'
            else:
                self.service_usb_test()
            self.flush_serial()
            self.publish_frame()
            if report['stop'] != 'guest_idle':
                return report

            self.messages.put(('idle', None))
            while not self.closing.is_set() and monotonic() < deadline:
                try:
                    sample = self.pointer.get(timeout=0.1)
                except Empty:
                    if self.navigation_ready and self.menu_button.is_set():
                        self.service_menu_button(monotonic())
                    elif not self.service_panel() and (self.phone_port is None or not self.phone_port.poll()):
                        continue
                else:
                    self.submit_input(sample, self.clock_ticks())
                self.entry = self.cpu.reg_read(UC_ARM_REG_PC) | ((self.cpu.reg_read(UC_ARM_REG_CPSR) >> 5) & 1)
                self.idle_blocked = False
                self.power.wake()
                self.messages.put(('resumed', None))
                break
            else:
                if self.closing.is_set() and report['stop'] != 'guest_error':
                    report['stop'] = 'guest_stopped'
                return report

    def flush_serial(self):
        if len(self.uart.output) != self.serial_length:
            with self.output.with_suffix('.serial.log').open('ab') as serial:
                serial.write(self.uart.output[self.serial_length:])
            self.serial_length = len(self.uart.output)

    def publish_frame(self):
        started = monotonic()
        report, frame = self.display.capture(self.cpu.mem_read, self.contains_ram)
        # Poll unchanged screens quickly and leave CPU time for the guest during animations.
        self.next_frame_time = started + max(0.125, 4 * (monotonic() - started))
        if frame is None:
            return
        if self.last_frame is None and report['uniform']:
            return
        if self.auto_calibrate and b'Run Touch_Calib.EXE' in self.uart.output:
            if b'Calib file write BuffLen' in self.uart.output:
                self.auto_calibrate = False
            else:
                contact = self.display.calibration_contact(self.calibration_points)
                if contact is not None:
                    self.calibration_points.add(contact)
                    self.auto_calibrate = contact != (400, 230)
                    for _ in range(34):
                        self.pointer.put((*contact, True))
                    self.pointer.put((*contact, False))
        if frame == self.last_frame:
            return
        self.boot_timings.setdefault('first_lcd_frame', round(started - self.boot_started, 3))
        self.last_frame = frame
        self.output.with_suffix('.png').write_bytes(frame)
        self.messages.put(('frame', frame))


def boot(image, disk, seconds, messages, pointer, menu_button, closing, output, public_rom, display_mode,
         software_gl_app, assist_navi_start, assist_touch_calibration, app_volume, usb_port, libusb, panel,
         state_path=None, usb_on_test=False, projection=None, auto_calibrate=False,
         boot_trace=False, show_map_preview=False, host_utc_offset=None, boot_clock_units=None, usb_clock_units=None):
    phone_port = None
    try:
        if boot_clock_units is not None:
            emulate_gd13my.VIRTUAL_CPU_UNITS_PER_SECOND = boot_clock_units
        if usb_port:
            from gd13my_usb_pc import PhonePort

            def usb_trace(text):
                with output.with_suffix('.usb-host.log').open('a', encoding='utf-8') as log:
                    print(text, file=log)

            def usb_status(text):
                usb_trace(text)
                messages.put(('usb', text))

            try:
                phone_port = PhonePort(usb_port, libusb, usb_status, usb_trace, wait_for_test=usb_on_test)
            except (ImportError, ValueError) as error:
                if usb_port != 'auto':
                    raise
                usb_status(f'USB 자동 연결 사용 불가 · {error}')
        with disk.open('rb') as media, (app_volume.open('rb') if app_volume else nullcontext()) as app:
            end = DISK_START_LBA + fstat(media.fileno()).st_size // ReadOnlyHsMmc.SECTOR
            backing = AppPartitionOverlay(media, app) if app is not None else media
            card = ReadOnlyHsMmc(backing, first_lba=DISK_START_LBA, writable_lbas=(DISK_START_LBA, end))
            state = persistent_diska(state_path, card) if state_path is not None else nullcontext()
            with state as restored:
                # The changing mailbox bytes are outside the persistent image identity.
                if host_utc_offset is not None:
                    backing.enable_host_utc(host_utc_offset)
                run = WindowedRun(image.read_bytes(), card,
                                  messages, pointer, menu_button, closing, output,
                                  omap_public_rom=public_rom.read_bytes() if public_rom else None,
                                  display_mode=display_mode, assist_navi_start=assist_navi_start,
                                  assist_touch_calibration=assist_touch_calibration, phone_port=phone_port,
                                  controls=panel, projection=projection, auto_calibrate=auto_calibrate,
                                  boot_trace=boot_trace, usb_clock_units=usb_clock_units)
                renderer = None
                if software_gl_app is not None:
                    from gd13my_software_gl import GuestGL

                    renderer = GuestGL(run, software_gl_app, preview=show_map_preview)
                try:
                    report = run.run_window(seconds)
                finally:
                    if renderer is not None:
                        renderer.close()
                report['touch'] = {'samples': run.touch.consumed, 'last_reply': hex(run.touch.last_reply),
                                   'commands': {hex(word): count for word, count in run.touch.commands.items()}}
                report['wall_seconds_from_guest_init'] = run.boot_timings
                report['virtual_micom_requests'] = list(run.micom.exchanges)
                report['media']['overlay_sectors'] = len(card.overlay)
                if restored is not None:
                    report['media']['restored_diska_sectors'] = restored
                    if report['stop'] == 'guest_error':
                        card.overlay.clear()
        output.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        messages.put(('stopped', report['stop']))
    except (ImportError, OSError, ValueError) as error:
        messages.put(('error', str(error)))
    finally:
        if projection is not None:
            projection.close()
        if phone_port is not None:
            phone_port.close_device()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=ROM_PATH)
    parser.add_argument('--disk', type=Path, default=BOOT_DIR / 'diska.img')
    parser.add_argument('--output-dir', type=Path, default=BOOT_DIR, help='Directory for emulator screenshots and logs')
    parser.add_argument('--boot-trace', action='store_true', help='Record detailed WinCE API calls for boot diagnosis')
    parser.add_argument('--app-volume', type=Path, help='Use DiskA from a compact image while retaining the original map volumes')
    parser.add_argument('--host-utc-offset', type=int, help='Supply current UTC to the reserved DiskA mailbox')
    parser.add_argument('--save-state', type=Path, help='Keep guest DiskA writes in a separate state database')
    parser.add_argument('--usb-port', metavar='BUS-PORT|auto',
                        help='Forward a physical port, or select a single eligible phone after the guest requests it')
    parser.add_argument('--usb-on-test', action='store_true', help='Attach the selected USB port when the CE test starts')
    projection_mode = parser.add_mutually_exclusive_group()
    projection_mode.add_argument('--projection-ca', type=Path, help='Enable phone projection with this enrolled CA')
    projection_mode.add_argument('--projection-mock', action='store_true', help='Use a local synthetic projection peer')
    projection_peer = parser.add_mutually_exclusive_group()
    projection_peer.add_argument('--projection-peer-name')
    projection_peer.add_argument('--projection-peer-sha256')
    parser.add_argument('--projection-cert', type=Path, help='Enrolled receiver client certificate')
    parser.add_argument('--projection-key', type=Path, help='Enrolled receiver client key')
    parser.add_argument('--projection-audio-out', type=int, help='WinMM device index for projected audio')
    parser.add_argument('--projection-mic-in', type=int, help='WinMM device index for the optional projection microphone')
    parser.add_argument('--libusb', type=Path, help='Optional libusb DLL path for the physical USB port')
    parser.add_argument('--omap-public-rom', type=Path, help='32 KiB OMAP35x public ROM at physical 0x40014000')
    parser.add_argument('--micom-display', choices=('av', 'navi'), default='av',
                        help='Initial display mode reported by the virtual MICOM')
    parser.add_argument('--assist-navi-start', action='store_true',
                        help='Replay the missing initial application-mode event on the .061 bench')
    parser.add_argument('--assist-touch-calibration', action='store_true',
                        help='Align simulated touch coordinates after stock .061 calibration')
    parser.add_argument('--auto-calibrate', action='store_true',
                        help='Replay the five recognized .061 calibration targets for the virtual touchscreen')
    parser.add_argument('--guest-clock-mhz', type=float, default=64,
                        help='Emulated CPU units per second in millions (default: 64)')
    parser.add_argument('--usb-clock-mhz', type=float, help='Guest CPU rate after native USB testing starts')
    parser.add_argument('--software-gl-app', type=Path,
                        help='Optional software renderer for the extracted stock GDdNavi.exe')
    parser.add_argument('--show-map-preview', action='store_true',
                        help='Open a separate map-only debugging window')
    parser.add_argument('--seconds', type=int, default=900)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error('--seconds must be positive')
    if args.host_utc_offset is not None and args.app_volume is None:
        parser.error('--host-utc-offset requires --app-volume')
    clock_units = args.guest_clock_mhz * 1_000_000
    if not isfinite(clock_units) or clock_units < 1:
        parser.error('--guest-clock-mhz must specify a finite rate of at least one CPU unit per second')
    usb_clock_units = None
    if args.usb_clock_mhz is not None:
        if not 1 <= args.usb_clock_mhz <= 100:
            parser.error('--usb-clock-mhz must be between 1 and 100')
        usb_clock_units = round(args.usb_clock_mhz * 1_000_000)
    if args.assist_navi_start and args.micom_display != 'navi':
        parser.error('--assist-navi-start requires --micom-display navi')
    if args.usb_on_test and not args.usb_port:
        parser.error('--usb-on-test requires --usb-port')
    if (args.projection_ca or args.projection_mock) and args.micom_display != 'navi':
        parser.error('Projection requires --micom-display navi')
    if args.projection_ca and not args.usb_on_test:
        parser.error('Live projection requires --usb-port and --usb-on-test')
    if args.projection_mock and args.usb_port:
        parser.error('Mock projection does not take a physical USB port')
    if args.projection_ca is None and any(option is not None for option in
                                         (args.projection_peer_name, args.projection_peer_sha256,
                                          args.projection_cert, args.projection_key,
                                          args.projection_audio_out, args.projection_mic_in)):
        parser.error('Projection trust and audio options require --projection-ca')
    emulate_gd13my.VIRTUAL_CPU_UNITS_PER_SECOND = int(clock_units)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / datetime.now().strftime('gd13my-window-%Y%m%d-%H%M%S-%f')
    messages = SimpleQueue()
    projection = None
    if args.projection_ca or args.projection_mock:
        try:
            import av
            from gd13my_projection import Projection
            from i30_receiver.cli import openssl_path, require_windows_audio
            from i30_receiver.tls import client_context

            if args.projection_mock and openssl_path() is None:
                raise ValueError('OpenSSL CLI is required for the mock certificate')
            if args.projection_audio_out is not None or args.projection_mic_in is not None:
                require_windows_audio()
            tls = (client_context(args.projection_ca, args.projection_peer_name, args.projection_peer_sha256,
                                  args.projection_cert, args.projection_key) if args.projection_ca else None)
            projection = Projection(av, messages, output, tls_factory=tls, mock=args.projection_mock,
                                    audio_out=args.projection_audio_out, mic_in=args.projection_mic_in)
        except (ImportError, OSError, ValueError) as error:
            parser.error(str(error))

    root = tk.Tk()
    root.title('GD13MY 순정 펌웨어')
    root.resizable(False, False)
    canvas = tk.Canvas(root, width=800, height=480, highlightthickness=0, background='black')
    canvas.pack()
    viewport = canvas.create_image(0, 0, anchor='nw')
    status = tk.StringVar(value='순정 펌웨어 부팅 중')
    input_status = tk.StringVar(value='내비가 로딩되면 F2로 메뉴를 열 수 있습니다.')
    controls = tk.Frame(root)
    controls.pack(fill='x')
    bezel = tk.Frame(root)
    bezel.pack(fill='x', padx=8, pady=4)
    tk.Label(controls, textvariable=status, anchor='w', padx=8, pady=6).pack(side='left', fill='x', expand=True)
    tk.Label(root, textvariable=input_status, anchor='w', padx=8, pady=4).pack(fill='x')
    usb_status = tk.StringVar(value=f'물리 USB {args.usb_port} 연결 대기')
    if args.usb_port:
        tk.Label(root, textvariable=usb_status, anchor='w', padx=8, pady=4, wraplength=775).pack(fill='x')
    projection_status = tk.StringVar(value='모의 투사 대기' if args.projection_mock else 'CE USB 연결 시험 대기')
    if projection is not None:
        tk.Label(root, textvariable=projection_status, anchor='w', padx=8, pady=4, wraplength=775).pack(fill='x')
    picture = None
    projected_picture = projected_frame = None

    pointer = SimpleQueue()
    panel = SimpleQueue()
    menu_button = Event()
    closing = Event()
    display_mode = 2 if args.micom_display == 'navi' else 3
    worker = None
    window_closing = power_stopping = False
    power_error = None
    guest_visible = False
    navigation_ready = False
    pressed = None
    idle = False
    last_heartbeat = None
    guest_seconds = touches = 0
    map_view = map_picture = None

    def power_on():
        nonlocal worker, closing, pointer, panel, menu_button
        nonlocal picture, projected_picture, projected_frame, guest_visible, navigation_ready, pressed
        nonlocal idle, last_heartbeat, guest_seconds, touches, map_view, map_picture, power_error
        if window_closing or power_stopping or (worker is not None and worker.is_alive()):
            return
        # The previous boot has released USB and committed its DiskA overlay before this starts.
        while True:
            try:
                messages.get_nowait()
            except Empty:
                break
        closing, menu_button = Event(), Event()
        pointer, panel = SimpleQueue(), SimpleQueue()
        picture = projected_picture = projected_frame = pressed = None
        guest_visible = navigation_ready = idle = False
        power_error = None
        last_heartbeat = None
        guest_seconds = touches = 0
        canvas.itemconfigure(viewport, image='')
        if map_view is not None:
            map_view.destroy()
            map_view = map_picture = None
        status.set('순정 펌웨어 부팅 중')
        input_status.set('내비가 로딩되면 F2로 메뉴를 열 수 있습니다.')
        usb_status.set(f'물리 USB {args.usb_port} 연결 대기')
        boot_output = args.output_dir / datetime.now().strftime('gd13my-window-%Y%m%d-%H%M%S-%f')
        if projection is not None:
            projection.ready.clear()
            projection.log_path = boot_output.with_suffix('.projection.jsonl')
            projection_status.set('모의 투사 대기' if args.projection_mock else 'CE USB 연결 시험 대기')
        worker = Thread(
            target=boot,
            args=(args.image, args.disk, args.seconds, messages, pointer, menu_button, closing, boot_output,
                  args.omap_public_rom, display_mode, args.software_gl_app, args.assist_navi_start,
                  args.assist_touch_calibration, args.app_volume, args.usb_port, args.libusb, panel,
                  args.save_state, args.usb_on_test, projection, args.auto_calibrate, args.boot_trace,
                  args.show_map_preview, args.host_utc_offset, int(clock_units), usb_clock_units),
            daemon=True,
        )
        ignition_on.configure(state='disabled')
        ignition_off.configure(state='normal')
        menu_control.configure(state='normal')
        worker.start()

    def power_off():
        nonlocal power_stopping, power_error
        if worker is None or not worker.is_alive() or power_stopping:
            return
        power_stopping = True
        power_error = None
        status.set('시동 끄는 중 · 게스트 저장 대기')
        ignition_off.configure(state='disabled')
        menu_control.configure(state='disabled')
        if projection is not None:
            projection.stop.set()
        closing.set()

    def refresh():
        nonlocal picture, guest_visible, navigation_ready, idle, last_heartbeat, guest_seconds, touches
        nonlocal projected_picture, projected_frame
        nonlocal map_view, map_picture
        nonlocal power_stopping, power_error
        if window_closing:
            if worker.is_alive():
                root.after(100, refresh)
            else:
                root.destroy()
            return
        while True:
            try:
                kind, payload = messages.get_nowait()
            except Empty:
                break
            if kind == 'frame':
                picture = tk.PhotoImage(data=payload, format='png')
                if projected_frame is None:
                    canvas.itemconfigure(viewport, image=picture)
                if not guest_visible:
                    guest_visible = True
                    root.title('GD13MY 순정 펌웨어 — 게스트 화면')
            elif kind == 'map':
                if not args.show_map_preview:
                    continue
                if map_view is None:
                    window = tk.Toplevel(root)
                    window.title('GD13MY 순정 지도 — 소프트웨어 렌더링')
                    window.resizable(False, False)
                    window.protocol('WM_DELETE_WINDOW', window.withdraw)
                    map_view = tk.Label(window, borderwidth=0)
                    map_view.pack()
                map_picture = tk.PhotoImage(data=payload, format='png')
                map_view.configure(image=map_picture)
            elif kind == 'heartbeat':
                guest_seconds, touches = payload
                last_heartbeat = monotonic()
            elif kind == 'navigation_ready':
                navigation_ready = True
                if not menu_button.is_set():
                    input_status.set('내비 로딩 완료 · F2로 메뉴 열기')
            elif kind == 'menu':
                input_status.set(payload)
            elif kind == 'usb':
                usb_status.set(payload)
            elif kind == 'projection':
                projection_status.set(payload)
            elif kind == 'idle':
                idle = True
            elif kind == 'resumed':
                idle = False
                last_heartbeat = monotonic()
            else:
                label = '실행 종료' if kind == 'stopped' else '실행 오류'
                if kind == 'error' or payload == 'guest_error':
                    power_error = payload
                status.set(f'{label} · {payload}')
                input_status.set('이 창에 마지막 게스트 화면이 남아 있습니다.')
                menu_control.configure(state='disabled')
        if power_stopping and not worker.is_alive():
            power_stopping = False
            picture = projected_picture = projected_frame = None
            canvas.itemconfigure(viewport, image='')
            if map_view is not None:
                map_view.withdraw()
            status.set(f'시동 꺼짐 · 게스트 오류: {power_error}' if power_error else '시동 꺼짐')
            input_status.set('같은 창에서 시동을 다시 켤 수 있습니다.')
            ignition_on.configure(state='normal')
        elif not worker.is_alive():
            ignition_on.configure(state='normal')
            ignition_off.configure(state='disabled')
        frame = projection.frame() if projection is not None else None
        if frame is not projected_frame:
            projected_frame = frame
            projected_picture = tk.PhotoImage(data=frame, format='PPM') if frame is not None else None
            canvas.itemconfigure(viewport, image=projected_picture or picture or '')
        if worker.is_alive() and not power_stopping:
            if idle:
                activity = '게스트 대기 중'
            elif last_heartbeat is not None and monotonic() - last_heartbeat > 6:
                activity = '게스트 진행 신호 대기 중'
            else:
                activity = '실행 중' if guest_visible else '부팅 중'
            status.set(f'{activity} · 게스트 {guest_seconds}초 · 터치 수신 {touches}회')
        root.after(33 if projected_frame is not None else 100, refresh)

    def close():
        nonlocal window_closing
        window_closing = True
        status.set('에뮬레이터 종료 중')
        if projection is not None:
            projection.stop.set()
        closing.set()

    def contact(event, down):
        nonlocal pressed
        if not guest_visible or not worker.is_alive() or power_stopping:
            return
        x, y = max(0, min(799, event.x)), max(0, min(479, event.y))
        if down and pressed is None:
            pressed = 'projection' if projected_frame is not None else 'stock'
            action = 'ACTION_DOWN'
        elif pressed is not None:
            action = 'ACTION_MOVED' if down else 'ACTION_UP'
        else:
            return
        if pressed == 'projection':
            projection.queue('pointer', action, x, y)
        else:
            # A quick desktop click can otherwise release before the .061 touch driver debounces it.
            for _ in range(6 if action == 'ACTION_DOWN' else 1):
                pointer.put((x, y, down))
        if not down:
            pressed = None

    def open_navigation_menu():
        if worker.is_alive() and not power_stopping:
            if projection is not None and projection.running:
                projection.stop.set()
            menu_button.set()
            input_status.set('F2 요청 접수' if navigation_ready else 'F2 요청 접수 · 내비 로딩 후 전송')

    def queue_panel(button):
        if guest_visible and worker.is_alive() and not power_stopping:
            panel.put(button)

    def panel_button(label, key, button):
        tk.Button(bezel, text=label, command=lambda: queue_panel(button)).pack(side='left', padx=3)
        root.bind_all(key, lambda _event: queue_panel(button))

    panel_button('현위치 (F3)', '<F3>', 'position')
    panel_button('목적지 (F4)', '<F4>', 'destination')
    panel_button('볼륨 − (F7)', '<F7>', 'volume_down')
    panel_button('볼륨 + (F8)', '<F8>', 'volume_up')
    bezel.bind('<MouseWheel>', lambda event: queue_panel('volume_up' if event.delta > 0 else 'volume_down'))
    if args.usb_port:
        tk.Button(bezel, text='USB 다시 연결', command=lambda: queue_panel('usb')).pack(side='right', padx=3)
    if projection is not None:
        if args.projection_mock:
            tk.Button(bezel, text='모의 투사',
                      command=lambda: worker.is_alive() and projection.ready.is_set() and projection.start()).pack(
                          side='right', padx=3)
        tk.Button(bezel, text='투사 종료', command=projection.stop.set).pack(side='right', padx=3)
        priority = tk.BooleanVar(value=False)

        def set_priority():
            if priority.get():
                projection.stock_priority.set()
            else:
                projection.stock_priority.clear()

        tk.Checkbutton(bezel, text='순정 화면 우선', variable=priority, command=set_priority).pack(side='right')
        root.bind('<Escape>', lambda _event: projection.stop.set())
        root.bind('<FocusOut>', lambda _event: projection.queue('reset'))

        def projection_key(button, down):
            if down and projected_frame is None:
                return
            projection.queue('key', button, down)

        for key, button in (('F1', 'HOME'), ('F5', 'VOICE'), ('F6', 'SEEK_NEXT')):
            root.bind(f'<KeyPress-{key}>', lambda _event, button=button: projection_key(button, True))
            root.bind(f'<KeyRelease-{key}>', lambda _event, button=button: projection_key(button, False))

    menu_control = tk.Button(controls, text='내비 메뉴 (F2)', command=open_navigation_menu)
    menu_control.pack(side='right', padx=8)
    root.bind_all('<F2>', lambda _event: open_navigation_menu())
    ignition_off = tk.Button(controls, text='시동 끄기', command=power_off)
    ignition_off.pack(side='right', padx=3)
    ignition_on = tk.Button(controls, text='시동 켜기', command=power_on)
    ignition_on.pack(side='right', padx=3)

    canvas.bind('<ButtonPress-1>', lambda event: contact(event, True))
    canvas.bind('<B1-Motion>', lambda event: contact(event, True))
    canvas.bind('<ButtonRelease-1>', lambda event: contact(event, False))
    root.protocol('WM_DELETE_WINDOW', close)
    root.attributes('-topmost', True)
    root.after(1500, lambda: root.attributes('-topmost', False))
    root.after(100, refresh)
    power_on()
    root.mainloop()


if __name__ == '__main__':
    main()
