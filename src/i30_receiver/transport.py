"""USB platform seam and AOA discovery/reenumeration without driver mutation."""

from dataclasses import dataclass
from typing import Protocol

GOOGLE = 0x18d1
ACCESSORY_PRODUCTS = {0x2d00, 0x2d01, 0x2d04, 0x2d05}
READ_SIZE = 0x8000


class TransportError(Exception):
    pass


class Disconnected(TransportError):
    pass


class Timeout(TransportError):
    pass


class InterfaceNotReady(TransportError):
    pass


@dataclass(frozen=True)
class Device:
    port: str | None
    vendor: int
    product: int
    address: int | None
    mass_storage: bool = False

    @property
    def accessory(self):
        return self.vendor == GOOGLE and self.product in ACCESSORY_PRODUCTS


class BulkLink(Protocol):
    def read(self, timeout_ms: int) -> bytes: ...
    def write(self, data: bytes, timeout_ms: int) -> None: ...
    def close(self) -> None: ...


class UsbBackend(Protocol):
    def devices(self) -> list[Device]: ...
    def control_in(self, device: Device, request: int, length: int, timeout_ms: int) -> bytes: ...
    def control_out(self, device: Device, request: int, index: int, payload: bytes, timeout_ms: int) -> None: ...
    def release_control(self, device: Device) -> None: ...
    def open_accessory(self, device: Device) -> BulkLink: ...


@dataclass(frozen=True)
class AccessoryIdentity:
    manufacturer: str = "i30 Research"
    model: str = "Android Auto"
    description: str = "i30 PC projection diagnostics"
    version: str = "1.0"

    def strings(self):
        for value in (self.manufacturer, self.model, self.description, self.version):
            encoded = value.encode("utf-8")
            if not encoded or len(encoded) > 254 or b"\x00" in encoded:
                raise ValueError("Invalid AOA identity string")
            yield encoded + b"\x00"


class AoaTransport:
    def __init__(self, backend: UsbBackend, port: str, platform, identity=AccessoryIdentity(),
                 reenumerate_seconds=8.0):
        if not port:
            raise ValueError("Select the physical USB port explicitly")
        self.backend = backend
        self.port = port
        self.platform = platform
        self.identity = identity
        self.reenumerate_seconds = reenumerate_seconds
        self.original_identity = None

    def detect(self):
        matches = [d for d in self.backend.devices() if d.port == self.port]
        if len(matches) > 1:
            raise TransportError("Ambiguous USB port")
        return matches[0] if matches else None

    def connect(self, device: Device):
        if device.port != self.port:
            raise TransportError("Selected USB device changed")
        if device.accessory:
            return self.backend.open_accessory(device)
        if device.mass_storage:
            raise TransportError("Selected device is a USB mass-storage device")
        fingerprint = (device.vendor, device.product)
        if self.original_identity is not None and fingerprint != self.original_identity:
            raise TransportError("A different USB device appeared on the selected port")
        self.original_identity = fingerprint
        try:
            data = self.backend.control_in(device, 51, 2, 1000)
            if len(data) != 2 or int.from_bytes(data, "little") not in (1, 2):
                raise TransportError("Selected device did not report AOA 1 or 2")
            self.platform.log("aoa", port=self.port, protocol=int.from_bytes(data, "little"))
            for index, value in enumerate(self.identity.strings()):
                self.backend.control_out(device, 52, index, value, 1000)
            try:
                self.backend.control_out(device, 53, 0, b"", 1000)
            except Disconnected:
                pass  # Device may reenumerate before the control request returns.
        finally:
            self.backend.release_control(device)
        deadline = self.platform.clock() + self.reenumerate_seconds
        last_error = None
        while not self.platform.stop_requested() and self.platform.clock() < deadline:
            accessory = self.detect()
            if accessory and accessory.accessory:
                try:
                    link = self.backend.open_accessory(accessory)
                except (Disconnected, InterfaceNotReady) as exc:
                    last_error = exc
                else:
                    self.platform.log("aoa_accessory", port=self.port, product=f"{accessory.product:04x}")
                    return link
            self.platform.pause(0.1)
        if last_error is not None:
            raise Timeout("Accessory reenumerated, but its data interface did not become ready") from last_error
        raise Timeout("Accessory did not reenumerate on the selected port")
