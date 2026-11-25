# Codex 세션 인계

11월 25일 인증 이후 통합에서는 순정 투사 터치와 영상·USB 안정성, 가상 MICOM 후진, WinCE Wave 포맷 질의를 검증했다. 결과와 남은 실기기 범위는 새 인계를 참조한다. [인증 이후 통합 인계](Codex-post-auth-integration/FINAL_HANDOFF.md)

11월 25일 인증서 교차 검증, ARM 인증 진단과 실폰의 외부 의존 조건은 인증 해결 보고서를 참조한다. [인증 해결 보고서](Codex-authentication-resolution/FINAL_HANDOFF.md)

작업 폴더는 `F:\i30-gen2-android-auto`다. 목표는 순정 내비 한 창에서 **내비 메뉴 → Android Auto**로 실폰 800×480 영상을 띄우고, 후방카메라·시스템 팝업·순정 OSD에 표시 우선권을 넘기는 것이다. 에뮬레이터에서 가상 영상과 실폰 인증 대기까지 확인했다. 실폰 화면은 WinCE에서 아직 나오지 않는다. [검증 및 오류 07 분석](ANDROID_AUTO_AUTH_STATUS.md)

11월 24일 후보는 CE에서 채널별 암호화 프레임 조립과 세분화된 인증 실패 로그를 적용했다. 격리 WinCE에서 영상 사이 제어 ping과 LCD 출력을 검증했다. [최신 분석·재현 절차](ANDROID_AUTO_REVERSE_ENGINEERING.md)

## 기존 PC에서 재개

```powershell
Set-Location 'F:\i30-gen2-android-auto'
git -c safe.directory=F:/i30-gen2-android-auto status --short --branch
.\tools\run_gd13my_phase78.ps1
```

실행기는 `build/gd13my-native-oem-screen/phone-wait/gd13my-aa-stock-display.img`와 같은 폴더의 `image.json`이 있으면 우선 사용한다. 다른 시험 이미지는 `-StockProjectionImage`로 선택한다. 회색 **동의함**이 활성화될 때까지 기다린 뒤 입력한다. 처음 `F2`에서 지도만 전면으로 나오면 `F2`를 한 번 더 눌러 **내비 메뉴 → Android Auto**를 선택한다. 대기 화면에서 연결 상태를 확인한다. 뷰어의 **시동 끄기/켜기**와 USB 재연결을 사용하면 반복 시험 때 호스트 앱을 계속 띄워 둘 수 있다. 콜드 부팅과 저장장치 속도를 따로 기록하고, C: 공간이 부족한 현재 PC에서는 `-FastStorage`를 생략한다. 실행 로그와 임시 파일은 F:의 `build/` 아래에 남는다. [화면 통합과 조작](CE_NATIVE_DISPLAY_INTEGRATION.md) · [에뮬레이터 구성](GD13MY_EMULATION.md)

## 새 체크아웃에서 준비할 로컬 입력

| 입력 | 위치와 준비 방법 |
| --- | --- |
| GD13MY .061 순정 패키지 | 사용 권한이 있는 국내형 GD13MY 업데이트 사본을 준비한다. `firmware/original/GD13MY/`에 `APP`, `BSP`, `MICOM`, `ACC`의 `.hdr` 및 `.spd.000`을 원래 이름으로 둔다. `tools/inventory.py`로 업데이트 매체 사본을 검증할 수 있다. |
| 순정 내비 PE와 에뮬레이터 ROM | 로컬 업데이트 사본에 `tools/extract_spd.py`를 실행한다. 실행기가 읽는 `firmware/extracted/GD13MY/APP/00d12869_GDdNavi.exe`와 `firmware/extracted/GD13MY/BSP/0002dfc7_kernel`을 확인한다. Phase 1 ROM 메타데이터가 필요한 경우 `tools/phase1_rom.py`로 로컬 분석본에서 `research/evidence/phase1-rom.json`을 생성한다. |
| 가상 DiskA | 기본 미디어 이미지 경로는 `%LOCALAPPDATA%\i30-gd13my\gd13my-media-v2.img`다. `tools/build_gd13my_diska.py`와 [GD13MY 가상 eMMC 안내](GD13MY_EMULATION.md#가상-emmc와-화면-캡처)를 참고한다. 실행기에는 가상 DiskA만 연결하며 상태 파일은 시험 이미지 옆에 생성된다. |
| Python과 PC 수신기 | `requirements-phase2.txt`, `requirements-phase5.txt`를 설치한다. DiskA 빌드는 `pyfatfs`와 `pkg_resources`가 있는 환경을 쓴다. PC 영상 시험은 `av==19.0.2`를 사용했다. 기존 실행기 Python은 `%LOCALAPPDATA%\i30-phase2-venv\Scripts\python.exe`다. [Phase 2 환경](PHASE2_ARCHITECTURE.md#빌드와-테스트)대로 `tools/build_phase2.py --protoc <protoc.exe> --schemas <aasdk/protobuf>`를 실행해 `src/i30_receiver/aasdk.pb`를 재생성한다. |
| ARM 툴체인과 네이티브 이미지 | ARM GNU 컴파일러, BearSSL 0.6, h264bsd 커밋 `42bcb5d753ad86d84903354bf3c68423c28adb7b`, 가상 TLS 시험용 OpenSSL CLI를 준비한다. 로컬 라이브러리 경로는 `build/ce-tls-dependency/bearssl-0.6`과 `build/ce-video-dependency/h264bsd`다. `tools/build_ce_usb.py`로 빌드한 뒤 .061 메뉴·표시·시작 패치와 `tools/build_gd13my_aa_lab.py`로 가상 DiskA와 `image.json`을 생성한다. [통합 이미지 빌드](CE_NATIVE_DISPLAY_INTEGRATION.md#에뮬레이터-빌드) · [Phase 7·8 빌드 예](PHASE7_8_RESULTS.md#이미지-재생성) |
| 헤드유닛 TLS 설정 | 실제 폰이 신뢰하고 이 프로젝트가 사용할 권한이 있는 자료를 확보한 뒤 로컬에서만 준비한다. 실험용 가상 DiskA의 `\DiskA\Application\NAVI\`에 `i30-client.pem` 또는 `.der`, 대응 `i30-client-key.pem` 또는 `.der`, `i30-ca.pem` 또는 `.der`, 그리고 `i30-peer.txt` 또는 `i30-peer-sha256.txt` 중 하나를 둔다. 가상 폰 시험 도구는 격리된 시험용 자격 증명을 임시 이미지에 주입한다. |

`firmware/`, `build/`, `research/evidence/`, `research/sources/`, `tools/vendor/`, 가상환경 및 인증 자료는 로컬에 보관한다. 기존 문서의 이 경로 링크는 이전 작업 폴더에서 확인할 수 있다. 원격 체크아웃에는 위 절차로 준비한다. 임시 디렉터리도 용량이 충분한 F:의 `build/temp/`를 우선한다.

기존 PC에서 가상 USB 재연결 시험을 실행하는 명령이다. 호스트 가상환경의 PyAV에 DiskA 가상환경의 패키지를 함께 사용한다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$compiler = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$disk = Join-Path $env:LOCALAPPDATA 'i30-gd13my/gd13my-media-v2.img'
$openssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'
$imageDir = 'build/gd13my-native-oem-screen/cert-chain'
$diskPackages = (Resolve-Path 'tools/venv/gd13my-disk/Lib/site-packages').Path
$priorPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = if ($priorPythonPath) { "$diskPackages;$priorPythonPath" } else { $diskPackages }
    & $py tools/verify_gd13my_virtual_phone.py `
        --image "$imageDir/gd13my-aa-stock-display.img" --manifest "$imageDir/image.json" `
        --disk $disk --compiler $compiler --openssl $openssl --seconds 1800 `
        --native-menu 'firmware/extracted/GD13MY/APP/00d12869_GDdNavi.exe' `
        --replug-after-frame --output 'build/gd13my-native-oem-screen/virtual-usb-replug-followup'
} finally {
    $env:PYTHONPATH = $priorPythonPath
}
```

## 재개 순서

1. 스키마를 준비하고 `python -m unittest discover -s tests`를 실행한다. 인계 시점 호스트 테스트 84개가 통과했다. 순정 이미지와 `image.json`을 대조하고 `tools/verify_gd13my_virtual_phone.py --help`의 입력에 맞춰 `--native-menu`와 `--replug-after-frame` 경로를 재검증한다. 적색 출력, 분리 시 표시 해제, 새 TLS 세션과 녹색 출력을 순서대로 확인한다. 인계 전 기존 가상 재연결 실행은 이 순서를 기록했다. 이후 시험 도구에 추가한 유휴 ping 변경의 전체 부팅 시험은 남아 있다.
2. 적법한 헤드유닛 자료를 받을 수 있는지 공급사 문의 진행 상태를 확인한다. 자료 확보 후 실폰 USB 재열거, 1.7 버전 교환, TLS 완료, 영상 서비스 응답, 순정 창의 첫 실폰 프레임을 각각 기록한다. TLS가 다시 실패하면 게스트 UTC, 파일 로드 결과, 체인 순서, BearSSL 오류 코드와 폰 로그를 비교한다. 공식 DHU는 실폰과 케이블의 기준시험에 사용한다.
3. `src/ce/ce_aa_usb_client.c`의 `USBDeviceAttach`와 20초 영상 타임아웃을 출발점으로 장시간 세션을 설계한다. 전송과 표시 소유권을 작업 스레드에서 관리하고, USB 분리·시동 꺼짐·`WM_CLOSE`에서 파이프와 영상 표시가 안전하게 해제되는지 반복 검증한 뒤 시간 제한을 조정한다. 순정 팝업·후방카메라·공조/볼륨 OSD의 표시와 복귀, 터치, 순정 Bluetooth 음악과 오디오 포커스도 이 순서에서 확인한다. 부팅 최적화 전후 비교에는 켜기부터 지도 및 활성화된 동의 버튼까지의 시간을 사용한다.

실제 차량에 적용하기 전 복구 가능한 벤치 조건을 확인한다. 순정 내비 프로세스를 실행한 상태에서 HWND 상대 배치로 공존한다. 부트로더, `nk.bin`, 실제 플래시 파티션 직접 접근·쓰기 및 순정 내비 강제 종료는 금지한다. [벤치 위험과 복구 조건](PHASE6_BRICK_RISK_ASSESSMENT.md)
