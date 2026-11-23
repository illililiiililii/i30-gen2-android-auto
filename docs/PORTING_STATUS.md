# Phase 2 · 구현체 선정과 순정 기기 포팅 상태

## 현재 구현체와 재사용 범위

조회 기준은 2026-11-20이다. 아래 구성 시험은 Visual Studio 2026 x64의 MSVC 19.51과 CMake 4.3.1에서 공개 기본 브랜치의 기록된 커밋을 대상으로 수행했다. 외부 의존성 다운로드를 제한한 CMake 구성 단계의 결과다.

| 후보 | 유지보수·라이선스·현재 구성 결과 |
|---|---|
| OpenCarDev/aasdk `9bf6adf9` | `newdev`의 확인 커밋은 2026-06-11. 원본 문서 GPLv3, C++ 소스에는 v3 이상 고지가 있다. C++17, Boost, C++ protobuf, libusb 및 OpenSSL 필요. 시스템 protobuf 경로로 구성했을 때 protoc는 발견됐으나 C++ protobuf 헤더·라이브러리가 없었다. [구성 로그](../research/evidence/phase2-configure-opencardev__aasdk.log) |
| f1xpl/OpenAuto `aa90412b` | `development`의 확인 커밋은 2024-12-12. GPLv3 계열. Qt5, Boost, aasdk, protobuf, OpenSSL, RtAudio 등이 필요하며 이 PC에서 Boost 미설치로 구성이 멈췄다. Qt/미디어 코드의 CE ABI 대상은 없다. [구성 로그](../research/evidence/phase2-configure-f1xpl__openauto.log) |
| OpenHU `49c5092a` | `main`의 확인 커밋은 2026-11-09. GPL-3.0. Linux/Pi에서 Qt6/QML, FFmpeg, aasdk 등을 사용한다. 이 Windows PC에서 C++ protobuf가 없어 CMake 단계가 중단됐다. [구성 로그](../research/evidence/phase2-configure-average-web-dev__openhu.log) |

PC 구현은 aasdk의 공개 protobuf와 프레임·세션 동작을 기준으로 자체 연결 계층을 작성했다. OpenAuto/OpenHU는 영상·입력과 플랫폼 간 분리의 참고 구현으로 유지한다. C++ 원본들에 대한 링크 빌드나 최신 스마트폰 호환성은 확인되지 않았다. 이 작업공간의 Python PC 진단 패키지 빌드는 성공했다.

재사용 시 aasdk의 고정 소스, 메시지 디스크립터 생성 명령, 라이선스 고지를 함께 관리한다. 외부 배포 전 GPLv3 계열 소스 및 libusb LGPL-2.1 등 의존성의 조건을 검토한다. OEM 파일은 프로젝트 빌드와 분리돼 있다. [aasdk](https://github.com/opencardev/aasdk/tree/9bf6adf933665dee26532201719fac14a047ccf1) · [OpenAuto](https://github.com/f1xpl/openauto/tree/aa90412bf93b5a5078495ea85ac9270c6297d369) · [OpenHU](https://github.com/average-web-dev/openhu/tree/49c5092a8a4850814866647210faf14d54a54320)

## GD13MY에서 필요한 최소 실행 환경

| 항목 | 판정과 필요한 확인 |
|---|---|
| OS/ABI | 분석한 ROM은 CE 6.0, PE32 little-endian ARM/Thumb 머신 `0x01c2`, OMAP3530 대상이다. 일반 데스크톱 MSVC x64/ARM64나 Linux armhf는 이 ABI의 검증을 대신할 수 없다. 실물 라벨·SW를 먼저 확인한다. |
| 크로스 컴파일러 | 작은 ARMV4I 사용자 모드 EXE/DLL 및 OEM 대상 SDK가 후보이다. Microsoft의 CE6 Platform Builder는 Visual Studio 2005 세대다. 라이선스가 있는 SDK와 그 장치에 맞는 헤더·링커·import library를 확보한다. PC용 MSVC만 확인됐고 CE 도구 체인은 검증하지 않았다. [Microsoft CE 6.0 Platform Builder](https://www.microsoft.com/en-us/download/details.aspx?id=4097) |
| 시스템 라이브러리 | `coredll.dll`과 OEM이 노출한 Win32 CE API를 우선한다. 실제 load/ABI 및 필요한 import를 작은 진단 프로그램으로 확인한다. TLS와 메시지 계층의 최소 구현 또는 이식 가능한 라이브러리는 정상 인증 경로와 크기·성능을 확인한 뒤 고른다. PC CPython·PyUSB·protobuf 런타임의 CE 호환은 검증되지 않았다. |
| USB | 순정 MUSB/USBD 및 클라이언트 등록 기능이 ROM에서 확인됐다. CE용 USB 클라이언트 접근과 bulk 전송을 시험해야 한다. 내부 USB 드라이버 호출 및 허용된 실행 경로는 미확인이다. [Phase 1 USB 분석](USB_ANALYSIS.md) |
| 스레드·메모리 | 단일 I/O 루프 및 한정된 버퍼를 우선한다. ROMHDR의 초기 19 MiB 범위로 가용 RAM을 산정할 수 없다. 영상 채널 없이 USB/보안/프레임 기능만 먼저 계측한다. |
| 크기·서비스 | PC zipapp 크기는 약 29 KiB이며 외부 런타임과 DLL을 제외한다. CE의 실행 파일 크기는 빌드한 뒤 PE import, `.text`, `.data`와 가용 메모리로 확인한다. 순정 UComH, MICOM과 카메라/음량 자원을 벤치에서 우선한다. |

**순정 기기용 산출물은 보류다.** 실물에서 허용된 앱 실행·복구, CE ABI, AOA 전송, 영상 및 순정 카메라 선점을 입증할 수 있는 자료가 필요하다. [Phase 1 하드웨어 판정](HARDWARE_COMPATIBILITY.md)
