# GD13MY 하드웨어 인벤토리

기준: 저장소의 .061 펌웨어 정적 자료, 게스트 MMIO 추적 및 이번 호스트 조회. 칩 자료의 기능과 실차에서 확인된 사용은 구분한다.

| 블록 | 판정 | 근거와 에뮬레이터 상태 | 미확인 |
|---|---|---|---|
| CPU | Cortex-A8 계열 ARMv7-A. GD13MY 실장 SKU와 클럭은 미확인. | 순정 CE BIN을 Unicorn Cortex-A8에서 부팅한다. `docs/GD13MY_EMULATION.md`, ROM OEM 메모리 표. | 실물 SKU, OPP/주파수, 부하별 클럭, 실기기 명령 처리량. |
| NEON | OMAP35x 후보 CPU에는 NEON이 포함될 수 있지만, 이 차량의 런타임 사용 확인은 없음. | 현재 Unicorn ARM 경로이며 네이티브 NEON 가속 경로 없음. | 펌웨어 코드의 NEON 명령 유무와 실물 사용. |
| SoC | OMAP35x/OMAP3530급 BSP가 유력한 추정. 제품 SKU 확정 자료는 없음. | TI 주소와 일치하는 MMIO 접근, `dsp_bridge.dll`, SGX530 식별 레지스터 `0x50000014 = 0x00010201`, IVA2 초기화 접근. | 보드 실크/실기 식별, 실장 OMAP SKU. |
| SGX GPU | 순정 지도 앱이 GLES를 호출하고 `srvkm.dll`의 SGX 초기화 대기에 도달함. 실차 GPU 렌더 사용률은 미측정. | 에뮬레이터는 순정 `GDdNavi.exe` GLES 호출 53개를 가상화한다. 게스트의 SGX 레지스터 모델은 revision 읽기뿐이며 GPU 명령/DMA/IRQ는 미구현. | SGX firmware 명령 큐, 메모리 매핑, 인터럽트와 실차 성능. |
| IVA2 / DSP | DSP 장치 경로가 펌웨어에 존재. H.264가 DSP에서 성공했다는 실차 증거는 없음. | `VID1:`/`DSP1:`, `videodev.dll:VID_IOControl`, `dsp_bridge.dll:DSP_IOControl` 분석 기록. 에뮬레이터는 초기화 대기와 RAM/MMIO 일부만 모델링하며 DSP 코어 실행은 하지 않음. | DSP SKU/클럭, 서버 이미지, 코덱 ABI·프로파일·버퍼 계약·점유 중재. |
| DSS / LCD | OMAP DISPC 경로가 순정 WinCE에서 사용됨. | `ddi.dll`의 DSS 레지스터 쓰기, 게스트 RGB565 scanout·GFX/VID1 합성. 에뮬레이터는 `tools/gd13my_display.py`에서 읽기/합성. | 실물 패널 타이밍, VSync/IRQ, 실제 프레임 갱신율과 표시 지연. |
| DMA | OMAP SDMA/DMA4 레지스터 경로가 있음. | 에뮬레이터는 SDMA 모델과 MUSB DMA를 제한적으로 제공하며, MMC 미디어의 DMA 지원 범위는 모듈별로 다름. | 실물 전송 지연/대역폭, 캐시 일관성 및 공유 버퍼. |
| USB | MUSB OTG와 BSP USB function/host 경로가 관측됨. | 가상 MUSB FIFO/DMA/IRQ와 Windows USB 전달을 구현. | 실기기 재열거 후속 시험과 실물 USB 타이밍. |
| 저장장치 | 순정 `moviDisk.dll`은 HSMMC1을 사용. | 읽기 전용 APP/MAP 이미지와 PIO/DMA 일부, 게스트 RAM 기반 가상 매체. 물리 eMMC 실측이 아님. | 실물 eMMC 모델/속도/쓰기 특성. |
| 오디오 | Wave 장치 두 출력/한 입력의 열거 및 포맷 질의는 WinCE에서 통과. SAF7730 관련 레지스트리/드라이버 문자열 확인. | 가상 오디오 레지스터 일부. DSP PCM과 차내 장치 연결은 구현/검증되지 않음. | 실물 오디오 칩, DSP 경로, 믹싱/점유 정책과 지연. |

순정 ROM 메모리 표는 여러 주소 영역의 OS 매핑이지, 각 주변장치가 보드에 실장됐다는 단독 증거는 아니다. 관련 추적과 출처는 [GD13MY 에뮬레이션 기록](../../GD13MY_EMULATION.md), [영상/오디오 분석](../../VIDEO_AUDIO_ANALYSIS.md), [OEM 하드웨어 시험](../../Codex-post-auth-integration/OEM_AND_HARDWARE.md)에 있다.
