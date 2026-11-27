# 순정 에뮬레이터에서 AARE 실행

## 준비한 시험 이미지 실행

2026-11-27 최신 자동 실행 이미지(USB 연결/부팅 대기 설정을 둘 다 켠 에뮬레이터 전용 복제본)는 다음과 같이 실행한다. 기존 에뮬레이터 창은 그대로 두고 새 실행 이미지를 열 수 있다. 물리 USB 장치를 연결하지 않으면 순정 지도가 계속 표시되고, AARE 인증/미디어 준비 전에는 화면을 가져오지 않는다.

```powershell
Set-Location F:\i30-gen2-android-auto
$image = 'build/gd13my-aa-autostart-v8/gd13my-aa-autostart.img'
.\tools\run_gd13my_phase78.ps1 -UsbPort auto -StockProjectionImage $image `
    -Seconds 86400 -OutputDirectory 'build/gd13my-aa-autostart-v8/live' `
    -StatePath 'build/gd13my-aa-autostart-v8/live-user-diska.sqlite3'
```

`내비 설정 → 기타 → AARE`에서 `USB 연결 시 AARE 자동 실행`과 `부팅 후 AARE 연결 대기`를 각각 저장할 수 있다. USB 자동 옵션은 순정 지도가 이미 떠 있을 때 연결을 감지하고, 부팅 대기 옵션은 지도 부팅 시 guest receiver를 먼저 띄운다. 같은 receiver가 장치를 소유하므로 두 옵션을 함께 켜도 중복 HCD 등록은 하지 않는다. 실폰은 AARE를 실행하고 케이블을 연결해야 한다. Android가 표시하는 USB 앱 선택/접근 권한과 최초 수신기 지문 `Trust`는 휴대폰에서 한 번 승인해야 하며, 이를 에뮬레이터가 대신 누르지 않는다.

새 사용자 상태로 시작하면 순정 내비게이션 동의 화면에서 사용자가 직접 `동의`를 눌러야 지도에 진입한다. 라이브 실행은 이 동의 버튼을 자동으로 누르지 않는다.

헤드리스 가상폰 시험은 `build/gd13my-aa-autostart-v8/native-auto-replug/`에 저장한다. 순정 지도 ACK 뒤 자동 투사 시작, 가상 USB/AOA, TLS 1.2 인증, AAP 서비스 탐색 및 첫 프레임 표시까지 확인했다. 분리/재연결의 출력 픽셀 검증과 실제 스마트폰 앱/USB 권한 대화상자는 미검증이다.

## 이전 준비 이미지 실행

현재 PC에서는 다음 명령으로 순정 WinCE 창을 연다. 실행 중인 동일 이미지의 에뮬레이터 창이 있다면 그 창을 사용한다.

```powershell
Set-Location F:\i30-gen2-android-auto
$disk = Join-Path $env:LOCALAPPDATA 'i30-gd13my/codex-auth-map-cache/gd13my-media-v2.img'
.\tools\run_gd13my_phase78.ps1 -DiskPath $disk `
    -StockProjectionImage E:/i30-gd13my-images/opencode-resume-perf/touch/gd13my-aare-settings-o2.img `
    -OutputDirectory E:/i30-gd13my-images/opencode-resume-perf/touch/aare-settings-live
```

1. 순정 시작 화면에서 **동의함**을 누른다. 지도가 나타나면 **내비 메뉴(F2) → AARE**를 선택한다. 첫 F2가 지도만 전면에 표시하면 내비 메뉴를 한 번 더 누른다. **사용법 보기**에서 안내와 설치 페이지의 공식 다운로드 QR을 확인할 수 있다. **내비 설정 → 기타 → AARE**에서는 부팅 후 USB 감지 여부를 설정한다.
2. 폰에서 AARE를 열고 데이터 USB 케이블을 연결한다. USB 앱 선택 또는 접근 권한이 나타나면 AARE를 선택한다. 기존 Android Auto가 이미 USB를 사용 중이면 세션을 닫고 케이블을 분리했다가 다시 연결한다.
3. 처음에는 AARE 홈 화면이나 알림에 수신기 인증서 지문과 **Trust**가 표시된다. 수신기에서 생성한 SHA-256과 전체 지문이 같은 경우 승인한다. 그 뒤 케이블을 다시 연결한다.
4. 실폰 확인은 WinCE 로그의 TLS 인증, `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임과 순정 화면 표시를 함께 확인한다. AARE 버튼을 눌러 화면이 변하는지 본 뒤 케이블을 분리하고 다시 꽂아 새 TLS 세션과 화면 복귀를 확인한다.

이미 디버깅이 승인된 실폰이 액세서리 모드에 남아 있고 ADB에서 보이면 `adb shell svc usb setFunctions mtp`로 휴대폰을 일반 USB 모드로 재열거할 수 있다. 이 요청 직후 USB가 전환되므로 ADB 연결이 먼저 끊길 수 있다. 이어 PC의 `adb kill-server`로 USB 핸들을 반환한다. 순정 WinCE가 새 AOA 전환을 요청하며, 필요할 때 창 하단의 **USB 다시 연결**로 가상 포트만 다시 연다. 폰 잠금이나 Android 권한 상태에 따라 일반 USB 재열거 뒤에도 AARE 실행이 보류될 수 있다.

2026년 11월 26일 실폰 시험에서 기존 P12로 상호 TLS, `AUTH_COMPLETE`, 서비스 탐색과 800×480 영상 출력을 확인했다. 시험에 사용한 전화는 소프트웨어로 USB를 다시 열거했다. 터치와 물리 케이블 재연결은 별도 검증 대상으로 기록한다. [실폰 로그 요약](REAL_PHONE_TEST_RESULTS.md)

## 최초 등록 간소화

공식 APK 설치는 안내의 공개 다운로드 QR로 열 수 있다. 기존 P12는 AARE에 한 번 가져온 뒤 계속 사용하고, 수신기 인증서는 AARE의 최초 연결 승인으로 등록한다. 향후 설치 도구에서 AARE 파일 가져오기용 P12와 확인용 수신기 공개 지문을 한 화면에 안내하면 최초 등록 동선을 줄일 수 있다. 공식 AARE 1.6.0의 파일 가져오기와 지문 승인 절차를 그대로 사용할 수 있다. [AARE 인증서 관리](https://github.com/prototux/AARE/blob/v1.6.0/docs/certificates.md)

## 새 시험 인증서로 다시 빌드

다음 예시는 기존 ARM 개발 환경, 기존 .061 패치 출력물과 WinCE 에뮬레이터용 가상 매체를 사용한다. 순정 매체는 읽기 전용으로 사용한다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$openssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'
$out = 'build/aare-new'
$patch = 'build/codex-authentication-resolution'
New-Item -ItemType Directory -Path $out -Force | Out-Null
& $py tools/new_gd13my_aare_identity.py "$out/identity" --openssl $openssl
& $py tools/build_ce_usb.py "$out/ce" --compiler $cc `
    --bearssl-source build/ce-tls-dependency/bearssl-0.6 --h264-source build/ce-video-dependency/h264bsd
& $py tools/build_gd13my_aa_lab.py $disk "$out/gd13my-aare-stock-display.img" `
    --settings "$out/ce/i30aa.exe" --usb-client "$out/ce/i30usb.dll" `
    --native-projection "$out/ce/i30nav.dll" --navigation-patch "$patch/navigation" `
    --stock-display "$patch/display" --startup-patch "$patch/uComH_New.exe" `
    --compact --emulator-utc --aare-identity "$out/identity" > "$out/image.json"
```

AARE의 **Advanced → Phone certificates → Import from file**에서 `GD13MY-AARE.p12`를 가져온다. 암호는 인증서 생성 시 입력한 값이다. 시험 파일은 폰에 가져온 뒤 Downloads에서 삭제할 수 있다. `head-unit-sha256.txt` 값을 최초 USB 승인 화면과 확인한다. 인증서가 만료되거나 변경되면 새 시험 이미지를 만들고 폰에 새 인증서를 가져온 뒤, AARE의 **Trusted head units**에서 이전 지문을 제거하고 새 지문을 확인해 승인한다. 사설 키가 포함된 인증서 파일과 이미지는 로컬에 보관한다. [AARE 공식 APK](https://github.com/prototux/AARE/releases/tag/v1.6.0) · [AARE 인증서 관리](https://github.com/prototux/AARE/blob/v1.6.0/docs/certificates.md)
