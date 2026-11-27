# GD13MY AARE 통합

기준 `5830cad`에서 시작했다. 로컬 `main`과 원격 `main`이 일치했고 작업 트리에 변경 사항이 없었다. 순정 .061 펌웨어, 이전 실폰 로그와 기존 DiskA를 보존하고 새 시험 DiskA를 `build/aare-integration/`에 만들었다.

- AARE 전용 에뮬레이터 이미지에 WinCE 수신기 RSA 인증서, 신뢰 CA와 휴대폰 리프 SHA-256을 설정한다. 앱에는 해당 CA로 발급한 휴대폰 신원을 PKCS#12로 가져온다. AARE의 헤드유닛 승인과 WinCE의 휴대폰 검증이 각각 작동한다.
- 순정 내비의 기존 투사 팝업에 한국어 연결 상태, 취소 및 네 페이지 안내를 추가했다. USB 대기는 기존 작업 스레드에서 이어지고 첫 영상 출력이 안내 화면을 대체한다.
- 공식 AARE 1.6.0을 Samsung SM-G996N(Android 15)에 설치했다. 사용자 폰 인증서 가져오기 완료. 초기 AARE 로그에서 USB 권한 허용과 액세서리 열기 실패를 확인했다. 같은 시점에 순정 Android Auto 세션이 USB를 사용하고 있어 이를 종료하고 AARE를 다시 실행했다.
- 중단 직전 UART에서 실폰 상호 TLS와 `AUTH_COMPLETE`, 서비스 탐색을 확인했다. 같은 실행에서 별도의 인증서 체인 실패 및 USB 타임아웃도 발견했다. 영상과 터치는 실폰에서 확인되지 않았다. [실폰 시험과 인증서 대조](REAL_PHONE_TEST_RESULTS.md)
- 재개 후 USB 속도 변경의 폴링 기준과 bulk IN 재시도를 수정했다. 안내의 설치 페이지에 공식 다운로드 QR을 추가했다. Python 회귀 86개를 통과했고 별도 800×480 순정 시험 이미지를 빌드했다.
- AARE가 앱에 포함된 다른 자격을 제공했을 때 WinCE의 `unknown_ca`가 실폰에 도착했다. 그 다음 실제 세션에서 AARE가 기존 `GD13MY-AARE.p12`를 선택했고 WinCE에서 동일한 리프 지문을 확인했다. 등록 지문을 받은 뒤 USB 읽기 중단이 다시 발생했다. [재시험 기록](REAL_PHONE_TEST_RESULTS.md#소프트웨어-재연결과-인증서-선택-확인)
- 실폰의 첫 TLS 응답 전체가 물리 USB와 가상 MUSB DMA를 통과했다. 짧은 패킷의 DMA 처리를 실제 컨트롤러 규격에 맞췄고 별도 수신 스레드로 WinUSB 읽기를 분리했다. 실폰 응답을 기다리는 동안 게스트 스레드에 제어가 반환되는 회귀를 포함해 Python 테스트 87개를 통과했다. 새 순정 부팅에서 WinCE USB 전송 완료 길이를 계측한다.
- 800×480 순정 팝업에서 `사용법 보기` 버튼과 연결 상태를 확인했다. 현재 에뮬레이터의 터치로 안내 페이지가 열리는 것은 확인되지 않았다. 실폰 영상, 사용자 터치 조작과 화면 복귀까지 이어지는 재연결도 검증이 남았다.
- OpenCode의 헤드리스 벤치와 기준값을 이어받아 시계 카운터를 C로 옮겼다. 같은 3,500만 명령 구간의 게스트 결과가 일치했고, 순정 내비 준비 시간이 기준 705.50초에서 144.33초로 줄었다. 두 시계 경로에서 기존 테스트 87개를 통과했다. [측정과 빌드](EMULATOR_PERFORMANCE.md)
- 14:13 실폰에서 짧은 bulk IN 패킷의 완료 처리를 보정한 뒤 기존 P12로 상호 TLS와 `AUTH_COMPLETE`를 확인했다. 순정 WinCE의 H.264 디코더가 AARE 화면을 800×480으로 표시했다. [실폰 시험 기록](REAL_PHONE_TEST_RESULTS.md#첫-실폰-영상-확인)
- 순정 내비가 투사 창을 대상으로 받은 포인터 메시지를 해당 창으로 전달하도록 수정했다. 새 빌드에서 실폰 영상과 WinCE 창의 터치 누름·뗌을 확인했다. 앱 목록 전환은 재현되지 않았고 화면 갱신에는 지연이 있다. [재시험 기록](REAL_PHONE_TEST_RESULTS.md#직접-터치-재시험)
- 순정 화면에서 `사용법 보기`를 터치해 안내와 설치 QR 페이지까지 열었다. 설정 → 기타의 버튼과 설정 대화상자에 AARE 이름과 최초 승인 안내를 넣었다. 기존 부팅 옵션은 현재 USB 감지를 담당한다. [실기 적용 및 자동 연결 점검](HARDWARE_READINESS.md)
- 800×480 ARM 시험에서 H.264 라이브러리만 `-O2`로 빌드해 같은 15프레임의 처리 시간을 4.365초에서 3.117초로 줄였다. [영상 계측](EMULATOR_PERFORMANCE.md#WINCE-영상-처리)
- 최신 통합 이미지에서 사용 안내 도중 실제 삼성 폰의 상호 TLS와 `AUTH_COMPLETE`가 완료됐고 800×480 영상으로 자동 전환했다. 실폰 앱 목록도 터치로 열었다. 화면에 이전 프레임의 일부가 잠시 남는 현상은 미해결이다. [실폰 터치 기록](REAL_PHONE_TEST_RESULTS.md#직접-터치-재시험)
- 전체 에뮬레이터 약 2.5배를 목표로 같은 이미지의 기준을 다시 측정했다. C eMMC 읽기, IRQ 처리, 장치 폴링과 ARM 예외 주소 재사용으로 내비 준비가 176.903초에서 115.449초로 감소했다. 이 기준의 목표는 약 71초다. 실차용 이미지는 에뮬레이터 최적화 다음 단계다. [전체 처리량](EMULATOR_PERFORMANCE.md#전체-에뮬레이터-처리량)

[소스 비교](COMPATIBILITY_ANALYSIS.md) · [실행 및 신뢰 등록](FINAL_HANDOFF.md)

## 2026-11-27 후속: 부팅/USB 자동 실행

- 설정 UI의 단일 시작 항목을 `USB 연결 시 AARE 자동 실행`과 `부팅 후 AARE 연결 대기`로 나눴다. 기존 `i30auto.opt` 설정은 USB attach monitor를 유지하고, 신규 `i30boot.opt`는 지도 UI 프로세스가 guest-native receiver를 띄운다. 두 항목은 기존 DiskA 파일 저장 방식을 사용한다.
- USB 자동 경로에서 AOA 버전 응답을 받으면 임시 드라이버 등록과 named gate를 정리한 뒤 handoff marker를 쓴다. 부팅/USB helper는 500ms 간격으로 지도 foreground에 합성 WM_MOUSEMOVE를 보내고, 순정 입력 훅이 자동 시작 함수를 호출한다. 같은 프로세스 안의 visible 800×480 map HWND를 제한된 enumeration으로 찾는다. Boot auto가 같은 USB client를 시작할 때는 uComH의 listener를 생략해 HCD 소유 중복을 막는다.
- 자동 투사 창은 지도 위에 소유된 상태로 숨겨진다. AAP media 준비 후 named render-pending event를 통해 기존 게스트 h264bsd/GDI 경로가 첫 프레임을 그릴 수 있고, 기존 `I30_AA_VIDEO_ACTIVE`가 확인된 뒤 화면을 표시한다. 재연결/인증 오류는 지도에 자동 overlay를 띄우지 않는다. decoder, TLS 또는 USB 수신을 호스트로 우회하지 않았다.
- `tools/emulate_ce_usb.py` 및 시작 ARM hook 에뮬레이션에서 두 설정 저장/해제, 자동 AOA handoff, 합성 WM_MOUSEMOVE wake, 기존 touch 전달과 startup 중복 방지를 확인했다. 전체 Python 회귀는 93개 통과, 1개 skip.
- v8 가상 이미지의 native-auto 시험에서 실제 순정 지도 ACK 뒤 자동 투사 창 시작, 가상 USB/AOA, TLS 1.2 상호 인증, 서비스 탐색과 `i30 CE projection frame presented.`까지 확인했다. 분리/재연결의 픽셀 감지 시험은 끝까지 확인되지 않아 미검증으로 남긴다. 물리 스마트폰 USB 권한/Trust, 실폰 최초 프레임, 실차 FPS와 ±5% 목표도 미검증이다.
- 가상폰 시험과 재현 산출물은 `build/gd13my-aa-autostart-v8/`에 있다. 자동 시작 추가로 FPS 개선을 주장하지 않으며, 측정되지 않은 실제 지도 속도와 기존 약 +0.9% 표본 차이는 성능 향상으로 분류하지 않는다.

GPU readback, 실측 지도 FPS와 DSP IOCTL ABI 결론은 이전 수치를 그대로 유지한다. 자세한 빌드·시험 상태는 [하드웨어 가속 인계](../../hardware/hardware-acceleration/FINAL_HANDOFF.md)에서 이어간다.
