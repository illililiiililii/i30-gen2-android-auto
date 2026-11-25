"""Build an emulator media image with the Android Auto ARM bench test."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from struct import unpack_from
from tempfile import TemporaryDirectory

from build_gd13my_diska import PARTITION_OFFSET, SECTOR_SIZE
from gd13my_guest_clock import UTC_PATH, UTC_PLACEHOLDER
from patch_gd13my_settings import STOCK_HASHES, verify_stock
from patch_gd13my_display import DISPLAY_HASHES, verify_stock_display
from patch_gd13my_startup import STOCK_APP, verify_stock_startup

PROBE_PATH = '/Application/AndroidAuto/i30-ce-probe.exe'
SETTINGS_PATH = '/Application/AndroidAuto/i30-aa-settings.exe'
NATIVE_SETTINGS_PATH = '/Application/NAVI/i30aa.exe'
NATIVE_USB_PATH = '/Application/NAVI/i30usb.dll'
NATIVE_PROJECTION_PATH = '/Application/NAVI/i30nav.dll'
NAVI_PATH = '/Application/NAVI/'
AV_PATH = '/Application/Av/'
STARTUP_PATH = '/Application/' + STOCK_APP


def read_ce_app(path, *, dll=False):
    payload = path.read_bytes()
    if payload[:2] != b'MZ' or len(payload) < 0x40:
        raise ValueError('The Android Auto test must be a Windows CE ARM executable')
    header, = unpack_from('<I', payload, 0x3c)
    if (header + 94 > len(payload) or payload[header:header + 4] != b'PE\0\0'
            or unpack_from('<H', payload, header + 4)[0] != 0x1c2
            or unpack_from('<HH', payload, header + 72) != (6, 0)
            or unpack_from('<H', payload, header + 92)[0] != 9
            or bool(unpack_from('<H', payload, header + 22)[0] & 0x2000) != dll):
        raise ValueError('Expected the GD13MY ARM/Thumb PE for Windows CE 6.0')
    return payload


def package(base, probe, output, *, settings=None, navigation_patch=None, usb_client=None, startup_patch=None,
            native_projection=None, stock_display=None, compact=False, emulator_utc=False, aare_identity=None):
    from pyfatfs.PyFatFS import PyFatFS

    if output.exists():
        raise FileExistsError(output)
    apps = {PROBE_PATH: read_ce_app(probe)} if probe is not None else {}
    replacements = {}
    if navigation_patch is not None and settings is None:
        raise ValueError('The navigation settings patch requires the CE settings app')
    if usb_client is not None and navigation_patch is None:
        raise ValueError('The USB client requires the native navigation settings patch')
    if native_projection is not None and usb_client is None:
        raise ValueError('The projection module requires the native USB client')
    if stock_display is not None and native_projection is None:
        raise ValueError('The stock display patch requires the navigation projection module')
    if aare_identity is not None:
        if stock_display is None or not compact or not emulator_utc:
            raise ValueError('AARE credentials require a compact emulator image with stock display and host UTC')
        for suffix in ('ca.pem', 'client.pem', 'client-key.pem', 'peer-sha256.txt'):
            name = 'i30-aare-' + suffix
            data = (aare_identity / name).read_bytes()
            if not data or len(data) > 16 * 1024:
                raise ValueError(f'Invalid AARE credential length: {name}')
            apps[NAVI_PATH + name] = data
        pin = apps[NAVI_PATH + 'i30-aare-peer-sha256.txt'].strip()
        if len(pin) != 64 or any(value not in b'0123456789abcdefABCDEF' for value in pin):
            raise ValueError('AARE requires a SHA-256 fingerprint of the enrolled phone leaf')
        apps[NAVI_PATH + 'i30-aare.opt'] = b'1\n'
    if startup_patch is not None and usb_client is None:
        raise ValueError('The startup patch requires the native USB settings app')
    if emulator_utc and (not compact or startup_patch is None):
        raise ValueError('The UTC mailbox requires the compact emulator image and its startup patch')
    utc_offset = None
    if emulator_utc:
        apps[UTC_PATH] = UTC_PLACEHOLDER
    settings_path = NATIVE_SETTINGS_PATH if navigation_patch is not None else SETTINGS_PATH
    if settings is not None:
        apps[settings_path] = read_ce_app(settings)
    if usb_client is not None:
        apps[NATIVE_USB_PATH] = read_ce_app(usb_client, dll=True)
    if native_projection is not None:
        apps[NATIVE_PROJECTION_PATH] = read_ce_app(native_projection, dll=True)
    if navigation_patch is not None:
        with PyFatFS(str(base), offset=PARTITION_OFFSET, preserve_case=True, read_only=True) as fs:
            for name in STOCK_HASHES:
                path = NAVI_PATH + name
                verify_stock(name, fs.readbytes(path))
                replacements[path] = (navigation_patch / name).read_bytes()
            if startup_patch is not None:
                verify_stock_startup(fs.readbytes(STARTUP_PATH))
                replacements[STARTUP_PATH] = startup_patch.read_bytes()
                if (stock_display is not None and emulator_utc and
                        '-i30clock'.encode('utf-16le') not in replacements[STARTUP_PATH]):
                    raise ValueError('The native display test requires the emulator clock startup hook')
            if stock_display is not None:
                for name in DISPLAY_HASHES:
                    path = AV_PATH + name
                    original = fs.readbytes(path)
                    verify_stock_display(name, original)
                    patched = (stock_display / name).read_bytes()
                    header, = unpack_from('<I', original, 0x3c)
                    if (patched[:header + 6] != original[:header + 6] or
                            patched[header + 22:header + 26] != original[header + 22:header + 26] or
                            b'.i30disp' not in patched[:0x400]):
                        raise ValueError(f'Expected an OEM display patch for {name}')
                    replacements[path] = patched
    with TemporaryDirectory(dir=output.parent, prefix='.gd13my-stage-') as directory:
        staged = Path(directory) / 'bench.img'
        with base.open('rb') as source:
            mbr = source.read(SECTOR_SIZE)
            if len(mbr) != SECTOR_SIZE or mbr[510:512] != b'\x55\xaa':
                raise ValueError('The original emulator media is missing its MBR')
            partition, sectors = unpack_from('<II', mbr, 454)
            if mbr[450] != 0x0c or partition * SECTOR_SIZE != PARTITION_OFFSET or not sectors:
                raise ValueError('The original emulator media lacks the expected DiskA FAT32 partition')
            length = base.stat().st_size
            app_end = (partition + sectors) * SECTOR_SIZE
            if app_end > length:
                raise ValueError('The original DiskA partition is truncated')
            remaining = (app_end if compact else length) - SECTOR_SIZE
            with staged.open('xb') as target:
                target.write(mbr[:462] + bytes(48) + mbr[510:] if compact else mbr)
                while remaining:
                    data = source.read(min(remaining, 4 * 1024 * 1024))
                    if not data:
                        raise ValueError('The original emulator media changed while copying')
                    target.write(data)
                    remaining -= len(data)
        with PyFatFS(str(staged), offset=PARTITION_OFFSET, preserve_case=True) as fs:
            if probe is not None:
                fs.makedirs('/Application/AndroidAuto', recreate=True)
            for path, payload in (replacements | apps).items():
                if fs.exists(path):
                    fs.remove(path)
                fs.writebytes(path, payload)
        changes = apps | replacements
        with PyFatFS(str(staged), offset=PARTITION_OFFSET, preserve_case=True, read_only=True) as fs:
            for path, payload in changes.items():
                if fs.readbytes(path) != payload:
                    raise ValueError(f'{path} did not round-trip through DiskA')
            if emulator_utc:
                cluster = fs._get_dir_entry(UTC_PATH).get_cluster()
                utc_offset = PARTITION_OFFSET + fs.fs.get_data_cluster_address(cluster)
                with staged.open('rb') as raw:
                    raw.seek(utc_offset)
                    if raw.read(len(UTC_PLACEHOLDER)) != UTC_PLACEHOLDER:
                        raise ValueError('The UTC mailbox offset does not match the reserved DiskA file')
            stock_unchanged = None
            if compact:
                with PyFatFS(str(base), offset=PARTITION_OFFSET, preserve_case=True, read_only=True) as original:
                    before, after = set(original.walk.files()), set(fs.walk.files())
                    if before & apps.keys() or after != before | apps.keys():
                        raise ValueError('Compact image has unexpected DiskA additions or removals')
                    remaining = before - replacements.keys()
                    for path in sorted(remaining):
                        if original.readbytes(path) != fs.readbytes(path):
                            raise ValueError(f'Unmodified stock file differs: {path}')
                    stock_unchanged = len(remaining)
        if output.exists():
            raise FileExistsError(output)
        staged.rename(output)
    report = {'media': str(output), 'size_bytes': output.stat().st_size}
    if compact:
        with output.open('rb') as image:
            digest = sha256()
            for chunk in iter(lambda: image.read(4 * 1024 * 1024), b''):
                digest.update(chunk)
        report.update(image_sha256=digest.hexdigest(), unchanged_stock_files=stock_unchanged,
                      compact_diska=True)
    if probe is not None:
        report.update(guest_path=r'\DiskA' + PROBE_PATH.replace('/', '\\'),
                      arm_probe_sha256=sha256(apps[PROBE_PATH]).hexdigest())
    if settings is not None:
        report['settings_guest_path'] = r'\DiskA' + settings_path.replace('/', '\\')
        report['settings_sha256'] = sha256(apps[settings_path]).hexdigest()
    if navigation_patch is not None:
        report['modified_stock_files'] = {name: sha256(replacements[NAVI_PATH + name]).hexdigest()
                                          for name in STOCK_HASHES}
    if usb_client is not None:
        report['usb_client_guest_path'] = r'\DiskA' + NATIVE_USB_PATH.replace('/', '\\')
        report['usb_client_sha256'] = sha256(apps[NATIVE_USB_PATH]).hexdigest()
    if native_projection is not None:
        report['native_projection_guest_path'] = r'\DiskA' + NATIVE_PROJECTION_PATH.replace('/', '\\')
        report['native_projection_sha256'] = sha256(apps[NATIVE_PROJECTION_PATH]).hexdigest()
    if stock_display is not None:
        report['stock_display_sha256'] = {name: sha256(replacements[AV_PATH + name]).hexdigest()
                                          for name in DISPLAY_HASHES}
    if startup_patch is not None:
        report['startup_sha256'] = sha256(replacements[STARTUP_PATH]).hexdigest()
    if aare_identity is not None:
        report['tls_profile'] = 'aare'
    if utc_offset is not None:
        report['emulator_utc_offset'] = utc_offset
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', type=Path)
    parser.add_argument('probe', type=Path, nargs='?')
    parser.add_argument('output', type=Path)
    parser.add_argument('--settings', type=Path, help='Include the optional ARM settings self-test app')
    parser.add_argument('--navigation-patch', type=Path, help='Apply the GD13MY .061 settings patch to the bench image')
    parser.add_argument('--usb-client', type=Path, help='Include the ARM CE USB host client DLL')
    parser.add_argument('--native-projection', type=Path, help='Include the navigation-process projection DLL')
    parser.add_argument('--stock-display', type=Path, help='Apply the .061 OEM display publishers to the bench image')
    parser.add_argument('--startup-patch', type=Path, help='Replace the .061 system manager with the opt-in startup patch')
    parser.add_argument('--compact', action='store_true', help='Copy and audit only DiskA for --app-volume')
    parser.add_argument('--emulator-utc', action='store_true', help='Reserve a read-only host UTC mailbox on DiskA')
    parser.add_argument('--aare-identity', type=Path, help='Provision an enrolled AARE identity in the emulator image')
    args = parser.parse_args()
    if args.probe is None and args.settings is None:
        parser.error('Supply a CE probe or --settings application')
    report = package(args.base, args.probe, args.output, settings=args.settings,
                     navigation_patch=args.navigation_patch, usb_client=args.usb_client,
                     startup_patch=args.startup_patch, native_projection=args.native_projection, stock_display=args.stock_display,
                     compact=args.compact, emulator_utc=args.emulator_utc, aare_identity=args.aare_identity)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
