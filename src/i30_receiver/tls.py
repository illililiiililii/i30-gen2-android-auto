"""TLS 1.2 record transport for the projection handshake and payloads."""

import hashlib
import hmac
from pathlib import Path
import ssl

from .wire import ProtocolError


def client_context(ca: Path, peer_name: str | None, peer_pin: str | None,
                   cert: Path | None = None, key: Path | None = None):
    if bool(peer_name) == bool(peer_pin):
        raise ValueError("Specify one expected peer name or certificate SHA-256")
    if bool(cert) != bool(key):
        raise ValueError("Client certificate and key must be provided together")
    if peer_pin is not None:
        try:
            if len(peer_pin) != 64 or len(bytes.fromhex(peer_pin)) != 32:
                raise ValueError
        except ValueError as exc:
            raise ValueError("Peer SHA-256 must be 64 hexadecimal digits") from exc
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = bool(peer_name)
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cafile=str(ca))
    if cert is not None:
        context.load_cert_chain(cert, key)
    return lambda: TlsRecords(context, peer_name=peer_name, peer_pin=peer_pin)


class TlsRecords:
    def __init__(self, context, *, server=False, peer_name=None, peer_pin=None):
        self.inbox, self.outbox = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.tls = context.wrap_bio(self.inbox, self.outbox, server_side=server, server_hostname=peer_name)
        self.pin = bytes.fromhex(peer_pin) if peer_pin is not None else None
        self.ready = False

    def handshake(self, data=b""):
        if self.ready:
            raise ProtocolError("TLS handshake repeated")
        if data:
            self.inbox.write(data)
        try:
            self.tls.do_handshake()
        except ssl.SSLWantReadError:
            return self.outbox.read()
        except ssl.SSLCertVerificationError as exc:
            raise ProtocolError(f"TLS peer certificate verification failed "
                                f"({exc.verify_code}): {exc.verify_message}") from exc
        except ssl.SSLError as exc:
            raise ProtocolError(f"TLS handshake failed: {exc.reason or 'TLS error'}") from exc
        if self.pin is not None:
            certificate = self.tls.getpeercert(binary_form=True)
            if not certificate or not hmac.compare_digest(hashlib.sha256(certificate).digest(), self.pin):
                raise ProtocolError("TLS peer certificate fingerprint does not match")
        self.ready = True
        return self.outbox.read()

    def negotiated(self):
        return self.tls.version(), self.tls.cipher()[0]

    def encrypt(self, plain):
        if not self.ready:
            raise ProtocolError("TLS not established")
        try:
            if self.tls.write(plain) != len(plain):
                raise ProtocolError("Short TLS plaintext write")
        except ssl.SSLError as exc:
            raise ProtocolError("TLS record encryption failed") from exc
        return self.outbox.read()

    def decrypt(self, wire):
        if not self.ready:
            raise ProtocolError("Protected frame before TLS finished")
        self.inbox.write(wire)
        chunks = []
        try:
            while True:
                chunk = self.tls.read(0x4000)
                if not chunk:
                    raise ProtocolError("Peer closed TLS")
                chunks.append(chunk)
        except ssl.SSLWantReadError:
            if not chunks or self.inbox.pending or self.outbox.pending:
                raise ProtocolError("Incomplete TLS data frame or unexpected renegotiation")
            return b"".join(chunks)
        except ssl.SSLError as exc:
            raise ProtocolError("TLS rejected protected frame") from exc
