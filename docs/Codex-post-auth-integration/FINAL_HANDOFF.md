# GD13MY 인증 이후 통합 인계

코드 `8afc73f`는 `.061` 순정 터치 선처리 경로의 메시지를 투사 창에 전달하고, 암호화된 단일 포인터 AAP 입력을 제공한다. 상주 영상 세션은 USB 활동을 기준으로 유휴 시간을 판단한다. 기존 BearSSL, H.264 디코더, 순정 표시 권한, 호스트 PCM 및 마이크 시험 환경을 사용했다. [기능별 구현 및 검증 수준](IMPLEMENTATION_STATUS.md)

순정 WinCE에서 터치가 가상폰에 도달했고, 가상폰이 터치 응답으로 만든 H.264 프레임의 색 변화가 LCD에 나타났다. 가상 MICOM 후진 이벤트가 투사 포커스를 선점했다가 같은 TLS 세션에 반환했다. 장시간 영상과 반복 연결 검증 수준, 정확한 프레임 수와 미실시 항목은 시험 결과에 기록했다. [터치 전후 및 수신 증거](TOUCH_INPUT_VALIDATION.md) · [ARM·순정·장기 시험](REGRESSION_TEST_RESULTS.md)

OEM `LibSound`의 권한 값은 모듈의 비공유 `.data`를 사용했다. 격리용 순정 WinCE에서 Wave 출력·입력 포맷 질의는 성공했다. 안내·경고음·Bluetooth 통화와의 자원 소유권, 실제 PCM 입출력, 스티어링 휠과 차량 전원 이벤트는 실기기 시험이 남아 있다. 최초 실폰 연결은 정지된 에뮬레이터에서 사용 권한이 확인된 시험 신원으로 시작한다. [OEM 및 차량 벤치 시험](OEM_AND_HARDWARE.md) · [무료 AI 후속 조사](FREE_AI_NEXT_TASKS.md)

빠른 회귀는 `python -m unittest discover -s tests`를 사용한다. WinCE 대상 ARM 검증은 `tools/emulate_ce_usb.py`의 TLS·투사·순정 트램펄린 경로를 사용한다. 전체 통합은 `tools/verify_gd13my_virtual_phone.py`의 순정 메뉴 경로를 쓰며 장시간 영상은 ARM에서 따로 실행한다. 두 검증 경로의 원본 로그, 빌드, 테스트 이미지와 LCD 증거는 F: `build/codex-post-auth-integration/`에 있다. [재현 명령과 산출물](REGRESSION_TEST_RESULTS.md#재현)
