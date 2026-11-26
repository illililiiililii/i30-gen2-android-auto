# 03_PLATFORM_ANALYSIS.md: 제네시스 고급형 2세대 플랫폼 및 실행 환경 분석

## 1. 운영체제 및 하드웨어 사양 비교

| 비교 항목 | 제네시스 고급형 2세대 (DHPE / G80 DIS) | 대상 차량 GD13MY (표준형 2세대 i30) |
|---|---|---|
| **운영체제 (OS)** | **Linux (GNU/Linux 2.6.25 커널, MeeGo IVI 기반)** | **Windows CE 6.0 (R3)** |
| **CPU 아키텍처** | **Intel x86 (IA-32 / i386 호환, Intel Atom E6xx계열)** | **ARM Cortex-A8 (ARMv7-A, 32-bit)** |
| **SoC / 칩셋** | Intel Atom IVI 플랫폼 (LGE DHAVN 맞춤 보드) | Texas Instruments OMAP3530 |
| **바이너리 포맷** | **ELF 32-bit LSB (Executable and Linkable Format)** | **PE32 (Portable Executable for ARM)** |
| **동적 링커** | `/lib/ld-linux.so.2` (GNU libc, glibc 2.1+) | `coredll.dll` (WinCE 커널 로더) |
| **엔디언 (Endianness)** | Little-Endian (LSB) | Little-Endian (LE) |
| **디스플레이 사양** | 1280 × 720 (16:9, 9.2인치 정전식/조그 DIS) | 800 × 480 (15:9, 7인치 저항막 감압식) |
| **그래픽 가속** | X11 (`libX11.so.6`) + OpenGL ES 2.0 (`libGLESv2.so.2`) | DirectDraw / OMAP PowerVR SGX530 (비활성/GDI) |
| **오디오 백엔드** | ALSA (`libasound.so.2`) | WinCE Waveform Audio (`waveOutOpen`) |
| **미디어 파이프라인** | GStreamer 0.10 (`libgstreamer-0.10.so.0`) | 순정 DirectShow 또는 자체 버퍼 디코더 |
| **UI 프레임워크** | Qt 4.8 (QtQuick 1.0 QML) + MeeGo Touch Core | Win32 GDI C++ (`GDdNavi.exe`, `i30nav.dll`) |
| **프로세스 통신 (IPC)**| D-Bus (`libQtDBus.so.4`), POSIX Pipe, Unix Domain Socket | WinCE Named Event, Mutex, Shared Memory |

---

## 2. ELF 바이너리 세부 특성 (직접 추출 및 확인 증거)

### 2.1 APPNAVI (메인 내비게이션 실행 파일)
- **경로**: `G:\BIN\APPNAVI`
- **파일 크기**: 5,993,104 bytes
- **SHA-256**: `7aa23ee2555c8463c29481db4d1a9e26826c009052d7184ef823f9c2843a7d79`
- **바이너리 헤더**:
  - Class: ELF32
  - Data: 2's complement, little endian
  - Machine: Intel 80386 (0x3)
  - Entry point: `0x815b360`
  - Flags: 0x0
- **동적 라이브러리 의존성 (`DT_NEEDED`)**:
  - `libappframework.so.0` (LGE 전장 애플리케이션 프레임워크)
  - `libmeegotouchcore.so.0`, `libmeegotouchextensions.so.0` (인텔/노키아 MeeGo IVI UI 툴킷)
  - `libQtDeclarative.so.4`, `libQtGui.so.4`, `libQtCore.so.4`, `libQtNetwork.so.4`, `libQtDBus.so.4` (Qt 4.8 런타임)
  - `libGLESv2.so.2` (OpenGL ES 2.0 하드웨어 가속)
  - `libX11.so.6` (X Window System 윈도우 관리자)
  - `libgstreamer-0.10.so.0` (GStreamer 멀티미디어 프레임워크)
  - `libasound.so.2` (ALSA 사운드 아키텍처)
  - `libDHAVN_LogUtil.so.1`, `libDHAVN_QCANController.so.1`, `libDHAVN_gpioCtl.so.1` (제네시스 DH 전용 CAN/GPIO 드라이버)

### 2.2 AppUpgrade (업그레이드 제어 데몬)
- **경로**: `G:\AppUpgrade`
- **파일 크기**: 1,274,224 bytes
- **SHA-256**: `e894b8eca2f534195ea2588e084071b442c41d483c68e2b65990f9c04d07c97f`
- **특성**: `libcrypto.so.10` (OpenSSL 1.0.x 암호 라이브러리) 및 `QtXml`, `QtDBus`를 사용하여 LGE 펌웨어 패키지를 검증하고 IBOX 및 HU 서브시스템에 배포.

---

## 3. 핵심 발견 및 GD13MY 이식에 주는 시사점

1. **아키텍처 불일치 (`x86 Linux` vs `ARM WinCE`)**:
   - "고급형 2세대"라는 명칭 때문에 기존에는 표준형 2세대(WinCE)와 유사한 OS를 공유할 가능성이 일부 제기되었으나, 본 조사를 통해 **제네시스 고급형 2세대는 완전히 다른 Intel Atom 기반 x86 Linux (MeeGo IVI) 시스템**임이 100% 확증되었다 (`VERIFIED`).
   - 따라서 제네시스 고급형 2세대의 순정 바이너리(ELF)를 GD13MY(WinCE ARM)에 **직접 동적 링크하거나 DLL처럼 로드하여 실행하는 것은 바이너리 레벨에서 불가능**하다.
2. **참조 모델로서의 가치**:
   - 직접 실행은 불가능하지만, 현대/기아/제네시스 차량에서 공식 Android Auto가 **AOA 핸드셰이크, 프로토콜 채널 구성, 인증서 공급 및 신뢰 체인(Trust Chain)을 어떻게 구성하였는지**에 대한 프로토콜 규격 및 설계 증거는 동일한 현대 순정 규격을 공유하므로 최고의 리버스 엔지니어링 교본이 된다.
