# AARE 자동 연결 및 USB 안정성 — 작업 상태

기준: `main` `704ca5c`에서 분기한 `feature/aare-auto-connect`. 기존 `feature/uiconfig-insets-experiment`, `feature/uyvy-directdraw-backend`는 보존한다. 실제 실행 이미지와 폰 세션을 바꿀 때마다 한 번에 하나의 변수만 바꾼다.

## 성공 기준

최초 AARE 인증서 등록과 시스템 필수 권한 승인 뒤에는 다음이 성립해야 한다.

- 스마트폰 USB 연결만으로 투사가 시작된다.
- 순정 Google Android Auto 설정 변경, 강제 종료, 사용 중지가 필요하지 않다.
- AARE 수동 실행, ADB, USB 디버깅, 루팅이 필요하지 않다.
- 차량 시동 OFF→ON 뒤 자동 재연결된다.
- 다른 차량의 순정 Android Auto 사용에 영향이 없다.
- Android 보안/권한 승인 절차는 우회하지 않는다.

`VERIFIED`는 실제 파일/로그/화면에서 확인한 사실, `INFERRED`는 근거 있는 추론, `UNKNOWN`은 미확인이다. mock, ARM fixture, 가상폰 결과는 실폰 결과로 승격하지 않는다.

## 현재 VERIFIED

| 항목 | 판정 | 근거 |
|---|---|---|
| 2026-11-28 실폰 세션은 Google Android Auto가 화면을 표시 | VERIFIED | 사용자 보고 전체 문구: `android auto에 오류가 발생했습니다. 통신 오류 16 - 문제가 발생했습니다. 휴대전화 연결을 해제한 뒤 다시 연결하세요.` |
| 같은 세션의 CE 로그는 AOA 2 후 첫 AAP 버전 요청 실패 | VERIFIED | `build/p0-usb-repro/live-fresh-agent/gd13my-window-20261128-235207-387221.usb-host.log`: `18d1:2d01` 재열거 후 엔드포인트 `0x01`에서 `[Errno 5] Input/Output Error` |
| TLS, `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임은 아직 없음 | VERIFIED | 동일 로그 세션에 해당 이벤트 없음 |
| 이전에도 순정 Android Auto 세션이 USB를 선점한 기록이 있음 | VERIFIED | `docs/android-auto/aare/PROGRESS.md` |
| 오류 코드 16의 Android 내부 정의 | UNKNOWN | 화면 문구만 확인. 코드 의미 단정 금지 |
| AARE는 AOA 전환을 하지 않고 `USB_ACCESSORY_ATTACHED`를 기다림 | VERIFIED | AARE v1.6.0 `UsbAccessoryActivity`, `ProjectionService.startUsb()` |
| AARE의 accessory filter는 model만 비교 | VERIFIED | `res/xml/accessory_filter.xml`: `Android Auto`, `Android Open Automotive Protocol`; upstream `UsbAccessoryTransport.MODELS` |
| GD13MY의 AOA model은 `Android Auto`로 AARE와 정확히 일치 | VERIFIED | `src/ce/ce_aa_usb_client.c:202-222` |
| manufacturer/description/version/URI/serial은 AARE 필터에 영향을 주지 않음 | VERIFIED | AARE는 model 외 필드를 필터에 쓰지 않음 |
| Android의 USB accessory 기본 앱 선택 키는 manufacturer/model/version | INFERRED | Android framework `AccessoryFilter`가 세 값으로 기본 앱을 조회·저장. 실폰에서 변경 전후 선택 화면은 미확인 |
| AOA version을 `1.0`→`2.0`으로 바꾸면 AARE는 계속 일치 | VERIFIED | AARE 필터는 version을 보지 않음. ARM fixture가 `2.0` 전송을 확인 |
| AOA model을 `Android Open Automotive Protocol`로 바꾸면 AARE는 계속 일치 | VERIFIED | AARE 필터가 두 model을 허용. ARM fixture가 문자열 전송을 확인 |
| version `2.0` 실폰 세션은 TLS 이전에 실패 | VERIFIED | `build/aare-auto-connect-v2-image/live/gd13my-window-20261129-011311-411777.usb-host.log`: AOA 2 → `18d1:2d01` → pipe error → AAP version request `[Errno 5] Input/Output Error`. `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임 없음. 이 실행의 폰 화면 문구는 보고되지 않음 |
| Google AA가 version `2.0`을 거부하거나 새 기본 앱 선택을 유도할지 | UNKNOWN | 실폰 로그만으로 과거 세션의 앱 소유자를 단정할 수 없음. 설치 APK filter는 확인했지만 거부 동작은 미검증 |
| OAP model 실폰 세션도 TLS 이전에 실패 | VERIFIED | `build/aare-auto-connect-oap-image/live/gd13my-window-20261129-020606-027911.usb-host.log`: AOA 2 → `18d1:2d01` → pipe error → AAP version request `[Errno 5] Input/Output Error`. `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임 없음. 사용자 보고는 화면 변화 없음 |
| manufacturer 변경은 AARE 매칭을 유지하면서 Android accessory 키를 바꿀 수 있음 | INFERRED | Android framework의 기본 앱 키는 manufacturer/model/version이고 AARE는 model만 비교. 실폰에서 chooser 변경은 미검증 |
| AARE를 USB accessory 기본 앱으로 한 번 선택하면 이후 자동 실행 가능 | INFERRED | AARE v1.6.0 README의 `AARE` + `Always` 안내와 exported `UsbAccessoryActivity`; 실폰 미검증 |
| Google AA 설치 APK의 accessory filter 값 | VERIFIED | `0x7f180004` → `res/9ii.xml`: `Android/Android Open Automotive Protocol`, `Android/Android Auto`, `Android/Android` |
| 과거 성공 이미지와 v8/P0의 자동 실행 설정은 다름 | VERIFIED | 성공 이미지에는 `i30auto.opt`/`i30boot.opt`가 없고 수동 시작이었음. v8/P0는 `i30auto.opt=1`, `i30boot.opt=1`, `i30-aare.opt=1`로 자동 실행용임 |
| v8와 P0는 같은 AOA 문자열과 같은 설정을 사용 | VERIFIED | 실제 이미지의 `i30usb.dll` 해시는 다르지만 AOA 문자열 오프셋과 값은 동일. `tls_profile=aare`, `usb_connect=true`, `boot_wait=true`, UTC 오프셋도 동일 |
| v8/P0의 `i30usb.dll`만 다름 | VERIFIED | v8 `dc2e2934…`, P0 `4bccda24…`; `i30nav.dll`/`i30aa.exe`는 동일 |
| 과거 성공 이미지의 `i30usb.dll`은 `54da76f6…`, `i30nav.dll` `fcb1e02c…`, `i30aa.exe` `36140002…` | VERIFIED | `E:\i30-gd13my-images\opencode-resume-perf\touch\gd13my-aare-settings-o2.img`에서 추출 |
| 과거 성공 이미지는 자동 실행 설정이 없음 | VERIFIED | 이미지에 `i30auto.opt`/`i30boot.opt` 없음; 문서상 수동 AARE 세션에서 성공 |
| v8은 신규 세션과 물리 재연결 성공, 시동 OFF→ON 중 AOA 잔존 실패로 문서화됨 | VERIFIED | `docs/testing/AARE_PHYSICAL_USB_RECOVERY.md`의 실행 기록. 정적 재현 아님 |
| 과거 수동 성공 이미지를 현재 폰/호스트에서 재실행해도 같은 pre-TLS `[Errno 5]`로 실패 | VERIFIED | `build/success-image-repro-20261129/gd13my-window-20261129-030712-510244.usb-host.log` 14행. firmware/인증서/Google AA 설정 변경 없음 |
| 재실행 세션의 AARE 액티비티·`ProjectionService`·USB FD 확보 | UNKNOWN | 실패 후 ADB가 device를 보지 못해 새 logcat/dumpsys 없음. 기존 02:34·02:35 로그는 별도 세션 |

상세 재현: [실폰 USB 복구 기록](../../testing/AARE_PHYSICAL_USB_RECOVERY.md#2026-11-28-재실행-aare-세션과-화면의-오류-16), [USB 소유권·전달 경로 진단](USB_OWNERSHIP_DIAGNOSIS_20261129.md)

## 정적 분석과 이미지 대조 결과

- **VERIFIED** — AARE v1.6.0은 AOA START를 보내지 않고 `USB_ACCESSORY_ATTACHED`를 받은 뒤 `UsbManager.openAccessory()`를 호출한다. 따라서 USB 선점은 Android 앱 선택과 권한 단계에서 결정된다.
- **VERIFIED** — AARE의 필터는 model만 비교한다: `Android Auto`, `Android Open Automotive Protocol`. GD13MY의 현재 model `Android Auto`는 그대로 일치한다.
- **VERIFIED** — 과거 수동 성공 이미지(`E:\...\gd13my-aare-settings-o2.img`)에는 `i30auto.opt`/`i30boot.opt`가 없고, v8/P0 자동 실행 이미지에는 둘 다 있다. 자동 실행 자체는 과거 수동 성공과 다른 조건이지만, v8은 신규 세션과 물리 재연결 성공도 문서화했다.
- **VERIFIED** — v8과 P0는 `tls_profile=aare`, `usb_connect=true`, `boot_wait=true`, UTC 오프셋이 같고 `i30usb.dll`만 다르다. 두 DLL의 AOA 문자열 값과 오프셋은 같다. Google AA 선점은 DLL 해시 차이로 설명되지 않는다.
- **VERIFIED** — 설치된 Google AA `18.0.664264-release` APK의 `0x7f180004`는 `resources.arsc`에서 `res/9ii.xml`로 확인됐다. 그 XML의 filter는 `Android/Android Open Automotive Protocol`, `Android/Android Auto`, `Android/Android` 세 가지다. 설치 APK SHA-256은 `EE9054FFC513DD317DEA4E1CF3006EC368796249BB059269C680B16B9451991C`. 이전에 이 결합을 `UNKNOWN`으로 둔 것은 simple `Res_value`를 complex entry로 잘못 읽은 파서 오류였다. [진단 근거](USB_OWNERSHIP_DIAGNOSIS_20261129.md#2-설치-apk와-filter-값)
- **VERIFIED** — `dumpsys usb`는 Google AA와 AARE의 filter를 모두 등록하고, 현재 저장된 두 accessory preference는 user 0의 `net.prototux.aare`를 가리킨다. 다만 이는 현재 저장 상태일 뿐 v2/OAP 과거 세션의 소유권을 증명하지 않는다.
- **UNKNOWN** — v2/OAP 세션의 앱 소유자, 오류 코드 16의 의미, version/model/manufacturer 변경이 실제 chooser와 기본 앱 저장을 바꾸는지. chooser 부재만으로 전역 기본 앱 상태를 추론하지 않는다.

원본 이미지·바이너리 해시와 추출 문자열은 `C:\Users\Admin\AppData\Local\Temp\opencode\aare_physical_compare_out\result.json`에 있다. 이 임시 산출물은 실폰 결과가 아니라 파일 대조 증거다.

## 2026-11-29 진단 추가 결과

[전체 근거](USB_OWNERSHIP_DIAGNOSIS_20261129.md)를 커밋했다. 요약:

- **VERIFIED** — 현재 완충 로그의 02:34·02:35 구간에서는 Android가 `USB_ACCESSORY_ATTACHED`를 `net.prototux.aare/.transport.UsbAccessoryActivity`로 해석·시작했다. 같은 구간에서 Google AA는 accessory handshake와 승인까지 갔지만 `USB_ISSUE_FIRST_ACTIVITY_NOT_LAUNCHED`와 projection timeout을 기록했다.
- **UNKNOWN** — 이 구간이 v2/OAP 과거 실패와 같은 앱 소유권이었는지. 당시 before/after 폰 로그가 없어 과거 세션으로 확장하지 않는다.
- **VERIFIED** — 후보 v2/OAP 모두 AOA 2 → `18d1:2d01` → 표준 Device SET_FEATURE(index 3/4) pipe error → bulk OUT AAP version request `[Errno 5]` 순서다. pipe error는 성공 v8 로그에도 있으므로 단독 원인이 아니다.
- **VERIFIED** — 별도 02:34·02:35 구간에서 AARE 액티비티와 `ProjectionService`가 시작됐지만 framework가 `/dev/usb_accessory`를 열지 못했고, Google AA는 `NO_FDS_OPEN`을 기록했다. 이 구간을 아래 03:07 재실행 세션으로 확장하지 않는다.
- **VERIFIED** — 과거 수동 성공 이미지의 `i30-aare-ca.pem`, `i30-aare-client.pem`, `i30-aare-client-key.pem`, `i30-aare-peer-sha256.txt`는 현재 로컬 identity와 파일 단위 SHA-256이 모두 일치한다. 폰에 등록된 client certificate 자체는 여전히 `UNKNOWN`.
- **VERIFIED** — 같은 과거 수동 성공 이미지를 현재 폰/호스트에서 재실행하면 63 B descriptor → `SET_CONFIGURATION` → bulk OUT `[Errno 5]`로 실패한다. 03:07 세션의 Android 앱/FD 이벤트는 `UNKNOWN`이고, 실패 후 ADB는 `- waiting for device -`로 로그 덤프가 막혔다. manufacturer 후보 이미지를 부팅한 것은 아니다.
- 진단 로그의 UTF-16 처리, APK 해시, 정확한 filter 값, CE→host 오류 경로와 source line은 위 문서에 있다. 원본 75 MB logcat과 APK는 커밋하지 않았다.

## 이번 변경

- **VERIFIED** — `src/ce/ce_aa_usb_client.c`와 `tools/build_ce_usb.py`에 AOA model/version 빌드 옵션을 추가했다. 기본값은 기존 `Android Auto` / `1.0`이라 현재 배포 동작은 바뀌지 않는다.
- **VERIFIED** — `--aoa-version 2.0`은 `Android Auto` model을 유지하면서 version만 바꾼다. AARE 필터에 영향이 없고, AARE 포크도 없다.
- **VERIFIED** — `--aoa-model "Android Open Automotive Protocol"`은 두 번째 진단 후보다. 기본값과 함께 ARM fixture에서 전송 문자열을 검증했다. 같은 이미지의 실폰 세션도 version 후보와 동일하게 AAP version request에서 실패했다.
- **VERIFIED** — `--aoa-manufacturer` 빌드 옵션을 추가했다. 기본값은 기존 `i30 Research`라 배포 동작은 바뀌지 않는다. `i30 GD13MY AARE` 후보는 model/version을 기본값으로 되돌리고 manufacturer만 바꾼다. AARE 필터는 manufacturer를 보지 않지만 Android accessory 기본 앱 키에는 포함된다.
- **VERIFIED** — `tools/view_gd13my.py`의 버전 응답 실패 메시지가 폰에서 AARE가 액세서리를 열었는지 확인하도록 안내한다. 이 변경은 호스트 진단용이며 CE 배포 코드가 아니다.
- 인증 무시, 권한 우회, Google AA 강제 종료·비활성화, AARE 수정 APK, 비밀키 내장은 포함하지 않는다.

빌드 산출물과 ABI:

| Variant | AOA manufacturer | AOA model | AOA version | `i30usb.dll` SHA-256 |
|---|---|---|---|---|
| `build/aare-auto-connect-bgra-final` | `i30 Research` | `Android Auto` | `1.0` | `4bccda24efc0e747a17ff95fc7bf9c877ded2331c1a7fc3d86c95afa1f693b5b` |
| `build/aare-auto-connect-v2` | `i30 Research` | `Android Auto` | `2.0` | `1b1c6f09445e415db839770c127d270b04917034a8755a5259befebccbcca666` |
| `build/aare-auto-connect-oap-final` | `i30 Research` | `Android Open Automotive Protocol` | `1.0` | `e8eb02a5eafb205ee418ac071f6ab15ff38160d2ac585ce26837203ef8166c2c` |
| `build/aare-auto-connect-mfg-final` | `i30 GD13MY AARE` | `Android Auto` | `1.0` | `46d97934b26cfc0a2a841bb9b6043cc0b7e14f464295f2e6c76d161ba556e390` |

네 변형의 `emulate_ce_usb.py --projection --stress-rounds 3 --navigation <v8 GDdNavi.exe>`는 모두 종료 코드 0이었다. 전체 Python 회귀는 98 run, 1 skip, 실패 0이다. manufacturer 추가 후 회귀 로그는 `build/aare-manufacturer-unittest.log`다.

실폰 후보 이미지 `build/aare-auto-connect-v2-image/gd13my-aa-autostart-v2.img`(SHA-256 `78e39559d4b95702e41dd1fae08cb9197228fbc56e35c767253fb2f81b1ef5ab`)는 v8과 같은 순정 파일·표시 패치·시작 패치·AARE 신원·자동 실행 옵션으로 `i30usb.dll`만 `2.0` version으로 바꿨다. 실폰 실행은 위 로그처럼 AAP version request에서 실패했고, 화면 보고가 없어 Google AA/AARE 중 앱 소유자는 `UNKNOWN`이다.

두 번째 후보 이미지는 `build/aare-auto-connect-oap-image/gd13my-aa-autostart-oap.img`다. 이미지 SHA-256은 `34ebac108c5bee41c754a94cac7912e951dd0840581138d5e6ba65f126d8ec46`이며, v2와 같은 순정 파일·표시 패치·시작 패치·AARE 신원·자동 실행 옵션(`usb_connect=true`, `boot_wait=true`)을 쓰고 `i30usb.dll`만 `Android Open Automotive Protocol` model로 바꿨다. 내비/표시 패치 디렉터리는 v8과 같은 `build/gd13my-aa-autostart-v8/navigation`과 `build/codex-authentication-resolution/display`를 사용했고, 다른 패치 디렉터리에서 나온 최초 빌드는 폐기했다. ARM projection/stress/navigation fixture와 startup fixture는 종료 코드 0이었다. 실폰 세션은 v2와 동일하게 AAP version request에서 실패했고 사용자 보고는 화면 변화 없음이었다.

세 번째 후보 이미지는 `build/aare-auto-connect-mfg-image/gd13my-aa-autostart-mfg.img`다. 이미지 SHA-256은 `ae3390afc9c51a7a160ea5e92868a76f098b41a14a44b814089ed4db2937fd54`이며, v8/v2와 같은 순정 파일·표시 패치·시작 패치·AARE 신원·자동 실행 옵션을 유지하고 `i30usb.dll`의 manufacturer만 `i30 GD13MY AARE`로 바꿨다. model/version은 기본값 `Android Auto`/`1.0`으로 되돌렸다. 이미지는 빌드만 했고 진단 단계에서 보류한다. agent가 시작한 viewer는 종료했으며 재실행하지 않는다.

## 작업 분해

### P0 — USB 선점 원인과 펌웨어 측 해결

1. 과거 연결 성공 이미지, 현재 안정판, 실제 로드되는 `i30usb.dll`, AOA 문자열, 장치 매칭 조건, 인증서 프로파일, 자동 실행 옵션, 에뮬레이터 전달 경로를 실제 바이너리 기준으로 비교한다.
2. AARE 1.6.0 APK의 manifest, USB accessory filter, `USB_ACCESSORY_ATTACHED` 처리, 권한 요청, 자동 실행 조건을 정적 분석했다. AARE는 model만 보고, GD13MY의 `Android Auto` model과 일치한다.
3. AARE는 model만 보므로 firmware가 AARE 매칭을 유지하려면 model은 `Android Auto` 또는 `Android Open Automotive Protocol`이어야 한다. description은 Android 기본 앱 키에 포함되지 않는다.
4. **첫 후보 version `2.0`은 실폰에서 AAP version request 실패로 끝났다.** AARE는 version을 무시하지만 Android의 기본 앱 키에는 version이 들어간다. 실제 세션에서 TLS 이전에 실패했고 화면 보고가 없어 앱 소유자는 확정하지 않았다.
5. 두 번째 변수 model `Android Open Automotive Protocol`도 같은 실패였다. 세 번째 변수 manufacturer 후보는 빌드만 했고 보류한다. AARE는 manufacturer를 보지 않지만 Android 기본 앱 키에는 포함된다.
6. 설치 APK filter, Android resolve 이벤트, 저장된 preference, CE→host 오류 경로와 과거 성공 이미지 인증 자료까지 진단 증거를 커밋·푸시했다. 구현 방향은 상위 수준 판단을 기다린다. 새 이미지/APK 변형이나 재연결 요청은 하지 않는다.
7. ADB는 진단에만 사용했다. 실제 사용 경로에서는 ADB, USB debugging, root, Google AA 설정 변경·강제 종료가 필요하지 않아야 한다.

### P0 — 자동 복구

실패 유형별로 허용된 복구만 사용한다: AOA 전환 실패, AAP Version Request 타임아웃, 이전 AOA 세션 잔존, 시동 OFF→ON, USB 전송 오류, TLS 인증 실패, 폰 재부팅/잠금, projection 비정상 종료.

금지: 무한 재시도, 무조건 USB 리셋, 인증 실패 무시, 권한 우회, 순정 지도/카메라 프로세스 종료. 호스트 에뮬레이터 전용 복구와 CE 배포 가능 복구를 문서에서 분리한다.

### P0 — 스마트폰 호환성

`ce_aa_usb_client.c`의 삼성 VID/PID 의존을 확인하고, 일반 USB 모드/MTP/ADB 조합, AOA 지원 판별, 인터페이스·디스크립터 판별, 저장장치 기능 충돌 방지를 검토한다. 실제 시험하지 않은 기종은 호환하다고 쓰지 않는다.

### P1 — 연결 속도/UI

USB 인식, AOA 전환, 재열거, AAP 버전, TLS, 서비스 탐색, 첫 영상까지 구간별 시간을 측정한다. 순정 UI의 연결 상태 표시를 우선 재사용하고, 대기/인증/완료/자동 복구/인증서 오류를 구분한다.

### P1 — 전용 앱 필요성

펌웨어와 기존 AARE로 목표 달성이 가능하면 포크하지 않는다. 불가능한 제약이 확인된 경우에만 최소 수정 APK를 검토한다. 라이선스, 전용 USB 식별자, Keystore, 순정 AA 공존, Play Protect EFP, 서명 배포, 비밀키/비밀번호 내장 금지를 평가한다.

### P2 — 기존 실험 연계

자동 연결이 안정된 뒤 티맵/UiConfig/Insets, UYVY DirectDraw, 후방카메라 우선권, 순정 복귀, 부팅 경고 자동 동의 누락을 각각 단일 변수로 시험한다.

## 사용자 조작이 필요한 지점

아래는 에뮬레이터가 대신할 수 없으므로 화면/케이블 조작을 요청한다.

- manufacturer 후보 이미지는 보류 중이다. 상위 판단 전까지 부팅·선택 요청을 하지 않는다
- AARE 최초 실행, P12 가져오기, 수신기 지문 승인(이미 등록됐다면 불필요)
- 물리 USB 분리/재연결, 폰 잠금 해제, 권한 dialog 승인
- 실제 폰에서 앱 목록/터치/티맵 화면 확인
- 진단 단계에서는 추가 화면 보고를 요청하지 않는다. 실제로 관찰된 문구만 위 로그에 기록했다

Google AA 강제 종료, 사용 중지, 설정 변경은 최종 절차에 포함하지 않는다. 다만 진단 중 이미 열린 Google AA 세션을 닫아야 하는지는 로그와 화면으로 판단한다.

요청 전에 로그로 필요한 최소 동작만 특정한다. 사용자가 직접 닫은 창은 다시 열지 않는다.
