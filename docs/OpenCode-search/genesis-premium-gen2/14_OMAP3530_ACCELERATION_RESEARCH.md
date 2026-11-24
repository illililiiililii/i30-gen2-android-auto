# 14. OMAP3530 영상 가속 조사 (GD13MY)

작성일: 2026-11-24
우선순위: 사용자 지시에 따라 **가장 낮음**. 인증/프로토콜 작업을 막지 않는다.
범위: i30 GD13MY(WinCE/ARM). Genesis G80(DHPE)에는 적용되지 않는다(플랫폼 다름).

---

## 1. 결론 요약

1. GD13MY 펌웨어는 **OMAP3430/3530 계열 BSP**를 사용한다. `evm3530_bus.pdb`와 `omap3430_*` 드라이버 PDB 이름이 커널에 직접 들어 있다. `[확인됨]`
2. `LibMMCodec.dll`은 **DSP/VideoDev 커널 드라이버에 IOCTL로 비디오 디코드를 위임**한다. 소프트웨어 디코더만 있는 플랫폼이 아니다. `[확인됨]`
3. 그러나 그 경로가 **Android Auto의 H.264 스트림을 실제로 디코드할 수 있는지는 미확인**이다. 코드 어딘가에 `H264(H263) Codec is not support !` 문자열도 있다. `[미검증 가설]`
4. 따라서 "h264bsd 30fps면 충분하다"는 이전 가정은 근거가 없다. **측정 전에는 어떤 결론도 확정하지 않는다.** `[미검증 가설]`
5. Antigravity의 "Intel GMA 하드웨어 디코드"는 G80에 대한 주장이며, GD13MY에는 해당되지 않는다. G80 바이너리도 이번에 확보하지 못했다. `[미검증 가설]`

---

## 2. 펌웨어 직접 증거

### 2.1 BSP: OMAP3430/3530

파일: `firmware/extracted/GD13MY/BSP/0002dfc7_kernel` (21,599,691 bytes)

문자열:

```
omap3430_dma.pdb
omap3430_spi.pdb
omap3430_rtc.pdb
omap3430_mcbsp.pdb
omap3430_uart.pdb
omap3430_quart.pdb
omap3430_musbotg.pdb
omap3430_musbhcd.pdb
evm3530_bus.pdb
EVM3530-
```

해석:

- TI OMAP BSP는 OMAP3430과 OMAP3530에 같은 드라이버 이름(`omap3430_*`)을 쓴다.
- `evm3530_bus.pdb`는 **3530 EVM 보드 지원**이 포함되었다는 뜻이다.
- 따라서 "OMAP3530 계열"이라는 기존 가설은 `[확인됨]`으로 승격한다. 정확한 SKU(3530 vs 3430)는 아직 단정하지 않는다.

### 2.2 LibMMCodec: DSP/VideoDev 경로

파일: `firmware/extracted/GD13MY/APP/002c98d9_LibMMCodec.dll` (580,608 bytes)

확인된 문자열(유니코드):

```
VideoReload: IOCTL_VDEV_VID_DECINIT
VideoReload: IOCTL_VDEV_VID_DECODE
VideoReload: IOCTL_VDEV_VID_ENCINIT
VideoReload: IOCTL_VDEV_IMG_QUERYINFO
VideoReload: IOCTL_VDEV_IMG_DECINIT
VideoReload: IOCTL_VDEV_AUD_DECINIT
-DecodeVideoCleanup IOCTL_VDEV_VID_DEC_DEINIT FAILED
DSP Version = %d.%d.%d VE=%08X VD=%08X AE=%08X AD=%08X
DSP Version FAILED
OpenVideoDevSession successful
mafDecInitVideo: width=%d height=%d
mafDecode PICTURE: DSP Resizing (%d, %d) to (%d, %d)
mafSelfServeM2DGetVideoFrame: failed on MAF video queue
[H264(H263) Codec is not support !]
```

임포트: `COREDLL.dll`, `DDRAW.dll`, `LibComm.dll` (PE Machine `0x1C2` = ARM Thumb-2 mixed).

해석:

- `IOCTL_VDEV_*`는 WinCE 스트림 드라이버(`VideoDev`)와 통신하는 이름이다.
- `VE/VD/AE/AD`는 Video Encode/Decode, Audio Encode/Decode 블록을 가리킨다.
- `MAF`(Mozen 계열 미디어 프레임워크) 큐를 통해 DSP 프레임을 받는다.
- `DDRAW` overlay/back buffer로 화면에 표시한다.
- 즉 **하드웨어(또는 DSP 펌웨어) 디코드 경로가 존재**한다.

### 2.3 LibVideo / LibUSB

- `LibVideo.dll` (40,960 bytes): `lVideoShowOverlay` 등 얇은 래퍼. `LibMMCodec.dll`을 임포트한다.
- `LibUSB.dll` (139,264 bytes): `lUSBFB*`(파일 브라우징), `lUSBmm*`(미디어 재생)만 있다. **AOA/Android 액세서리 문자열이 없다.**
  - 따라서 "IBOX/LibUSB가 AOA를 처리한다"는 가설은 GD13MY에서는 성립하지 않는다. AOA는 별도 구현이 필요하다.

---

## 3. OMAP3530 하드웨어 사실 (외부 자료)

| 항목 | 내용 | 출처 |
| --- | --- | --- |
| CPU | ARM Cortex-A8, 최대 720 MHz | TI OMAP3530 데이터시트 |
| DSP | TMS320C64x+ (IVA2.2) | TI |
| GPU | PowerVR SGX530 (2D/3D) | TI/Variscite |
| 비디오 | OMAP3525/3530에 **전용 비디오 하드웨어 가속기**, 720p H.264 encode/decode | TI 마케팅/데이터시트 |
| OS | Linux, Windows CE 지원 | TI |
| 메모리 | LPDDR/DDR2, 외부 | 보드별 |

주의:

- OMAP3430과 3530은 같은 계열이지만, 3530/3525에 비디오 가속 블록이 추가된다. GD13MY의 정확한 SKU는 아직 미확정이다.
- "720p decode"는 프로파일/비트레이트/컨테이너에 따라 다르다. TI의 주장은 이상적 조건이다.

---

## 4. Android Auto 비디오 요구사항

- phone은 HU로 H.264 비디오를 보낸다(해상도/프레임레이트/비트레이트는 협상).
- 일반적으로 480p/720p, 30fps, 1~3 Mbps 범위.
- HU는 디코드 후 화면에 표시하고, 터치/키 입력을 역방향으로 보낸다.
- 프로토콜/채널 구조는 11번 문서 참조.

**미확인:** GD13MY의 VideoDev가 어떤 H.264 프로파일을 지원하는지, AAP가 요구하는 프로파일과 일치하는지. `[GPT 분석 필요]`

---

## 5. 구현 옵션

### 옵션 A: 기존 VideoDev/DSP 경로 재사용

- 장점: 전력/CPU 효율, 이미 검증된 드라이버.
- 단점: WinCE 커널 드라이버 인터페이스가 문서화되지 않음. `CreateFile("VDEV...")` 디바이스 이름과 IOCTL 코드, 입력 버퍼 포맷을 리버싱해야 한다.
- 필요 작업:
  1. `LibMMCodec.dll`에서 `CreateFile`/`DeviceIoControl` 인자 추적.
  2. 디바이스 이름 확인(예: `VDEV1:`, `DSP1:` 등).
  3. H.264 Annex-B/AVCC 입력 포맷과 출력 YUV/RGB 포맷 확인.
  4. AAP 디코더와 연결하는 얇은 계층 작성.
- 리스크: 높음. 드라이버가 특정 컨테이너/코덱만 받을 수 있다.

### 옵션 B: ARM 소프트웨어 디코더

- 후보: h264bsd(Android 오픈소스, baseline), OpenH264(Cisco, BSD), FFmpeg(h264).
- 장점: 문서/소스가 있고 이식성이 좋다. WinCE ARM 빌드 가능.
- 단점: Cortex-A8 720MHz에서 720p 30fps는 빠듯하다. 480p는 가능성이 있다.
- 필요 작업: 실제 기기에서 fps/CPU/발열 측정. 최적화(NEON) 여부 확인.
- 리스크: 중간. 측정 없이 "충분하다"고 말할 수 없다.

### 옵션 C: 하이브리드/축소

- AAP 비디오 해상도를 480p로 낮춘다(phone이 수락하는 경우).
- 프레임 드롭/스킵을 허용한다.
- 오디오/입력/내비게이션 텍스트를 먼저 구현하고, 비디오는 후순위로 둔다.
- 리스크: 낮음. 사용자 경험은 떨어짐.

---

## 6. 실험 계획 (우선순위 낮음, 그러나 재현 가능하게)

### E1. 기존 플레이어로 디코드 성능 측정

- USB에 H.264 480p/720p 30fps 샘플을 넣고 기본 미디어 플레이어로 재생.
- 측정: 끊김 여부, CPU 점유, 발열, 오디오 싱크.
- 이 실험만으로 "하드웨어 경로가 H.264를 지원하는지" 대략 판별 가능.

### E2. VideoDev 인터페이스 추적

- `LibMMCodec.dll`의 `CreateFileW`/`DeviceIoControl` 호출을 정적 분석.
- 디바이스 이름, IOCTL 번호, 입출력 구조체 크기 확인.
- `IOCTL_VDEV_VID_DECODE`의 입력이 Annex-B인지 AVCC인지 확인.

### E3. DSP 펌웨어 존재 확인

- `\Windows`, `\ResidentFlash`, BSP에 DSP 코드 이미지가 있는지 확인.
- 없으면 옵션 A는 불가능하다.

### E4. 소프트웨어 디코더 벤치마크

- h264bsd/OpenH264를 WinCE ARM으로 크로스 컴파일.
- 480p/720p 샘플로 fps 측정.
- 목표: 480p 30fps 이상, 720p 24fps 이상이면 옵션 B 현실적.

### E5. AAP 비디오 협상

- phone에 요청하는 해상도/프레임레이트를 낮춰 협상이 되는지 확인.
- 프로토콜 필드(`VideoConfig`)는 11번 문서의 AAP 정의 참조.

---

## 7. Antigravity/ChatGPT 주장 정리

| 주장 | 판정 |
| --- | --- |
| GD13MY는 OMAP3530 계열 | `[확인됨]` (BSP) |
| 하드웨어 디코드 경로가 있다 | `[확인됨]` (IOCTL/DSP) |
| H.264를 실제로 디코드할 수 있다 | `[미검증 가설]` |
| h264bsd 30fps로 충분 | `[미검증 가설]` (측정 없음) |
| Intel GMA 하드웨어 디코드 | `[미검증 가설]` (G80 주장, GD13MY 무관) |
| IBOX가 AOA 처리 | `[미검증 가설]` (GD13MY LibUSB는 미디어 전용) |

---

## 8. 권고

1. **지금은 비디오 가속에 투자하지 않는다.** 인증/프로토콜/입력이 먼저다.
2. 비디오가 필요해지는 시점에 E1(기존 플레이어 측정) → E2(인터페이스 추적) → E4(소프트웨어 벤치마크) 순서로 진행한다.
3. 옵션 A는 드라이버 리버싱 리스크가 크므로, E1/E3에서 가능성이 확인되기 전에는 설계에 넣지 않는다.
4. 어떤 경우에도 펌웨어 플래시/파티션 쓰기는 하지 않는다. 실험은 별도 이미지/복제 기기에서만.
