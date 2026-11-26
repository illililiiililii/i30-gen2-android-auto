# GD13MY DSP 영상 가속 후속 연구

- 작성 기준: 2026-11-25. 공개 자료 및 GitHub 정적 코드 열람만 수행. GD13MY 실물 DSP 디코딩 실험 **미실시**.
- 판정: **공식 OMAP3530+WinCE 6.0 R3용 DSP H.264 구현은 실재**하지만, GD13MY 순정 `VID1:`/`DSP1:` 경로가 그 코덱을 지원한다는 결론은 도출되지 않는다.
- 프로젝트: https://github.com/illililiiililii/i30-gen2-android-auto

## A. 신규 발견: TI의 실제 Windows CE 제품과 제한

| 항목 | 직접 근거 | GD13MY 의미 |
|---|---|---|
| Windows CE 6.0 R3 OMAP3530/3525 DVSDK 1.11.00.03 | 2011-03-25 TI 릴리스 노트: ARM A8 BSP, XDM 1.0, H.264 **Baseline** encoder/decoder, DirectShow filters, DMAI, WMP 데모 | **WinCE에서 DSP H.264 구현 실재**. 순정 펌웨어에 동일 SDK/코덱이 내장되었는지는 별도 |
| H.264 Main/High | 위 문서: BP/MP/HP는 **DM3730**, OMAP3530은 BP로 구분. 720p는 DM3730만 표기 | OMAP3530 추정 GD13MY에서 Main Profile/720p를 기대해서는 안 됨 |
| Codec Engine WinCE 빌드 | TI 공식 `Codec Engine 2.25` WinCE 예제: `DSPLink`, `CMEM`, `LPM`, `platform.bib/.reg`, `ARMV4I` 드라이버 지정 | 사용 가능하다면 OEM DSP 펌웨어/메모리 분배 및 드라이버가 일치해야 함. 타 기기용 BSP를 덮어쓰면 안 됨 |
| TI 코덱 상세 | **H.264 Baseline Decoder v2.01.007**: XDM `IVIDDEC2`, Level 3.0, 폭 32~864, WVGA/D1, NAL-unit stream, YUV420 planar/YUV422 interleaved, cropping, multiple slices/reference frames, 16의 배수가 아닌 프레임 지원 | 800×480/30 영상 입력·출력 형식 비교의 구체적인 후보. GD13MY 내보낸 `VideoDev` 구조체와 동일함은 미확인 |
| DSP 충돌 문제 | TI DVSDK 알려진 문제: **WMP와 DMAI 동시 실행 불가(DSPLINK 자원 중재자 없음)**, 그래픽 데모 실행 시 프레임레이트 하락, 720p 특별 빌드에서 D1/CIF 디코딩 실패 | 차량 순정 동영상/DMB/내비 등과 DSP 동시 점유를 반드시 조사 |
| 영상 출력 경로 | TI 패치: DirectShow VRFB 회전; GDI 모드에서는 YUV→RGB 변환 때문에 실시간을 만족하지 못하거나 영상이 손상될 수 있음 | 순정 DirectDraw overlay를 우선 조사. h264bsd→BGRA→`StretchDIBits`와 비교할 때 복사/변환 비용 별도 계측 |

**원본:**
1. https://software-dl.ti.com/sdoemb/sdoemb_public_sw/wince_sdk/01_01_00/exports/dvsdk_wince_01_11_00_03_patch_01_release_notes.html (Features, Known Issues, Defects Fixed)
2. https://software-dl.ti.com/dsps/dsps_public_sw/sdo_sb/targetcontent/ce/2_25_00_05/exports/codec_engine_2_25_00_05/examples/build_instructions_wince.html (Configuring WindowsCE BSP Files)
3. https://www.ti.com/tool/download/OMAP35XCODECS
4. https://software-dl.ti.com/dsps/dsps_public_sw/codecs/OMAP35xx/OMAP35xx_latest/H264_Decoder_OMAP3530_Datasheet_2_01_007.pdf (p.1–2)
5. https://software-dl.ti.com/sdoemb/sdoemb_public_sw/wince_sdk/latest_1_x/index_FDS.html (BSP/DVSDK 구성)
6. https://www.farnell.com/datasheets/841878.pdf (MPC Data CE BSP, 2차 기술자료; 사용 조건 확인 필요)

## B. TI 데이터시트 실제 OMAP3530 EVM 측정치

아래 값은 **DSP 초당 백만 사이클(Mcycles/s)** 요구량이며, **fps 자체도, GD13MY의 CPU 사용률도 아니다**. 조건은 TI OMAP3530 EVM, 지정 DSP 메모리 구성, 30fps 프레임 기반 분석이다.

| BP 3.0 시험 스트림 | 평균 | 피크 | 해석 |
|---|---:|---:|---|
| VGA 640×480, 5 Mbps | 262 | 303 | 비트레이트와 복잡도에 따라 요구량 증가 |
| D1 720×480, 2 Mbps | 251 | 263 | SD 해상도 연속 처리 참고점 |
| WVGA 864×480, 1.4 Mbps | 192 | 272 | 800×480보다 큰 폭의 참고점이나 직접 환산 금지 |
| WVGA 854×480, 10 Mbps | 363 | 563 | 높은 비트레이트와 복잡도에 상당히 민감 |

TI는 DSP 동작 예제에서 350 MHz 조건을 언급한다. 854×480/10 Mbps의 피크 요구량은 이 값을 상회하므로 모든 480p 콘텐츠가 무조건 30fps라는 뜻이 아니다. 특히 GD13MY의 DSP 클럭 및 다른 작업의 자원 점유를 알지 못한다. **Main Profile 미지원 문제는 속도 문제가 아니라 비트스트림 기능 문제**이다.

원본: https://software-dl.ti.com/dsps/dsps_public_sw/codecs/OMAP35xx/OMAP35xx_latest/H264_Decoder_OMAP3530_Datasheet_2_01_007.pdf (Table 2, p.2).

## C. 문자열·함수·IOCTL 대조 결과

검색어: `"IOCTL_VDEV_VID_DECINIT"`, `"IOCTL_VDEV_VID_DECODE"`, `"OpenVideoDevSession successful"`, `"mafDecInitVideo"`, `"H264(H263) Codec is not support !"`, `"LibMMCodec.dll"`, 그리고 TI `VideoDev`, `XDM 1.0`, `Codec Engine`, `DSPLink` 변형. **공개 검색에서 동일 문자열의 신뢰할 만한 소스 구현을 찾지 못했다.** TI 문서는 일반 Codec Engine/XDM 인터페이스이며 OEM `IOCTL_VDEV_*` 구현의 원본으로 입증되지 않는다.

GD13MY 자체 기존 확인 값(이번에 바이너리를 재분석한 것은 아님):

| GD13MY 단서 | 위치 | 의미와 주의 |
|---|---|---|
| `IOCTL_VDEV_VID_DECINIT`, `IOCTL_VDEV_VID_DECODE` | `LibMMCodec.dll` 문자열 | VideoDev를 통한 디코더 제어 **후보**. 정확한 IOCTL 숫자/구조체는 바이너리 추적 필요 |
| `OpenVideoDevSession successful`, `mafDecInitVideo` | `LibMMCodec.dll` | OEM 미디어 프레임워크 영상 세션. TI `IVIDDEC2`와 동일하다고 볼 수 없음 |
| `DSP Version`, `DSP Resizing` | `LibMMCodec.dll` | DSP 경로 존재 증거, **H.264 지원 증거 아님** |
| `H264(H263) Codec is not support !` | `LibMMCodec.dll` | 특정 분기에서 지원 불가를 알리는 문자열. 실행 조건을 모르면 H.264 전체 미지원/지원 모두 단정 불가 |
| `VID1:` 및 `DSP1:` | `LibMMCodec.dll`, ROM `videodev.dll` | 기존 자료의 장치명 정적 근거. `VID_IOControl`, `DSP_IOControl` 인터페이스 중점 분석 |
| `lVideoShowOverlay`, `DirectDrawCreate` | `LibVideo.dll`, `LibMMCodec.dll` | 영상 최종 출력 경로 조사 지점 |

프로젝트 증거: https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/VIDEO_AUDIO_ANALYSIS.md 및 https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/OpenCode-search/genesis-premium-gen2/14_OMAP3530_ACCELERATION_RESEARCH.md

### C-1. 기존 코드와의 간극

현재 `src/ce/ce_aa_video.c`의 `i30_video_push()`는 `h264bsdDecode()`를 사용하고, `i30_video_open()`이 소프트웨어 디코더를 생성한다. 프레임은 BGRA로 변환한 뒤 `StretchDIBits`로 표시한다. DSP/`VID1:` 호출은 이 경로에 존재하지 않는다. Baseline(`profile_idc=66`)만 수락하고 디코드 크기도 800×480으로 제한한다. **DSP가 나중에 이용 가능하더라도 바로 교체할 수 있는 인터페이스는 아직 없음.**

코드: https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_video.c

## D. 현실적인 확인 경로와 결정 지점

1. **정적 분석(비파괴, P1):** OEM `LibMMCodec.dll`의 `CreateFileW("VID1:")` → `DeviceIoControl` → `videodev.dll:VID_IOControl` → `DSP1:` 및 `dsp_bridge.dll:DSP_IOControl`를 *실제 호출 관계*로 추적. IOCTL 숫자, 버퍼 구조, 세션 상태, DSP firmware/image 파일명, H.264 거부 문자열에 도달하는 조건을 기록. 먼저 이미 추출된 코드/증거를 재사용.
2. **선행 조건 검사(P1):** 실기기/에뮬레이터 환경의 `VID1:`/`DSP1:` 존재, 코덱 등록, 고정 DSP 메모리/CMEM 구성, 사용 가능 자원 확인. 커널에 새 드라이버를 주입하지 않음.
3. **소프트웨어 성능 기준선(P1):** 800×480 Annex-B BP 30fps, 다양한 비트레이트/슬라이스로 `h264bsd` 디코드 시간, 변환+GDI 표시 시간, 프레임 손실, 피크 메모리 각각 측정. 표시와 디코드 성능을 한 숫자로 합치지 않음.
4. **DSP 별도 격리 시험(P2, 가능할 때):** OEM 플레이어에서 합법적인 테스트 H.264 클립 재생. H.264 Baseline/Main, 800×480, 720×480, 640×480의 결과 및 `DSP1:` 활성 근거 확인. 정규 코덱 API가 판명되기 전 AA 바이트를 `DeviceIoControl`에 바로 넣지 않음.
5. **Go/No-Go:** SDK의 코덱 데이터시트와 OEM의 지원 코덱·ABI, 디코더 입력 규격, DRM/인증 및 라이선스 조건, CPU/GDI 성능과 자원 충돌까지 일치할 때만 DSP 연결 스파이크 작성.

**재실험 금지:** 기존 가상폰에서 이미 확인된 빨강/초록 프레임 렌더·TLS·USB 재연결 결과를 DSP 영상 가속 성공 근거로 재사용하지 않는다. 실제 DSP 동작 증거가 필요하다.

## E. Windows CE 서드파티 구현 및 DSP 서버 파일 형태 (추가 발견)

- TI Codec Engine의 **WinCE 실제 원격 실행 예제**는 ARM의 `app_remote_wince.exe`, `remote.cfg`, DSP 서버 `all.x64P`를 명시한다. 이와 유사한 DSP 서버 등록 및 런타임 동적 로딩 흔적을 GD13MY에서 **읽기 전용으로** 찾아볼 근거가 생겼다. 단, OEM이 TI Codec Engine 형식을 그대로 사용할 필요는 없으므로 `all.x64P` 파일이 없다는 이유만으로 DSP H.264 부재를 확정해서는 안 된다. 원본: https://software-dl.ti.com/dsps/dsps_public_sw/sdo_sb/targetcontent/ce/2_25_00_05/exports/codec_engine_2_25_00_05/examples/build_instructions_wince.html (Running image1_copy)
- 현장 개발자 사례(AXONIM, **OMAP-L138**, OMAP3530과 다른 칩): WinCE 6.0의 DirectShow → `TIMM.DLL` → VISA/Codec Engine → DSP 계층을 설명하고, **720×576 MPEG4 30fps, ARM CPU 약 30%**의 사례를 보고한다. 이는 WinCE에서 DSP 미디어 파이프라인이 작동할 수 있다는 유추 근거이나 **OMAP3530 H.264 또는 GD13MY 성능 수치가 아님**. 원본: https://www.embedded.com/porting-embedded-windows-ce-6-0-r2-to-the-omap-l138-part-3/
- Advantech PCM-C3530/3503 개발 보드 매뉴얼의 제품 사양은 OMAP3530 C64x+ DSP 및 WinCE 6.0, H.264 처리 지원을 제시한다. OEM GD13MY 구현과는 별개이다. 원본: https://advdownload.advantech.com/productfile/Downloadfile4/1-J4IQBC/PCM-C3500_Series_Eva.Kit_User_Manual_Ed.1.pdf
- 중국어(解码), 일본어(デコード), 러시아어(декодирование), 한국어 검색어를 추가 사용했으나 **동일 OEM IOCTL 구현 신규 발견 없음**. 이러한 언어 검색에서도 TI 일반 BSP/코덱 자료가 주로 반복됨.

## F. 제한 및 발견 없음

- 오픈소스에서 GD13MY OEM `IOCTL_VDEV_*`, `mafDecInitVideo`, `LibMMCodec.dll`과 **동일한 구현 발견 없음**.
- GD13MY에 TI DVSDK 1.11 코덱 바이너리가 들어 있다는 증거 없음.
- GD13MY 실물 SoC SKU, DSP 클럭, 800×480/30 실제 측정치 없음.
- 자동차 내비게이션에서 이 **동일 DLL/IOCTL**을 재사용한 공개 사례 확인 못함.
- Linux DVSDK는 Codec Engine/XDM 구조를 이해하는 데만 참고한다. WinCE 커널 드라이버/ARM-DSP IPC를 그대로 이식할 수 없다.
