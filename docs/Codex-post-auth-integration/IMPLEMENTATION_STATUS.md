# GD13MY 인증 이후 구현 현황

기준 커밋은 `ef0438a`이며 착수 시 `main`과 `origin/main`이 일치했다. 기존 BearSSL 상호 인증, 800×480 H.264 디코더, WinCE USB와 순정 화면 권한, Python 호스트의 입력·PCM·마이크와 가상 폰을 사용했다. 검증 수준은 L1 코드 및 단위 시험, L2 ARM 네이티브, L3 순정 Windows CE 통합, L4 실폰, L5 실제 내비게이션이다.

| 기능 | 이번 소스의 상태 및 검증 |
| --- | --- |
| 상호 TLS, AuthComplete, 서비스 탐색 | 기존 구현을 재사용. ARM에서 상호 TLS와 채널 통과. 순정 .061 시험 결과는 아래 문서에 기록. |
| 투사 터치 | WinCE 단일 터치 입력 서비스와 OEM `CNaviMain` 선처리 경로 연결. L2에서 프로토콜 이벤트와 정확한 경계 좌표, 수신 대기 중 송신, 종료를 검증. [터치 검증](TOUCH_INPUT_VALIDATION.md) |
| 연속 영상 | 800×480 H.264 Baseline 기존 경로 재사용. L2 프레임·시간 측정. [영상·USB 회귀](REGRESSION_TEST_RESULTS.md) |
| USB·리소스 | 상주 투사는 수신 활동 기준 idle 제한. L2 동일 ARM 주소 공간에서 5/10/30회, 분할 영상·TLS·인증 직후·터치 단절 검증. |
| 순정 화면 보호 | 기존 후방 이벤트, 지도 상대 HWND 순서, GDI 클립을 재사용. OEM 화면이 노출되면 투사 입력을 해제한다. |
| 오디오·마이크 | PCM 및 모의 마이크 Python L1. 격리 WinCE에서 순정 API의 PCM 입력·출력 포맷 질의 통과. OEM 소유권 미확인으로 WinCE 투사에서 오디오·마이크 채널 미등록. |
| 물리 버튼·Bluetooth | NAVIMENU·내비 음량 가상 MICOM 코드 재사용. 스티어링 휠과 Bluetooth 통화·음악의 실제 이벤트·자원 계약 확인 필요. |
| 시동·설정 | L2 자동 시작 플래그, 중복 실행 방지, 순정 시작 실패 복귀, 취소 및 설정 시험. 전원 순서와 실제 시동 복귀는 L5 시험 대상. |
| 혼합 스트레스 | L2 영상+터치+USB 및 화면 우선권 회귀. 음악·마이크·통화가 포함된 순정 혼합 시나리오는 OEM 오디오 계약 확인 뒤 진행. |
| 실폰·실차 | 이번 범위는 L3까지. 실제 Google Android Auto 연결, OMAP 성능, 차량 I/O는 L4/L5 절차를 따른다. |

REA의 기존 스킬 안내와 CLI/도구 설명을 확인하고 `.061` PE export/import에 적용했다. Serena, Code Review Graph, RTK, Ponytail 및 Caveman은 실행 가능한 CLI/MCP 또는 로컬 스킬을 찾지 못했다. REA의 Windows Ghidra 공급자는 레거시 ARM/Thumb PE `0x01c2`를 지원하지 않았다. 순정 오디오의 작은 함수 검증은 GNU ARM objdump를 사용했다. 그 외 Git, `rg`, Python, Unicorn, ARM GCC, OpenSSL, PyAV의 libx264 및 libavfilter를 사용했다. [OEM 경로 및 하드웨어 벤치](OEM_AND_HARDWARE.md)
