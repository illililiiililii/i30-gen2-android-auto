# 다음 작업

현재 우선순위는 에뮬레이터와 AARE 기능 개선이다. 실제 펌웨어 기록은 별도 안전 검증 전 금지한다.

1. v8 실폰 자동 연결: 가상 연결 완료 후 실폰 사용자 터치 승인, 첫 프레임, 분리·재연결, 시동 재시작 실폰 확인. [검증 보고](testing/AARE_AUTOSTART_VALIDATION.md).
2. 티맵 분할 화면: VideoConfiguration 내 Insets 미제공 분석 완료. 향후 AAP UiConfig(Content Insets) 패킷 추가 및 DPI 변경 시험. [티맵 증거](android-auto/aare/TMAP_DISPLAY_EVIDENCE.md).
3. AARE 영상 성능: 8단계 인벤토리 기반 YUV->BGRA 이중 변환 제거 및 DirectDraw 서피스 연결 검토. 순정 DSP 556B 구조체 런타임 프로빙 후 적용. [DSP 증거](hardware/hardware-acceleration/DSP_INTERFACE_EVIDENCE.md), [파이프라인](android-auto/aare/VIDEO_PIPELINE_INVENTORY.md).
4. 실제 지도 성능: 동일 조건 3회 반복 벤치마크 완료 (GDI vs WGL 리드백 병목 입증). [벤치마크](testing/EMULATOR_REPEATED_BENCHMARK.md).
5. 실기 재현: 장치별 실측 기준 확보 후 ±5% 평가. 고성능 모드와 실기 재현 모드를 구분한다.
6. 실차 빌드 전: 보드 식별, 쓰기 범위, 원본 백업, 독립 복구, 업데이트 실패 검증. [안전](safety/PHASE6_BRICK_RISK_ASSESSMENT.md).

완료 판단은 재현 가능한 시험과 결과를 기준으로 한다. 미검증 항목은 통과 처리하지 않는다.
