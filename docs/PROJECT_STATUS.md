# 현재 프로젝트 상태 — 2026-11-27

v8 게스트 자동 실행은 `b912009`에서 추가됐다. 실폰 USB 시험의 소스 기준은 `f004f6f`다.

대상: GD13MY.KOR.SOP.00.061, Windows CE 6.0 ARM. 정확한 SoC SKU 및 실기 클럭은 미확인. 목표는 순정 내비 내부의 USB AARE 투사이며 호스트는 에뮬레이션 및 USB 전달만 담당한다.

| 항목 | 확인 수준 | 근거 |
|---|---|---|
| 순정 지도 부팅 | 에뮬레이터 | [최신 인계](android-auto/aare/FINAL_HANDOFF.md) |
| AARE 800×480 영상·앱 목록 터치 | 이전 실폰+에뮬레이터 | [실폰 기록](android-auto/aare/REAL_PHONE_TEST_RESULTS.md) |
| USB 자동 실행·부팅 연결 대기 | ARM/API 및 v8 가상폰 첫 프레임 | [진행 기록](android-auto/aare/PROGRESS.md) |
| v8 실폰 자동 연결·재연결 | 두 옵션 ON에서 AOA 2, AAP 1.7, 상호 TLS, 첫 프레임, 터치, 순정 지도 복귀 및 재연결 확인. 새 USB DLL은 버전 OUT 실패 주입 뒤 실제 폰 재연결 및 첫 프레임까지 확인했다. 기존 AOA를 유지한 재시동의 첫 OUT 타임아웃은 남아 있다 | [실폰 재연결 시험](testing/AARE_PHYSICAL_USB_RECOVERY.md) |
| 회귀시험 | Python 97개 통과, 환경 조건 1개 건너뜀. ARM USB/TLS/투사 fixture 통과 | [실폰 재연결 시험](testing/AARE_PHYSICAL_USB_RECOVERY.md) |
| GPU | WGL 선택 경로; readback 때문에 GDI 기본 유지 | [실지도 벤치](hardware/hardware-acceleration/REAL_MAP_BENCHMARK.md) |
| GPTimer | 전체 guest 처리량 +7.7%, 지도 구간 +0.9%; 체감 개선 미입증 | [실지도 벤치](hardware/hardware-acceleration/REAL_MAP_BENCHMARK.md) |
| 순정 지도 리소스 | 지도와 투사 창은 기존 구조에서 같은 프로세스에 의존한다. 가상폰 투사 구간 지도 swap/복사 0~6회, GPS 재설정 로그 지속, 분리 후 순정 메뉴 응답 확인 | [A 기준 측정](testing/AARE_STOCK_RESOURCE_BASELINE.md) |
| 순정 영상 출력 | 순정 UYVY 생성·해제 흐름 확인, ARM에서 h264bsd→UYVY 메모리 스테이징 및 BGRA 폴백 검증, 실제 표면 점유 미검증 | [영상 출력](testing/AARE_STOCK_RESOURCE_BASELINE.md#순정-영상-출력) |
| DSP | DECINIT·DECODE의 556B 입력과 4B 상태, H.264 타입 6의 DSP 버전 응답 기능 비트와 일부 버퍼 필드 확인. 하드웨어 디코딩 미검증 | [DSP ABI](hardware/hardware-acceleration/DSP_IOCTL_ABI.md) |
| 영상 파이프라인 | 8단계 인벤토리 정리(USB-TLS-AAP-H264-색변환-복사-출력), BGRA 변환 병목 식별 | [파이프라인](android-auto/aare/VIDEO_PIPELINE_INVENTORY.md) |
| H.264 디코더 최적화 | ARM fixture에서 fast-copy 후보 반복 개선 확인, 실기 미검증으로 opt-in 유지; codegen/NEON 기본값 변경 없음 | [최적화 결과](android-auto/aare/H264_OPTIMIZATION_RESULTS.md) |
| 자동 실행 옵션별 실폰 동작 | 두 옵션 ON 검증. USB만 ON, 부팅만 ON, 모두 OFF, 후방카메라 선점 및 비정상 종료 복구 미검증. 약 2초 자동 동의는 v8에 없음 | [실폰 재연결 시험](testing/AARE_PHYSICAL_USB_RECOVERY.md) |
| 티맵 분할 | VideoConfiguration/Insets(미제공) 대조 완료, 800x480 DPI 및 UI Insets 영향 분석 | [티맵 증거](android-auto/aare/TMAP_DISPLAY_EVIDENCE.md) |
| 실차 ±5% | 실측 기준 없음 | [가속 인계](hardware/hardware-acceleration/FINAL_HANDOFF.md) |
| 실차 설치 | 승인되지 않음; 복구 경로와 실제 MUSB 동작 미검증 | [실기 점검](android-auto/aare/HARDWARE_READINESS.md), [위험 평가](safety/PHASE6_BRICK_RISK_ASSESSMENT.md) |

이전 순정 Google Android Auto 신뢰 실패와 AARE 등록 인증서 성공은 다른 경로다. 실폰+에뮬레이터 성공은 실차 성공이 아니다. 기존 HARDWARE_READINESS의 자동 연결 설명은 v8 이전 상태이며 최신 자동 실행 상태는 PROGRESS와 FINAL_HANDOFF를 따른다.

사용자 보고: 티맵 분할 화면 차량 아이콘 위치 및 속도계 이상, 체감 성능 부족. 원인 및 수정 여부는 미검증. [다음 작업](NEXT_TASKS.md).
