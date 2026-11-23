# 하드웨어와 순정 기능

아래 주소는 GD13MY에서 추출한 파일의 오프셋이며, ROM 목차 이름은 `BSP/0002dfc7_kernel` 기준이다.

| 항목 | 근거 | 판정 |
|---|---|---|
| OS | Windows CE BIN의 `nk.exe`, `kernel.dll`, `udevice.exe`, UTF-16LE `0xc4f51f`의 `WINCE600` BSP 경로. `0x1a0c7`의 ARM Thumb CE 커널 배너에는 2008-07-16 컴파일 시각이 있다. `install.exe`의 PE Subsystem 버전은 6.0이다. | 펌웨어는 Windows Embedded CE 6.0 계열. 빌드 번호와 실물에 설치된 버전은 미확인. [CE 6.0 커널 구조](https://learn.microsoft.com/en-us/archive/msdn-magazine/2006/december/mobilize-explore-the-new-features-in-windows-embedded-ce-6-0) |
| CPU | ROMHDR `0x14975cf`에 `0x01c2`. 커널 UTF-16LE `0x5ea7`에 `Cortex-A8`, `0x5ebb`에 `OMAP3530`, `0x5ecf`에 `Texas Instruments`. 부트로더 `0x13a4`·`0x216ec`에도 EVM 3530 표기. | 펌웨어 대상 BSP는 TI OMAP3530/Cortex-A8이고 실행 ABI는 ARM/Thumb little-endian 32비트다. 보드의 실장 SoC와 클럭은 미확인. [TI OMAP3530 데이터시트](https://www.ti.com/lit/ds/symlink/omap3530.pdf) |
| RAM | ROMHDR `ulRAMStart=0x85500000`, `ulRAMFree=0x8551b000`, `ulRAMEnd=0x86800000`. | 초기 OS RAM 범위가 19 MiB다. 별도 RAM 영역, 실제 장착 용량, 순정 앱 가동 시 여유 RAM은 미확인. |
| 저장장치 | `DiskA/A2/A3` 경로, ROM의 `sdmemory.dll`, `exfat.dll`, `moviDisk.dll`, iNAND X-Loader `0x13a4`. 압축된 지도 데이터 약 2.53 GB. | BSP는 iNAND 계열을 가리킨다. 물리 칩과 용량은 미확인. |
| 화면과 그래픽 | BSP `logo`가 800×480, 16 bpp. `ddraw.dll` 이름 `0x4588b3`, `ddi.dll` `0x7d2127`, `libglesv2.dll` `0x163333`. `LibMMCodec.dll`의 DirectDraw 오버레이 로그. | 800×480 리소스와 DirectDraw/OpenGL ES 구성 확인. OMAP3530의 SGX는 데이터시트 사양이다. 실물 패널과 사용 가능한 합성 경로는 미확인. [TI OMAP3530 데이터시트](https://www.ti.com/lit/ds/symlink/omap3530.pdf) |
| H.264 | `LibMMCodec.dll` `0x64c98`에 H.264 TS 파서, `0x5f662`에 H.264/H.263 미지원 분기 메시지, `0x65c58`에 VideoDev 오류 메시지. ROM 목차의 `dsp_bridge.dll` 및 `videodev.dll` 이름은 `0xc44797`, `0xc447a7`. | 디코더 후보가 있다. Android Auto의 H.264 스트림 입력 형식·프로파일·지연·하드웨어 경로는 미검증. H.264 관련 문자열만으로 동작 여부를 확정할 수 없다. |
| USB | `usbd.dll` `0x480a9b`, `usbmsc.dll` `0x3fbeb7`, `musbhcd.dll` `0x574ccb`, `musbotg.dll` `0x5cb3d3`. `LibUSB.dll`에 attach, 마운트, 전원 이벤트. | MUSB 계열 호스트 드라이버 및 USB 저장장치 경로가 있다. 물리 포트의 AOA 제어 전송 및 bulk I/O 접근은 미확인. |
| 오디오와 마이크 | `saf7730wav.dll` `0x5cb3b7`, `waveapi.dll`, APP의 `LibSound.dll`, `GDDVoiceHandler.exe`, ASR 리소스. | OEM 오디오와 음성 처리 구성 확인. PCM 출력/입력 권한과 믹싱, 덕킹, 샘플레이트, 마이크 경로는 벤치 필요. |
| 터치 | `digen_touch.dll` `0xa642eb`, `Touch_Calib.exe` `0xa0dc43`, `uComH_New.exe` `0x2e8b0` 좌표 로그. | 드라이버, 보정 및 이벤트 흔적 확인. 포그라운드 입력 가져오기, 좌표 변환과 복귀 검증 필요. |
| 버튼과 CAN | `uComH_New.exe`의 기능별 프로세스 메시지, 별도 MICOM 이미지 및 `omap2430_micommgr_cdp.dll`. | OEM MCU 연동 후보. CAN의 직접 접속 여부, 프레임과 버튼 이벤트 매핑은 미확인. |

## 순정 기능 통합 지점

- `systemCfg.xml`에서 내비 `GDDNavi.exe`, AV `GDDMedia.exe`, Bluetooth `GDDPcomH.exe`, 음성 `GDDVoiceHandler.exe`, DMB `GDDTdmb.exe` 경로를 확인했다. Bluetooth 패키지에는 `btHAbigP.exe`, `BTDB.dll`도 있다.
- USB 미디어는 OS의 대용량 저장장치 드라이버와 `LibUSB.dll`/AV 앱이 처리하는 구성이 유력하다. Projection 연결 시 OEM 미디어 모드와의 USB 소유권 전환이 필요하다.
- 순정 화면 경로에는 GDI/GWES, DirectDraw와 OpenGL ES 라이브러리가 보인다. APP의 GCF 리소스와 `graphics.dll`, `HMI.dll`은 기존 UI를 분석할 출발점이다.
- ROM `camera.dll` `0x5cb3c7`과 APP `LibVideo.dll`의 `lVideoGetRearViewStatus`(RVA `0x13fc`), `lVideoGetVideoAuthority`(RVA `0x113c`)가 카메라 및 영상 점유 상태의 근거다. 실제 후진 신호, 전환 우선순위 및 파킹 가이드 타이밍은 미확인이다.
- 순정 기능 유지 조건은 후방카메라의 즉시 우선 표시, 안내 음성 및 통화 우선순위 보존, 터치와 차량 버튼의 순정 UI 복귀, 케이블 분리 또는 수신기 장애 후 복구다. 전환 과정은 차량과 분리한 벤치에서 먼저 검증한다.

[Windows CE ROM 근거](../research/evidence/ce-rom.json) · [BSP 문자열과 오프셋](../research/evidence/bsp-markers.json) · [PE 인터페이스](../research/evidence/pe-interfaces.json) · [추출 파일 목록](../research/evidence/gd13my-streams.json)
