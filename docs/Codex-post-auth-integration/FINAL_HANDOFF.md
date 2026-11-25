# GD13MY 인증 이후 통합 인계

코드 `8afc73f`는 `.061` 순정 터치 선처리 경로의 메시지를 투사 창에 전달하고, 암호화된 단일 포인터 AAP 입력을 제공한다. 상주 영상 세션은 USB 활동을 기준으로 유휴 시간을 판단한다. 기존 BearSSL, H.264 디코더, 순정 표시 권한, 호스트 PCM 및 마이크 시험 환경을 사용했다. [기능별 구현 및 검증 수준](IMPLEMENTATION_STATUS.md)

순정 WinCE에서 다섯 세션의 새 TLS, `AUTH_COMPLETE`, 영상, 터치 응답 영상, 분리 후 표시 해제, 마지막 순정 메뉴 복귀를 확인했다. 가상 MICOM 후진은 투사 포커스와 입력을 선점했다가 같은 TLS 세션에 반환했다. 첫 세션에서 접촉 분할이 관측돼 전체 제스처 검사는 실패했다. ARM은 30분 분량 27,000프레임과 30회 재연결 종료에서 추적 할당 0건을 기록했다. [터치 전후 및 수신 증거](TOUCH_INPUT_VALIDATION.md) · [ARM·순정·장기 시험](REGRESSION_TEST_RESULTS.md)

최신 ARM 빌드는 실폰 AOA, AAP 1.7, TLS 1.2 협상과 CertificateVerify 송신까지 도달했다. 폰이 임시 자체 시험 신원의 체인을 거부했다. 별도 ClientHello 전용 캡처의 유일한 발급기관 이름은 보관한 GAL 루트와 일치했으며, 폰이 RSA PKCS#1/SHA-256을 허용 목록에 제시했다. 다음 실폰 시험은 사용 권한과 대응 키가 확인된 RSA 리프·중간 체인이 확보되면 진행한다. [실폰 시험과 발급기관](../Codex-authentication-resolution/REAL_PHONE_TEST_RESULTS.md#11월-25일-후속-실폰-시험) · [평가 신원 후속 조사](../Codex-authentication-resolution/FREE_AI_NEXT_TASKS.md)

격리 순정 WinCE에서 Wave 장치 및 포맷 질의가 성공했다. OEM 장치 소유권, 실제 PCM 입출력, Bluetooth 통화, 스티어링 휠, 차량 전원 및 DSP 가속은 후속 시험이다. [OEM 및 차량 벤치 시험](OEM_AND_HARDWARE.md) · [무료 AI 후속 조사](FREE_AI_NEXT_TASKS.md)

빠른 회귀는 `python -m unittest discover -s tests`를 사용한다. WinCE 대상 ARM 검증은 `tools/emulate_ce_usb.py`의 TLS·투사·순정 트램펄린 경로를 사용한다. 전체 통합은 `tools/verify_gd13my_virtual_phone.py`의 순정 메뉴 경로를 쓰며 장시간 영상은 ARM에서 따로 실행한다. 두 검증 경로의 원본 로그, 빌드, 테스트 이미지와 LCD 증거는 F: `build/codex-post-auth-integration/`에 있다. [재현 명령과 산출물](REGRESSION_TEST_RESULTS.md#재현)
