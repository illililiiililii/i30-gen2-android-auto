# 선행 연구와 도구 선택

2026-11-20에 링크 12개가 모두 공개 저장소로 유효함을 확인했다. 기본 브랜치의 README, 대표 소스 또는 빌드 매니페스트, 라이선스 파일과 커밋을 조사했다. 표의 업데이트 시점은 확인한 기본 브랜치 커밋 날짜다. 정확한 커밋 및 GitHub 라이선스 자동 인식 결과는 [upstream-metadata.json](../research/evidence/upstream-metadata.json)에 있다.

| 저장소 | 역할과 실제 소스 | 라이선스 · 최근 커밋 · 선택 |
|---|---|---|
| [morluto/rea](https://github.com/morluto/rea) | 바이너리 정적 메타데이터, Ghidra 등 분석기와 연결하는 Codex MCP/CLI. `package.json`, 설치 및 MCP 계약 문서. 고정 릴리스는 Node 22.23.4+/24.22.1+/26.12.1+의 지정 계열 필요. | MIT · 2026-11-20 · REA 6.10.1 설치 및 Codex 등록. |
| [REA_Skill](https://github.com/smartworldarafath/REA_Skill) | REA 자체 엔진과 별개인 에이전트 워크플로 모음. README, `package.json`, `LICENSE` 확인. 기능이 중복되고 현 분석 범위보다 넓다. | MIT · 2026-11-09 · 생략. |
| [rei-skills](https://github.com/rootcastleco/rei-skills) | 독립적인 스킬 카탈로그 및 설치 도구. `package.json`, REA 통합 문서 확인. 패키지별 라이선스 별도 확인 필요. | 루트 MIT, GitHub NOASSERTION · 2026-11-19 · 생략. |
| [bethington/ghidra-mcp](https://github.com/bethington/ghidra-mcp) | Ghidra 확장과 MCP 브리지. `build.gradle`, `pyproject.toml`, README 기준 Java/Gradle, Python 및 Ghidra 버전 결합. | Apache-2.0 · 2026-11-20 · REA의 Ghidra 제공자와 중복. |
| [onekey-sec/unblob](https://github.com/onekey-sec/unblob) | 포맷 핸들러 및 외부 추출기, Python 3.11+와 Rust/maturin. `pyproject.toml`, `Cargo.toml`, Docker/Linux 설치 문서 확인. | MIT · 2026-11-16 · 범용 보조 도구. 이 패키지는 헤더 연동 추출기가 포맷 경계를 더 잘 검증한다. |
| [rgerganov/gen5fw](https://github.com/rgerganov/gen5fw) | `gen5.py`, Python requirements 및 Android sparse 이미지 도구를 사용하는 Gen5 Android 패키지 연구. 구조가 이 GD13MY의 Windows CE `.hdr/.spd`와 다르다. | MIT · 2025-01-08 · 세대 비교에 한정. |
| [onekey-sec/firmware-workshop](https://github.com/onekey-sec/firmware-workshop) | Linux 기반 EV 충전기 펌웨어 워크숍. `install-prerequisites`와 문서에 unblob, Linux 유틸리티, 에뮬레이션 도구 등. | 루트 라이선스 파일 확인되지 않음 · 2026-07-02 · 방법론 참고. |
| [NationalSecurityAgency/ghidra](https://github.com/NationalSecurityAgency/ghidra) | PE/ARM 로더와 역어셈블 및 디컴파일. Java/Gradle 프로젝트이며 공식 배포 12.2는 64비트 JDK 25 지원. | Apache-2.0 · 2026-11-19 · Ghidra 12.2 설치 및 분석. |
| [f1xpl/openauto](https://github.com/f1xpl/openauto) | 기본 브랜치 `development`, `Readme.md`. `Projection/OMXVideoOutput.cpp`, `QtVideoOutput.cpp`, `QtAudioOutput.cpp`, `InputDevice.cpp`에서 백엔드 분리 확인. Qt, Boost, aasdk, CMake, RtAudio 및 선택적 Pi OpenMAX. | GPLv3, 소스 고지에는 v3 이상 · 2024-12-12 · PC 참조 및 설계 참고. |
| [opencardev/aasdk](https://github.com/opencardev/aasdk) | 기본 브랜치 `newdev`, `Readme.md`. `src/USB/AOAPDevice.cpp`, `src/Transport/USBTransport.cpp`, `SSLWrapper.cpp` 및 채널/메시지 정의. `CMakeLists.txt`에 libusb, OpenSSL, Boost, protobuf, 조건부 Abseil. | README GPLv3, 주요 소스 v3 이상 고지. 기본 브랜치 루트 LICENSE 파일은 확인되지 않음 · 2026-06-11 · USB/프로토콜 참고. |
| [average-web-dev/openhu](https://github.com/average-web-dev/openhu) | OpenAuto 계열 Linux 헤드유닛. `FfmpegVideoOutput.cpp`, `InputDevice.cpp`, AudioGraph와 덕킹 모듈. Qt 6.8/QML, FFmpeg, Boost, aasdk, libusb 및 Linux 서비스. | GPL-3.0 · 2026-11-09 · UI 및 오디오 참고. |
| [mretallack/AndroidAuto](https://github.com/mretallack/AndroidAuto) | **휴대폰 송신기**. `UsbAoaTransport.kt`, `VideoChannel.kt`, Android SDK 빌드 파일 검토. Kotlin/MediaCodec으로 영상을 보내는 프로젝트다. | GPL-3.0 · 2026-11-04 · 수신기 후보에서 제외. |

추가 후보는 GPL-3.0 [OpenCarDev OpenAuto](https://github.com/opencardev/openauto)다. `CMakeLists.txt`와 README 기준 Linux/Qt 계열 헤드유닛이고, PC 비교 기준으로 적합하다. 기본 브랜치 커밋은 2026-02-08이다. [ReFirmLabs Binwalk v3](https://github.com/ReFirmLabs/binwalk/releases/tag/v3.1.0)은 Rust 재작성, MIT, Windows 빌드 지원 및 Windows CE 이미지 인식이 있는 보조 도구다. [Google DHU](https://developer.android.com/training/cars/testing/dhu)는 PC의 공식 Android Auto 프로젝션 기준이다.

한국 i30 GD13MY는 현대자동차의 소프트웨어 목록에서 표준형 2세대로 확인된다. TI 데이터시트는 OMAP3530의 ARM Cortex-A8, IVA2.2 DSP와 SGX 사양을 설명한다. 동일 차명으로 판매된 해외 기기나 다른 세대 펌웨어의 칩과 OS 정보는 이 기기의 근거로 사용하지 않았다. 정확한 GD13MY에서 동작한 Android Auto 수신기 공개 사례는 확인하지 못했다. [현대자동차 소프트웨어 목록](https://update.hyundai.com/KR/KO/updateNoticeView/GVgVE4) · [TI 데이터시트](https://www.ti.com/lit/ds/symlink/omap3530.pdf)
