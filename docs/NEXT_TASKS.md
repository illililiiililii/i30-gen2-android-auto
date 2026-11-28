# 다음 작업

AARE 프로젝트의 다음 작업은 순정 지도 자원과 순정 영상 출력이다. 실제 차량 기록은 별도 안전 검증 전 금지한다.

1. 순정 WinCE에서 프로세스·스레드 CPU와 힙·핸들 계측을 확보한다. 같은 지도 상태에서 협력적 렌더링 일시 중지 후보를 찾은 뒤 A/B를 비교한다. 지도 종료 C는 독립 투사와 복구 계약이 확보되면 검토한다. [A 기준 및 의존성](testing/AARE_STOCK_RESOURCE_BASELINE.md)
2. HAL이 UYVY를 광고한다. 800×480 표면의 Create·Lock 결과와 Flip 완료, 후방카메라의 점유 반환을 실제 드라이버에서 확인한 뒤 선택형 출력에 연결한다. CE6 호출 계약과 실패 처리는 별도 명세를 따른다. [출력 근거 및 ARM 비교](testing/AARE_STOCK_RESOURCE_BASELINE.md#hal과-arm-성능-대조), [UYVY 구현 명세](android-auto/aare/UYVY_DIRECTDRAW_IMPLEMENTATION_SPEC.md)
3. DSP H.264는 실제 지원 판별 불가다. 순정 `videodev` RVA `0xda38`에서 버전 응답을 캡처하고 오프라인 도구로 해석한다. DSP 측 버전 생성, 타입 6 호출 및 출력 버퍼 수명이 확인되면 연결을 검토한다. 소프트웨어 디코더 대안은 DSP 미지원이 입증되면 진행한다. [DSP 펌웨어 판별](hardware/hardware-acceleration/GD13MY_DSP_PAYLOAD.md)
4. 물리 USB에서는 새 폰의 AARE 및 등록 인증서 설정 후 첫 영상·터치·분리·재연결을 확인한다. 기존 AOA 상태로 시동할 때의 최초 타임아웃, 자동 실행 옵션 나머지 조합과 실기 카메라·비정상 종료 복구도 남아 있다. [기존 실폰 결과](testing/AARE_PHYSICAL_USB_RECOVERY.md)
5. 실차 설치 전에는 보드 식별, 쓰기 범위, 원본 백업, 독립 복구, 업데이트 실패를 별도 검증한다. [안전](safety/PHASE6_BRICK_RISK_ASSESSMENT.md)
6. AARE 1.6.0 설치는 완료됐다. 다음은 사용자가 스마트폰에서 앱을 열고 P12 가져오기와 수신기 지문 승인을 수행한 뒤 첫 영상·터치·분리·재연결을 확인하는 것이다. ADB 점유는 이미 해제했다. [설치 기록](android-auto/aare/AARE_APK_INSTALL_ATTEMPT.md)
7. 티맵 분할 화면은 가설만 정리됐다. AARE 1.6.0 기준 `0x8009`는 HU→phone request, `0x800A`는 phone→HU reply임을 확인했고 GD13MY에는 양쪽 경로가 없다. 원인 확정을 위해 discovery의 margin/density/UiConfig, `0x8009`/`0x800A` 트래픽, GD13MY 실제 safe area를 같은 세션에서 캡처한다. 임의 좌표·DPI·인셋 변경으로 해결을 보고하지 않는다. [방향 재확인](android-auto/aare/TMAP_DISPLAY_UPSTREAM_CROSSCHECK.md)

현재 P0는 2026-11-28 23:52부터 실행 중인 복구 이미지 뷰어에서 AOA 2까지 진행했으나 첫 AAP 버전 요청의 USB I/O 오류로 멈췄다. 폰에는 Google Android Auto의 `통신 오류 16`이 표시됐고 AARE가 세션을 열지 못했다. 정적 분석상 AARE는 AOA model만 보고, Google AA가 같은 accessory를 선점한 것으로 판단된다. `feature/aare-auto-connect`에서 기본 신원을 유지한 채 AOA version만 `2.0`으로 바꾼 이미지를 만든 뒤, 앱 선택 화면에서 AARE + `Always`를 한 번 설정하고 AAP/TLS/첫 프레임을 확인한다. Google AA 강제 종료·비활성화는 최종 흐름에 넣지 않는다. 그 전에는 P1·P2 실폰 캡처를 BLOCKED로 유지한다. [자동 연결 작업 상태](android-auto/aare/AARE_AUTO_CONNECT_STATUS.md), [최신 추적](testing/AARE_PHYSICAL_USB_RECOVERY.md#2026-11-28-재실행-aare-세션과-화면의-오류-16)

완료 판단은 재현 가능한 시험과 결과를 기준으로 한다. 미검증 항목은 통과 처리하지 않는다.
