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
| Google AA가 version `2.0`을 거부하거나 새 기본 앱 선택을 유도할지 | UNKNOWN | 설치된 Google APK의 filter를 추출하지 않음. 공개 로그에는 `Android Open Automotive Protocol`도 처리 사례 있음 |
| AARE를 USB accessory 기본 앱으로 한 번 선택하면 이후 자동 실행 가능 | INFERRED | AARE v1.6.0 README의 `AARE` + `Always` 안내와 exported `UsbAccessoryActivity`; 실폰 미검증 |
| Google AA의 정확한 accessory filter 값 | UNKNOWN | 설치된 Google APK에서 추출하지 않음 |
| 과거 성공 이미지와 v8/P0의 자동 실행 설정은 다름 | VERIFIED | 성공 이미지에는 `i30auto.opt`/`i30boot.opt`가 없고 수동 시작이었음. v8/P0는 `i30auto.opt=1`, `i30boot.opt=1`, `i30-aare.opt=1`로 자동 실행용임 |
| v8와 P0는 같은 AOA 문자열과 같은 설정을 사용 | VERIFIED | 실제 이미지의 `i30usb.dll` 해시는 다르지만 AOA 문자열 오프셋과 값은 동일. `tls_profile=aare`, `usb_connect=true`, `boot_wait=true`, UTC 오프셋도 동일 |
| v8/P0의 `i30usb.dll`만 다름 | VERIFIED | v8 `dc2e2934…`, P0 `4bccda24…`; `i30nav.dll`/`i30aa.exe`는 동일 |
| 과거 성공 이미지의 `i30usb.dll`은 `54da76f6…`, `i30nav.dll` `fcb1e02c…`, `i30aa.exe` `36140002…` | VERIFIED | `E:\i30-gd13my-images\opencode-resume-perf\touch\gd13my-aare-settings-o2.img`에서 추출 |
| 과거 성공 이미지는 자동 실행 설정이 없음 | VERIFIED | 이미지에 `i30auto.opt`/`i30boot.opt` 없음; 문서상 수동 AARE 세션에서 성공 |
| v8은 신규 세션과 물리 재연결 성공, 시동 OFF→ON 중 AOA 잔존 실패로 문서화됨 | VERIFIED | `docs/testing/AARE_PHYSICAL_USB_RECOVERY.md`의 실행 기록. 정적 재현 아님 |

상세 재현: [실폰 USB 복구 기록](../../testing/AARE_PHYSICAL_USB_RECOVERY.md#2026-11-28-재실행-aare-세션과-화면의-오류-16)

## 정적 분석과 이미지 대조 결과

- **VERIFIED** — AARE v1.6.0은 AOA START를 보내지 않고 `USB_ACCESSORY_ATTACHED`를 받은 뒤 `UsbManager.openAccessory()`를 호출한다. 따라서 USB 선점은 Android 앱 선택과 권한 단계에서 결정된다.
- **VERIFIED** — AARE의 필터는 model만 비교한다: `Android Auto`, `Android Open Automotive Protocol`. GD13MY의 현재 model `Android Auto`는 그대로 일치한다.
- **VERIFIED** — 과거 수동 성공 이미지(`E:\...\gd13my-aare-settings-o2.img`)에는 `i30auto.opt`/`i30boot.opt`가 없고, v8/P0 자동 실행 이미지에는 둘 다 있다. 자동 실행 자체는 과거 수동 성공과 다른 조건이지만, v8은 신규 세션과 물리 재연결 성공도 문서화했다.
- **VERIFIED** — v8과 P0는 `tls_profile=aare`, `usb_connect=true`, `boot_wait=true`, UTC 오프셋이 같고 `i30usb.dll`만 다르다. 두 DLL의 AOA 문자열 값과 오프셋은 같다. Google AA 선점은 DLL 해시 차이로 설명되지 않는다.
- **UNKNOWN** — Google AA의 정확한 AOA filter, 오류 코드 16의 의미, 그리고 version/model 변경이 실제 폰의 기본 앱 선택을 바꾸는지.

원본 이미지·바이너리 해시와 추출 문자열은 `C:\Users\Admin\AppData\Local\Temp\opencode\aare_physical_compare_out\result.json`에 있다. 이 임시 산출물은 실폰 결과가 아니라 파일 대조 증거다.

## 이번 변경

- **VERIFIED** — `src/ce/ce_aa_usb_client.c`와 `tools/build_ce_usb.py`에 AOA model/version 빌드 옵션을 추가했다. 기본값은 기존 `Android Auto` / `1.0`이라 현재 배포 동작은 바뀌지 않는다.
- **VERIFIED** — `--aoa-version 2.0`은 `Android Auto` model을 유지하면서 version만 바꾼다. AARE 필터에 영향이 없고, AARE 포크도 없다.
- **VERIFIED** — `--aoa-model "Android Open Automotive Protocol"`은 두 번째 진단 후보다. 기본값과 함께 ARM fixture에서 전송 문자열을 검증했다.
- **VERIFIED** — `tools/view_gd13my.py`의 버전 응답 실패 메시지가 폰에서 AARE가 액세서리를 열었는지 확인하도록 안내한다. 이 변경은 호스트 진단용이며 CE 배포 코드가 아니다.
- 인증 무시, 권한 우회, Google AA 강제 종료·비활성화, AARE 수정 APK, 비밀키 내장은 포함하지 않는다.

빌드 산출물과 ABI:

| Variant | AOA model | AOA version | `i30usb.dll` SHA-256 |
|---|---|---|---|
| `build/aare-auto-connect-bgra-final` | `Android Auto` | `1.0` | `4bccda24efc0e747a17ff95fc7bf9c877ded2331c1a7fc3d86c95afa1f693b5b` |
| `build/aare-auto-connect-v2` | `Android Auto` | `2.0` | `1b1c6f09445e415db839770c127d270b04917034a8755a5259befebccbcca666` |
| `build/aare-auto-connect-oap-final` | `Android Open Automotive Protocol` | `1.0` | `e8eb02a5eafb205ee418ac071f6ab15ff38160d2ac585ce26837203ef8166c2c` |

세 변형의 `emulate_ce_usb.py --projection --stress-rounds 3 --navigation <v8 GDdNavi.exe>`는 모두 종료 코드 0이었다. 전체 Python 회귀는 98 run, 1 skip, 실패 0이다.

실폰 후보 이미지는 `build/aare-auto-connect-v2-image/gd13my-aa-autostart-v2.img`다. 이미지 SHA-256은 `78e39559d4b95702e41dd1fae08cb9197228fbc56e35c767253fb2f81b1ef5ab`이며, v8과 같은 순정 파일·표시 패치·시작 패치·AARE 신원·자동 실행 옵션(`usb_connect=true`, `boot_wait=true`)을 쓰고 `i30usb.dll`만 `2.0` version으로 바꿨다. `emulate_gd13my_startup.py <v8 uComH_New.exe>`도 종료 코드 0이었다. 아직 실폰에서 실행하지 않았다.

## 작업 분해

### P0 — USB 선점 원인과 펌웨어 측 해결

1. 과거 연결 성공 이미지, 현재 안정판, 실제 로드되는 `i30usb.dll`, AOA 문자열, 장치 매칭 조건, 인증서 프로파일, 자동 실행 옵션, 에뮬레이터 전달 경로를 실제 바이너리 기준으로 비교한다.
2. AARE 1.6.0 APK의 manifest, USB accessory filter, `USB_ACCESSORY_ATTACHED` 처리, 권한 요청, 자동 실행 조건을 정적 분석했다. AARE는 model만 보고, GD13MY의 `Android Auto` model과 일치한다.
3. AARE는 model만 보므로 firmware가 보낼 수 있는 값은 `Android Auto` 또는 `Android Open Automotive Protocol` 두 가지뿐이다. manufacturer/description은 앱 선택 해결책이 아니다.
4. **첫 후보는 version `2.0`이다.** AARE는 version을 무시하지만 Android의 기본 앱 키에는 version이 들어간다. 따라서 기존 Google AA 기본 선택을 건드리지 않고 새 accessory identity에 대한 앱 선택을 유도할 가능성이 있다. 성공한다고 가정하지 않고 한 번에 이 변수만 바꿔 실폰에서 검증한다.
5. version 후보가 실패하면 두 번째 변수로 model을 `Android Open Automotive Protocol`로 바꾼다. Google AA가 이 model도 처리할 수 있으므로 단독 해결책으로 가정하지 않는다.
6. 선택 화면에서 AARE + `Always`를 한 번 설정한 뒤, 이후 재연결에서 Google AA 설정 변경이나 강제 종료 없이 AARE가 자동 실행되는지 확인한다. 단순히 Google AA가 실행되지 않는 것은 성공이 아니다. AARE 자동 실행, TLS 상호 인증, 첫 프레임까지 확인한다.
7. Google AA의 정확한 filter가 필요하면 ADB 진단으로 설치 APK의 manifest/filter를 확인한다. 실제 사용 경로에서는 ADB가 필요하지 않아야 한다.

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

- version `2.0` 이미지로 부팅한 뒤, 앱 선택 화면이 나오면 AARE + `Always` 선택
- AARE 최초 실행, P12 가져오기, 수신기 지문 승인(이미 등록됐다면 불필요)
- 물리 USB 분리/재연결, 폰 잠금 해제, 권한 dialog 승인
- 실제 폰에서 앱 목록/터치/티맵 화면 확인
- version 후보에서 Google AA가 여전히 열리면 model 후보로 한 변수만 바꿔 재시험

Google AA 강제 종료, 사용 중지, 설정 변경은 최종 절차에 포함하지 않는다. 다만 진단 중 이미 열린 Google AA 세션을 닫아야 하는지는 로그와 화면으로 판단한다.

요청 전에 로그로 필요한 최소 동작만 특정한다. 사용자가 직접 닫은 창은 다시 열지 않는다.
