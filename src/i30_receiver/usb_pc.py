"""PyUSB/libusb adapter for the PC. USB driver selection stays with the OS."""

from pathlib import Path

from .transport import Device, Disconnected, InterfaceNotReady, READ_SIZE, Timeout, TransportError


class PyUsb:
    def __init__(self, library: Path | None = None):
        import usb.backend.libusb1
        import usb.core
        import usb.util

        self.core = usb.core
        self.util = usb.util
        kwargs = {} if library is None else {"find_library": lambda _: str(library.resolve())}
        self.backend = usb.backend.libusb1.get_backend(**kwargs)
        if self.backend is None:
            raise TransportError("libusb is unavailable; install it or pass --libusb")
        self.inventory = {}
        self.control_handles = {}

    def invoke(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except self.core.USBTimeoutError as exc:
            raise Timeout("USB I/O timed out") from exc
        except self.core.USBError as exc:
            if exc.backend_error_code == -4:
                raise Disconnected("USB device removed") from exc
            raise TransportError(f"USB I/O failed: {exc}") from exc

    def devices(self):
        found = self.invoke(lambda: list(self.core.find(find_all=True, backend=self.backend)))
        rows = {}
        for raw in found:
            ports = raw.port_numbers
            port = f"{raw.bus}-" + ".".join(map(str, ports)) if raw.bus is not None and ports else None
            row = Device(port, raw.idVendor, raw.idProduct, raw.address, raw.bDeviceClass == 8)
            rows[row] = raw
        self.inventory = rows
        return sorted(rows, key=lambda row: (row.port or "", row.address or 0, row.vendor, row.product))

    def control(self, device):
        if device in self.control_handles:
            return self.control_handles[device]
        raw = self.get_device(device)
        # Many USB sticks identify as per-interface rather than device class 8.
        try:
            configuration = self.active_configuration(raw)
            if any(interface.bInterfaceClass == 8 for interface in configuration):
                raise TransportError("Selected configuration contains a USB mass-storage interface")
        except TransportError:
            self.dispose(raw)
            raise
        self.control_handles[device] = raw
        return raw

    def get_device(self, device):
        try:
            return self.inventory[device]
        except KeyError as exc:
            raise Disconnected("Selected USB device disappeared") from exc

    def control_in(self, device, request, length, timeout_ms):
        raw = self.control(device)
        return bytes(self.invoke(raw.ctrl_transfer, 0xc0, request, 0, 0, length, timeout=timeout_ms))

    def control_out(self, device, request, index, payload, timeout_ms):
        raw = self.control(device)
        written = self.invoke(raw.ctrl_transfer, 0x40, request, 0, index, payload, timeout=timeout_ms)
        if written != len(payload):
            raise TransportError("Short AOA control write")

    def release_control(self, device):
        raw = self.control_handles.pop(device, None)
        if raw is not None:
            self.dispose(raw)

    def dispose(self, raw):
        try:
            self.util.dispose_resources(raw)
        except self.core.USBError:
            pass  # An already unplugged device has no active handle to return.

    def active_configuration(self, raw):
        try:
            return self.invoke(raw.get_active_configuration)
        except NotImplementedError as exc:
            # PyUSB maps libusb's NOT_SUPPORTED to this exception. On Windows
            # the device can enumerate before its interface driver is ready.
            raise InterfaceNotReady("USB interface driver is not ready or unsupported") from exc

    def open_accessory(self, device, *, raw=None):
        if not device.accessory:
            raise TransportError("Device has no AOA accessory data interface")
        if raw is None:
            raw = self.get_device(device)
        try:
            config = self.active_configuration(raw)
            # AOSP and aasdk use interface 0, alternate 0 for accessory data.
            interface = config[(0, 0)]
            bulk_in = [e.bEndpointAddress for e in interface
                       if (e.bmAttributes & 3) == 2 and (e.bEndpointAddress & 0x80)]
            bulk_out = [e.bEndpointAddress for e in interface
                        if (e.bmAttributes & 3) == 2 and not (e.bEndpointAddress & 0x80)]
            if len(bulk_in) != 1 or len(bulk_out) != 1 or interface.bInterfaceClass != 0xff:
                raise TransportError("Accessory data interface has unexpected endpoints")
            try:
                self.invoke(self.util.claim_interface, raw, interface.bInterfaceNumber)
            except NotImplementedError as exc:
                raise InterfaceNotReady("USB accessory interface driver is not ready or unsupported") from exc
        except KeyError as exc:
            self.dispose(raw)
            raise TransportError("Accessory interface 0 is missing") from exc
        except (TransportError, ValueError):
            self.dispose(raw)
            raise
        return UsbLink(self, raw, bulk_in[0], bulk_out[0])


class UsbLink:
    def __init__(self, adapter, device, input_endpoint, output_endpoint):
        self.adapter = adapter
        self.device = device
        self.input_endpoint = input_endpoint
        self.output_endpoint = output_endpoint

    def read(self, timeout_ms, *, size=READ_SIZE):
        data = self.adapter.invoke(self.device.read, self.input_endpoint, size, timeout=timeout_ms)
        return bytes(data)

    def write(self, data, timeout_ms):
        written = self.adapter.invoke(self.device.write, self.output_endpoint, data, timeout=timeout_ms)
        if written != len(data):
            raise TransportError("Short USB bulk write")

    def close(self):
        self.adapter.dispose(self.device)
