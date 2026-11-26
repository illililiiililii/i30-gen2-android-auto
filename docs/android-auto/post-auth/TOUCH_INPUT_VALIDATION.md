# 순정 투사 터치 검증

## 입력 경로

`.061` ARM의 `CNaviMain` 선처리 트램펄린은 활성 투사 창이 있을 때 `I30RouteProjectionTouch`에 실제 `MSG.hwnd`, 메시지 번호와 좌표를 전달한다. `i30nav.dll`은 OEM 허가, 영상 창·순정 지도의 Z-order, 원본 HWND의 소유 관계와 대상 화면 좌표를 확인한다. 다른 창이 터치 위치를 덮거나 후방 표시가 활성화되면 순정 경로로 전달한다. 입력 큐는 단일 터치를 처리하고, 같은 위치의 이동을 생략하고, 연속 이동을 합치며, 화면 밖에서 시작한 접촉을 거부한다. 진행 중 가장자리 좌표는 화면 안으로 보정한다. 권한 상실, 연결 종료와 큐 초과는 입력 상태를 초기화한다. [순정 ARM 진입점](../../src/ce/gd13my_aa_menu.S) · [WinCE 투사 창](../../src/ce/ce_aa_native_display.cpp)

`i30usb.dll`은 순정 투사 HWND가 있는 세션에서 AAP 입력 채널 `1`과 800×480 터치스크린을 광고한다. 채널 open 및 binding 이후의 DOWN/MOVE/UP을 단조 증가하는 송신 기준 마이크로초 타임스탬프와 함께 TLS로 전송한다. WinCE 창 메시지는 정수 이벤트만 교환하며, 일시적인 응답 지연 동안 접촉 상태를 유지한다. 화면 권한이 사라지거나 창 통신이 계속 실패하면 접촉을 종료한다. USB 수신을 대기할 때는 새 암호화 프레임 헤더 경계에서 입력을 보낼 수 있다. BearSSL은 USB 처리 스레드가 소유한다. [CE 투사 프로토콜](../../src/ce/ce_aa_projection.c) · [TLS 전송](../../src/ce/ce_aa_tls.c) · [Windows CE SendMessageTimeout](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms939981(v=msdn.10))

## 증거

추가로 받은 Web-ChatGPT 자료의 viewport와 입력 좌표 분리 사례를 현재 구현에 대조했다. WinCE 투사 창은 현재 800×480 크기를 확인하고 디코더의 크롭 결과를 그 전체 영역에 그린다. 입력 서비스도 800×480을 광고한다. 실폰에서 영상 viewport, letterbox 또는 다른 입력 설정이 협상되면 실제 화면과 AAP 좌표를 따로 대조한다. [인증 이후 호환성 조사](../chatGPT-search/Web-chatGPT/ANDROID_AUTO_POST_AUTH_COMPATIBILITY.md)

- 첫 순정 통합 시험은 AAP 1.7, TLS 1.2, AuthComplete 및 첫 영상에 도달했다. 이후 주입한 `(400, 240)`, `(701, 430)` 접촉이 `CNaviMain::OnMessage`에 들어가 순정 메뉴 `SHOT_NMN02`를 열었다. 순정 `WndProc`만 사용하는 입력 처리에서 관측된 실패를 바탕으로 동일한 선처리 트램펄린을 확장했다. [첫 시도 UART](../../build/codex-post-auth-integration/native-integration/virtual-phone.serial.log)
- L2 가상 상대는 복호화한 Protobuf에서 `(0,0)` DOWN, `(400,240)` MOVE, `(799,479)` MOVE/UP과 다음 짧은 터치를 받았다. 좌표, 순서, 단일 포인터 ID와 타임스탬프를 독립적으로 대조했다. 폰이 추가 메시지를 보내지 않는 대기 상태와 USB zero-length packet 상태에서도 보고를 수신했다. [ARM 입력 및 USB 증거](../../build/codex-post-auth-integration/arm-stress-final.json)
- 트램펄린 적용 뒤 순정 게스트의 터치 경로에서 `(701,430)` DOWN/UP, 드래그 이동과 `(5,5)`, `(794,474)` 가장자리 이벤트를 가상폰이 수신했다. 가상폰이 받은 UP에 따라 다음 H.264 프레임의 배경을 바꿨고 LCD가 적색에서 녹색으로 변했다. 짧은 첫 접촉은 누락됐고, 길게 누르기에서 반복 DOWN/UP이 관측됐다. 입력 활성 시점을 첫 프레임 표시 전으로 당기고 WinCE 창 응답의 일시 지연에서 기존 접촉을 유지하도록 보강했다. 반복 접촉의 원인은 직접 계측하지 못했다. [가상폰 수신 원장](../../build/codex-post-auth-integration/final-integration/virtual-phone.touch.jsonl) · [터치 이전 LCD](../../build/codex-post-auth-integration/final-integration/virtual-phone-before-touch.png) · [터치 이후 LCD](../../build/codex-post-auth-integration/final-integration/virtual-phone-after-touch.png)
- 최신 `tested-ce`의 중단된 순정 실행에서는 이전에 누락됐던 중앙 `(400,240)` DOWN/UP이 도달했다. 가상폰이 만든 응답 프레임 4가 화면에 표시됐다. 좌표와 이동 경로는 원장에 남았고, 하나로 주입한 접촉이 여러 DOWN/UP으로 분리되는 현상도 남아 있다. [최신 가상폰 원장](../../build/codex-post-auth-integration/stock-integration/virtual-phone.touch.jsonl) · [터치 전](../../build/codex-post-auth-integration/stock-integration/virtual-phone-before-touch.png) · [터치 응답](../../build/codex-post-auth-integration/stock-integration/virtual-phone-after-touch.png)
- 재개한 동일 빌드의 순정 시험에서 5세션 모두 가상폰이 입력을 받고 응답 프레임을 출력했다. 첫 세션의 수신 이벤트는 DOWN 12, MOVE 3, UP 12였다. 해당 세션의 전체 제스처 검사는 접촉 분할 때문에 실패했다. 두 번째부터 다섯 번째 세션의 중앙 터치 검사는 통과했고, 마지막 종료 후 순정 메뉴 입력을 확인했다. [재개 시험 입력 원장](../../build/codex-post-auth-integration/resumed-stock/virtual-phone.touch.jsonl) · [실행 결과](../../build/codex-post-auth-integration/resumed-stock/virtual-phone.json)
