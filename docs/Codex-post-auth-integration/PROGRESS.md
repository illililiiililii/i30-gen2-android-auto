# 인증 이후 통합 작업 기록

## 2026-11-25 · 세션 복구

- 로컬 `main`의 터치·USB 통합 `8afc73f`와 두 연구 자료 병합을 복원했다. 원격 `main`의 마지막 조회는 `adee6ca`였다. 초기화나 파일 삭제 없이 소스와 미커밋 시험 도구·문서를 이어서 작업한다.
- 중단된 순정 시험은 `stock-integration/`에 첫 프레임과 터치 응답 프레임, 가상폰 수신 이벤트 30건 이상을 남겼다. 종료 JSON과 후진·분리 단계 기록은 없으며 이전 프로세스도 남아 있지 않았다. 같은 시험 이미지를 `resumed-stock/`으로 다시 실행해 기존 증거를 보존했다.
- ARM 30분 시험은 종료 JSON까지 남겼다. 한 세션에서 27,000프레임 송신·ACK·표시, 종료 후 추적 할당 0건이었다. 별도 최신 ARM 빌드는 5분 및 5/10/30회 재연결을 통과했다. [회귀 결과](REGRESSION_TEST_RESULTS.md)
- Web-ChatGPT 자료의 새 제안 중 Wave 장치 열거·포맷 조회를 순정 격리 환경에서 검증했다. 실폰과 승인된 시험 신원이 필요한 검증을 보류하고, 영상 파라미터 집합·순정 화면 및 USB 시험을 이어간다. [OEM 시험](OEM_AND_HARDWARE.md)

## 2026-11-25 · 재개 후 확인

- `b9d633e`에서 격리 WinCE Wave 장치 질의 도구를 커밋했다. 출력 2개, 입력 1개를 열거하고 장치 0의 조회와 기존 두 PCM 포맷 질의의 성공을 확인했다.
- Python 84개를 재실행했다. 최신 ARM에서 별도 SPS/PPS 메시지, 제어 프레임 교차 처리, 타임스탬프가 붙은 첫 IDR 및 STOP 이후 재협상을 모두 재현했다. 시험기에서 재시작 시 재사용되는 프레임 인덱스에 의존한 검사를 바로잡고, 확인은 ACK·표시 카운터로 진행했다.
- 실폰 연결 가능 상태로 변경됐다. ADB로 SM-G996N(Android 15, Android Auto 18.0.664294)을 확인했다. ADB 서버를 정지한 뒤 최신 ARM USB DLL로 AOA 재열거와 AAP 1.7을 수신했다. 임시 자체 서명 시험 신원과 기존 공개 폰 CA·지문을 사용하는 격리 WinCE 실행을 시작했다.
- 격리 WinCE도 실폰 AAP 1.7을 수신했다. 첫 시험의 TLS 전 등록 실패는 FAT의 8.3 이름 배정에 있었다. 별칭을 분리한 임시 이미지로 재실행한다. [실폰 기록](../Codex-authentication-resolution/REAL_PHONE_TEST_RESULTS.md#11월-25일-후속-실폰-시험)
- REA에서 순정 `VID_IOControl`과 `DSP_IOControl`의 export 및 장치 API import를 대조했다. 기존 `VID1:`과 `DSP1:` 장치 경로를 확인했고 코덱 계약과 동시 점유 정책은 후속 연구에 남겼다. [DSP 근거](OEM_AND_HARDWARE.md#영상-dsp-가능성)
- 별칭을 분리한 WinCE 시험에서 실폰 TLS 1.2, 헤드유닛 리프 및 CertificateVerify 송신을 확인했다. 폰 Conscrypt가 자체 시험 신원의 신뢰 앵커를 찾지 못했다. 인증 완료 이전에 종료됐고 ADB를 복구했다. 순정 가상폰 실행은 독립적으로 후방과 반복 연결을 계속한다. [실폰 결과](../Codex-authentication-resolution/REAL_PHONE_TEST_RESULTS.md#11월-25일-후속-실폰-시험)
- ARM 영상 예외 회귀를 확장했다. 잘못된 IDR NAL과 816픽셀 폭을 각각 거부했고, 이후 출력·영상 ACK 및 추적 할당이 모두 0건임을 확인했다. [ARM 회귀](REGRESSION_TEST_RESULTS.md)
