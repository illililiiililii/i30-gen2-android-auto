"""Render stock GDdNavi OpenGL ES calls through host WGL or the bitmap fallback."""

import ctypes as C
import os
from ctypes import wintypes as W
from struct import iter_unpack, pack, pack_into, unpack
from time import monotonic

import pefile
from gd13my_arm import RM, abort_status, exception_entry, translate
from gd13my_display import png
from unicorn import UC_HOOK_CODE, UcError
from unicorn.arm_const import (
    UC_ARM_REG_CPSR,
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_SP,
)

I, U, F, D, B, P = C.c_int, C.c_uint, C.c_float, C.c_double, C.c_ubyte, C.c_void_p

FUNC = {
    29: ("glBindTexture", None, "uu"),
    30: ("glBlendFunc", None, "uu"),
    31: ("glClear", None, "u"),
    32: ("glClearColor", None, "ffff"),
    38: ("glColor4f", None, "ffff"),
    48: ("glDepthFunc", None, "u"),
    49: ("glDepthMask", None, "b"),
    52: ("glDisable", None, "u"),
    53: ("glDisableClientState", None, "u"),
    56: ("glEnable", None, "u"),
    57: ("glEnableClientState", None, "u"),
    60: ("glFogf", None, "uf"),
    64: ("glFrontFace", None, "u"),
    65: ("glFrustum", None, "dddddd"),
    68: ("glGetError", U, ""),
    71: ("glHint", None, "uu"),
    80: ("glLineWidth", None, "f"),
    82: ("glLoadIdentity", None, ""),
    90: ("glMatrixMode", None, "u"),
    98: ("glOrtho", None, "dddddd"),
    105: ("glPopMatrix", None, ""),
    106: ("glPushMatrix", None, ""),
    108: ("glRotatef", None, "ffff"),
    112: ("glScalef", None, "fff"),
    114: ("glScissor", None, "iiii"),
    125: ("glTexParameterf", None, "uuf"),
    128: ("glTranslatef", None, "fff"),
    131: ("glViewport", None, "iiii"),
    141: ("glColor4ub", None, "bbbb"),
}
EGL = {
    1: "eglChooseConfig",
    3: "eglCreateContext",
    6: "eglCreateWindowSurface",
    10: "eglGetConfigs",
    14: "eglGetDisplay",
    15: "eglGetError",
    17: "eglInitialize",
    18: "eglMakeCurrent",
    22: "eglSwapBuffers",
}
CLIENT_ARRAYS = {
    41: ("glColorPointer", 0x8076),
    119: ("glTexCoordPointer", 0x8078),
    130: ("glVertexPointer", 0x8074),
}
BYTES = {
    0x1400: 1,
    0x1401: 1,
    0x1402: 2,
    0x1403: 2,
    0x1404: 4,
    0x1405: 4,
    0x1406: 4,
    0x140C: 4,
}
PIXEL_CHANNELS = {0x1906: 1, 0x1907: 3, 0x1908: 4, 0x1909: 1, 0x190A: 2, 0x80E1: 4}
PACKED = {
    0x8363: ((11, 5), (5, 6), (0, 5)),
    0x8033: ((12, 4), (8, 4), (4, 4), (0, 4)),
    0x8034: ((11, 5), (6, 5), (1, 5), (0, 1)),
}
LIMIT = 32 * 1024 * 1024
THUNK = bytes.fromhex("04c09fe500c09ce51cff2fe1")
GLES_WIDTH, GLES_HEIGHT = 800, 480


class RetryGuestCall(Exception):
    pass


def api(dll, name, result, *args):
    proc = getattr(dll, name)
    proc.restype, proc.argtypes = result, args
    return proc


class PFD(C.Structure):
    _fields_ = (
        [("size", W.WORD), ("version", W.WORD), ("flags", W.DWORD)]
        + [
            (name, B)
            for name in (
                "type",
                "color",
                "r",
                "rs",
                "g",
                "gs",
                "b",
                "bs",
                "a",
                "as",
                "acc",
                "accr",
                "accg",
                "accb",
                "acca",
                "depth",
                "stencil",
                "aux",
                "layer",
                "reserved",
            )
        ]
        + [(name, W.DWORD) for name in ("layer_mask", "visible_mask", "damage_mask")]
    )


class BitmapGL:
    def __init__(self):
        self.gdi, self.dll = C.WinDLL("gdi32"), C.WinDLL("opengl32")
        self.user = C.WinDLL("user32", use_last_error=True)
        self.dc = self.surface = self.ctx = self.previous = self.window = None
        self.window_class = None
        self.window_proc = None
        self.backend = "software"
        self.vendor = self.renderer = self.version = "unknown"
        try:
            requested = os.environ.get("GD13MY_GL_BACKEND", "software").casefold()
            if requested not in ("auto", "hardware", "software"):
                raise ValueError("GD13MY_GL_BACKEND must be auto, hardware, or software")
            if requested != "software":
                try:
                    self._init_window()
                    self._identify_renderer()
                    if self.backend == "hardware":
                        return
                    self.close()
                    self.__init_software()
                except (AttributeError, C.ArgumentError, OSError, RuntimeError):
                    self.close()
                    if requested == "hardware":
                        raise
                    self.__init_software()
            else:
                self.__init_software()
            self._identify_renderer()
            if requested == "hardware" and self.backend != "hardware":
                raise RuntimeError(f"Hardware OpenGL unavailable ({self.renderer})")
        except Exception:
            self.close()
            raise

    def __init_software(self):
        self.dc = api(self.gdi, "CreateCompatibleDC", W.HDC, W.HDC)(None)
        if not self.dc:
            raise RuntimeError("Win32 could not create the OpenGL memory DC")
        info = pack(
            "<IiiHHIIiiII",
            40,
            GLES_WIDTH,
            GLES_HEIGHT,
            1,
            32,
            0,
            GLES_WIDTH * GLES_HEIGHT * 4,
            0,
            0,
            0,
            0,
        )
        bits = P()
        self.surface = api(
            self.gdi,
            "CreateDIBSection",
            W.HBITMAP,
            W.HDC,
            P,
            U,
            C.POINTER(P),
            W.HANDLE,
            U,
        )(self.dc, info, 0, C.byref(bits), None, 0)
        self.select = api(self.gdi, "SelectObject", W.HGDIOBJ, W.HDC, W.HGDIOBJ)
        self.previous = self.select(self.dc, self.surface) if self.surface else None
        if not self.previous:
            raise RuntimeError("Win32 could not select the OpenGL bitmap")
        desc = PFD()
        desc.size, desc.version = C.sizeof(PFD), 1
        desc.flags, desc.color, desc.depth, desc.stencil = 0x28, 32, 24, 8
        choose = api(self.gdi, "ChoosePixelFormat", I, W.HDC, C.POINTER(PFD))
        selected = choose(self.dc, C.byref(desc))
        if not selected or not api(
            self.gdi, "SetPixelFormat", W.BOOL, W.HDC, I, C.POINTER(PFD)
        )(self.dc, selected, C.byref(desc)):
            raise RuntimeError("Win32 bitmap OpenGL pixel format unavailable")
        self.ctx = api(self.dll, "wglCreateContext", W.HANDLE, W.HDC)(self.dc)
        self.current = api(self.dll, "wglMakeCurrent", W.BOOL, W.HDC, W.HANDLE)
        if not self.ctx or not self.current(self.dc, self.ctx):
            raise RuntimeError("Win32 bitmap OpenGL context unavailable")
        self.backend = "software"
        self.call("glPixelStorei", None, "ui", 0x0CF5, 1)
        self.call("glPixelStorei", None, "ui", 0x0D05, 1)

    def _init_window(self):
        class WNDCLASS(C.Structure):
            _fields_ = (("style", U), ("procedure", P), ("class_extra", I),
                        ("window_extra", I), ("instance", W.HINSTANCE), ("icon", W.HICON),
                        ("cursor", W.HCURSOR), ("background", W.HBRUSH),
                        ("menu_name", W.LPCWSTR), ("class_name", W.LPCWSTR))

        result = C.c_ssize_t
        self.user.DefWindowProcW.restype = result
        self.user.DefWindowProcW.argtypes = (W.HWND, U, W.WPARAM, W.LPARAM)
        self.window_proc = C.WINFUNCTYPE(result, W.HWND, U, W.WPARAM, W.LPARAM)(
            self.user.DefWindowProcW
        )
        kernel = C.WinDLL("kernel32")
        instance = api(kernel, "GetModuleHandleW", W.HINSTANCE, W.LPCWSTR)(None)
        self.window_class = f"GD13MYHiddenWGL-{id(self):x}"
        descriptor = WNDCLASS(0x20, C.cast(self.window_proc, P), 0, 0, instance,
                              None, None, None, None, self.window_class)
        register = api(self.user, "RegisterClassW", W.WORD, C.POINTER(WNDCLASS))
        if not register(C.byref(descriptor)):
            raise OSError(C.get_last_error(), "RegisterClassW failed")
        create = api(self.user, "CreateWindowExW", W.HWND, U, W.LPCWSTR, W.LPCWSTR, U,
                     I, I, I, I, W.HWND, W.HMENU, W.HINSTANCE, P)
        self.window = create(0, self.window_class, "", 0x80000000, 0, 0,
                             GLES_WIDTH, GLES_HEIGHT, None, None, instance, None)
        if not self.window:
            raise OSError(C.get_last_error(), "Could not create hidden OpenGL window")
        self.dc = api(self.user, "GetDC", W.HDC, W.HWND)(self.window)
        if not self.dc:
            raise OSError(C.get_last_error(), "GetDC failed for hidden OpenGL window")
        desc = PFD()
        desc.size, desc.version = C.sizeof(PFD), 1
        desc.flags, desc.type, desc.color, desc.depth, desc.stencil = 0x24, 0, 32, 24, 8
        choose = api(self.gdi, "ChoosePixelFormat", I, W.HDC, C.POINTER(PFD))
        selected = choose(self.dc, C.byref(desc))
        set_pixel = api(self.gdi, "SetPixelFormat", W.BOOL, W.HDC, I, C.POINTER(PFD))
        if not selected or not set_pixel(self.dc, selected, C.byref(desc)):
            raise RuntimeError("Window OpenGL pixel format unavailable")
        self.ctx = api(self.dll, "wglCreateContext", W.HANDLE, W.HDC)(self.dc)
        self.current = api(self.dll, "wglMakeCurrent", W.BOOL, W.HDC, W.HANDLE)
        if not self.ctx or not self.current(self.dc, self.ctx):
            raise RuntimeError("Window OpenGL context unavailable")
        self.backend = "window"
        self.call("glPixelStorei", None, "ui", 0x0CF5, 1)
        self.call("glPixelStorei", None, "ui", 0x0D05, 1)

    def _identify_renderer(self):
        def query(name, enum):
            value = self.call("glGetString", C.c_char_p, "u", enum)
            return value.decode("ascii", "replace") if value else "unknown"

        self.vendor = query("vendor", 0x1F00)
        self.renderer = query("renderer", 0x1F01)
        self.version = query("version", 0x1F02)
        identity = f"{self.vendor} {self.renderer}".casefold()
        self.backend = "software" if any(
            marker in identity for marker in ("gdi generic", "basic render", "llvmpipe", "swiftshader")
        ) else "hardware" if any(marker in identity for marker in ("intel", "nvidia", "amd", "radeon")) else "unknown"

    def call(self, name, result, form, *args):
        f = api(
            self.dll,
            name,
            result,
            *({"i": I, "u": U, "f": F, "d": D, "b": B, "p": P}[key] for key in form),
        )
        return f(*args)

    def read_pixels(self, x, y, w, h, mode):
        size = w * h * PIXEL_CHANNELS[mode]
        if not 0 <= size <= LIMIT:
            raise ValueError("OpenGL readback exceeds test buffer limit")
        out = C.create_string_buffer(size)
        self.call("glReadPixels", None, "iiiiuup", x, y, w, h, mode, 0x1401, out)
        return out.raw

    def close(self):
        if self.ctx:
            if hasattr(self, "current"):
                self.current(None, None)
            api(self.dll, "wglDeleteContext", W.BOOL, W.HANDLE)(self.ctx)
            self.ctx = None
        if self.previous and self.dc:
            self.select(self.dc, self.previous)
        if self.surface:
            api(self.gdi, "DeleteObject", W.BOOL, W.HGDIOBJ)(self.surface)
            self.surface = None
        if self.dc:
            if self.window:
                api(self.user, "ReleaseDC", I, W.HWND, W.HDC)(self.window, self.dc)
            else:
                api(self.gdi, "DeleteDC", W.BOOL, W.HDC)(self.dc)
            self.dc = None
        if self.window:
            api(self.user, "DestroyWindow", W.BOOL, W.HWND)(self.window)
            self.window = None
        if self.window_class:
            kernel = C.WinDLL("kernel32")
            instance = api(kernel, "GetModuleHandleW", W.HINSTANCE, W.LPCWSTR)(None)
            api(self.user, "UnregisterClassW", W.BOOL, W.LPCWSTR, W.HINSTANCE)(
                self.window_class, instance
            )
            self.window_class = None


def thunks(path):
    pe = pefile.PE(str(path))
    lib = next(
        d for d in pe.DIRECTORY_ENTRY_IMPORT if d.dll.lower() == b"libgles_cm.dll"
    )
    imports = {i.address: i.ordinal for i in lib.imports}
    base = pe.OPTIONAL_HEADER.ImageBase
    for section in pe.sections:
        if not section.IMAGE_SCN_MEM_EXECUTE:
            continue
        b = section.get_data()
        offset = b.find(THUNK)
        while offset != -1:
            if offset % 4 == 0 and offset + 16 <= len(b):
                address = unpack("<I", b[offset + 12 : offset + 16])[0]
                if address in imports:
                    yield (
                        base + section.VirtualAddress + offset,
                        imports[address],
                        b[offset : offset + 16],
                    )
            offset = b.find(THUNK, offset + 4)


class GuestGL:
    def __init__(self, run, exe, *, preview=False):
        self.preview = preview
        from texture2ddecoder import decode_etc1, decode_pvrtc

        self.run = run
        self.decode_etc1 = decode_etc1
        self.decode_pvrtc = decode_pvrtc
        self.gl = None
        self.error = 0x3000
        self.gl_error = 0
        self.arrays = {}
        self.enabled = set()
        self.next_map_copy = 0
        self.next_preview = 0
        self.swaps = 0
        self.ready_swaps = 0
        self.map_copies = 0
        self.map_copy_seconds = 0.0
        self.first_map_copy = self.last_map_copy = None
        self.logged = set()
        self.retries = {}
        self.log = run.output.with_suffix(".gles.log")
        binds = list(thunks(exe))
        if len(binds) != 53:
            raise ValueError(
                f"Expected 53 GDdNavi GLES import thunks, found {len(binds)}"
            )
        for pc, ordinal, signature in binds:
            run.cpu.hook_add(
                UC_HOOK_CODE, self.intercept, (ordinal, signature), begin=pc, end=pc
            )

    def close(self):
        if self.gl:
            self.gl.close()

    def note(self, *args):
        with self.log.open("a", encoding="utf-8") as out:
            print(self.run.clock_ticks(), *args, file=out)

    def guest_ranges(self, addr, length):
        if not 0 <= length <= LIMIT or not 0 <= addr <= 0xFFFFFFFF - length:
            raise ValueError("Invalid GLES guest buffer extent")
        while length:
            mapping = translate(self.run.cpu, addr)
            chunk = min(length, 4096 - (addr % 4096))
            if (
                mapping is None
                or mapping.physical is None
                or not self.run.contains_ram(mapping.physical, chunk)
            ):
                raise ValueError(f"GLES could not map guest address {addr:#x}")
            yield mapping.physical, chunk
            addr += chunk
            length -= chunk

    def read(self, address, size):
        return b"".join(
            bytes(self.run.cpu.mem_read(pa, n))
            for pa, n in self.guest_ranges(address, size)
        )

    def write(self, address, data):
        offset = 0
        for pa, n in self.guest_ranges(address, len(data)):
            self.run.cpu.mem_write(pa, data[offset : offset + n])
            offset += n

    def u32(self, address, val):
        if address:
            self.write(address, pack("<I", val))

    def arguments(self, cpu, count):
        args = [cpu.reg_read(r) for r in RM[: min(count, 4)]]
        if count > 4:
            size = count - 4
            args.extend(
                unpack(f"<{size}I", self.read(cpu.reg_read(UC_ARM_REG_SP), 4 * size))
            )
        return args

    def intercept(self, cpu, pc, size, target):
        ordinal, signature = target
        mapped = translate(cpu, pc)
        if (
            mapped is None
            or mapped.physical is None
            or not self.run.contains_ram(mapped.physical, 16)
            or bytes(cpu.mem_read(mapped.physical, 16)) != signature
        ):
            return
        try:
            if ordinal not in self.logged:
                self.logged.add(ordinal)
                self.note(
                    "call",
                    ordinal,
                    EGL.get(ordinal, FUNC.get(ordinal, ("GLES",))[0]),
                    hex(cpu.reg_read(UC_ARM_REG_LR)),
                )
            result = self.dispatch(cpu, ordinal)
        except RetryGuestCall:
            return
        except (
            AttributeError,
            C.ArgumentError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            UcError,
            ValueError,
        ) as exc:
            key = ("error", ordinal, str(exc))
            if key not in self.logged:
                self.logged.add(key)
                self.note(*key)
            self.error = 0x3001
            self.gl_error = 0x0502
            result = 0 if ordinal in EGL else None
        if result is not None:
            cpu.reg_write(RM[0], result)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def dispatch(self, cpu, ordinal):
        if ordinal in EGL:
            return self.egl(cpu, ordinal)
        if not self.gl:
            self.gl_error = 0x0502
            return 0 if ordinal == 68 else None
        if ordinal == 68 and self.gl_error:
            value, self.gl_error = self.gl_error, 0
            return value
        if ordinal in FUNC:
            name, result, form = FUNC[ordinal]
            args = self.arguments(cpu, len(form))
            for index, key in enumerate(form):
                if key in "fd":
                    args[index] = unpack("<f", pack("<I", args[index]))[0]
            if ordinal in (53, 57):
                if ordinal == 53:
                    self.enabled.discard(args[0])
                else:
                    self.enabled.add(args[0])
            return self.gl.call(name, result, form, *args)
        if ordinal in CLIENT_ARRAYS:
            _, flag = CLIENT_ARRAYS[ordinal]
            self.arrays[flag] = (CLIENT_ARRAYS[ordinal][0], self.arguments(cpu, 4))
        elif ordinal in (54, 55):
            mode, second, third = self.arguments(cpu, 3)
            if ordinal == 55:
                count, data_type = second, third
                addr = self.arguments(cpu, 4)[3]
                width = BYTES[data_type]
                indices = self.read(addr, count * width)
                code = {1: "B", 2: "H", 4: "I"}[width]
                largest = max(
                    (i for (i,) in iter_unpack("<" + code, indices)), default=0
                )
                # Keep Python-owned vertex memory alive until OpenGL finishes reading it.
                _buffers = self.prepare_arrays(largest + 1)
                self.gl.call(
                    "glDrawElements", None, "uiup", mode, count, data_type, indices
                )
            else:
                first, count = second, third
                _buffers = self.prepare_arrays(first + count)
                self.gl.call("glDrawArrays", None, "uii", mode, first, count)
        elif ordinal in (47, 67):
            n, addr = self.arguments(cpu, 2)
            if n > 32768:
                raise ValueError("Invalid OpenGL texture name count")
            names = (
                C.create_string_buffer(n * 4)
                if ordinal == 67
                else self.read(addr, n * 4)
            )
            self.gl.call(
                "glGenTextures" if ordinal == 67 else "glDeleteTextures",
                None,
                "ip",
                n,
                names,
            )
            if ordinal == 67:
                self.write(addr, names.raw)
        elif ordinal in (61, 91):
            if ordinal == 91:
                (pointer,) = self.arguments(cpu, 1)
                self.gl.call("glMultMatrixf", None, "p", self.read(pointer, 64))
            else:
                name, pointer = self.arguments(cpu, 2)
                self.gl.call(
                    "glFogfv",
                    None,
                    "up",
                    name,
                    self.read(pointer, 16 if name == 0x0B66 else 4),
                )
        elif ordinal == 149:
            name, pointer = self.arguments(cpu, 2)
            values = C.create_string_buffer(64)
            n = (
                16
                if name in (0x0BA6, 0x0BA7, 0x0BA8)
                else 4
                if name in (0x0BA2, 0x0C22, 0x0B66, 0x0B00)
                else 1
            )
            self.check_float_buffer(cpu, pointer, n * 4)
            self.gl.call("glGetFloatv", None, "up", name, values)
            self.write(pointer, values.raw[: 4 * n])
        elif ordinal == 126:
            target, name, fixed = self.arguments(cpu, 3)
            value = C.c_int32(fixed).value
            if name in (0x2800, 0x2801, 0x2802, 0x2803, 0x8191):
                self.gl.call("glTexParameteri", None, "uui", target, name, value)
            else:
                self.gl.call(
                    "glTexParameterf", None, "uuf", target, name, value / 65536.0
                )
        elif ordinal in (42, 124, 127):
            self.texture(ordinal, self.arguments(cpu, 8 if ordinal == 42 else 9))
        elif ordinal == 107:
            x, y, w, h, mode, kind, addr = self.arguments(cpu, 7)
            if kind == 0x8363 and mode == 0x1907:
                rgb = self.gl.read_pixels(x, y, w, h, 0x1907)
                rgb565 = bytearray(w * h * 2)
                for i in range(w * h):
                    r, g, b = rgb[3 * i : 3 * i + 3]
                    pack_into(
                        "<H",
                        rgb565,
                        2 * i,
                        ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3),
                    )
                data = bytes(rgb565)
                width = w * 2
            elif kind == 0x1401:
                data = self.gl.read_pixels(x, y, w, h, mode)
                width = w * PIXEL_CHANNELS[mode]
            else:
                raise ValueError(f"Unsupported glReadPixels {mode:#x}/{kind:#x}")
            stride = (width + 3) & ~3
            if stride != width:
                data = b"".join(
                    data[n : n + width].ljust(stride, b"\0")
                    for n in range(0, len(data), width)
                )
            self.write(addr, data)
        else:
            raise ValueError(f"Unsupported GDdNavi GLES ordinal {ordinal}")
        return None

    def check_float_buffer(self, cpu, pointer, length):
        # A caller can pass an untouched CE data page. Let CE commit it before writing.
        pc = cpu.reg_read(UC_ARM_REG_PC)
        cpsr = cpu.reg_read(UC_ARM_REG_CPSR)
        for address in (pointer, pointer + length - 1):
            mapping = translate(cpu, address)
            status = (
                abort_status(cpu, mapping, cpsr, write=True, fetch=False)
                if mapping is not None
                else 0
            )
            key = (pc, address)
            if status not in (5, 7):
                self.retries.pop(key, None)
                continue
            attempts = self.retries.get(key, 0)
            if attempts >= 2:
                raise ValueError(f"CE did not commit OpenGL data page {address:#x}")
            self.retries[key] = attempts + 1
            cpu.cpr_write(15, 0, 5, 0, 0, 0, False, status | (1 << 11))
            cpu.cpr_write(15, 0, 6, 0, 0, 0, False, address)
            exception_entry(
                cpu,
                cpsr,
                pc,
                vector_offset=0x10,
                mode=0x17,
                return_offset=8,
                mask_async=True,
            )
            self.note("guest demand-page fault", hex(address), hex(status))
            raise RetryGuestCall

    def egl(self, cpu, ordinal):
        if ordinal == 14:
            return 1
        if ordinal == 15:
            result, self.error = self.error, 0x3000
            return result
        args = self.arguments(
            cpu, {1: 5, 3: 4, 6: 4, 10: 4, 17: 3, 18: 4, 22: 2}[ordinal]
        )
        if args[0] != 1:
            self.error = 0x3008
            return 0
        if ordinal == 17:
            if not self.gl:
                self.gl = BitmapGL()
                self.note("host OpenGL", self.gl.backend, self.gl.vendor,
                          self.gl.renderer, self.gl.version)
            self.u32(args[1], 1)
            self.u32(args[2], 1)
            return 1
        if not self.gl:
            self.error = 0x3001
            return 0
        if ordinal in (1, 10):
            configs, size, count = args[-3:]
            self.u32(count, 1)
            if configs and size:
                self.u32(configs, 1)
            return 1
        if ordinal in (3, 6):
            if args[1] != 1:
                self.error = 0x3005
                return 0
            return 1
        if ordinal == 18:
            return (
                int(bool(self.gl.current(self.gl.dc, self.gl.ctx)))
                if args[-1]
                else int(bool(self.gl.current(None, None)))
            )
        if ordinal == 22:
            self.swaps += 1
            self.ready_swaps += self.run.navigation_ready
            now = monotonic()
            preview = self.preview and now >= self.next_preview
            copy = self.run.display is not None and now >= self.next_map_copy
            self.gl.call("glFlush", None, "")
            if copy or preview:
                b = self.gl.read_pixels(0, 0, GLES_WIDTH, GLES_HEIGHT, 0x1907)
                if copy:
                    copied = self.run.display.copy_map_to_video(
                        b, GLES_WIDTH, GLES_HEIGHT, self.run.cpu.mem_write, self.run.contains_ram
                    )
                    elapsed = monotonic() - now
                    self.next_map_copy = now + max(1 / 30, 4 * elapsed)
                    if copied:
                        if self.first_map_copy is None:
                            self.first_map_copy = now
                        self.last_map_copy = now
                        self.map_copies += 1
                        self.map_copy_seconds += elapsed
                if preview:
                    self.next_preview = now + 2
                    width = GLES_WIDTH * 3
                    rows = b"".join(
                        b"\0" + b[i : i + width]
                        for i in range((GLES_HEIGHT - 1) * width, -1, -width)
                    )
                    frame = png(GLES_WIDTH, GLES_HEIGHT, rows)
                    self.run.output.with_suffix(".gles.png").write_bytes(frame)
                    self.run.messages.put(("map", frame))
            if self.swaps <= 3:
                self.note("swap", self.swaps, "stock guest OpenGL render")
            return 1
        return 0

    def map_report(self):
        return {
            "host_gl_backend": self.gl.backend if self.gl else None,
            "host_gl_vendor": self.gl.vendor if self.gl else None,
            "host_gl_renderer": self.gl.renderer if self.gl else None,
            "host_gl_version": self.gl.version if self.gl else None,
            "guest_swaps": self.swaps,
            "guest_swaps_after_ready": self.ready_swaps,
            "video_plane_copies": self.map_copies,
            "copy_seconds": round(self.map_copy_seconds, 4),
            "copy_window_seconds": (round(self.last_map_copy - self.first_map_copy, 4)
                                    if self.first_map_copy is not None else None),
        }

    def prepare_arrays(self, count):
        keep = []
        for flag in self.enabled:
            if flag not in self.arrays:
                continue
            name, (components, fmt, stride, ptr) = self.arrays[flag]
            item = components * BYTES[fmt]
            step = stride or item
            size = 0 if not count else step * (count - 1) + item
            data = self.read(ptr, size)
            if fmt == 0x140C:
                data = b"".join(
                    pack("<f", x / 65536.0)
                    for base in range(0, size, step)
                    for x in unpack(f"<{components}i", data[base : base + item])
                )
                fmt, stride = 0x1406, 0
            elif fmt == 0x1400 and name != "glColorPointer":
                data = b"".join(
                    pack("<f", float(x))
                    for base in range(0, size, step)
                    for x in unpack(f"<{components}b", data[base : base + item])
                )
                fmt, stride = 0x1406, 0
            keep.append(data)
            self.gl.call(name, None, "iuip", components, fmt, stride, data)
        return keep

    def texture(self, ordinal, a):
        if ordinal == 42:
            target, level, compression, w, h, border, size, ptr = a
            if not (0 < w <= 4096 and 0 < h <= 4096 and w * h * 4 <= LIMIT):
                raise ValueError("Invalid compressed texture dimensions")
            compressed = self.read(ptr, size)
            if compression == 0x8D64:
                need = ((w + 3) // 4) * ((h + 3) // 4) * 8
                decoded = (
                    self.decode_etc1(compressed, w, h)
                    if len(compressed) >= need
                    else None
                )
            elif compression in (0x8C00, 0x8C01, 0x8C02, 0x8C03):
                two = bool(compression & 1)
                need = max(w, 16 if two else 8) * max(h, 8) * (2 if two else 4) // 8
                powers = not (w & (w - 1) or h & (h - 1))
                decoded = (
                    self.decode_pvrtc(compressed, w, h, two)
                    if len(compressed) >= need and powers
                    else None
                )
            else:
                raise ValueError(f"Unsupported texture compression {compression:#x}")
            if decoded is None:
                raise ValueError(
                    "Compressed texture payload is too short or dimensions are unsupported"
                )
            self.gl.call(
                "glTexImage2D",
                None,
                "uiiiiiuup",
                target,
                level,
                0x1908,
                w,
                h,
                border,
                0x80E1,
                0x1401,
                decoded,
            )
            return
        if ordinal == 124:
            target, level, storage, w, h, border, mode, kind, addr = a
        else:
            target, level, x, y, w, h, mode, kind, addr = a
        width = w * (PIXEL_CHANNELS[mode] if kind == 0x1401 else 2)
        span = (width + 3) & ~3
        pixels = self.read(addr, span * (h - 1) + width) if addr and w and h else None
        if pixels and span != width:
            pixels = b"".join(
                pixels[k : k + width] for k in range(0, len(pixels), span)
            )
        if kind in PACKED:
            fields = PACKED[kind]
            if pixels:
                pixels = bytes(
                    ((p >> shift) & ((1 << bits) - 1)) * 255 // ((1 << bits) - 1)
                    for (p,) in iter_unpack("<H", pixels)
                    for shift, bits in fields
                )
            mode, kind = (0x1907 if len(fields) == 3 else 0x1908), 0x1401
        if kind != 0x1401:
            raise ValueError(f"Unsupported GLES texture type {kind:#x}")
        if ordinal == 124:
            self.gl.call(
                "glTexImage2D",
                None,
                "uiiiiiuup",
                target,
                level,
                storage,
                w,
                h,
                border,
                mode,
                kind,
                pixels,
            )
        else:
            self.gl.call(
                "glTexSubImage2D",
                None,
                "uiiiiiuup",
                target,
                level,
                x,
                y,
                w,
                h,
                mode,
                kind,
                pixels,
            )
