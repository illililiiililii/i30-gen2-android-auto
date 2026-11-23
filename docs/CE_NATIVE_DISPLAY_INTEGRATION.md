# GD13MY .061 순정 내비 화면 통합

## 메뉴와 창 계층

내비 메뉴의 Android Auto 버튼은 터치 누름과 떼기를 순정 경로정보 처리 전에 가로챈다. 떼기에서 `GDdNavi.exe`가 같은 프로세스에 `i30nav.dll`을 로드하고 `I30ToggleProjection(MSG.hwnd)`를 호출한다. 모듈은 해당 HWND의 최상위 소유 창을 찾고 800×480 클라이언트 영역인지 확인한다. 새 투사 창은 지도와 같은 프로세스 및 UI 스레드에 속한 모델리스 팝업이다. USB 대기와 정리는 별도 작업 스레드에서 진행한다. [메뉴 트램펄린](../src/ce/gd13my_aa_menu.S) · [WinCE C++ 구현](../src/ce/ce_aa_native_display.cpp)

`GetWindow(map, GW_HWNDPREV)`로 지도 바로 위의 HWND를 얻고 이 창 뒤에 투사 창을 삽입한다. `SWP_NOACTIVATE | SWP_NOOWNERZORDER`로 배치하고 `GetWindow(projection, GW_HWNDNEXT) == map`을 확인한 뒤 표시한다. 일반 창들의 기존 순서를 이용하고, 그 순서를 확인할 수 없으면 투사 창을 숨긴다. WinCE에서는 위치·크기 설정과 표시·숨김 호출을 분리한다. [SetWindowPos](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/aa453662%28v%3Dmsdn.10%29) · [GetWindow](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/aa453178%28v%3Dmsdn.10%29)

## 순정 표시 상태 연결

1. 서로 다른 HWND로 표시되는 시스템 팝업이나 OSD는 투사보다 위에 놓인 순정 창으로 남긴다. 영상 출력은 `GetDCEx(projection, 0, DCX_CACHE | DCX_CLIPSIBLINGS)`로 상위 HWND가 덮은 영역을 제외한다. [GetDCEx](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms929228%28v%3Dmsdn.10%29)
2. .061 `LibSystem.dll`의 SYS `0x95` 처리 경로가 순정 후방 비트를 읽는다. 후진 진입 처리 전에 표시 허가 이벤트를 리셋하고, 유효한 중립 샘플을 처리해 순정 후방 상태와 표시 래치가 모두 0이면 이벤트를 설정한다. 첫 샘플을 받기 전에는 투사 창을 숨긴다. [순정 이벤트 코드](../src/ce/gd13my_display_events.S)
3. `LibVideo.dll`은 순정 `lVideoShowRearView`가 시작되기 전 후방 표시 이벤트를 설정한다. 순정 종료 경로가 0을 반환한 뒤 이벤트를 리셋한다. 투사 UI와 USB 영상 출력 모두 표시 허가와 후방 표시 이벤트를 확인한다. 실제 카메라 합성 해제 타이밍과 동일 HWND 안에서 합성되는 공조·볼륨 OSD는 차량 벤치 확인이 남아 있다. [순정 분석](VIDEO_AUDIO_ANALYSIS.md)
4. 순정 `GDdNavi.exe`는 `NaviMainFrame`을 만들 때 확장 창 스타일에 0을 전달하고, 생성 직후 800×480으로 배치한다. 런타임에서는 메뉴 입력 HWND의 루트가 이 지도 창인지 확인한다. 순정 뒤로 가기 또는 지도 버튼에서 투사를 끝내려면 해당 순정 이벤트 처리기가 투사 HWND에 `WM_CLOSE`를 전달한다. 투사 창만 숨기고 USB 작업 취소 이벤트를 알린다.

## 800×480 영상과 검증

- 영상 서비스와 H.264 Baseline 디코더의 800×480 프로필을 유지한다. 크롭은 디코더가 제공한 원본 좌표를 사용한다. BGRA DIB는 코딩 가로 픽셀 × 4바이트 행 크기와 음수 높이로 전달하고, 800×480 WinCE 클라이언트 DC에 그린다. LCD 픽셀을 읽는 코드는 격리 검증에 한정한다. 통합용 USB DLL은 `--virtual-lcd-bench` 없이 빌드한다. [영상 코드](../src/ce/ce_aa_video.c) · [투사 DC 코드](../src/ce/ce_aa_projection.c)
- 기존 가상 폰 격리 시험은 800×480에서 H.264 프레임 수신 확인 1회와 LCD의 빨간 픽셀 3점을 기록했다. 기존 순정 소유 대화상자 시험은 포그라운드를 얻지 못했다. 두 결과를 순정 메뉴에서의 투사 완료로 간주할 수 없다. [격리 시험](../build/gd13my-virtual-lcd/standalone/virtual-phone.json) · [이전 순정 창 시험](../build/gd13my-ce-owned-window/guest-owner/virtual-phone.serial.log)
- 순정 게스트 통합 시험에서 동의 처리, 내비 메뉴 생성과 실제 터치, 표시 허가, 지도 바로 위의 투사 창 배치, 가상 폰과의 USB 버전 교환 및 TLS 상호 인증을 확인했다. WinCE가 800×480 H.264 시험 프레임을 그리고 프레임을 확인 응답했으며, LCD 세 지점에서 RGB `255,0,0`을 읽었다. 시험 중 순정 지도를 전면에 표시한 첫 NAVIMENU 입력 뒤 두 번째 NAVIMENU 입력을 전달했다. [통합 결과](../build/gd13my-native-oem-screen/stock-menu-full-boot/virtual-phone.json) · [WinCE 로그](../build/gd13my-native-oem-screen/stock-menu-full-boot/virtual-phone.serial.log)
- 이 후보의 USB 드라이버는 `USBDeviceAttach` 안에서 영상 시험을 최대 20초 동안 실행한다. 지속 투사에는 순정 USB 분리 통지와 파이프 정리 순서에 맞춘 세션 소유권이 필요하다. [CE 포팅 상태](CE_PORTING_STATUS.md)
- 통합 시험에서는 순정 메뉴 터치 → 모듈 로드 → 800×480 HWND 생성 → 상대 순서 → 영상 프레임 수신과 LCD 표시를 함께 확인한다. 순정 지도가 GLES나 별도 플레인으로 직접 합성된다면 HWND 순서가 LCD에 반영되는지 확인하고, 필요하면 순정 표시 권한 API를 연결한다. 후방·팝업·공조·볼륨을 각각 켰다 끄고, 후진과 OSD가 겹치는 경우도 확인한다. 대기 중 지도 복귀와 USB 분리 시에는 투사 창만 닫히고 순정 UI가 계속 응답해야 한다.

## 에뮬레이터 빌드

`tools/build_ce_usb.py`에 기존 BearSSL과 h264bsd 소스를 전달해 `i30nav.dll`, `i30usb.dll`, `i30aa.exe`를 같은 빌드에서 만든다. `tools/patch_gd13my_settings.py --native-projection`과 `tools/patch_gd13my_display.py`로 .061 메뉴와 표시 경로를 빌드한다. 가상 DiskA 생성 시 `tools/build_gd13my_aa_lab.py`에 `--compact`, `--native-projection <i30nav.dll>`, `--stock-display <패치 디렉터리>`와 기존 앱 옵션을 전달한다.

`tools/verify_gd13my_virtual_phone.py --native-menu <순정 GDdNavi.exe>`는 순정 부팅 뒤 MICOM 상태와 메뉴 키, 실제 게스트 터치를 전달하고 USB로 시험 영상을 전송한다. 시험용 자격 증명은 가상 DiskA의 임시 사본에만 들어간다. 실제 휴대폰 검증에는 별도로 등록된 신뢰 자료가 필요하다.

대화형 실행은 `tools/run_gd13my_phase78.ps1`을 사용한다. `build/gd13my-native-oem-screen`에 빌드된 순정 투사 이미지가 있으면 기본으로 선택한다. 다른 이미지는 `-StockProjectionImage <DiskA 이미지 경로>`로 지정한다. 이미지와 같은 디렉터리의 `image.json`에서 표시 패치와 게스트 UTC 설정을 읽는다.

실행기는 기본적으로 프로젝트의 `build/gd13my-boot`에 로그를, `build/temp`에 실행 중 임시 파일을, 선택한 이미지 옆에 DiskA 저장 상태를 기록한다. ARM 빌드의 임시 파일은 출력 디렉터리와 같은 드라이브에 생성한다. 현재 설치된 도구와 기존 읽기 전용 베이스 이미지는 C:에서 읽는다. `-FastStorage`를 명시하면 실행 이미지 캐시를 C:에 둔다.

`phone-wait` 빌드가 있으면 실행기가 이 이미지를 우선한다. **내비 메뉴 → Android Auto**에서 순정 지도 위에 USB 대기 화면이 열린다. 폰이 버전 질의에 실제로 응답한 뒤 로컬 TLS 자료를 확인한다. 자료가 빠졌으면 **휴대폰 연결됨 · 헤드유닛 인증 설정 필요**를 표시하고 USB 연결 요청을 계속 받는다. **지도 돌아가기**를 누르면 투사 창을 숨기고 USB 대기와 임시 등록을 정리한다.

실제 순정 메뉴 터치로 대기 화면을 열었다. 첫 USB 세션의 시간 초과 뒤 투사 창을 닫지 않고 에뮬레이터의 USB를 다시 연결했다. WinCE가 실폰에서 Android Auto 1.7 응답을 받고, 800×480 화면이 인증 설정 안내로 바뀌는 것을 LCD 픽셀과 UART 로그로 확인했다. [LCD 검증](../build/gd13my-native-oem-screen/phone-wait/live-wait-screen.json) · [WinCE 로그](../build/gd13my-native-oem-screen/phone-wait/live-wait-screen.serial.log) · [물리 USB 로그](../build/gd13my-native-oem-screen/phone-wait/live-wait-screen.usb.log)

## 실폰 화면 여는 방법

1. 실폰에서 USB 디버깅을 허용하고 USB 케이블을 연결한다.
2. 폰의 Android Auto 설정에서 **버전**을 열고 **버전 및 권한 정보**를 10회 눌러 개발자 모드를 켠다. 우측 상단 메뉴에서 **헤드 유닛 서버 시작**을 누른다. [Google DHU 연결 안내](https://developer.android.com/training/cars/testing/dhu#connect-using-adb-tunneling)
3. Windows PowerShell에서 아래 명령을 실행한다. 이전에 같은 폰으로 연결한 `tcp:5277` 포워딩이 남아 있으면 포워딩 명령을 건너뛴다.

```powershell
$adb = Join-Path $env:LOCALAPPDATA 'i30-gd13my\android-tools\platform-tools\adb.exe'
$dhu = Join-Path $env:LOCALAPPDATA 'i30-gen2-android-auto\google-dhu\r02.0'
& $adb devices
& $adb forward --no-rebind tcp:5277 tcp:5277
& "$dhu\desktop-head-unit.exe" --adb=5277 --input=touch "--config=$dhu\config\default.ini"
```

4. **Android Auto - Desktop Head Unit** 창에서 앱을 마우스로 선택한다. 2026년 11월 23일 연결한 실폰에서 정상 TLS와 800×480 영상 표시를 확인했다. [실폰 연결 로그](../build/gd13my-native-oem-screen/live-phone-visible.stderr.log)

순정 WinCE 창에서는 회색 **동의함**이 활성화된 뒤 입력한다. `F2`로 지도가 앞으로 나오면 `F2`를 한 번 더 눌러 **내비 메뉴 → Android Auto**를 선택한다. 실폰의 개발자 서버는 자체 시험용 헤드유닛 인증서로 접속할 때 TLS를 종료하고 **통신 오류 7**을 표시했다. WinCE 실폰 투사에는 폰이 신뢰하는 헤드유닛 인증 자료가 필요하다. [시험 로그](../build/gd13my-native-oem-screen/live-phone-native-identity-fresh.log)

같은 날 순정 WinCE 창의 메뉴에서 지도를 덮는 투사 창을 열고 실폰 AOA 인터페이스 `18d1:2d01`을 열거했다. 첫 USB bulk 출력이 시간 초과되어 실폰 영상 서비스까지 도달하지 못했다.

재시험에서는 실폰을 일반 USB 모드에서 새로 AOA로 전환하고 Windows ADB 서버를 정지한 뒤 ARM 수신기로 Android Auto 1.7 응답을 받았다. Windows USB 어댑터는 AOA 인터페이스를 실제로 열 수 있을 때 CE 쪽에 연결을 알린다. 이어 실폰의 USB TLS 응답에서 헤드유닛 인증서 요청을 확인했다. [ARM USB 재시험](../build/gd13my-native-oem-screen/live-phone-aoa-reenumeration.log) · [실폰 TLS 요청](../build/gd13my-native-oem-screen/live-phone-aoa-auth-stage.json)

순정 창만 연 상태에서도 메뉴 버튼을 눌러 지도 위에 투사 창을 배치하고, WinCE가 실폰에 직접 보낸 Android Auto 버전 질의에 1.7 응답을 받았다. 이어 WinCE가 등록된 TLS 인증 자료를 기다리는 상태에 진입했다. [순정 WinCE 실행 로그](../build/gd13my-native-oem-screen/live-phone-stock-menu.serial.log) · [실폰 USB 로그](../build/gd13my-native-oem-screen/live-phone-stock-menu.usb.log)

별도의 물리 USB 대조 시험에서는 실폰이 TLS 1.2를 시작하고 자체 발급한 시험용 헤드유닛 인증서를 받은 뒤 `Trust anchor for certification path not found`를 기록했다. 시험은 개발에 사용할 수 있는 신뢰된 헤드유닛 인증서 체인과 대응 키가 필요함을 확인했다. [USB 송신 로그](../build/gd13my-native-oem-screen/live-phone-usb-trust-root-cause.log) · [안드로이드 TLS 로그](../build/gd13my-native-oem-screen/live-phone-usb-trust-android.log)
