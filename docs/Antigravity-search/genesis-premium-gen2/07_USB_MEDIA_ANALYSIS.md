# 07_USB_MEDIA_ANALYSIS.md: USB 및 미디어 처리 구조 분석

## 1. USB 통신 및 AOA (Android Open Accessory) 아키텍처

| 항목 | 제네시스 고급형 2세대 (DHPE) | GD13MY 표준형 2세대 (i30) |
|---|---|---|
| **USB 역할** | USB Host (USB 2.0 High-Speed, 480 Mbps) | USB Host (OMAP3530 OTG/Host, 480 Mbps) |
| **AOA 식별자** | `18d1:2d00` (AOA) / `18d1:2d01` (AOA + ADB) | `18d1:2d00` / `18d1:2d01` |
| **AOA 요청 명령** | Control Transfer (Request: 51, 52, 53) | `ce_aa_usb_client.c` 내 AOA 제어 전송 |
| **드라이버 스택** | Linux USB Core / usbfs / IBOX 커널 모듈 | WinCE 6.0 `USBOTG.dll` / `USBD.dll` 커스텀 드라이버 |
| **I/O 버퍼 구조** | 링 버퍼(Ring Buffer) 기반 비동기 대량 전송 | 정적 16KB ~ 64KB 고정 버퍼 비동기 Bulk Pipe |
| **Keepalive** | Channel 0 Ping/Pong (타임아웃 주기: 2.5초 ~ 5초) | `ce_aa_projection.c` Ping/Pong 구현 |

---

## 2. AAP 채널 다중화 (Channel Multiplexing) 규격

Android Auto는 단일 USB Bulk In/Out 파이프 상에서 1바이트 채널 ID와 프레임 헤더를 통해 멀티채널을 시분할 다중화한다.

```
[AAP 프레임 헤더 (4~8 바이트)]
  Byte 0   : Channel ID (0 ~ 4)
  Byte 1   : Flags (0x01: First, 0x02: Last, 0x08: Encrypted)
  Byte 2~3 : Payload Length (Big-Endian)
  [Optional]: Extended Header / Sequence Number
  [Payload]: 암호화된 TLS 레코드 또는 미디어 페이로드
```

| 채널 ID | 용도 | 데이터 형식 및 사양 | 제네시스 처리 방식 | GD13MY 대응 방식 |
|---|---|---|---|---|
| **Channel 0** | **제어 및 세션 관리** | AAP 제어 메시지, TLS 1.2 핸드셰이크, Ping/Pong | IBOX 프로토콜 코어 | `ce_aa_tls.c`, `ce_aa_projection.c` |
| **Channel 1** | **마이크 (Audio In)** | PCM 16kHz, 16-bit Mono | ALSA Capture (`libasound`) | WinCE `waveInOpen` (준비) |
| **Channel 2** | **미디어/안내 오디오** | PCM 48kHz (미디어), 16kHz (안내) Stereo | ALSA Playback / DSP 믹서 | WinCE `waveOutOpen` 버퍼링 |
| **Channel 3** | **영상 스트림 (Video)** | H.264 (AVC) Baseline / Main Profile | GStreamer 0.10 + OpenGL ES 2.0 (1280x720) | `h264bsd` 소프트웨어 디코더 (800x480) |
| **Channel 4** | **터치/버튼 입력** | Touch Event (ABS_X, ABS_Y, Down/Up), 조그휠 | X11 / Qt 이벤트 직렬화 | Win32 `WM_LBUTTONDOWN` / Touch 좌표 변환 |

---

## 3. 영상 디코딩 및 디스플레이 파이프라인 비교

### 3.1 제네시스 순정 구현
- **해상도**: 1280 × 720 (720p, 30/60 fps)
- **비디오 파이프라인**:
  `IBOX (Channel 3 H.264 수신)` -> `IPC` -> `HU GStreamer 0.10` -> `Intel GMA 하드웨어 가속 디코더` -> `OpenGL ES 2.0 텍스처` -> `X11 Compositor` -> `LCD 패널`
- **화면 우선순위 처리**:
  - 후방카메라(RVC): 하드웨어 비디오 스위처 또는 FPGA(`V2.63`)를 통해 OS보다 최우선으로 LCD 오버레이.
  - 순정 내비/공조 팝업: D-Bus 신호로 수신된 팝업 UI를 최상위 X11 레이어로 표출.

### 3.2 GD13MY 순정 이식 구현
- **해상도**: 800 × 480 (WVGA)
- **비디오 파이프라인**:
  `AOA Bulk In (Channel 3)` -> `BearSSL 복호화` -> `h264bsd ARM 최적화 소프트웨어 디코더` -> `RGB565 / YUV 변환` -> `DirectDraw 프레임버퍼 (GetDCEx)` -> `LCD 패널`
- **CPU 부하 분석**:
  - TI OMAP3530 (ARM Cortex-A8 600~720MHz) 환경에서 800x480 30fps H.264 소프트웨어 디코딩 시 약 40~55% CPU 점유 예상.
  - 제네시스 720p 스트림에 비해 800x480 픽셀 수는 절반 이하(384,000 vs 921,600 pixels)이므로 `h264bsd`로도 부드러운 재생이 가능하다.

---

## 4. 오디오 및 입력 처리 구조

1. **오디오 포커스 (Audio Focus) 제어**:
   - Android Auto는 내비게이션 음성 안내 시 음악 볼륨을 자동으로 줄이는 Ducking 기능을 지원한다.
   - 제네시스는 하드웨어 DSP 믹서를 통해 채널별 게인을 제어하며, GD13MY에서는 WinCE 사운드 믹서 또는 소프트웨어 PCM 스케일링으로 구현 가능하다.
2. **터치 좌표 보정 및 스케일링**:
   - 제네시스는 1280x720 정전식 터치스크린과 센터 콘솔 통합 조그 다이얼(DIS) 이벤트를 AAP 입력 포맷으로 변환한다.
   - GD13MY는 800x480 저항막 감압식 터치 패널을 사용하므로, 터치 지연 보정 및 클릭 해제(Release) 이벤트의 확실한 전달이 핵심 품질 요소이다.
