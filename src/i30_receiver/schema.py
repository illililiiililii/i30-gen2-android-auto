"""Bind pinned upstream protobuf descriptors without copying field definitions."""

from functools import cache
from importlib.resources import files

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.message import DecodeError

from .wire import ProtocolError

CTL = "aap_protobuf.service.control.message."
MEDIA = "aap_protobuf.service.media."


@cache
def _pool():
    descriptors = descriptor_pb2.FileDescriptorSet.FromString(
        files(__package__).joinpath("aasdk.pb").read_bytes()
    )
    pool = descriptor_pool.DescriptorPool()
    for file in descriptors.file:
        pool.Add(file)
    return pool


@cache
def message(name):
    return message_factory.GetMessageClass(_pool().FindMessageTypeByName(name))


def value(enum, name):
    return _pool().FindEnumTypeByName(enum).values_by_name[name].number


def parse(name, data):
    try:
        decoded = message(name).FromString(data)
        if not decoded.IsInitialized():
            raise ProtocolError(f"Incomplete {name.rsplit('.', 1)[-1]}")
        return decoded
    except DecodeError as exc:
        raise ProtocolError(f"Malformed {name.rsplit('.', 1)[-1]}") from exc
