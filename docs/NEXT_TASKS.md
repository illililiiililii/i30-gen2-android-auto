# 다음 작업

현재 우선순위는 에뮬레이터와 AARE 기능 개선이다. 실제 펌웨어 기록은 별도 안전 검증 전 금지한다.

1. P0 실폰 자동 실행을 계속 검증한다. 두 옵션 ON의 새 AOA 연결과 분리·재연결이 확인됐다. 새 DLL은 버전 OUT 타임아웃 주입 후 실폰 재연결과 첫 프레임을 통과했다. 기존 AOA가 유지된 시동에서 최초 타임아웃 및 자동 복구를 다시 확인하고, 두 옵션의 나머지 세 조합, 후방카메라, 비정상 종료와 부팅 경고 동의를 검증한다. [실폰 재연결 시험](testing/AARE_PHYSICAL_USB_RECOVERY.md)
2. 티맵 분할 화면: VideoConfiguration 내 Insets 미제공 분석 완료. 향후 AAP UiConfig(Content Insets) 패킷 추가 및 DPI 변경 시험. [티맵 증거](android-auto/aare/TMAP_DISPLAY_EVIDENCE.md).
3. AARE 영상 성능: 8단계 인벤토리 기반 YUV->BGRA 이중 변환 제거 및 DirectDraw 서피스 연결 검토. 순정 DSP 556B 구조체 런타임 프로빙 후 적용. H.264 fast-copy는 ARM fixture에서 개선이 확인됐지만 실기 미검증이므로 `--h264-fast-copy` opt-in으로 유지하고 실폰/실차 동일 계측으로 승격 여부를 판단한다. [DSP 증거](hardware/hardware-acceleration/DSP_INTERFACE_EVIDENCE.md), [파이프라인](android-auto/aare/VIDEO_PIPELINE_INVENTORY.md), [H.264 최적화](android-auto/aare/H264_OPTIMIZATION_RESULTS.md).
4. 실제 지도 성능: 동일 조건 3회 반복 벤치마크 완료 (GDI vs WGL 리드백 병목 입증). [벤치마크](testing/EMULATOR_REPEATED_BENCHMARK.md).
5. 실기 재현: 장치별 실측 기준 확보 후 ±5% 평가. 고성능 모드와 실기 재현 모드를 구분한다.
6. 실차 빌드 전: 보드 식별, 쓰기 범위, 원본 백업, 독립 복구, 업데이트 실패 검증. [안전](safety/PHASE6_BRICK_RISK_ASSESSMENT.md).

완료 판단은 재현 가능한 시험과 결과를 기준으로 한다. 미검증 항목은 통과 처리하지 않는다.
