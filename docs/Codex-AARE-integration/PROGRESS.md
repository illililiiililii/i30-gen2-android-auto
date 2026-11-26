# GD13MY AARE 통합

기준 `5830cad`에서 시작했다. 로컬 `main`과 원격 `main`이 일치했고 작업 트리에 변경 사항이 없었다. 순정 .061 펌웨어, 이전 실폰 로그와 기존 DiskA를 보존하고 새 시험 DiskA를 `build/aare-integration/`에 만들었다.

- AARE 전용 에뮬레이터 이미지에 WinCE 수신기 RSA 인증서, 신뢰 CA와 휴대폰 리프 SHA-256을 설정한다. 앱에는 해당 CA로 발급한 휴대폰 신원을 PKCS#12로 가져온다. AARE의 헤드유닛 승인과 WinCE의 휴대폰 검증이 각각 작동한다.
- 순정 내비의 기존 투사 팝업에 한국어 연결 상태, 취소 및 네 페이지 안내를 추가했다. USB 대기는 기존 작업 스레드에서 이어지고 첫 영상 출력이 안내 화면을 대체한다.
- 공식 AARE 1.6.0을 Samsung SM-G996N(Android 15)에 설치했다. 사용자 폰 인증서 가져오기 완료. 초기 AARE 로그에서 USB 권한 허용과 액세서리 열기 실패를 확인했다. 같은 시점에 순정 Android Auto 세션이 USB를 사용하고 있어 이를 종료하고 AARE를 다시 실행했다.
- 중단 직전 UART에서 실폰 상호 TLS와 `AUTH_COMPLETE`, 서비스 탐색을 확인했다. 같은 실행에서 별도의 인증서 체인 실패 및 USB 타임아웃도 발견했다. 영상과 터치는 실폰에서 확인되지 않았다. [실폰 시험과 인증서 대조](REAL_PHONE_TEST_RESULTS.md)
- 재개 후 USB 속도 변경의 폴링 기준과 bulk IN 재시도를 수정했다. 안내의 설치 페이지에 공식 다운로드 QR을 추가했다. Python 회귀 86개를 통과했고 별도 800×480 순정 시험 이미지를 빌드한다.

[소스 비교](COMPATIBILITY_ANALYSIS.md) · [실행 및 신뢰 등록](FINAL_HANDOFF.md)
