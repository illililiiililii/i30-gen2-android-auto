# 현재 프로젝트 상태 — 2026-11-27

기준: [b912009](https://github.com/illililiiililii/i30-gen2-android-auto/commit/b912009113ee52dd7023c10c0195712fe5ecf621) (guest-native AARE auto projection startup).

대상: GD13MY.KOR.SOP.00.061, Windows CE 6.0 ARM. 정확한 SoC SKU 및 실기 클럭은 미확인. 목표는 순정 내비 내부의 USB AARE 투사이며 호스트는 에뮬레이션 및 USB 전달만 담당한다.

| 항목 | 확인 수준 | 근거 |
|---|---|---|
| 순정 지도 부팅 | 에뮬레이터 | [최신 인계](android-auto/aare/FINAL_HANDOFF.md) |
| AARE 800×480 영상·앱 목록 터치 | 이전 실폰+에뮬레이터 | [실폰 기록](android-auto/aare/REAL_PHONE_TEST_RESULTS.md) |
| USB 자동 실행·부팅 연결 대기 | ARM/API 및 v8 가상폰 첫 프레임 | [진행 기록](android-auto/aare/PROGRESS.md) |
| v8 실폰 자동 연결·재연결 | 미검증; 가상 재연결 픽셀 검증도 미완료 | [최신 인계](android-auto/aare/FINAL_HANDOFF.md) |
| 회귀시험 | 보고상 93개 통과, 1개 skip (원문 표기) | [진행 기록](android-auto/aare/PROGRESS.md) |
| GPU | WGL 선택 경로; readback 때문에 GDI 기본 유지 | [실지도 벤치](hardware/hardware-acceleration/REAL_MAP_BENCHMARK.md) |
| GPTimer | 전체 guest 처리량 +7.7%, 지도 구간 +0.9%; 체감 개선 미입증 | [실지도 벤치](hardware/hardware-acceleration/REAL_MAP_BENCHMARK.md) |
| DSP | VID1/DSP1 IOCTL 코드(0x00220808 등 22개), 556B 입력 버퍼 확인, 상세 ABI 미입증; h264bsd 유지 | [DSP 증거](hardware/hardware-acceleration/DSP_INTERFACE_EVIDENCE.md) |
| 영상 파이프라인 | 8단계 인벤토리 정리(USB-TLS-AAP-H264-색변환-복사-출력), BGRA 변환 병목 식별 | [파이프라인](android-auto/aare/VIDEO_PIPELINE_INVENTORY.md) |
| 자동 연결 | v8 가상/에뮬레이터 독립 옵션·동시 활성화·첫 프레임·분리 복귀 PASS, 실폰 미검증 | [자동 실행 검증](testing/AARE_AUTOSTART_VALIDATION.md) |
| 티맵 분할 | VideoConfiguration/Insets(미제공) 대조 완료, 800x480 DPI 및 UI Insets 영향 분석 | [티맵 증거](android-auto/aare/TMAP_DISPLAY_EVIDENCE.md) |
| 실차 ±5% | 실측 기준 없음 | [가속 인계](hardware/hardware-acceleration/FINAL_HANDOFF.md) |
| 실차 설치 | 승인되지 않음; 복구 경로와 실제 MUSB 동작 미검증 | [실기 점검](android-auto/aare/HARDWARE_READINESS.md), [위험 평가](safety/PHASE6_BRICK_RISK_ASSESSMENT.md) |

이전 순정 Google Android Auto 신뢰 실패와 AARE 등록 인증서 성공은 다른 경로다. 실폰+에뮬레이터 성공은 실차 성공이 아니다. 기존 HARDWARE_READINESS의 자동 연결 설명은 v8 이전 상태이며 최신 자동 실행 상태는 PROGRESS와 FINAL_HANDOFF를 따른다.

사용자 보고: 티맵 분할 화면 차량 아이콘 위치 및 속도계 이상, 체감 성능 부족. 원인 및 수정 여부는 미검증. [다음 작업](NEXT_TASKS.md).
