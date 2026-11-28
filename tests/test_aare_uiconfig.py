"""Host checks for the experimental AARE UiConfig wire codec.

The C codec is compiled as a Windows DLL and compared against the pinned
upstream protobuf descriptors. Nothing here enables the experiment in a
shipped image; it only proves the 0x8009/0x800A body contract.
"""

import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ZIG = Path(os.environ.get('LOCALAPPDATA', '')) / 'i30-phase5-tools/zig/zig-x86_64-windows-0.15.2/zig.exe'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from i30_receiver import schema  # noqa: E402
import build_phase2  # noqa: E402
import verify_gd13my_virtual_phone as virtual_phone  # noqa: E402

SHARED = 'aap_protobuf.service.media.shared.message.'
CONTROL = 'aap_protobuf.service.control.message.'

HARNESS = r'''
#include "ce_aa_uiconfig.h"

__declspec(dllexport) unsigned test_encode(unsigned id, const I30UiInsets *margins,
                                           const I30UiInsets *content, const I30UiInsets *stable,
                                           unsigned present, uint8_t *out, unsigned capacity)
{
    I30UiConfig config = {present, *margins, *content, *stable};
    return i30_uiconfig_encode(out, capacity, id, &config);
}

__declspec(dllexport) unsigned test_encode_ui(const I30UiInsets *margins,
                                              const I30UiInsets *content, const I30UiInsets *stable,
                                              unsigned present, uint8_t *out, unsigned capacity)
{
    I30UiConfig config = {present, *margins, *content, *stable};
    return i30_uiconfig_encode_ui(out, capacity, &config);
}

__declspec(dllexport) int test_decode(const uint8_t *body, unsigned length,
                                      unsigned *present, I30UiInsets *margins,
                                      I30UiInsets *content, I30UiInsets *stable)
{
    I30UiConfig config;
    if (!i30_uiconfig_decode(body, length, &config))
        return 0;
    *present = config.present;
    *margins = config.margins;
    *content = config.content;
    *stable = config.stable;
    return 1;
}
'''


class I30UiInsets(ctypes.Structure):
    _fields_ = [('top', ctypes.c_uint32), ('bottom', ctypes.c_uint32),
                ('left', ctypes.c_uint32), ('right', ctypes.c_uint32)]


def insets(top, bottom, left, right):
    return I30UiInsets(top, bottom, left, right)


def proto_insets(top, bottom, left, right):
    return schema.message(SHARED + 'Insets')(top=top, bottom=bottom, left=left, right=right)


def proto_ui(margins=None, content=None, stable=None):
    config = schema.message(SHARED + 'UiConfig')()
    for name, value in (('margins', margins), ('content_insets', content),
                        ('stable_content_insets', stable)):
        if value is not None:
            getattr(config, name).CopyFrom(proto_insets(*value))
    return config


@unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
class AareUiConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        directory = Path(cls.temporary.name)
        harness = directory / 'uiconfig_harness.c'
        library = directory / 'uiconfig.dll'
        harness.write_text(HARNESS, encoding='ascii')
        subprocess.run([str(ZIG), 'cc', '-target', 'x86_64-windows-gnu', '-O2',
                        '-I' + str(ROOT / 'src/ce'), '-shared', str(harness),
                        str(ROOT / 'src/ce/ce_aa_uiconfig.c'), '-o', str(library)], check=True)
        dll = ctypes.CDLL(str(library))
        cls.encode = dll.test_encode
        cls.encode.argtypes = [ctypes.c_uint, ctypes.POINTER(I30UiInsets), ctypes.POINTER(I30UiInsets),
                               ctypes.POINTER(I30UiInsets), ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        cls.encode.restype = ctypes.c_uint
        cls.encode_ui = dll.test_encode_ui
        cls.encode_ui.argtypes = [ctypes.POINTER(I30UiInsets), ctypes.POINTER(I30UiInsets),
                                  ctypes.POINTER(I30UiInsets), ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        cls.encode_ui.restype = ctypes.c_uint
        cls.decode = dll.test_decode
        cls.decode.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint),
                               ctypes.POINTER(I30UiInsets), ctypes.POINTER(I30UiInsets),
                               ctypes.POINTER(I30UiInsets)]
        cls.decode.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def encode_request(self, message_id, *, margins=None, content=None, stable=None, capacity=128):
        output = (ctypes.c_ubyte * capacity)()
        used = self.encode(message_id, insets(*(margins or (0, 0, 0, 0))),
                           insets(*(content or (0, 0, 0, 0))), insets(*(stable or (0, 0, 0, 0))),
                           (1 if margins else 0) | (2 if content else 0) | (4 if stable else 0),
                           output, capacity)
        return bytes(output[:used]), used

    def test_request_and_reply_bodies_match_upstream_protobuf(self):
        content = (32, 48, 96, 64)
        stable = (8, 12, 16, 20)
        expected_body = b'\x0a' + bytes([len(proto_ui(content=content, stable=stable)
                                              .SerializeToString())]) + \
            proto_ui(content=content, stable=stable).SerializeToString()
        for message_id in (0x8009, 0x800A):
            data, used = self.encode_request(message_id, content=content, stable=stable)
            self.assertEqual(data, bytes((message_id >> 8, message_id & 255)) + expected_body)
            self.assertEqual(used, len(data))

    def test_large_inset_values_use_protobuf_varints(self):
        content = (16384, 32768, 49152, 65535)
        expected_config = proto_ui(content=content).SerializeToString()
        expected_body = b'\x0a' + bytes((len(expected_config),)) + expected_config
        data, used = self.encode_request(0x8009, content=content)
        self.assertEqual(data, b'\x80\x09' + expected_body)
        self.assertEqual(used, len(data))

    def test_full_uint32_insets_round_trip(self):
        edges = (1, 127, 128, 0xffffffff)
        expected_config = proto_ui(margins=edges, content=edges, stable=edges).SerializeToString()
        data, used = self.encode_request(0x8009, margins=edges, content=edges, stable=edges)
        self.assertEqual(data, b'\x80\x09\x0a' + bytes((len(expected_config),)) + expected_config)
        self.assertEqual(used, len(data))
        present = ctypes.c_uint()
        margins, content, stable = I30UiInsets(), I30UiInsets(), I30UiInsets()
        self.assertEqual(self.decode(data[2:], len(data) - 2, ctypes.byref(present),
                                     ctypes.byref(margins), ctypes.byref(content),
                                     ctypes.byref(stable)), 1)
        self.assertEqual(present.value, 7)
        for actual in (margins, content, stable):
            self.assertEqual(tuple(getattr(actual, name) for name in
                                   ('top', 'bottom', 'left', 'right')), edges)

    def test_discovery_ui_config_matches_upstream_protobuf(self):
        margins = (1, 2, 3, 4)
        content = (5, 6, 7, 8)
        stable = (9, 10, 11, 12)
        output = (ctypes.c_ubyte * 128)()
        used = self.encode_ui(insets(*margins), insets(*content), insets(*stable), 7, output, 128)
        self.assertEqual(bytes(output[:used]), proto_ui(margins, content, stable).SerializeToString())

    def test_decode_round_trip_reports_present_fields(self):
        margins = (9, 8, 7, 6)
        stable = (1, 2, 3, 4)
        data, _ = self.encode_request(0x8009, margins=margins, stable=stable)
        present = ctypes.c_uint()
        decoded = [insets(0, 0, 0, 0) for _ in range(3)]
        self.assertEqual(self.decode(data[2:], len(data) - 2, ctypes.byref(present),
                                     *[ctypes.byref(item) for item in decoded]), 1)
        self.assertEqual(present.value, 5)
        self.assertEqual(tuple(getattr(decoded[0], name) for name in ('top', 'bottom', 'left', 'right')), margins)
        self.assertEqual(tuple(getattr(decoded[2], name) for name in ('top', 'bottom', 'left', 'right')), stable)

    def test_wrong_direction_and_short_buffer_are_rejected(self):
        self.assertEqual(self.encode_request(0x8008)[1], 0)
        self.assertEqual(self.encode_request(0x8009, content=(1, 2, 3, 4), capacity=8)[1], 0)
        present = ctypes.c_uint()
        malformed = (ctypes.c_ubyte * 3)(0x0a, 0x02, 0x08)
        self.assertEqual(self.decode(malformed, 3, ctypes.byref(present),
                                     ctypes.byref(insets(0, 0, 0, 0)), ctypes.byref(insets(0, 0, 0, 0)),
                                     ctypes.byref(insets(0, 0, 0, 0))), 0)


class UiConfigSchemaTests(unittest.TestCase):
    def test_descriptor_build_includes_update_messages(self):
        self.assertIn(build_phase2.CONTROL + 'message/UpdateUiConfigRequest.proto', build_phase2.SCHEMAS)
        self.assertIn(build_phase2.CONTROL + 'message/UpdateUiConfigReply.proto', build_phase2.SCHEMAS)
        for name in ('UpdateUiConfigRequest', 'UpdateUiConfigReply'):
            self.assertIsNotNone(schema.message(CONTROL + name))

    def test_typed_update_messages_match_the_shared_wire_wrapper(self):
        config = proto_ui(content=(32, 48, 96, 64))
        body = virtual_phone.wrap_ui_update(config)
        for name in ('UpdateUiConfigRequest', 'UpdateUiConfigReply'):
            message = schema.message(CONTROL + name)()
            message.ui_config.CopyFrom(config)
            self.assertEqual(message.SerializeToString(), body)
            parsed = schema.parse(CONTROL + name, body)
            self.assertEqual(parsed.ui_config, config)


class VirtualPhoneUiConfigFixtureTests(unittest.TestCase):
    def test_request_wrapper_round_trip(self):
        config = proto_ui(content=(16, 32, 48, 64), stable=(1, 2, 3, 4))
        body = virtual_phone.wrap_ui_update(config)
        parsed = virtual_phone.parse_ui_update(body)
        self.assertEqual(parsed, config)
        self.assertEqual(virtual_phone.ui_config_summary(parsed),
                         {'content_insets': {'top': 16, 'bottom': 32, 'left': 48, 'right': 64},
                          'stable_content_insets': {'top': 1, 'bottom': 2, 'left': 3, 'right': 4}})

    def test_malformed_update_is_rejected(self):
        with self.assertRaises(virtual_phone.ProtocolError):
            virtual_phone.parse_ui_update(b'\x0a\x05\x08\x01')


if __name__ == '__main__':
    unittest.main()
