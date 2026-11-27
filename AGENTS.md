# GD13MY agent guide

Start with [status](docs/PROJECT_STATUS.md), [next tasks](docs/NEXT_TASKS.md), and [handoff](docs/HANDOFF.md). Use [topic index](docs/INDEX.md) for targeted reading; do not load every historical report. Check git status and current commit first.

- Preserve original firmware, existing evidence, and local changes. No physical flashing, bootloader, BSP, kernel, partition or MICOM changes during emulator work.
- Keep guest USB/TLS/AAP processing and software fallback; separate host-only acceleration from deployable CE code.
- Distinguish static evidence, ARM/API tests, virtual phone, physical phone through emulator, and physical head unit. Do not claim real hardware performance without measurements.
- Use LeanREA and targeted CLI analysis when available; Serena, Code Review Graph, RTK, Ponytail, Caveman only if supported and useful. Avoid repeated full boot, full decompilation and screenshots. Preserve accuracy and regression coverage.
- Run relevant focused tests before full regression. Record conditions, baseline, results, limitations and reproduction commands. Do not commit credentials, private keys or large firmware images.
- Update status/next tasks/handoff when results change. Preserve historical evidence and consult docs/RELOCATION.md for moved paths. Never silently promote an inference to a verified fact.
