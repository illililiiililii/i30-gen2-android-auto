# AARE 1.6.0 APK 설치 기록 — 2026-11-28

## 1. 목적과 결과

스마트폰에 AARE 1.6.0을 ADB로 설치하거나, 설치가 불가능한 경우 정확한 실패 지점을 확보한다. 앱 데이터 초기화, 기존 서명 충돌 해결을 위한 삭제, 보안 설정 변경은 하지 않는다.

**결과: 설치 성공.** 초기에는 ADB 승인이 없어 설치 전 단계에서 막혔고, 사용자가 화면에서 승인한 뒤 `adb install -r`이 `Success`로 완료됐다.

## 2. 시험 조건

| 항목 | 값 |
|---|---|
| 기준 커밋 | `68ed2f4` (`main`, `origin/main` 동일) |
| 작업 경로 | `F:\i30-gen2-android-auto` |
| ADB | `build/aare-tools/platform-tools/adb.exe`, Android Debug Bridge 1.0.41 / 37.0.3-16887417 |
| APK | `build/aare-tools/aare-1.6.0.apk` |
| APK 크기 | 18,700,995 bytes |
| APK SHA-256 | `75d5a6778980bdc34f3545f984396ad9b591cc22909a3e0e22e0cc8e9ec4f281` |
| 연결 단말 | `R3CW50QVR3X`, `product:dm1qksx model:SM_S911N device:dm1q` |
| 사용자 조작 | USB 디버깅 승인. 다른 화면 조작 없음 |
| 설치 옵션 | `-r` (기존 앱 데이터 유지) |
| 설치 후 처리 | `adb kill-server`로 ADB 점유 해제 |

## 3. 초기 차단 지점

첫 번째 `adb devices -l`은 단말을 `unauthorized`로 보고했다.

```powershell
& 'build/aare-tools/platform-tools/adb.exe' devices -l
Write-Output "adb_exit=$LASTEXITCODE"
& 'build/aare-tools/platform-tools/adb.exe' version | Select-Object -First 2
```

```text
* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached
R3CW50QVR3X            unauthorized transport_id:1

adb_exit=0
Android Debug Bridge version 1.0.41
Version 37.0.3-16887417
```

이 단계에서는 `adb install`을 실행하지 않았다. 원인은 APK가 아니라 ADB 디버그 승인 미완료였다. 점유 해제를 위해 한 번 `adb kill-server`를 실행했다.

사용자에게 화면 승인을 요청했고, 사용자가 **“승인했다, 설치 계속”**이라고 확인했다.

## 4. 설치 실행

```powershell
$adb = 'build/aare-tools/platform-tools/adb.exe'
$lines = & $adb devices -l
$ready = $lines | Where-Object { $_ -match '^\S+\s+device\s' }
if (-not $ready) { exit 2 }
& $adb install -r 'build/aare-tools/aare-1.6.0.apk'
Write-Output "install_exit=$LASTEXITCODE"
```

```text
* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached
R3CW50QVR3X            device product:dm1qksx model:SM_S911N device:dm1q transport_id:1

Performing Streamed Install
Success
install_exit=0
```

## 5. 설치 후 확인

| 확인 | 명령 | 결과 | 판정 |
|---|---|---|---|
| 패키지 경로 | `adb shell pm path net.prototux.aare` | `package:/data/app/~~BrMBr7fXZ9JZ6drEhlaTMw==/net.prototux.aare-gdjymCNQwKKk2--Tv132sQ==/base.apk` | VERIFIED |
| 버전 메타데이터 | `adb shell dumpsys package net.prototux.aare` | `versionCode=10600 minSdk=23 targetSdk=37`, `versionName=1.6.0` | VERIFIED |
| 설치 시각 | 동일 | `lastUpdateTime=2026-11-28 17:57:21`, `firstInstallTime=2026-11-28 17:57:21` | VERIFIED |
| 서명 상태 | 동일 | `signatures=PackageSignatures{a531164 version:2, signatures:[ba6ee29e], past signatures:[]}` | VERIFIED |
| 실행 가능 액티비티 | `adb shell cmd package resolve-activity --brief net.prototux.aare` | `net.prototux.aare/.ui.MainActivity` | VERIFIED |
| 앱 실행 | 없음 | 화면 조작과 AARE USB 세션은 시작하지 않음 | UNKNOWN |
| AARE 인증서 가져오기/승인 | 없음 | 사용자의 AARE 화면 조작 필요 | UNKNOWN |

APK 자체의 오프라인 정적 확인도 설치 전에 통과했다.

| 확인 항목 | 결과 | 판정 |
|---|---|---|
| ZIP 무결성 | `testzip()` 반환값 `None`, 530 entries | VERIFIED |
| 서명 엔트리 | `META-INF/MANIFEST.MF`, `META-INF/CERT.SF`, `META-INF/CERT.RSA` | VERIFIED |
| APK 서명 주체 | `O=AARE contributors, CN=AARE` (자기 서명) | VERIFIED |
| `CERT.SF` 서명 검증 | OpenSSL `smime -verify ... -noverify` 결과 `Verification successful` | VERIFIED |
| 패키지명 | `net.prototux.aare` | VERIFIED |
| 애플리케이션 클래스 | `net.prototux.aare.AareApp` | VERIFIED |

## 6. 결론

| 항목 | 판정 | 내용 |
|---|---|---|
| ADB 물리 연결과 승인 | VERIFIED | 최초 `unauthorized`, 사용자 승인 후 `device` |
| APK 설치 | VERIFIED | `Performing Streamed Install` → `Success` |
| 설치된 패키지 버전 | VERIFIED | `net.prototux.aare` 1.6.0 / versionCode 10600 |
| 서명 충돌·다운그레이드·저장공간·권한 오류 | VERIFIED 아님 | 이번 설치에서 발생하지 않음 |
| 앱 첫 실행과 USB/TLS 연결 | UNKNOWN | 실행하지 않았으므로 미검증 |
| 인증서 세트 일치 | UNKNOWN | `build/aare-tools/identity` 목록만 확인. 개인키 내용은 읽거나 전송하지 않음 |

기존 앱 데이터나 설정을 삭제·초기화하지 않았다. 설치 완료 후 `adb kill-server`를 실행해 ADB 점유를 해제했으므로, 다음 AARE USB 연결 시 ADB가 포트를 점유하지 않는다.

## 7. 다음 사용자 조작

스마트폰에서 AARE를 열고, 기존 절차에 따라 P12 가져오기와 수신기 지문 승인을 수행해야 실제 USB/TLS 세션을 확인할 수 있다. 이 작업은 사용자의 화면 조작이 필요하므로 여기서는 실행하지 않았다. 설치 자체는 완료됐다.
