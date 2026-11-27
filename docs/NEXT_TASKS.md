# 다음 작업

AARE 프로젝트의 다음 작업은 순정 지도 자원과 순정 영상 출력이다. 실제 차량 기록은 별도 안전 검증 전 금지한다.

1. 순정 WinCE에서 프로세스·스레드 CPU와 힙·핸들 계측을 확보한다. 같은 지도 상태에서 협력적 렌더링 일시 중지 후보를 찾은 뒤 A/B를 비교한다. 지도 종료 C는 독립 투사와 복구 계약이 확보되면 검토한다. [A 기준 및 의존성](testing/AARE_STOCK_RESOURCE_BASELINE.md)
2. UYVY 오버레이 계약을 순정 Lock/Flip/해제와 카메라 선점 경로에서 확인한다. 실제 800×480 지원이 확인되면 선택형 출력과 GDI 폴백을 검증한다. [출력 근거](testing/AARE_STOCK_RESOURCE_BASELINE.md#순정-영상-출력)
3. DSP H.264는 `LibMMCodec`의 `0x117d08` DECINIT 입력 준비 및 `0x111c0c` DECODE 호출자에서 계속 추적한다. 메모리·프레임·완료 계약과 실제 DSP 응답이 확인되면 연결한다. [DSP ABI](hardware/hardware-acceleration/DSP_IOCTL_ABI.md)
4. 물리 USB에서는 새 폰의 AARE 및 등록 인증서 설정 후 첫 영상·터치·분리·재연결을 확인한다. 기존 AOA 상태로 시동할 때의 최초 타임아웃, 자동 실행 옵션 나머지 조합과 실기 카메라·비정상 종료 복구도 남아 있다. [기존 실폰 결과](testing/AARE_PHYSICAL_USB_RECOVERY.md)
5. 실차 설치 전에는 보드 식별, 쓰기 범위, 원본 백업, 독립 복구, 업데이트 실패를 별도 검증한다. [안전](safety/PHASE6_BRICK_RISK_ASSESSMENT.md)

완료 판단은 재현 가능한 시험과 결과를 기준으로 한다. 미검증 항목은 통과 처리하지 않는다.
