# GD13MY 순정 에뮬레이터 검증

`GD13MY.KOR.SOP.00.061` 순정 App 파티션에 기존 내비 설정, 표시·시작 패치와 현재 ARM DLL을 넣었다. 변경 대상 외 순정 파일 114개의 바이트가 원본과 일치했다. 결과 FAT32 파티션을 다시 열어 `i30usb.dll`의 SHA-256이 빌드와 매니페스트 양쪽과 일치하고 TLS 등록 파일이 0개임을 확인했다. 가상 시험 신원은 시험 중 이미지의 임시 사본에만 들어간다. [이미지 매니페스트](../../build/codex-authentication-resolution/verified-image/image.json)

순정 모드 검증은 기존 가상폰 시험기의 `--native-menu`와 `--replug-after-frame` 경로를 사용한다. 순정 동의 화면, 지도 준비, MICOM 메뉴 입력, Android Auto 항목 터치, 화면 선점, 가상 USB 상호 TLS, 서비스 탐색, 첫 프레임, 분리 후 화면 반환, 새 TLS 세션과 다른 색상 프레임을 순서대로 확인한다. Windows CE 게스트가 보고한 UART와 800×480 LCD의 세 지점이 결과에 남는다. 투사 화면에서 폰으로 보내는 터치 이벤트는 이 검증 경로에 포함되지 않는다.

기존 전체 가상 매체가 없어 `build_gd13my_diska.py --with-map`으로 다시 생성했다. 재생성 가능한 4GB 맵 매체는 로컬 C: 캐시에서 만들었다. ARM 빌드, 이미지, 원본 UART와 실행 결과는 F: 프로젝트의 무시된 `build/codex-authentication-resolution/`에 저장한다.

```powershell
$out = 'build/codex-authentication-resolution'
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$openssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'
$cache = Join-Path $env:LOCALAPPDATA 'i30-gd13my/codex-auth-map-cache'
$disk = Join-Path $cache 'gd13my-media-v2.img'
$env:PYTHONPATH = (Resolve-Path 'tools/venv/gd13my-disk/Lib/site-packages').Path
& $py tools/verify_gd13my_virtual_phone.py `
    --image "$out/verified-image/gd13my-aa-stock-display.img" --manifest "$out/verified-image/image.json" `
    --disk $disk --compiler $cc --openssl $openssl --seconds 1800 `
    --native-menu firmware/extracted/GD13MY/APP/00d12869_GDdNavi.exe `
    --replug-after-frame --output "$out/stock-menu-replug"
```

생성 명령은 `tools/build_gd13my_diska.py <disk> --with-map` 및 기존 `tools/patch_gd13my_{settings,display,startup}.py`와 `tools/build_gd13my_aa_lab.py --compact --emulator-utc`를 사용한다. 설정 패치는 `--native-projection`으로 만든다. [기존 이미지 구성](../CE_NATIVE_DISPLAY_INTEGRATION.md#에뮬레이터-빌드) · [ARM 빌드 명령](TLS_REGRESSION_RESULTS.md#빌드-및-시험)

## 순정 전체 부팅과 격리 LCD 상태

순정 전체 부팅과 USB 재연결 시험은 763.639초에 성공했다. WinCE와 순정 내비가 시작됐고, 동의 화면과 내비 메뉴를 거쳐 Android Auto 항목의 게스트 터치가 전달됐다. 투사 창은 순정 지도 바로 위에 자리했다. 가상폰이 AAP 1.7, 상호 TLS, `AUTH_COMPLETE`, 암호화된 서비스 탐색과 영상 응답 1회를 완료했다. 첫 800×480 프레임의 세 표본은 모두 RGB `(255, 0, 0)`이었다. USB 분리 시 UART에 순정 표시 반환이 기록됐다. 재연결 세션도 상호 TLS, `AUTH_COMPLETE`, 서비스 탐색과 영상 응답 1회를 완료했고 세 표본이 RGB `(0, 255, 0)`으로 바뀌었다. [순정 실행 결과](../../build/codex-authentication-resolution/stock-menu-replug/virtual-phone.json) · [순정 실행 UART](../../build/codex-authentication-resolution/stock-menu-replug/virtual-phone.serial.log)

첫 격리 시도는 순정용 DLL을 사용했다. AAP 버전, 상호 TLS, `AUTH_COMPLETE`, 서비스 탐색까지 통과했고 격리 창에서는 영상 채널이 열리지 않았다. 같은 소스를 `--virtual-lcd-bench`로 빌드하고 기존 시험기의 `--lcd-bench --interleave-control` 경로로 다시 실행했다. 124.37초에 AAP 1.7, 상호 TLS, `AUTH_COMPLETE`, 서비스 탐색, 영상 채널과 H.264 프레임 응답 1회, 영상 조각 사이의 제어 pong 1회를 확인했다. 800×480 LCD의 표본 세 점은 모두 RGB `(255, 0, 0)`이다. [첫 격리 실행](../../build/codex-authentication-resolution/isolated-lcd/virtual-phone.json) · [LCD 검증 결과](../../build/codex-authentication-resolution/lcd-bench-verified/virtual-phone.json) · [LCD 검증 UART](../../build/codex-authentication-resolution/lcd-bench-verified/virtual-phone.serial.log)
