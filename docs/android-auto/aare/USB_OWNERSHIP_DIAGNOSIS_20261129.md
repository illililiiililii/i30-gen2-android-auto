# 2026-11-29 USB accessory 소유권·전달 경로 진단 근거

기준 브랜치: `feature/aare-auto-connect`, 커밋 `6ad5e09`. 이 문서는 진단 증거만 정리한다. 새 firmware 후보, AOA 식별자 변경, 전용 APK, 실폰 재연결 요청은 포함하지 않는다. 원본 로그와 이미지는 `build/usb-ownership-diagnosis-20261129/` 등 로컬에 두고 커밋하지 않는다.

`VERIFIED`는 실제 파일·로그·실행 중 이벤트에서 확인한 사실, `INFERRED`는 근거 있는 추론, `UNKNOWN`은 미확인이다. mock/ARM/가상폰 결과를 실폰 결과로 승격하지 않는다.

## 1. 요약

| 항목 | 판정 | 핵심 근거 |
|---|---|---|
| 실폰 단말은 Android 15 / SDK 35 / `SM_F721N` / `R3CT80QSGMA` | VERIFIED | `device-props.txt`, `adb devices` |
| AARE 설치본은 `net.prototux.aare` 1.6.0 / versionCode 10600 | VERIFIED | `aare-package.txt` |
| Google AA 설치본은 `com.google.android.projection.gearhead` 18.0.664264-release / versionCode 180664264 | VERIFIED | `google-aa-package.txt` |
| 두 앱 모두 user 0에 설치, Google AA의 `:car`·`:projection` 프로세스와 AARE 프로세스가 동시에 관측됨 | VERIFIED | `users.txt`, `ps.txt` |
| AARE 설치 APK의 USB accessory filter는 `model`만 사용: `Android Auto`, `Android Open Automotive Protocol` | VERIFIED | 설치 APK `res/S5.xml`, `aare-xml-scan.json` |
| Google AA 설치 APK의 accessory filter 리소스는 `0x7f180004` → `res/9ii.xml`이며 세 조합을 허용 | VERIFIED | 설치 APK `AndroidManifest.xml`, `resources.arsc`, `res/9ii.xml` |
| Android `dumpsys usb`도 Google AA와 AARE의 위 filter를 모두 등록 목록에 표시 | VERIFIED | `dumpsys-usb.txt:1156-1220` |
| 02:34·02:35 현재 진단 세션에서 Android가 `USB_ACCESSORY_ATTACHED`를 AARE 액티비티로 해석·시작 | VERIFIED | `logcat-filtered.txt`의 `UsbProfileGroupSettingsManager`, `ActivityTaskManager` 구간 |
| 같은 02:35 구간에서 Google AA가 USB accessory handshake를 시작하고 승인했지만 첫 activity를 띄우지 못함 | VERIFIED | `GH.ConnLoggerV2` event 57-76 |
| AARE 액티비티와 `ProjectionService`가 시작됐어도 Android가 `/dev/usb_accessory`를 열지 못함 | VERIFIED | 02:34:04.562, 02:34:05.066, 02:35:17.215의 `UsbDeviceManagerJNI: could not open /dev/usb_accessory` |
| Google AA가 활성 세션에서 FD를 열지 못했다고 기록 | VERIFIED | 02:35:17.222 `GH.ConnLoggerV2` event 70 `USB_ACCESSORY_ATTACHED_WHILE_ACTIVE_NO_FDS_OPEN` |
| v2/OAP 실패 세션의 실제 앱 소유권 | UNKNOWN | 당시 폰 로그의 before/after 스라이스가 없음. 현재 완충 로그로 과거 세션을 대표할 수 없음 |
| 저장된 accessory 기본 앱이 AARE로 표시됨 | VERIFIED | `dumpsys-usb.txt:1228-1251`. 다만 특정 과거 세션의 소유권을 증명하지는 않음 |
| `통신 오류 16`의 내부 의미 | UNKNOWN | 화면 문구만 존재 |
| 과거 성공 이미지의 AARE 인증 자료 4개 파일과 현재 `build/aare-tools/identity`는 파일 단위 SHA-256이 모두 일치 | VERIFIED | 이미지 FAT 파티션 판독, 해시 비교 |
| 과거 수동 성공 이미지를 현재 폰/호스트에서 재실행해도 첫 AAP version request가 같은 `[Errno 5]`로 실패 | VERIFIED | `build/success-image-repro-20261129/*.usb-host.log` 14행 |
| v2/OAP 공통 실패 지점은 bulk OUT AAP version request의 `[Errno 5] Input/Output Error` | VERIFIED | 두 `*.usb-host.log` 13행 |
| `[Errno 32] Pipe error` 자체는 과거 성공 세션에도 나타나므로 단독 실패 원인이 아님 | VERIFIED | 성공 v8 로그 28-29행과 실패 로그 11-12행 비교 |
| 재열거 후 accessory config descriptor 길이 63 B는 실패 세션, 55 B는 v8 성공 세션에서 관측 | INFERRED | 상관관계만; descriptor 내용과 인과관계는 미확인 |

## 2. 설치 APK와 filter 값

설치 APK 해시:

| APK | 크기 | SHA-256 |
|---|---:|---|
| Google AA installed base | 35,247,723 | `EE9054FFC513DD317DEA4E1CF3006EC368796249BB059269C680B16B9451991C` |
| AARE installed base | 18,700,995 | `75D5A6778980BDC34F3545F984396AD9B591CC22909A3E0E22E0CC8E9EC4F281` |
| `build/aare-tools/aare-1.6.0.apk` | 18,700,995 | `75D5A6778980BDC34F3545F984396AD9B591CC22909A3E0E22E0CC8E9EC4F281` |

### 2.1 AARE

`build/usb-ownership-diagnosis-20261129/aare-xml-scan.json`의 `res/S5.xml`:

```text
<usb-accessory model="Android Auto" />
<usb-accessory model="Android Open Automotive Protocol" />
```

`manufacturer`, `description`, `version`, `serial` 필드는 filter에 없다. 설치 APK의 `AndroidManifest.xml`도 `USB_ACCESSORY_ATTACHED`와 `@0x7f100000` resource를 참조한다. 따라서 현 AARE는 AOA model만 보고 GD13MY의 현재 model `Android Auto`와 일치한다.

### 2.2 Google AA

설치 APK의 `AndroidManifest.xml`은 USB accessory meta-data resource `0x7f180004`를 참조한다. `resources.arsc`에서 이 ID를 올바르게 읽으면 다음과 같다.

```text
rid 0x7f180004
type xml
key car_usb_accessory_filter
entry esize 8, flags 0x0
Res_value dtype 0x3 (STRING), data index 554
global string 554 = res/9ii.xml
```

`res/9ii.xml`의 실제 값:

```text
<usb-accessory manufacturer="Android" model="Android Open Automotive Protocol" />
<usb-accessory manufacturer="Android" model="Android Auto" />
<usb-accessory manufacturer="Android" model="Android" />
```

이전 진단에서 `0x7f180004`의 결합을 `UNKNOWN`으로 남긴 것은 단순 `Res_value`를 complex entry로 오해해 offset +9/+10을 읽었기 때문이다. 실제 simple entry는 +11의 dataType과 +12의 data를 읽어야 한다. 위 해석은 설치 APK의 `resources.arsc`와 압축 엔트리에서 직접 확인했다.

`dumpsys-usb.txt:1168-1190`도 같은 세 filter를 Google AA의 `FirstActivityImpl`에 연결해 표시한다. `dumpsys-usb.txt:1202-1219`는 AARE의 `UsbAccessoryActivity`에 model-only 두 filter를 표시한다.

## 3. Android 실행 이벤트

원본 `logcat-current.txt`는 UTF-16이며, `filter_logcat.py`로 만든 `logcat-filtered.txt`에 6,160줄을 남겼다. 아래는 그 스라이스다.

### 3.1 02:34:00 — AARE 액티비티 시작

```text
11-29 02:34:00.327 ... SurfaceFlinger: ... com.android.systemui/.usb.UsbConfirmActivity ...
11-29 02:34:04.509 ... ActivityTaskManager: Non-opaque activity is created ... net.prototux.aare/.transport.UsbAccessoryActivity
11-29 02:34:04.521 ... ActivityTaskManager: START u0 {act=android.hardware.usb.action.USB_ACCESSORY_ATTACHED ... cmp=net.prototux.aare/.transport.UsbAccessoryActivity ...} from uid 10037
```

`UsbConfirmActivity`가 먼저 떠오른 뒤 AARE 액티비티가 시작됐다. 권한 확인 터치 직후 AARE가 `ProjectionService`를 시작했지만, framework는 곧 accessory character device를 열지 못했다.

```text
11-29 02:34:04.521 ... ActivityTaskManager: START u0 {cmp=net.prototux.aare/.transport.UsbAccessoryActivity ...}
11-29 02:34:04.544 ... ActivityManager: Background started FGS ... cmp=net.prototux.aare/.service.ProjectionService
11-29 02:34:04.562 ... UsbDeviceManagerJNI: could not open /dev/usb_accessory
11-29 02:34:05.066 ... UsbDeviceManagerJNI: could not open /dev/usb_accessory
```

따라서 액티비티 START와 서비스 시작은 **VERIFIED**지만 USB FD 획득은 **VERIFIED 실패**다. 이 구간에서 Google AA의 `GH.ConnLoggerV2`는 handshake 후 `USB_ISSUE_FIRST_ACTIVITY_NOT_LAUNCHED`, `USB_ACCESSORY_TO_PROJECTION_TIMEOUT`, `USB_ISSUE_PROJECTION_TIMEOUT`을 기록했다.

### 3.2 02:35:17 — 기본 액티비티 해석과 Google AA monitor

```text
11-29 02:35:17.058 ... UsbProfileGroupSettingsManager: resolveActivity: intent=Intent { act=android.hardware.usb.action.USB_ACCESSORY_ATTACHED ... } defaultActivity=ActivityInfo{... net.prototux.aare.transport.UsbAccessoryActivity}
11-29 02:35:17.059 ... UsbProfileGroupSettingsManager: ResolveInfo{... net.prototux.aare/.transport.UsbAccessoryActivity ...}
11-29 02:35:17.082 ... ActivityTaskManager: START u0 {act=android.hardware.usb.action.USB_ACCESSORY_ATTACHED ... cmp=net.prototux.aare/.transport.UsbAccessoryActivity ...} from uid 1000
```

같은 session의 Google AA 연결 로그:

```text
event 55  USB_TRIGGER_CONNECTED_ACCESSORY
event 56  USB_TRIGGER_CONNECTED_CONFIGURED_ACCESSORY
event 57  USB_ACCESSORY_HANDSHAKE_GET_PROTOCOL
event 58  USB_ACCESSORY_HANDSHAKE_SEND_STRING
event 59  USB_ACCESSORY_HANDSHAKE_START
event 67  USB_ENTERED_ACCESSORY_MODE
event 70  USB_ACCESSORY_ATTACHED_WHILE_ACTIVE_NO_FDS_OPEN
event 72  USB_TRIGGER_ACCESSORY_ACCEPTED, detail OptionalInt[4]
event 75  USB_ISSUE_FIRST_ACTIVITY_NOT_LAUNCHED
event 76  USB_MONITOR_STOPPED
```

해석:

- **VERIFIED** — 현재 완충 로그 구간에서는 Android framework가 AARE 액티비티를 선택해 시작했다.
- **VERIFIED** — 같은 구간에서 Google AA가 accessory mode에 들어가고 승인했지만 projection activity가 시작되지 않았다.
- **VERIFIED** — AARE 시작 직후와 02:35:17 재시도에서 framework가 `/dev/usb_accessory`를 열지 못했고, Google AA는 `USB_ACCESSORY_ATTACHED_WHILE_ACTIVE_NO_FDS_OPEN`을 기록했다. 액티비티 resolve/START만으로 FD 확보를 추정하지 않는다.
- **UNKNOWN** — `/dev/usb_accessory` 개방 실패의 정확한 원인(이미 다른 프로세스가 보유, gadget 상태, 권한, 타이밍)과 이 구간이 v2/OAP 과거 세션과 동일한지. 당시 before/after 폰 로그가 없고 사용자에게 재연결을 요청하지 않았다.
- chooser가 보이지 않았다는 사실만으로 전역 기본 앱 저장 상태를 추론하지 않는다.

## 4. 저장된 accessory 선호와 현재 accessory

`dumpsys-usb.txt:1228-1251`:

```text
accessory_preferences=[
  filter={manufacturer=i30 GD13MY AARE, model=Android Auto, version=1.0}
    user_package={user_id=0, package_name=net.prototux.aare}
  filter={manufacturer=i30 Research, model=Android Auto, version=1.0}
    user_package={user_id=0, package_name=net.prototux.aare}
]
```

`dumpsys-usb.txt:38-44`의 현재 accessory:

```text
manufacturer=i30 GD13MY AARE
model=Android Auto
description=i30 GD13MY AARE
version=1.0
serial=null
```

저장된 두 filter는 모두 AARE를 가리킨다. 이는 **현재 저장 상태에 대한 VERIFIED**이고, v2 `version=2.0` 또는 OAP model 세션의 실제 소유권에 대한 증거는 아니다. `i30 GD13MY AARE` manufacturer 후보 이미지는 별도로 부팅하지 않았다. 다만 02:33부터 이어진 accessory 문자열과 03:07 성공 이미지 재실행 시작 시점의 문자열은 모두 `i30 GD13MY AARE`였으므로, 아래 재실행은 그 식별자가 남은 상태에서 수행됐다.

`dumpsys activity services`는 user 150에 대해 `SecurityException: Shell does not have permission to access user 150`을 반환했다. 이 출력은 user 150 상태 근거로 사용하지 않는다.

## 5. CE → Windows USB 오류 경로

### 5.1 AOA 문자열과 START

`src/ce/ce_aa_usb_client.c:202-235`:

- 기본값: manufacturer `i30 Research`, model `Android Auto`, version `1.0`. description은 `i30 GD13MY USB test`.
- `control(link, device, 51, ...)`로 AOA protocol을 읽고 1 또는 2를 확인한다.
- `control(..., 52, index, ...)`로 네 문자열을 보낸 뒤 `control(..., 53, ...)`으로 START를 보낸다.
- manufacturer만 빌드 옵션 `I30_AOA_MANUFACTURER`로 바꿀 수 있다. 배포 기본값은 그대로다.

### 5.2 control 오류

경로:

1. `tools/gd13my_musb.py:231-277` — guest EP0 setup/data를 host `PhonePort.control`로 전달. 오류 시 host ERROR 비트 설정.
2. `tools/gd13my_usb_pc.py:181-216` — 라벨 `USB 제어 요청 {kind:02x}/{request:02x}/{value:04x}/{index:04x}` 생성 후 `raw.ctrl_transfer(..., timeout=750)` 호출. AOA START `(0x40, 53, 0, 0, 0)`은 전환 중 disconnect를 허용하기 위해 특별 처리.
3. `src/i30_receiver/usb_pc.py:23-31` — libusb `USBError`를 `TransportError(f"USB I/O failed: {exc}")`로 감싼다. `-4`만 disconnect로 분류한다.
4. `tools/gd13my_usb_pc.py:164-179` — 실패 라벨을 host log와 UI로 내보내고 `UsbTransferError`를 던진다.

로그의 `USB 제어 요청 00/03/0003/0000 실패 · USB I/O failed: [Errno 32] Pipe error`와 `00/03/0004/0000`은 `bmRequestType=0x00`, `bRequest=3`인 **표준 Device SET_FEATURE** 요청이다. AOA `SEND_STRING`은 `src/ce/ce_aa_usb_client.c:191-199,224-230`의 vendor request `0x40 / code 52 (0x34)`이므로 라벨은 `40/34/0000/000N` 형태이며 위 메시지와 혼동하면 안 된다. 두 SET_FEATURE의 feature selector `3`/`4` 의미는 이 계층에서 해석하지 않는다. 같은 Pipe error가 성공 세션에도 있으므로 이를 AAP version 실패의 직접 원인으로 단정하지 않는다.

### 5.3 재열거와 bulk handle

- `src/i30_receiver/usb_pc.py:33-42` — `devices()`가 `Device(port, vendor, product, address, mass_storage)`로 inventory를 다시 만든다. 재열거로 address가 바뀌면 새 raw handle이 사용된다.
- `src/i30_receiver/usb_pc.py:94-119` — `open_accessory()`는 interface 0 alternate 0의 bulk IN/OUT을 찾고 `claim_interface`한다.
- `tools/gd13my_usb_pc.py:96-157` — `poll()`이 새 후보를 잡아 `self.device/self.raw/self.link`를 갱신한다. WinUSB가 같은 interface의 두 번째 handle을 거부할 수 있어 `accessory_link()`가 필요하면 다시 연다 (`218-228`).
- `tools/gd13my_usb_pc.py:230-250` — AAP version request를 `VERSION_REQUEST = 00030006000100010006`로 식별하고 `link.device.write(0x01, ..., timeout=500)`을 호출한다. 실패 시 `WinCE Android Auto 버전 요청 · 엔드포인트 0x01 실패 · ...`를 기록한다. 성공한 경우에만 trace를 남긴다.
- `tools/gd13my_usb_pc.py:252-267` — 응답을 모아 12-byte prefix `00 03 00 08 00 02`와 major/minor/status를 검사해 version packet을 만든다.
- `src/ce/ce_aa_usb_client.c:237-247,350-375` — CE의 `write_link`/`read_link`가 AAP version 협상을 수행하고 성공 시에만 TLS로 넘어간다.
- `src/ce/ce_aa_usb_session.c:140-143` — 응답 실패 시 `USB accessory found, but the version request failed.`를 signal한다. `tools/view_gd13my.py:247-248`가 이를 host UI 메시지로 바꾼다.

`[Errno 5] Input/Output Error`는 `PyUsb.invoke`가 구분하지 않는 libusb I/O 오류다. 상대端이 bulk endpoint를 열지 않음, stale session, WinUSB 상태를 로그만으로 구분할 수 없으므로 **UNKNOWN**으로 유지한다.

보강 확인 사항:

- **VERIFIED** — `src/i30_receiver/usb_pc.py:23-31`은 `backend_error_code == -4`만 disconnect로 바꾸고 나머지는 `str(exc)`로 평탄화한다. 숫자 코드는 `error.__cause__.backend_error_code`에만 남으며 `tools/gd13my_usb_pc.py:164-179`의 재래핑 이후에는 로그에 남지 않는다. 성공/실패 로그의 `[Errno 32]`, `[Errno 5]`는 모두 이 문자열에서 왔고 실제 backend code는 기록되지 않았다.
- **VERIFIED** — `open_accessory()`는 interface 0 / alternate 0의 bulk IN·OUT을 찾아 `claim_interface`한다 (`src/i30_receiver/usb_pc.py:94-110`). 호스트는 `SET_CONFIGURATION`을 실제로 보내지 않고 Windows active configuration 값을 게스트에만 흉내 낸다 (`tools/gd13my_usb_pc.py:185-195`).
- **VERIFIED 잠재 위험** — `PyUsb.devices()`가 inventory를 교체할 때 이전 raw handle을 정리하지 않고, `control_handles`도 재열거 시 비우지 않는다 (`src/i30_receiver/usb_pc.py:33-42,44-57`). 다만 이 에뮬레이터 경로는 `control_in/out`을 쓰지 않고 `raw.ctrl_transfer`를 직접 쓰므로 과거 세션의 직접 원인으로 확정하지 않는다.
- **VERIFIED** — 중복 `open_accessory()`는 `self.link is None`일 때만 열도록 막혀 있고 (`tools/gd13my_usb_pc.py:218-228`), 실패 로그에 `USB bulk 인터페이스 열기 실패`는 없다. 따라서 이 실행들에서 WinUSB 2차 handle 거부가 관측됐다고 말할 수 없다.
- **VERIFIED** — 03:07 재실행 첫 시도는 ADB/타 프로그램이 장치를 사용 중일 수 있다는 `[Errno 13] Access denied` 힌트를 남겼다. USB ADB 서버를 진단용으로 정지한 뒤 같은 뷰어가 장치를 열고 63 B descriptor → `SET_CONFIGURATION` → `[Errno 5]`까지 진행됐다. ADB 서버 재시작과 로그 덤프는 실패 이후에 했다.

## 6. 성공 세션과 실패 세션 비교

성공 v8 (`build/p0-usb-repro/v8/gd13my-window-20261127-133451-486372.usb-host.log`):

```text
28: USB 제어 요청 00/03/0003/0000 실패 · USB I/O failed: [Errno 32] Pipe error
29: USB 제어 요청 00/03/0004/0000 실패 · USB I/O failed: [Errno 32] Pipe error
30: WinCE Android Auto 버전 요청 · 엔드포인트 0x01
31: WinCE에서 실폰 Android Auto 버전 응답 수신 · 000300080002000100070000
32: 물리 USB 재열거 대기
```

실패 v2 (`build/aare-auto-connect-v2-image/live/gd13my-window-20261129-011311-411777.usb-host.log`)와 OAP (`build/aare-auto-connect-oap-image/live/gd13my-window-20261129-020606-027911.usb-host.log`):

```text
10: WinCE USB SET_CONFIGURATION 1
11: USB 제어 요청 00/03/0003/0000 실패 · USB I/O failed: [Errno 32] Pipe error
12: USB 제어 요청 00/03/0004/0000 실패 · USB I/O failed: [Errno 32] Pipe error
13: WinCE Android Auto 버전 요청 · 엔드포인트 0x01 실패 · USB I/O failed: [Errno 5] Input/Output Error
```

**VERIFIED** — pipe error는 성공과 실패 양쪽에 있다. 실패를 구분하는 것은 version request의 bulk OUT `[Errno 5]`와 이어지는 version response 부재다. 두 실패 세션 모두 `AUTH_COMPLETE`, 서비스 탐색, 첫 프레임이 없다.

호스트 로그의 순서만 놓고 보면 네 세션 모두 `AOA START → 분리 → 18d1:2d01 연결 → config descriptor → SET_CONFIGURATION → 첫 bulk OUT`가 즉시 이어진다. v8 성공의 재열거 config descriptor는 55 B였고, P0/v2/OAP 실패는 63 B였다. 과거 성공 이미지 재실행도 63 B였다. **INFERRED** — descriptor 길이 차이는 강한 상관이지만 내용이 캡처되지 않아 인과관계는 확정하지 않는다. AOA START→재열거의 절대 시각은 호스트 로그에 없어 밀리초 단위 비교는 **UNKNOWN**이다.

## 7. 과거 성공 이미지 인증 자료 대조

이미지: `E:\i30-gd13my-images\opencode-resume-perf\touch\gd13my-aare-settings-o2.img`. FAT 파티션 offset `2048 * 512`, guest 경로 `\DiskA\Application\NAVI\`. 파일 내용이나 개인키는 출력하지 않고 파일 단위 SHA-256만 비교했다.

| 파일 | 이미지 /= 현재 | SHA-256 |
|---|---|---|
| `i30-aare-ca.pem` | 일치 | `6139b252f35a92839c2784f625f6090022560fb5e78defb4e4063ac22583c866` |
| `i30-aare-client.pem` | 일치 | `10686a2fb7cd7b2d039a1442c8c2320b4a11c4b3104569ece1e83bb01be2b647` |
| `i30-aare-client-key.pem` | 일치 | `6619376286f1f955528cf43a6dae1b2992aa249c91d036cf3a550c8d03e4eb93` |
| `i30-aare-peer-sha256.txt` | 일치 | `44deb291e9b94489ae258f5e6604d57815989aa61299fed6f4a0f315b1083c89` |

공개 인증서 메타데이터:

```text
i30-aare-ca.pem
 subject CN=GD13MY-AARE-Local-CA, issuer CN=GD13MY-AARE-Local-CA
 not_before 2026-11-25T14:50:23Z, not_after 2027-11-25T14:50:23Z
 fingerprint_sha256 57fa7bab752dab0d8e859eadc2f9a91c1d233c65c576c2efde3f2c5685ab07a4

i30-aare-client.pem
 subject CN=GD13MY-AARE-Head-Unit, issuer CN=GD13MY-AARE-Head-Unit
 not_before 2026-11-25T14:50:23Z, not_after 2027-11-25T14:50:23Z
 fingerprint_sha256 929eb15696d39f7f96ae98ecbe33f830494b9fe78de8d2127712e0dbdd8521a0

i30-aare-peer-sha256.txt pin = 297fd68ebd0ecc2ee6d7b3d036aa0432150c1893c574fae7bcb83918d55bae0d
```

**VERIFIED** — 과거 성공 이미지와 현재 로컬 identity 사이에는 파일 수준 차이가 없다. **UNKNOWN** — 폰에 현재 등록된 client certificate 및 그 private key 조합. 앱 private data에 접근하지 않았고 권한 우회도 하지 않았다.

## 8. 과거 성공 이미지를 현재 폰·호스트에서 재실행

조건: 이미지 `E:\i30-gd13my-images\opencode-resume-perf\touch\gd13my-aare-settings-o2.img`를 그대로 사용했다. firmware 재빌드, 인증서 재생성, Google AA 설정 변경·강제 종료, 권한 우회는 하지 않았다. 별도 상태 DB `build/success-image-repro-20261129/live-user-diska.sqlite3`와 `-Seconds 1800 -BootTrace -LivePng`로 뷰어를 시작했고, 기존 수동 흐름(동의 탭, F2 두 번, projection 메뉴 탭)만 사용했다. 사용자에게 재연결이나 반복 조작을 요청하지 않았다.

직전 accessory 문자열은 `i30 GD13MY AARE`가 남아 있었다. 따라서 아래 결과는 "manufacturer 후보 이미지를 부팅해 성공했다/실패했다"는 뜻이 아니라, 그 식별자가 남은 상태에서 **과거 수동 성공 이미지를 재실행**한 결과다.

최초 시도는 ADB/타 프로그램이 장치를 사용 중일 수 있다는 힌트를 남겼다.

```text
3: Windows USB 접근 실패 · 18d1:2d01 구성 조회 · USB I/O failed: [Errno 13] Access denied (insufficient permissions) · ADB 등 같은 장치를 사용 중인 프로그램을 확인하세요
```

진단용으로 USB ADB 서버만 정지한 뒤 같은 뷰어가 장치를 열었다. 이후 호스트 로그는 다음 순서다.

```text
4: 물리 USB 1-2 · 18d1:2d01 가상 포트 연결
5: WinCE USB GET_DESCRIPTOR 1 · 8바이트
6: WinCE USB SET_ADDRESS 1
7: WinCE USB GET_DESCRIPTOR 1 · 8바이트
8: WinCE USB GET_DESCRIPTOR 1 · 18바이트
9: WinCE USB GET_DESCRIPTOR 2 · 9바이트
10: WinCE USB GET_DESCRIPTOR 2 · 63바이트
11: WinCE USB SET_CONFIGURATION 1
12: USB 제어 요청 00/03/0003/0000 실패 · USB I/O failed: [Errno 32] Pipe error
13: USB 제어 요청 00/03/0004/0000 실패 · USB I/O failed: [Errno 32] Pipe error
14: WinCE Android Auto 버전 요청 · 엔드포인트 0x01 실패 · USB I/O failed: [Errno 5] Input/Output Error
```

게스트 시리얼 로그는 `i30 native projection placed immediately above the stock map.`, `i30 USB attach ready. Connect Samsung phone.`, `i30 native USB waiting screen painted.`를 기록했고, 이후 `TxCSR_H_Error at EP 1, clear it`가 이어졌다. USB 대기 화면까지는 도달했지만 version response, TLS, 첫 프레임은 없다.

| 단계 | 판정 | 근거 |
|---|---|---|
| AOA 후 `18d1:2d01` 재열거 | VERIFIED | 호스트 로그 4행, `baseline.txt`의 사전 probe. 개별 AOA START control 로그는 없음 |
| AARE `UsbAccessoryActivity` START | UNKNOWN | 03:07 세션 직후 ADB가 device를 보지 못해 새 logcat을 못 받음. 02:34·02:35 완충 로그는 별도 세션이므로 이 실행에 확장하지 않음 |
| `ProjectionService` 시작 | UNKNOWN | 위와 같음. 02:34·02:35 구간의 FGS 시작은 별도 세션 근거 |
| Android accessory open / FD 확보 | UNKNOWN | 03:07 세션과 직접 대응하는 로그 없음. 별도 02:34·02:35 구간에서는 open 실패 관측 |
| 첫 AAP Version Request 전송 시도 | VERIFIED | 호스트 로그 14행 + 게스트 `TxCSR_H_Error at EP 1` |
| Version Response 수신 | VERIFIED 없음 | 호스트 로그에 응답 없음 |
| TLS 및 첫 프레임 | VERIFIED 없음 | 호스트/게스트 로그와 PNG에 인증·투사 이벤트 없음 |
| 실패 후 `logcat -d`, `dumpsys usb` | BLOCKED | `adb start-server` 후 `- waiting for device -`; 폰이 accessory 모드에 남아 ADB가 연결되지 않음. 덤프 파일은 비어 있거나 생성되지 않음 |

따라서 과거 성공 이미지의 authentication 파일 차이, 자동 실행 옵션 차이, AARE 등록 자료 자체는 이번 실패로 설명되지 않는다. 남은 차이는 현재 폰/호스트 USB 환경과 AOA 재열거 후 descriptor 상태다. **INFERRED** — phone 측 endpoint/FD 준비가 호스트 첫 bulk OUT보다 늦거나 실패하면 이 증상과 일치한다. 세부 원인은 **UNKNOWN**이다.

## 9. 가설 상태

| 가설 | 판정 | 근거/한계 |
|---|---|---|
| AARE filter 불일치가 v2/OAP 실패 원인 | 반박에 가까움, 단 과거 세션 소유권은 UNKNOWN | installed AARE는 model-only이고 두 model 모두 일치. v2/OAP도 같은 model 계열이거나 default model 유지 |
| Google AA가 v2/OAP accessory를 점유해 AAP version을 거부 | UNKNOWN | 과거 세션의 폰 로그 부재. 현재 구간에서는 Google AA monitor가 handshake 후 첫 activity를 띄우지 못함 |
| AARE 액티비티가 accessory intent를 받아 START됨 | VERIFIED | 02:34, 02:35 `UsbAccessoryActivity` START/resolve 기록. 액티비티 START는 USB FD 확보와 `ProjectionService` 정상 시작을 증명하지 않음 |
| Android가 accessory FD를 확보하지 못해 호스트 bulk OUT이 실패 | 강한 지지, 세부 원인은 UNKNOWN | framework가 AARE 시작 직후와 02:35 재시도에서 `/dev/usb_accessory`를 열지 못했고 Google AA는 `NO_FDS_OPEN`을 기록. 호스트는 63 B descriptor 후 `[Errno 5]`. 폰이 endpoints를 열지 않으면 이 증상과 일치 |
| 저장된 기본 앱이 AARE로 바뀌면 자동 실행된다 | INFERRED | 현재 저장 filter가 AARE이고 framework가 AARE를 resolve. 자동 실행·TLS·첫 프레임까지 실폰 미검증 |
| stale WinUSB handle이 Errno 5를 만들었다 | UNKNOWN | 재열거 후 새 inventory/handle 경로가 있음. 직접 증거 없음. 단 숨은 control handle 정리 누락은 잠재 위험으로 확인 |
| TLS 인증 자료 불일치가 이번 P0 원인 | 범위 밖/UNKNOWN | version request 이전에 멈췄고 `AUTH_COMPLETE` 없음. 이미지 파일 해시는 일치 |
| `통신 오류 16`이 특정 Android 내부 오류를 의미 | UNKNOWN | 화면 문구만 확인 |

## 10. 산출물과 재현 메모

- 커밋되는 문서: 이 파일과 상태/인계 업데이트.
- 로컬 전용: `build/usb-ownership-diagnosis-20261129/`의 `dumpsys-usb.txt`, `device-props.txt`, `ps.txt`, `google-aa-package.txt`, `aare-package.txt`, `logcat-current.txt`, `logcat-filtered.txt`, 두 APK, 파서와 JSON 스캔. 원본 75 MB logcat은 커밋하지 않는다.
- 로컬 전용 재실행 산출물: `build/success-image-repro-20261129/`의 `*.usb-host.log`, `*.serial.log`, `*.png`, `*.mode.log`, `baseline.txt`, `android-timeline-existing.txt`, 상태 DB. raw 로그와 이미지·상태 DB는 커밋하지 않는다. `logcat-after.txt`는 ADB가 device를 보지 못해 비어 있다.
- ADB는 진단에만 사용했다. 최종 사용자 흐름에서는 ADB, USB debugging, root, Google AA 설정 변경·강제 종료가 필요하지 않아야 한다.
- 재현 필터 예: `adb devices -l`, `adb shell getprop`, `adb shell pm list packages -f`, `adb shell dumpsys usb`, `adb logcat -d`. `logcat-current.txt`는 UTF-16이므로 디코딩 후 필터링한다.
- 사용자가 직접 닫은 창은 재실행하지 않았다. agent가 시작한 OAP/manufacturer viewer 프로세스는 종료했다. 03:07에 시작한 과거 성공 이미지 viewer는 실패 evidence 수집 후에도 종료하지 않고 남겨 두었다.

진단 증거를 커밋·푸시한 뒤에는 상위 수준 판단을 기다린다. 이 문서만으로 새 firmware/APK 변형을 선택하지 않는다.
