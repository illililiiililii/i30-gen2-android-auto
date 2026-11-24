# 08_GD13MY_COMPARISON.md: 제네시스 순정 구현과 GD13MY 기존 구현 비교 분석

## 1. 종합 아키텍처 비교표

| 비교 항목 | 제네시스 고급형 2세대 (DHPE 순정) | GD13MY 현재 구현 (`i30-gen2-android-auto`) | 확인된 주요 차이점 | 근거 파일 및 심볼 / 주소 | 직접 호환 여부 | 적용 가능 기술 / 시사점 |
|---|---|---|---|---|---|---|
| **운영체제 및 아키텍처** | Linux (GNU/Linux 2.6.25, MeeGo IVI), Intel x86 (i386) | Windows CE 6.0 (R3), ARM Cortex-A8 (ARMv7-A) | 완전히 다른 OS 및 CPU 아키텍처 (ELF vs PE) | `G:\BIN\APPNAVI`<br>`src/ce/ce_minimal.h` | **불가 (Incompatible)** | 바이너리 직접 이식 불가. 구조적/프로토콜 설계 참조만 가능 |
| **TLS 암호 라이브러리** | OpenSSL 1.0.x / mbedtls 2.x | BearSSL 0.6 | BearSSL이 극도로 가볍고 WinCE 6.0 메모리 제약에 최적 | `extracted/essentials/decrypt/DecryptToFile` (`0x8059c90`)<br>`src/ce/ce_aa_tls.c#L36` | **대체 호환 (BearSSL 유지 권장)** | BearSSL 0.6으로도 TLS 1.2 `0xC02F` 완벽 수행 입증 |
| **TLS 핸드셰이크 역할** | TLS Client (헤드유닛) / TLS Server (폰) | TLS Client (헤드유닛) / TLS Server (폰) | 동일한 표준 AAP 규격 준수 | `05_ANDROID_AUTO_REVERSE_ENGINEERING.md`<br>`src/ce/ce_aa_tls.c#L45` | **일치 (Identical)** | 클라이언트 역할 구현 검증 완료 |
| **암호화 스위트** | `TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256` (`0xC02F`) | `0xC02F` (`BR_TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256`) | 동일 암호화 스위트 사용 | `06_TLS_AUTHENTICATION_ANALYSIS.md`<br>`src/ce/ce_aa_tls.c` | **일치 (Identical)** | 추가 암호화 스위트 불필요 |
| **헤드유닛 인증서 체인** | Google Automotive Link 또는 공인 OEM 서명 체인 탑재 (`genesis.keystore`) | 자체 서명(Self-signed) 테스트 인증서 사용 중 | **실물 폰 연결 시 오류 07 유발의 핵심 원인** | `G:\AppUpgrade` (`:decrypt/genesis.keystore`)<br>`docs/ANDROID_AUTO_AUTH_STATUS.md` | **불일치 (Mismatch)** | Google/OEM 공인 인증서 체인 구조 부합 필요 |
| **USB 드라이버 스택** | Linux USB Core / IBOX 게이트웨이 | WinCE 6.0 Native USB Driver (`usbd.dll` 클라이언트) | Linux 커널 드라이버 vs WinCE 스트림 인터페이스 | `src/ce/ce_aa_usb_client.c#L10` | **OS 종속적** | GD13MY의 WinCE 커스텀 드라이버 유지 필수 |
| **비디오 디코더** | Intel GMA 하드웨어 가속 (GStreamer 0.10) | `h264bsd` 소프트웨어 디코더 (Cortex-A8 최적화) | 1280x720 30/60fps vs 800x480 Baseline | `07_USB_MEDIA_ANALYSIS.md`<br>`src/ce/ce_aa_projection.c#L13` | **대체 호환** | 800x480 해상도에서는 `h264bsd`로도 30fps 충분 |
| **디스플레이 표출 방식** | X11 / OpenGL ES 2.0 텍스처 오버레이 | DirectDraw / Win32 GDI (`GetDCEx`, Z-order 제어) | X11 윈도우 합성 vs WinCE 클립박스/DC | `src/ce/ce_aa_projection.c#L36`<br>`G:\BIN\QML\DHAVN_APPNAVI_MAIN.qml` | **OS 종속적** | `I30_NAVIGATION_PROJECTION_CLASS` 유지 |
| **오디오 서브시스템** | ALSA (`libasound.so.2`) + DSP 믹서 | WinCE Waveform Audio (`waveOutOpen`) | ALSA vs WinCE Wave Audio | `G:\BIN\APPNAVI`<br>`docs/VIDEO_AUDIO_ANALYSIS.md` | **OS 종속적** | PCM 48kHz 스테레오 및 16kHz 안내 분리 |

---

## 2. 세부 소스 파일별 비교 분석

### 2.1 `src/ce/ce_aa_tls.c` vs 제네시스 순정 TLS 구현
- **발견 사항**:
  - GD13MY의 BearSSL 0.6 구현(`src/ce/ce_aa_tls.c`)은 제네시스 순정 구현과 동일하게 TLS 1.2 `0xC02F` 암호 스위트와 AAP Channel 0 패킷 캡슐화(`TLS_FRAME_MAX 0x4200`)를 정확하게 구현하고 있다.
  - 가상 스마트폰 및 Google 공식 DHU 2.0 환경에서는 현재의 `ce_aa_tls.c`로도 완벽히 핸드셰이크가 완결되며 비디오 채널이 개방된다.
  - 실물 폰 연결 시 발생하는 오류 07은 `ce_aa_tls.c`의 암호 엔진 결함이 아니라, 스마트폰 앱 내부의 **PKIX X.509 신뢰 앵커 부재**에 기인한다.

### 2.2 `src/ce/ce_aa_usb_client.c` vs 제네시스 USB AOA
- **발견 사항**:
  - 제네시스 IBOX는 Linux USB 서브시스템을 통해 `18d1:2d00` AOA 모드를 열거한다.
  - GD13MY의 `ce_aa_usb_client.c`는 WinCE 6.0의 `usbd.dll` 구조체(`UsbDevice`, `UsbConfig`, `UsbInterface`, `UsbEndpoint`)를 정확히 준수하여 AOA 디바이스를 Bulk Pipe로 개방하고 있다. USB 하위 계층은 이미 검증을 통과하였다.

### 2.3 `src/ce/ce_aa_projection.c` vs 제네시스 프로젝션 윈도우
- **발견 사항**:
  - 제네시스는 X11 Compositor와 Qt Quick 1.0(1280x720) 환경에서 비디오 싱크를 처리한다.
  - GD13MY는 `GDdNavi.exe`의 Z-Order 및 `GetDCEx`를 통해 순정 내비게이션 화면 위에 800x480 영상을 직접 블리팅(`BitBlt`)하도록 구현되어 있다.
  - 800x480 화면에서는 OMAP3530의 CPU 부하가 720p 대비 약 40% 수준으로 억제되므로 하드웨어 가속 없이도 소프트웨어 디코딩이 안정적으로 동작한다.

---

## 3. 후속 GPT 및 Codex 작업을 위한 핵심 판단 사항

1. **오류 07 (인증서 신뢰 체인) 해결 방안 선택**:
   - **가설 A (공인 헤드유닛 인증서 형식 채택)**:
     - Android Auto 앱의 `TrustManagerImpl`이 수락할 수 있는 발급자(`Google Automotive Link` CA) 및 OID(`clientAuth`)를 충족하는 헤드유닛 인증서 구조를 채택.
   - **가설 B (DHU / 개발자 인증 모드 활용)**:
     - Android 스마트폰의 개발자 설정에서 "알 수 없는 소스" 및 "헤드유닛 인증서 검증 무시" 플래그를 활용하여 순정 인증 우회.
   - **가설 C (인증 우회 프록시 / 가상화 핸드셰이크)**:
     - Android Auto APK의 버전 호환성(구버전 1.7 호환 옵션)을 활용하여 엄격한 PKIX 검증을 회피하는 파라미터 조합 검토.
2. **이식 불가 판정 및 코드 보호**:
   - 제네시스 순정 펌웨어는 x86 Linux 바이너리이므로 바이너리 직접 복제/이식은 절대 시도하지 않는다.
   - 현재 완성도 높은 GD13MY의 BearSSL 0.6 및 `ce_aa_*.c` 소스 코드를 온전히 유지하며 인증서 공급 인터페이스만 보강하는 방향으로 후속 작업을 진행한다.
