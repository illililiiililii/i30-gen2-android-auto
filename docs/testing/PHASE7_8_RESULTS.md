# GD13MY Phase 7·8 에뮬레이터 시험판

한국형 `GD13MY.KOR.SOP.00.061`의 순정 CE BIN과 지도 가상 매체를 사용한다. 현재 실행기는 `build/gd13my-native-menu/gd13my-aa-native-menu.img`를 `DiskA`에 적용한다. [이미지 검증](../build/gd13my-native-menu/image.json) · [부팅 및 장치 구조](EMULATOR_ARCHITECTURE.md)

## 구성과 동작

| 구성 | 변경 |
|---|---|
| `GDdNavi.exe`, `nfdNaviGui_lit.gcf` | 순정 `내비 메뉴`에 Android Auto 실행 항목을 추가했다. 기존 `내비설정 → 기타 → Android Auto`에서 설정한다. 실행 항목은 순정 버튼 입력으로 CE USB 연결을 시작한다. |
| `uComH_New.exe` | 자동 연결 옵션이 켜져 있으면 `동의함` 입력을 처리한 순정 내비가 첫 준비 완료 ACK를 보낼 때 CE USB 등록 대기를 시작한다. 설정이 꺼져 있으면 수동 진입을 사용한다. |
| `i30aa.exe`, `i30usb.dll` | 지원 폰의 AOA와 Android Auto 버전 교환을 시도한다. 수동 진입은 유한 대기이고, 자동 진입은 옵션을 해제할 때까지 USB를 대기한다. |
| 부팅 경고 | 순정 화면은 정지 상태에서 조작하고 실제 교통 법규를 따르라는 안전 고지이며 `동의함` 입력을 요구한다. 순정 `systemCfg.xml`에서 `window="true"`를 확인했다. 시험판에서 2초 자동 동의와 이전 v6의 동의 옵션을 제거했다. 자동 연결을 켜도 경고 화면의 동의 상태를 변경하지 않는다. |
| 같은 창에서 시동 시험 | `시동 끄기`가 게스트를 정리하고 `DiskA` 쓰기를 저장한다. `시동 켜기`는 같은 창에서 저장된 설정을 복원해 콜드 부팅한다. 새 이미지용 프로필을 사용한다. |

새 후보의 ARM 빌드와 FAT32 이미지 재읽기를 확인했다. 파일 세 개를 수정하고 ARM PE 두 개를 추가했으며, 나머지 순정 파일 116개는 원본과 바이트 단위로 일치한다. 새 후보 부팅과 실폰 투사는 검증 전이다. CE 경로는 버전 교환까지이며 TLS, 서비스 채널과 영상 디코딩·출력이 필요하다. [이미지 검증](../build/gd13my-native-menu/image.json) · [CE 포팅 상태](CE_PORTING_STATUS.md)

CE 감독기에서 후방카메라·주차 화면·차량 경고가 투사 화면을 선점하고, 활성 순정 Bluetooth 음악·통화·우선 경고음이 투사 오디오를 선점하도록 화면과 오디오 권한을 분리했다. 순정 Bluetooth 음악을 듣는 동안 영상 세션은 유지하는 정책이다. 여기에 순정 `LibVideo.dll`과 오디오 상태를 연결하고 실제 화면·스피커 전환을 검증해야 한다. [순정 영상·오디오 경로](VIDEO_AUDIO_ANALYSIS.md)

## 무선 Android Auto

**Bluetooth만으로 무선 Android Auto 투사를 구성할 수 없다.** Google은 최초 무선 연결의 Bluetooth 페어링과 5 GHz Wi‑Fi 호환 요건을 각각 명시한다. [Google 설정 절차](https://support.google.com/androidauto/answer/6348029?hl=ko) · [Google 호환 요건](https://support.google.com/androidauto/answer/6348019?hl=ko)

순정 구성에서 `GDDPComH.exe`와 `btHAbigP.exe`, `BTDB.dll`을 확인했다. 실행 파일의 Parrot 부트로더·펌웨어 파일명은 별도 Parrot 계열 모듈 경로의 근거다. 순정 프로필 기능의 흔적으로 통화 상태, 주소록 동기화, 스트리밍, AVRCP 서비스를 확인했다. REA가 읽은 `btHAbigP.exe`의 PE import는 `coredll.dll`, `osAPI.dll`, `HMI.dll`, `BTDB.dll`이다. 정확한 모듈 번호, Bluetooth 버전, 각 프로필의 버전과 Android Auto용 협상 API는 확인되지 않았다.

CE BIN에는 TCP/IP 표식과 `ndis.dll`이 있다. 이 자료에서 동작하는 5 GHz Wi‑Fi 칩이나 GD13MY 전용 WLAN 드라이버를 식별하지 못했다. USB Wi‑Fi는 해당 칩셋의 CE 6 ARM 드라이버, 5 GHz 동작, Android Auto 협상을 검증할 때 후보가 된다. 외부 Wi‑Fi 모듈도 호스트 연동 검증이 필요하다. 이 시험판의 구성은 유선 USB다.

## 실행 및 피드백

프로젝트 루트의 PowerShell에서 실행한다.

```powershell
.\tools\run_gd13my_phase78.ps1
```

반복 시험에는 `-AutoCalibrate`를 지정할 수 있다. 순정 터치 보정 앱의 다섯 표식과 보정 결과 화면을 가상 터치로 처리한다. 이후 순정 안전 고지에서는 사용자 입력을 기다린다. `-GuestClockMHz`는 가상 CPU와 타이머의 비율을 비교하는 벤치 옵션이며 기본은 4.5 MHz다. 부팅 종료 보고서의 `wall_seconds_from_guest_init`에 첫 LCD 화면, 내비 준비와 CE USB 버전 응답의 경과 시간이 기록된다.

기본 실행기는 수정 APP 이미지, CE 커널 및 지도 렌더러 참조 파일을 내부 드라이브의 `%LOCALAPPDATA%\i30-gd13my\phase78-runtime`에 복사해 재사용한다. 게스트 LCD와 로그도 해당 폴더의 `logs`에 기록한다. 전체 지도 매체와 순정 원본 및 설정 프로필 경로는 유지한다. 자세한 WinCE API 추적은 `-BootTrace`로 켤 수 있다. 별도 지도 미리보기는 뷰어의 `--show-map-preview`가 활성화된 경우에만 PNG를 생성하며, 순정 화면의 지도 출력은 기본 실행에도 제공한다.

같은 APP 이미지의 Windows 파일 캐시를 끈 읽기 시험에서 순차 64 MiB는 F: 19.9 MiB/s, C: 1,664.3 MiB/s였다. 4 KiB 위치 500곳은 F: 444.4 ms, C: 50.5 ms였다. 이 수치는 저장장치 측정이며 전체 부팅 시간은 아니다. 800×480 순정 화면 하나를 반복 압축한 시험에서 PNG 압축 시간은 평균 8.31 ms에서 2.49 ms로 줄었고, 풀어낸 픽셀은 동일했다.

1. 창에 흰색 터치 보정 화면이 나오면 십자가를 하나씩 잠시 누른 뒤 떼고 마지막 보정 완료 입력을 한다. 가상 장치 초기화와 지도 로딩에는 수 분이 걸릴 수 있다. 다음 실행에도 터치 보정 화면이 나올 수 있다.
2. 순정 `주의` 화면에서 `동의함`이 회색 글씨로 비활성화된 동안에는 로딩을 기다린다. 버튼이 활성화되면 내용을 읽고 직접 누른다. 내비가 로딩을 마쳤다는 상태 표시가 나온 뒤 `F2`를 누른다. 지도가 전면에 표시되면 `F2`를 한 번 더 눌러 메뉴를 열고 `내비설정 → 기타 → Android Auto`를 선택한다.
3. 자동 연결을 보려면 옵션을 켜고 `저장`을 누른 뒤, 같은 창에서 `시동 끄기`, `시동 켜기`를 순서대로 누른다. 부팅 후 활성화된 `동의함`을 누른다. 수동 연결은 순정 `내비 메뉴 → Android Auto`로 시작한다.
4. 지정한 실폰 포트가 `1-2`라면 `.\tools\run_gd13my_phase78.ps1 -UsbPort 1-2`로 시작한다. 포트는 CE USB 등록 알림 뒤 가상 호스트에 연결된다. 액세서리 재열거 후에도 연결이 실패하면 순정 설정의 `USB 연결 시험`과 USB 로그에서 단계를 확인한다.
5. 문제가 발생하면 화면 단계, 눌렀던 버튼, 기대 결과와 관찰 결과를 함께 남긴다. `build/gd13my-boot`의 최신 `.png`, `.serial.log`, `.json`과 USB 시험의 `.usb-host.log`가 진단 근거다.

## 이전 이미지 검증 기록

| 시험 | 결과 |
|---|---|
| 이미지와 원본 | 원본 GD13MY 구성, 추출 커널, 전체 가상 매체 26개 항목의 전후 SHA-256이 일치했다. 소형 이미지의 순정 파일 119개 가운데 변경 대상 3개를 제외한 116개가 일치했고 ARM PE 두 개가 추가됐다. [원본 해시](../build/gd13my-phase78/original-after.json) · [이미지 감사](../build/gd13my-phase78/image-audit.json) |
| ARM 설정·시작 코드 | 기본 꺼짐, 저장·해제, 이전 동의 플래그 무시, NAVI 시작 중복 억제와 시작 실패 복귀를 확인했다. 모의 USB ABI에서 AOA 요청, 버전 응답, 파이프·전송 및 등록 정리를 확인했다. [시작 시험](../build/gd13my-phase78/test-arm-startup.json) · [USB·설정 시험](../build/gd13my-phase78/test-arm-usb.json) |
| 회귀 | Python 73개가 통과했다. 첫 실행에서는 PC 영상 회귀 1개가 25초를 넘겼으며, 단독 재시험과 전체 재시험이 통과했다. [전체 재시험](../build/gd13my-phase78/regression-final.log) |
| 실폰 ARM 시험 | 이전 액세서리 연결에서는 유효하지 않은 버전 응답을 받았다. 폰 재연결 후 임시 WinUSB에서 동일 ARM DLL로 AOA 요청, `18d1:2d00` 재열거, 실제 Android Auto **1.7** 응답을 확인했다. 이 시험은 Windows에서 USB I/O를 연결한 ARM DLL 단독 실행이다. [처음 시험](../build/gd13my-phase78/arm-phone-probe.jsonl) · [새 연결 시험](../build/gd13my-phase78/arm-phone-fresh.jsonl) |
| 첫 콜드 부팅 | 수정 DiskA를 순정 CE BIN으로 시작했다. `AVNSysInit.exe`, GWES와 `Touch_Calib.exe` 실행, 보정 파일 쓰기 및 시스템 관리자의 LCD 전환을 확인했다. 순정 내비 홈 전환이 정체된 뒤 이 실행을 종료했다. [부팅 결과](../build/gd13my-phase78/boot-default.json) · [UART 로그](../build/gd13my-phase78/boot-default.serial.log) |
| 경고 화면 대조 | 다른 콜드 부팅에서 순정 주의 화면과 로딩 중 회색 버튼을 확인했다. 버튼 활성화 뒤 벤치 입력을 보냈고 순정 `BUTTON_PUSH_AGREE_ON`과 `PATH_Navi` 등록을 관측했다. [경고 화면](../build/gd13my-phase78/stock-warning-loading.png) · [순정 UART](../build/gd13my-phase78/boot-4mhz.serial.log) |
| 자동 연결과 CE USB | 별도 QA 프로필에 저장된 옵션으로 콜드 부팅했다. 순정 CE의 시작 코드가 `i30aa.exe`를 실행했고, 기본 Windows 삼성 드라이버에서 접근이 실패하자 대기 시간이 끝났다. WinUSB 전환 뒤 순정 CE가 폰을 열거했지만 USB 시험은 이미 종료돼 버전 응답은 ARM DLL 단독 시험에서 확인했다. [게스트 UART](../build/gd13my-phase78/boot-phone.serial.log) · [가상 USB 로그](../build/gd13my-phase78/boot-phone.usb-host.log) |

### 재개 후 콜드 부팅과 새 폰 시험

| 시험 | 결과 |
|---|---|
| 순정 내비와 메뉴 | 소프트웨어 지도 렌더러를 사용해 순정 지도를 표시했다. `MAIN mode ACK` 뒤 순정 코드가 F2를 처리했고, 화면에서 `내비설정 → 기타 → Android Auto`에 진입했다. [지도 홈](../build/gd13my-phase78/resume-stock-home.png) · [순정 메뉴](../build/gd13my-phase78/resume-native-menu.png) |
| 설정 쓰기 | 기본 체크 해제 상태를 확인했다. 켜고 저장한 뒤 대화상자를 다시 열어 체크 상태를 확인했다. 정상 종료 뒤 별도 QA 사이드카의 한 섹터를 적용한 FAT32에 `i30auto.opt`가 존재했다. 배포 후보의 기본값은 꺼짐 상태였다. [기본값](../build/gd13my-phase78/resume-native-settings-default.png) · [저장 후 화면](../build/gd13my-phase78/resume-native-settings-saved.png) · [FAT 감사](../build/gd13my-phase78/resume-preference-audit.json) |
| 재부팅 뒤 자동 실행 | 화면에서 저장한 같은 사이드카의 섹터를 복원하고 콜드 부팅했다. 옵션을 읽어 USB 시험 프로세스를 한 번 시작했다. USB를 전달하지 않은 상태에서 정상 타임아웃이 발생했고, 순정 주의 화면은 동의 입력을 기다렸다. [재부팅 UART](../build/gd13my-phase78/boot-resume-saved.serial.log) · [복원된 섹터 수](../build/gd13my-phase78/boot-resume-saved.json) |
| 새 폰의 순정 CE USB | Windows 드라이버 변경 없이 순정 CE가 AOA 2를 요청하고 `18d1:2d01`을 재열거했다. 최초 bulk 출력은 Windows I/O 오류로 실패했다. 같은 순정 설정 창에서 재시험해 **Android Auto 1.7** 응답 `000300080002000100070000`을 받았다. 창을 닫은 뒤 순정 설정 화면으로 복귀했다. [USB 로그](../build/gd13my-phase78/boot-resume-usb.usb-host.log) · [성공 화면](../build/gd13my-phase78/resume-native-usb-version.png) |

이전 폰에는 임시 WinUSB 시험 뒤 삼성 드라이버 롤백을 요청했다. 재개 시 해당 폰은 연결되지 않은 상태여서 복원을 확인하지 못했다. 새 폰의 기본 모드는 삼성 복합 드라이버였으며 테스트 중 Windows 바인딩을 변경하지 않았다. [이전 드라이버 시험 기록](../build/gd13my-phase78/winusb-trial.log) · [새 폰에서 읽기 전용 AOA 조회](../build/gd13my-phase78/resume-phone-readonly.log)

재개 후 Python 회귀 73개가 통과했고 수정 이미지의 SHA-256이 처음 감사와 일치했다. [회귀 로그](../build/gd13my-phase78/resume-regression.log) · [이미지 해시](../build/gd13my-phase78/image-audit.json)

## 이전 Windows 수신기 진단

이전 진단은 CE 버전 교환 이후 USB 핸들을 Windows 수신기에 넘겨 TLS, 디코딩, 터치와 오디오를 처리했다. 현재 표준 실행기는 이 인계와 창의 투사 버튼을 비활성화한다. 원시 뷰어의 진단 옵션과 이전 로그는 별도로 남아 있다.

콜드 부팅한 순정 CE에서 내비 준비 후 모의 TLS 피어를 연결했다. 800×480 H.264 시험 프레임을 출력했고 `순정 화면 우선`과 F2로 순정 지도가 표시됐다. 종료 응답을 받고 USB와 미디어 자원을 반환했다. 회귀 79개는 USB 인계, 터치, 버튼, PCM, 모의 마이크, 우선권과 분리 복귀를 포함한다. [모의 영상](../build/gd13my-phase78/projection-native-mock-frame.png) · [복귀한 순정 화면](../build/gd13my-phase78/projection-native-restored.png) · [모의 투사 로그](../build/gd13my-phase78/boot-projection-validation.projection.jsonl) · [회귀 로그](../build/gd13my-phase78/projection-regression.log)

실폰 거부 시험에서 순정 CE는 1.7 버전 응답을 받았고 Windows 수신기는 같은 USB 핸들로 TLS 응답을 받았다. 의도적으로 신뢰되지 않은 시험용 CA를 넣었을 때 `CERTIFICATE_VERIFY_FAILED`가 발생했고, 영상은 출력되지 않았으며 순정 화면은 유지됐다. 실폰 투사 확인에는 등록된 시험 인증 자료가 필요하다. 호스트 수신기 로그는 `build/gd13my-boot`의 `.projection.jsonl`에 저장한다. [실폰 TLS 거부 로그](../build/gd13my-phase78/boot-projection-untrusted.projection.jsonl) · [거부 뒤 순정 화면](../build/gd13my-phase78/projection-untrusted-stock.png)

## 2016년형 순정 Android Auto 비교

국내 G80 **고급형 2세대 블루링크**의 공식 식별자는 `DHBS.P2ALC.KR`이고 배포 SW는 `DHPE.KOR.SOP.00.057`이다. 미국형 2018 G80의 DIS 설명서는 USB 연결과 `설정 → Phone Projection → Android Auto`를 문서화한다. 미국형의 동작은 국내 빌드의 활성화 여부를 확인하는 근거와 구분한다. [제네시스 국내 SW 목록](https://update.genesis.com/KR/KO/updateNoticeView/software-version) · [2018 G80 DIS 공식 설명서](https://owners.genesis.com/genesis/us/mygenesis/manuals/glovebox-manual/2018/G80/2018-Gensis-G80-DIS-NAV-MANUAL.pdf)

현대의 2016년 미국 서비스 문서에 Android Auto 업데이트 적용 대상으로 Elantra GT (GD)가 포함된다. 현대는 2016–17 Elantra GT의 캐나다 순정 내비를 표준형 4세대로 분류한다. 한국형 2013 i30의 `GD13MY.KOR.SOP.00.061`은 표준형 2세대다. 미국형 GD는 같은 차종 계열의 동작 비교 후보다. 사용자가 말한 국내 고급형 2세대는 차종과 SW 버전으로 식별해야 한다. [현대 미국 서비스 문서](https://static.nhtsa.gov/odi/tsbs/2016/SB-10081532-0699.pdf) · [현대 캐나다 플랫폼 표](https://update.hyundai.com/CA/EN/updateNoticePopup/GJJKD4) · [현대 한국 SW 목록](https://update.hyundai.com/KR/KO/updateNoticeView/software-version)

비교 펌웨어를 확보하면 운영체제와 ARM ABI, USB·영상·오디오 드라이버 의존성을 먼저 확인한다. 연결 상태 전환, 화면 선점·복귀, 오디오 권한을 비교해 GD13MY의 순정 인터페이스에서 구현할 범위를 결정한다. 현재 작업 매체에는 해당 대조 이미지가 없다.

## 이미지 재생성

```powershell
$phasePython = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv\Scripts\python.exe'
$diskPython = '.\tools\venv\gd13my-disk\Scripts\python.exe'
$phaseCompiler = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools\arm-gnu-14.2\bin\arm-none-eabi-gcc.exe'
$phaseBase = Join-Path $env:LOCALAPPDATA 'i30-gd13my\gd13my-media-v2.img'
$phaseOut = 'build\gd13my-native-menu-rebuild'
& $phasePython tools\build_ce_usb.py "$phaseOut\ce" --compiler $phaseCompiler
& $phasePython tools\patch_gd13my_settings.py "$phaseOut\navigation" --compiler $phaseCompiler
& $phasePython tools\patch_gd13my_startup.py "$phaseOut\uComH_New.exe" --compiler $phaseCompiler
& $diskPython tools\build_gd13my_aa_lab.py $phaseBase "$phaseOut\gd13my-aa-native-menu.img" --compact --settings "$phaseOut\ce\i30aa.exe" --navigation-patch "$phaseOut\navigation" --usb-client "$phaseOut\ce\i30usb.dll" --startup-patch "$phaseOut\uComH_New.exe"
```

실제 기기용 산출 단계는 에뮬레이터 검증과 사용자 승인 뒤 본체 부품 번호, HW 리비전, SW 버전, 제조사 검증 정책, 순정 복구 경로를 대조해야 한다. [기존 업데이트 감사](FIRMWARE_PACKAGING.md) · [복구 확인 항목](PHASE6_BRICK_RISK_ASSESSMENT.md)
