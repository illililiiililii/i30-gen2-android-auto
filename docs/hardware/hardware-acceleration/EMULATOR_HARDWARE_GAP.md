# 에뮬레이터 하드웨어 간극

| 기능 | 현행 상태 | 다음 근거/작업 |
|---|---|---|
| CPU/NEON | Unicorn 기반 ARM 게스트. 실기기 클럭/명령 실행 시간 재현은 미달. | 정확한 CPU SKU와 동일 코드 실기 벤치 수집. NEON 코드 경로 여부 조사 후 필요한 명령만 가속. |
| SGX GPU | GLES thunk HLE에서 호스트 GL로 렌더. SGX 명령/레지스터 큐가 아님. | 실제 SGX 커맨드/버퍼 자료가 있을 때만 레지스터 모델과 완료/IRQ 계약을 추가. |
| DSS/LCD | 제한된 DISPC 레지스터, RGB565 scanout 및 GFX/VID1 합성. | VSync/프레임 주소 전환/IRQ와 실기 타이밍 계측. |
| IVA2 DSP | 일부 리셋/MMU/RAM 및 상태 접근을 모델링. DSP 실행·펌웨어 로딩은 없음. | 순정 `VID1:` IOCTL 버퍼/반환값과 `DSP1:` 세션을 읽기 전용으로 밝혀야 함. |
| AARE H.264 | h264bsd WinCE 소프트웨어 디코더. | DSP ABI 증명 전에는 소프트웨어 fallback 유지. AARE access-unit 경계와 순정 OEM decoder 입력 계약 비교. |
| DMA | 장치별 제한 모델. 전체 DMA 메모리/IRQ/캐시 일관성 모델 아님. | 장치별 실기 지연·완료 플래그 자료. |
| 저장장치 | 이미지 기반 가상 HSMMC, 일부 PIO/DMA. | 실기 지연 분포 측정, 단일 global throttle 지양. |
| 오디오 | 일부 주변장치/가상 포맷 질의. 순정 코덱/DSP 오디오 아님. | 실기 경로의 장치 소유권과 샘플 레이트/지연 조사. |

이번 WGL 경로는 host OpenGL backend 선택이 추가된 HLE PoC다. 이는 게스트 SGX register fidelity를 구현하지 않는다. 현재 측정 장비에는 실기기 비교 기준도 없으므로 ±5% 목표를 주장할 수 없다.
