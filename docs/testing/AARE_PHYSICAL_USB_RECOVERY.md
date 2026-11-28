# v8 실폰 USB 재연결 확인 — 2026-11-27

`f004f6f` 소스의 뷰어, .061 WinCE, `gd13my-aa-autostart-v8/gd13my-aa-autostart.img`, 삼성 실폰과 기존 AARE 인증서로 같은 USB 포트에서 시험했다. 이미지의 `/i30auto.opt`와 `/i30boot.opt`는 모두 활성 상태였다.

| 조건 | 실폰 결과 |
|---|---|
| 문제 세션 | 처음부터 `18d1:2d01`을 열어 WinCE 설명자와 구성 1을 처리했다. 첫 Bulk OUT은 타임아웃됐다. 뒤이은 `04e8:6860` 연결은 호스트까지 확인했고 WinCE의 설명자 요청은 관찰하지 못했다. |
| 새 세션, 부팅 전에 일반 USB 모드의 폰 연결 | 순정 지도 뒤 guest receiver 한 번 시작. AOA 2 → `18d1:2d01` 재열거 → AAP 1.7 → TLS 1.2 상호 인증 → 서비스 탐색 → 첫 프레임. 왼쪽 아래 런처를 눌러 실폰 앱 목록으로 전환했다. |
| 물리 분리와 재연결 | WinCE 영상 출력권 해제와 순정 지도 복귀 확인. 같은 포트에 재연결한 뒤 새 AOA 전환과 인증, 첫 프레임을 확인했다. |
| 연결을 유지한 채 같은 창에서 시동 끄기·켜기 | 이전 뷰어는 USB 핸들을 반환했다. 새 게스트는 이미 액세서리 모드인 폰의 인터페이스와 설명자를 열었고 첫 Bulk OUT이 다시 타임아웃됐다. |
| 타임아웃 이후 같은 게스트에서 물리 재연결 | 3초 정도 분리 후 같은 포트에 연결했다. 일반 USB 모드에서 AOA 2와 재열거를 거쳐 AAP 1.7, TLS 1.2, 서비스 탐색, 첫 프레임이 다시 성공했다. |
| 기존 v8 DLL에서 지연 재연결 | Windows가 `04e8:6860`을 열었지만 WinCE 설명자 요청이 없었다. 뷰어의 가상 USB 재연결도 같은 상태였다. |
| 새 DLL, 버전 OUT 타임아웃 주입 후 실폰 재연결 | 첫 AAP Version Request 쓰기에 타임아웃을 한 번 주입했고 즉시 원래 USB 전송 경로를 복원했다. 이후 WinCE가 실폰의 일반 USB 설명자를 다시 읽었다. 최종 물리 재연결에서 AOA 2, AAP 1.7, TLS 1.2 상호 인증, 서비스 탐색과 첫 프레임이 성공했다. 케이블을 빼자 순정 지도로 복귀했다. |

재현 조건은 **시동 사이에 물리 폰이 기존 AOA 모드를 유지하는 경우**다. 실패 위치는 AAP 응답을 받기 전 호스트의 Bulk OUT이다. 기존 세션의 Windows 장치 열기 및 WinCE USB 열거까지는 성공했다. ADB 서버나 중복 뷰어는 관찰되지 않았다. 실행기와 자식 Python은 뷰어 하나의 프로세스 트리였다. Android 내부에서 OUT을 수신하지 못한 이유와 사용자가 처음 본 오류의 정확한 문구는 확인하지 못했다. USB 기능 요청 `00/03/0003`, `00/03/0004`의 pipe error는 성공 연결에도 있었다.

지연 재연결 실패의 WinCE 로그에는 `TxCSR_H_Error at EP 1`, `No Driver Found`, `!USBD: Could not load driver for attached device`가 순서대로 있었다. 실행 중 레지스터 스냅샷에서 가상 케이블은 연결됐고 `DEVCTL=0`, `INTRUSBE=0`, IRQ 92 경로 비활성을 관찰했다. 이 상태에서는 가상 포트를 다시 연결해도 게스트가 설명자 요청을 시작하지 않았다. 스냅샷은 `build/p0-usb-repro/live-musb.json`에 있다.

`ce_aa_usb_client.c`는 지원 액세서리 인터페이스의 두 Bulk 파이프를 열면 USB 인터페이스를 인수한다. 이후 AAP 버전 교환이 실패하면 기존 `Failure` 이벤트를 보내고 파이프와 전송을 정리한다. 확인하지 못한 인터페이스와 파이프 열기 실패는 기존처럼 거부한다. [Windows CE USBDeviceAttach API](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms923216%28v%3Dmsdn.10%29)

새 DLL의 주입 시험에서는 동일한 `TxCSR_H_Error at EP 1`을 관찰했고 USBD 드라이버 로드 실패는 기록되지 않았다. 게스트의 후속 설명자 요청과 실제 재인증을 확인했다. 이미 액세서리 모드인 폰을 꽂은 채 시동을 다시 켤 때 최초 타임아웃을 자동으로 피하는 동작은 남아 있다.

뷰어는 AAP Version Request 쓰기가 타임아웃되면 해당 단계와 물리 재연결 안내를 표시하고, 새 버전 요청 시 이전 응답 추적을 비운다. Windows 허브 포트의 전원 재설정에는 관리자 권한이 필요하며 이 세션은 비관리자였다. [Windows USB 포트 재설정 요구사항](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ni-usbioctl-ioctl_usb_hub_cycle_port)

## 실행 이미지와 산출물 대조

DiskA를 읽기 전용으로 열어 SHA-256을 비교했다. 아래 값은 앞 16자리다. v8 이미지의 세 바이너리는 동봉된 `ce/` 빌드와 일치했다. 이전 실폰 연결 성공 이미지와 공개 인증서, AARE 설정 및 등록 피어 pin이 일치했다.

| 바이너리 | v8 실행 이미지 | `h264-final-baseline` 및 `aare-bgra-compare` | 이전 실폰 성공 이미지 |
|---|---|---|---|
| `i30usb.dll` | `dc2e2934987f1e72` | `8546bb15e0b84e68` | `54da76f655ce50ed` |
| `i30nav.dll` | `bcd1ea832b1fef7b` | `bcd1ea832b1fef7b` | `fcb1e02c07138ede` |
| `i30aa.exe` | `d9ffb37d1ae2b109` | `d9ffb37d1ae2b109` | `36140002b83c486c` |

`f004f6f`의 ARMv4T/-Os, BGRA 기본 빌드와 그 직전 BGRA 비교 빌드는 세 모듈 모두 동일하다. v8 `i30usb.dll`은 v7 이미지와 같은 USB 클라이언트다. `f004f6f`의 공통 링커·재배치 변경으로 생성한 DLL을 v8 실행 이미지가 로드했다는 근거는 없다. Cortex-A8, fast-copy 및 NEON 프리셋은 이번 실폰 비교 대상에서 제외했다.

후속 시험 이미지 `build/p0-usb-repro/recovery-build/gd13my-aa-autostart-p0.img`는 v8에서 `i30usb.dll`만 교체했다. 새 DLL SHA-256은 `4bccda24efc0e747a17ff95fc7bf9c877ded2331c1a7fc3d86c95afa1f693b5b`다. 같은 빌드에서 생성한 `i30nav.dll`과 `i30aa.exe`는 v8 파일과 바이트 단위로 일치했다.

## 2026-11-28 재실행: AARE 세션과 화면의 `오류 16`

새 DiskA 상태 파일 `build/p0-usb-repro/p0-fresh-agent-user-diska.sqlite3`로 P0 복구 이미지를 다시 실행했다. 로그는 `build/p0-usb-repro/live-fresh-agent/gd13my-window-20261128-235207-387221.*`에 있다. 부팅, 동의 처리, 자동 투사 시작, `i30 USB attach ready`까지 진행됐다. USB 추적에서는 실폰의 일반 USB 모드 `04e8:6860`에서 AOA 2 요청과 START_ACCESSORY를 보냈고, `18d1:2d01` 재열거까지 확인했다. 그 직후 WinCE의 AAP 버전 요청이 엔드포인트 `0x01`에서 `USB I/O failed: [Errno 5] Input/Output Error`로 실패했고, 게스트는 다시 분리·재열거·AOA 전환을 반복했다. `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임, 앱 목록, 터치 이벤트는 아직 없다.

사용자가 확인한 전체 문구는 `android auto에 오류가 발생했습니다. 통신 오류 16 - 문제가 발생했습니다. 휴대전화 연결을 해제한 뒤 다시 연결하세요.`이며 화면 앱은 **Google Android Auto**였다. 즉 이번 세션은 AARE가 아니라 순정 Android Auto 앱이 액세서리 인터페이스를 열고 오류를 표시했다. **VERIFIED**: Google Android Auto 화면과 오류 문구. **UNKNOWN**: 내부 코드 16의 정확한 의미. 이전에도 순정 Android Auto 세션이 USB를 선점해 AARE의 액세서리 열기가 실패한 기록이 있다. [AARE 진행 기록](../android-auto/aare/PROGRESS.md)

AARE도 Google Android Auto와 같은 AOA 2/AAP 초기 전송을 사용하므로 CE 로그의 `WinCE Android Auto 버전 요청` 자체는 두 앱에서 동일하게 나올 수 있다. 그러나 폰 화면까지 확인한 이번 경우는 Google AA가 세션 소유자다. **VERIFIED**된 CE 측 실패 지점은 TLS 이전의 AAP 버전 교환이며, 인증서/P12/TLS 원인으로 넘어갈 근거는 아직 없다.

당시 진단 복구 순서: Google Android Auto 세션을 닫고 AARE를 포그라운드에 둔 뒤 USB 앱 선택 화면에서 AARE를 선택했다. 연결을 해제한 상태에서 뷰어가 켜진 뒤 케이블을 약 3초 분리했다가 같은 포트에 다시 연결했다. 그 후 USB 추적에서 AAP 1.7, TLS 1.2 상호 인증, 서비스 탐색, 첫 프레임이 재개되는지 확인했다.

최종 흐름에서는 Google AA 강제 종료, 사용 중지, 설정 변경을 요구하지 않는다. 후속 `feature/aare-auto-connect`는 AARE 필터가 model만 본다는 정적 근거를 바탕으로, 기본 model을 유지한 채 AOA version `2.0`으로 새 accessory identity를 만들어 Android의 앱 선택을 AARE + `Always`로 한 번 설정하는 후보를 준비했다. 실제 시도 결과는 아래와 같다. [자동 연결 작업 상태](../android-auto/aare/AARE_AUTO_CONNECT_STATUS.md)

## 재현 기록

- 원래 실패는 `build/gd13my-aa-autostart-v8/live-final/gd13my-window-20261127-123743-477720.*.log`에 있다.
- 부팅과 실폰 분리·재연결은 `build/p0-usb-repro/v8/gd13my-window-20261127-133451-486372.*.log`에 있다.
- 시동 때 기존 AOA로 시작한 실패 및 물리 재연결 복구는 같은 디렉터리의 `gd13my-window-20261127-133940-973236.*.log`에 있다.
- 타임아웃 안내와 기존 v8 DLL의 지연 재연결 실패는 `build/p0-usb-repro/recovery/gd13my-window-20261127-134412-796226.*.log`에 있다.
- 새 DLL의 주입 시험과 실폰 복구는 `build/p0-usb-repro/candidate/gd13my-window-20261127-140009-116428.*.log`에 있다. 시작 시 새 DiskA 상태 파일이 필요하다. 이전 v8 이미지의 상태 파일은 이미지 식별자가 다르다.
- 실행 옵션은 AARE 인계를 따른다. 이 시험은 `-UsbPort auto`, `-Seconds 86400`, `-GuestClockMHz 4.5`, `-UsbClockMHz 12` 및 보존 상태 복제본을 사용했다. [실행 절차](../android-auto/aare/FINAL_HANDOFF.md)

관련 Python 시험 10개가 통과했다. 전체 회귀는 98개 중 97개 통과, 네이티브 GPTimer DLL 환경 조건으로 1개 건너뜀이다. 새 DLL의 ARM fixture는 AAP 타임아웃 및 버전 도중 분리에서 USB 인터페이스 인수와 AAP `Failure` 이벤트, 파이프 정리를 함께 확인했다. 버전 성공, 설정, TLS, 투사 및 순정 터치 경로도 통과했다. 원본은 `build/p0-usb-repro/unittest-candidate.log`와 `arm-candidate-regression.json`이다.

실폰 시험에서 두 자동 실행 옵션을 각각 켠 구성, 둘 다 끈 구성, 후방카메라 선점 및 비정상 프로세스 종료 복구는 미검증이다. 순정 부팅 경고 동의 입력은 약 2초에 자동으로 발생하지 않았다. 이전 시험판에서 자동 동의가 제거된 기록이 있다. [부팅 경고 이력](PHASE7_8_RESULTS.md)

## 2026-11-29: AOA version `2.0` 실폰 시도

`build/aare-auto-connect-v2-image/gd13my-aa-autostart-v2.img`(SHA-256 `78e39559d4b95702e41dd1fae08cb9197228fbc56e35c767253fb2f81b1ef5ab`)를 신규 상태 DB `build/aare-auto-connect-v2-image/live-user-diska.sqlite3`로 실행했다. 이 이미지는 v8과 같은 설정·패치·신원을 쓰고 `i30usb.dll`만 `Android Auto` model + version `2.0`으로 바꿨다. USB 추적 `build/aare-auto-connect-v2-image/live/gd13my-window-20261129-011311-411777.usb-host.log`에서 `18d1:2d01` 재열거까지 확인했으나, 기능 요청 두 건의 `[Errno 32] Pipe error` 뒤 AAP version request가 엔드포인트 `0x01`에서 `[Errno 5] Input/Output Error`로 실패했다. `TLS 1.2`, `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임은 없다. 이 실행의 폰 화면 문구는 보고되지 않았으므로 Google AA 소유 여부는 `UNKNOWN`이다. [자동 연결 상태](../android-auto/aare/AARE_AUTO_CONNECT_STATUS.md)

## 2026-11-29: AOA model `Android Open Automotive Protocol` 이미지 준비

두 번째 단일 변수 후보 `build/aare-auto-connect-oap-image/gd13my-aa-autostart-oap.img`(SHA-256 `34ebac108c5bee41c754a94cac7912e951dd0840581138d5e6ba65f126d8ec46`)를 만들었다. v2와 같은 순정 파일·표시 패치·시작 패치·AARE 신원·자동 실행 옵션을 유지했고, `i30usb.dll`만 `Android Open Automotive Protocol` / version `1.0`(SHA-256 `e8eb02a5eafb205ee418ac071f6ab15ff38160d2ac585ce26837203ef8166c2c`)으로 바꿨다. 매니페스트 `build/aare-auto-connect-oap-image/image.json`의 나머지 해시와 UTC 오프셋은 v8/v2와 같다. ARM projection/stress/navigation fixture와 startup fixture는 종료 코드 0이었다. 신규 상태 DB `build/aare-auto-connect-oap-image/live-user-diska.sqlite3`로 뷰어를 시작했고, 이후 물리 케이블 재연결과 화면 확인 결과는 아래와 같다. 성공 판정은 AARE TLS 인증, `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임이다.

실폰 재연결 결과는 version 후보와 같았다. `build/aare-auto-connect-oap-image/live/gd13my-window-20261129-020606-027911.usb-host.log`에 `18d1:2d01` 재열거, 기능 요청의 `[Errno 32] Pipe error`, AAP version request의 `[Errno 5] Input/Output Error`가 순서대로 있다. TLS, `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임은 없다. 사용자는 앱 선택 화면이나 화면 변화가 없다고 보고했다. **VERIFIED**: OAP model도 이 전화에서 pre-TLS 실패. 설치된 Google AA APK의 accessory filter 값도 확인했다. **UNKNOWN**: 이 세션을 연 앱. [USB 소유권 진단](../android-auto/aare/USB_OWNERSHIP_DIAGNOSIS_20261129.md)

## 2026-11-29: AOA manufacturer 단일 변경 후보

세 번째 후보는 `build/aare-auto-connect-mfg-image/gd13my-aa-autostart-mfg.img`(SHA-256 `ae3390afc9c51a7a160ea5e92868a76f098b41a14a44b814089ed4db2937fd54`)다. model/version은 기본값 `Android Auto`/`1.0`으로 되돌리고 `i30usb.dll`의 manufacturer만 `i30 Research` → `i30 GD13MY AARE`(DLL SHA-256 `46d97934b26cfc0a2a841bb9b6043cc0b7e14f464295f2e6c76d161ba556e390`)로 바꿨다. AARE v1.6.0은 manufacturer를 필터에 쓰지 않아 매칭이 유지되고, Android accessory 기본 앱 키에는 manufacturer가 포함된다는 점을 이용한다. ARM projection/stress/navigation fixture, startup fixture, 전체 Python 회귀 98 run/1 skip/실패 0을 확인했다. 이미지는 빌드만 했고 진단 단계에서 보류한다. agent가 시작한 viewer는 종료했으며 재실행하거나 물리 재연결을 다시 요청하지 않았다.

## 2026-11-29: USB 소유권·전달 경로 진단

ADB 진단으로 설치 APK, Android framework 이벤트, 저장된 accessory preference, CE→host 오류 경로와 과거 성공 이미지 인증 자료를 확인했다. 원본 로그·APK는 커밋하지 않고 `build/usb-ownership-diagnosis-20261129/`에 둔다.

- **VERIFIED** — 설치 AARE 1.6.0의 filter는 model `Android Auto`와 `Android Open Automotive Protocol`뿐이다. manufacturer/description/version/serial은 보지 않는다.
- **VERIFIED** — 설치 Google AA `18.0.664264-release`의 filter resource `0x7f180004`는 `res/9ii.xml`이며 `Android/Android Open Automotive Protocol`, `Android/Android Auto`, `Android/Android`를 허용한다.
- **VERIFIED** — 현재 완충 로그의 02:34·02:35 구간에서 Android는 `USB_ACCESSORY_ATTACHED`를 `net.prototux.aare/.transport.UsbAccessoryActivity`로 해석·시작했다. Google AA는 같은 구간에서 accessory handshake와 승인까지 갔지만 `USB_ISSUE_FIRST_ACTIVITY_NOT_LAUNCHED`와 projection timeout을 기록했다.
- **VERIFIED** — 현재 저장된 두 accessory preference는 모두 user 0의 `net.prototux.aare`를 가리킨다. chooser가 보이지 않았다는 사실만으로 과거 세션의 전역 기본 앱 상태를 추론하지 않는다.
- **UNKNOWN** — v2/OAP 실폰 세션을 실제로 연 앱. 당시 before/after 폰 로그가 없어 현재 완충 로그를 그 세션에 확장하지 않는다.
- **VERIFIED** — 성공 v8 로그에도 AOA string index 3/4의 `[Errno 32] Pipe error`가 있다. 실패를 구분하는 것은 bulk OUT AAP version request의 `[Errno 5] Input/Output Error`와 version response 부재다.
- **VERIFIED** — 과거 수동 성공 이미지의 네 AARE 인증 자료 파일은 로컬 identity와 파일 단위 SHA-256이 일치한다. 폰에 등록된 client certificate 자체는 `UNKNOWN`이다.

ADB는 진단에만 사용했고 최종 흐름의 사용자 의존성으로 추가하지 않았다. 상위 수준 판단 전까지 manufacturer 후보를 부팅하지 않고 추가 화면 보고나 재연결을 요청하지 않는다. 자세한 근거와 재현 메모는 [USB 소유권·전달 경로 진단](../android-auto/aare/USB_OWNERSHIP_DIAGNOSIS_20261129.md)에 있다.
