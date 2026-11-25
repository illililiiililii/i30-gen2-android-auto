# GD13MY 인증 해결 인계

11월 25일 `bf3c347`의 인증 연구를 교차 검증했다. 과거 오류 07은 자체 시험 신원에 대한 폰의 인증서 체인 거부였다. 공개 오프셋 인증서는 BearSSL 파싱에서 별도로 실패한다. WinCE는 구성 오류에서 TLS 시작 전에 종료한다. 공개 인증서 서명 확인, 사용 권한, 폰 수락은 독립적인 결과다. [근거와 재현](RESEARCH_VALIDATION.md)

`b5ce302`에서 WinCE 인증서 로딩과 USB·TLS 관측을 보강했다. Python 84개, ARM USB 전용과 TLS/영상 회귀가 통과했다. 정상 시험에서 로딩·실제 송신·가상 상대 수신 리프 지문이 일치했다. 순정 전체 부팅에서 메뉴 터치, 가상폰 상호 TLS, `AUTH_COMPLETE`, 서비스 탐색, 800×480 출력, 분리 시 표시 반환과 재연결 뒤 새 세션 및 프레임을 확인했다. 투사 터치의 폰 전달은 미시험이다. ARM DLL, 에뮬레이터 이미지와 원본 로그는 F: `build/codex-authentication-resolution/`에 있다. [빌드와 회귀](TLS_REGRESSION_RESULTS.md) · [순정 및 격리 에뮬레이터](EMULATOR_VALIDATION.md)

사용자가 폰을 연결할 수 없어 새 ARM DLL 실폰 시험을 보류했다. 프로젝트가 사용할 권한을 확보한 신뢰된 헤드유닛 평가 신원도 필요하다. 다음 실폰 시험에서는 UART의 송신 지문과 안드로이드 Conscrypt 결과를 먼저 대응시킨다. 상호 TLS 이후 `AUTH_COMPLETE`, 서비스 탐색, 영상, 투사 터치, 분리·재연결을 순서대로 기록한다. [실폰 시험 상태](REAL_PHONE_TEST_RESULTS.md) · [공식 평가 신원 조사 인계](FREE_AI_NEXT_TASKS.md)

사용 도구는 Git, `rg`, Python, OpenSSL, BearSSL 호스트 프로브, ARM GNU GCC, Unicorn, ADB, Windows PnP와 REA PE import 검사다. REA의 설치된 `reverse-engineer-anything` 지침을 확인했다. Serena, Code Review Graph, RTK, Ponytail 및 Caveman은 실행 가능한 CLI·MCP 또는 로컬 스킬을 확인할 수 없었다. Ghidra Headless 설치는 확인했고 이번 소스 및 인증서 증거에는 디컴파일이 필요하지 않았다.
