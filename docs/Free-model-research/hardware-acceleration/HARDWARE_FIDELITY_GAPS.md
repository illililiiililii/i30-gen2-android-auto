# 하드웨어 재현 차이 및 검증 공백

현재 emulator는 OMAP 계열 주요 register bank를 HLE로 모델링하고 stock WinCE 및 GDdNavi를 실행한다. 정상 부팅은 주변장치의 cycle-accurate 동작을 입증하지 않는다.

| 블록 | 현재 근거 | 남은 차이/검증 |
|---|---|---|
| Cortex-A8/NEON | Unicorn ARM 게스트 실행과 native block hook | CPI/cache/TLB/NEON throughput 실기기 비교 없음 |
| SGX/GLES | stock GLES 호출 HLE, WGL host option, software GDI default | GLES conformance 및 실제 GPU frame path 검증 없음; GPU readback이 지도 copy에서 느림 |
| IVA/DSP | reset/clock 상태와 VID1/DSP1 정적 문자열/xref | DSP ioctl, 펌웨어, DMA, decode 완료/오류 계약 미확인 |
| DMA/SDMA | GD13MY HLE transfer 경로 | 실기기 완료 지연/IRQ 순서 및 bus contention 비교 없음 |
| LCD/DSS | RGB565 scanout/plane composition, LCD capture | VSYNC timing 및 panel-level latency 미측정 |
| GPTimer/IRQ | GPTimer bank, 32 kHz virtual clock, IRQ dispatch | native read 선택 PoC는 기능 일치 검증됨, cycle fidelity/실제 timer drift 미검증 |
| eMMC/HSMMC | 읽기 전용 이미지와 stock map 부팅 I/O | 실기기 latency, cache, burst 크기 미측정 |
| MUSB/USB | host USB/HCD guest path | phone/vehicle physical interoperability, sustained throughput 미검증 |
| MICOM/power | UART frame HLE 및 display boot mode | 실차 MICOM timing, ignition/reset handshake 미검증 |

확인되지 않은 주변장치가 요청을 무조건 성공 처리하는 방식은 피한다. 실제 firmware, bootloader, partition table, vehicle storage, MICOM image는 수정하지 않는다. 구현 세부와 수치 측정표는 [하드웨어 충실도 벤치마크](HARDWARE_FIDELITY_BENCHMARK.md).
