"""Build the PC diagnostic zipapp using pinned aasdk protobuf input."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipapp

from inspect_firmware import ROOT

CONTROL = "aap_protobuf/service/control/"
MEDIA = "aap_protobuf/service/media/"
INPUT = "aap_protobuf/service/inputsource/"
SCHEMAS = [
    CONTROL + "ControlMessageType.proto",
    *(CONTROL + "message/" + name + ".proto" for name in (
        "AuthResponse", "ServiceDiscoveryRequest", "ServiceDiscoveryResponse", "ChannelOpenRequest",
        "ChannelOpenResponse", "PingRequest", "PingResponse", "ByeByeRequest", "ByeByeResponse",
        "AudioFocusRequest", "AudioFocusNotification", "VoiceSessionNotification")),
    MEDIA + "sink/MediaMessageId.proto",
    *(MEDIA + "shared/message/" + name + ".proto" for name in ("Setup", "Config", "Start", "Stop")),
    MEDIA + "source/message/Ack.proto",
    MEDIA + "source/message/MicrophoneRequest.proto",
    MEDIA + "source/message/MicrophoneResponse.proto",
    MEDIA + "video/message/VideoFocusNotification.proto",
    MEDIA + "video/message/VideoFocusRequestNotification.proto",
    INPUT + "InputMessageId.proto",
    INPUT + "message/InputReport.proto",
    MEDIA + "sink/message/KeyBindingRequest.proto",
    MEDIA + "sink/message/KeyBindingResponse.proto",
    MEDIA + "sink/message/KeyCode.proto",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protoc", required=True, type=Path)
    parser.add_argument("--schemas", type=Path, default=ROOT / "research/sources/opencardev__aasdk/protobuf")
    args = parser.parse_args()
    package = ROOT / "src/i30_receiver"
    descriptor = package / "aasdk.pb"
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        output = staging / "aasdk.pb"
        subprocess.run([str(args.protoc.resolve()), f"--proto_path={args.schemas.resolve()}",
                        "--include_imports", f"--descriptor_set_out={output}", *SCHEMAS],
                       cwd=args.schemas, check=True)
        shutil.copyfile(output, descriptor)
        shutil.copytree(package, staging / package.name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        output.unlink()
        (staging / "__main__.py").write_text(
            "from i30_receiver.cli import main\n\nraise SystemExit(main())\n", encoding="utf-8")
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        zipapp.create_archive(staging, build / "i30-receiver.pyz", compressed=True)
    print(build / "i30-receiver.pyz")


if __name__ == "__main__":
    main()
