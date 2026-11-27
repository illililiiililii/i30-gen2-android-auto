# Phase 2 · USB 연결 시험

2026-11-22 재시험에서 PC 수신기를 종료하고 같은 AOA 열거 상태로 다시 실행하자 Android Auto 1.7 응답 이후 TLS가 완료되지 않았다. 삼성 폰 케이블을 재연결한 뒤 공식 DHU에서 TLS 1.2 인증과 800×480 영상 출력이 확인됐으나, 이후 `Ping timeout`으로 세션이 종료됐다. 다음 DHU 재시도에서는 `Out of sync with phone (-251)`를 관측했다. 이 결과는 PC USB 시험에 해당한다. [재연결 결과](../build/gd13my-aa-lab/phone-recovery-20261122.json)

**삼성 테스트폰에서 AOA 2와 Android Auto 1.7 응답을 확인했다.** 2026-11-20에 PC의 포트 `1-2`에서 삼성 기본 USB 모드 `04e8:6860`을 Windows 기본 WinUSB로 열었다. 액세서리 모드 `18d1:2d00`은 Windows에서 WinUSB로 자동 열거됐다. 프로젝트 수신기는 bulk 인터페이스를 열어 평문 버전 응답을 받았다. 공식 DHU는 같은 폰에서 TLS 1.2 연결과 인증서 검증 성공을 기록했다. [프로젝트 수신기 로그](../research/evidence/phase2-winusb-clean-probe-20261120-230036.jsonl) · [공식 DHU 로그](../research/evidence/phase2-winusb-trial-20261120-225824.dhu.stderr.log)

## 실폰 검증 수준

| 시험 항목 | 첫 삼성 시험폰 | 업데이트한 삼성 서브폰 |
|---|---|---|
| 공식 DHU 2.0 USB·TLS·영상 | **확인됨.** AOA 2, Android Auto 1.7, TLS 1.2 인증서 검증과 800×480 화면 표시가 반복 시험 10회 모두 통과했다. [반복 로그](../research/evidence/phase2-dhu-repeat-20261120-232305.jsonl) | **확인됨.** AOA 2, Android Auto 1.7, TLS 1.2 인증서 검증과 800×480 화면 표시를 관찰했다. [서브폰 결과](../research/evidence/phase2-secondary-retest-20261120-234150.jsonl) |
| 공식 DHU 터치 | **확인됨.** 앱 런처 탭 뒤 화면 변화를 관찰했다. [터치 로그](../research/evidence/phase2-dhu-touch-20261120-231323.log) | **부분 확인.** 앱 런처 위치로 탭 두 번을 전송했다. 화면 비교 결과가 저장되지 않았고, 재측정 중 USB가 끊겨 반응 판정은 보류했다. [탭 전송 로그](../research/evidence/phase2-secondary-retest-20261120-234150.jsonl) · [재측정 로그](../research/evidence/phase2-secondary-touch-verified-20261120-234316.jsonl) |
| 프로젝트 수신기 USB·버전 `probe` | **확인됨.** AOA 2 전환, bulk 개방, Android Auto 1.7 응답이 10회 모두 통과했다. [반복 로그](../research/evidence/phase2-receiver-repeat-20261120-232514.jsonl) | **확인됨.** 업데이트 후 AOA 2 전환, bulk 개방, Android Auto 1.7 응답을 관찰했다. [서브폰 프로브](../research/evidence/phase2-secondary-retest-20261120-234150.probe.jsonl) |
| 프로젝트 수신기 TLS·서비스·영상·터치 | **실폰 미검증.** 모의 세션에서 TLS·서비스 탐색·H.264 프레임·암호화된 탭 전송을 확인했다. [모의 통합 로그](../research/evidence/phase2-pc-video-touch-mock-20261120-231851.jsonl) | **실폰 미검증.** 폰 인증서를 검증할 신뢰 자료와 예상 인증서 이름 또는 지문이 필요하다. |

서브폰의 마지막 재측정에서는 Windows가 분리된 장치의 임시 WinUSB 바인딩을 유지했다. 삼성 USB 드라이버 복원은 재연결 후 확인한다. [복원 확인 로그](../research/evidence/phase2-secondary-touch-verified-20261120-234316.jsonl)

| 구분 | 관찰 결과 |
|---|---|
| 기본 삼성 드라이버에서 실폰 시험 | `dg_ssudbus`와 `WUDFWpdMtp`가 설치된 초기 상태에서 프로젝트 수신기의 USB 활성 설정 열기와 AOA GET_PROTOCOL(51)이 모두 `LIBUSB_ERROR_NOT_FOUND (-5)`였다. 공식 DHU도 두 번 모두 `Couldn't find/access compatible USB device`로 끝났다. [수신기 로그](../research/evidence/phase2-phone-probe-20261120-224117.jsonl) · [DHU 진단 로그](../research/evidence/phase2-google-dhu-usb-diagnostic-20261120-224743.stderr.log) |
| WinUSB에서 공식 Google DHU 2.0 Windows | AOA 2, `18d1:2d00` 재열거, 인터페이스 `0`, bulk IN `0x81` 및 OUT `0x01`, Android Auto 1.7, TLS 1.2 및 인증서 검증 성공을 확인했다. DHU 콘솔에서 두 번 화면을 확인했고 두 프레임 모두 800×480에 단색이 아닌 내용이 렌더링됐다. 화면 이미지는 폐기했고 터치 입력을 전송하지 않았다. Windows의 삼성 복합 드라이버를 다시 복원했다. [DHU 세션 로그](../research/evidence/phase2-dhu-display-20261120-230704.stderr.log) · [화면 확인 및 복원 로그](../research/evidence/phase2-dhu-display-20261120-230704.log) |
| WinUSB에서 프로젝트 수신기 | DHU 직후에는 이전 세션의 암호화 프레임이 남아 버전 확인이 실패했다. 기본 USB 모드가 다시 열거된 뒤 프로젝트 수신기를 먼저 실행해 AOA 전환과 평문 버전 응답을 확인했다. 프로젝트 수신기의 실폰 TLS와 서비스 탐색은 미검증이다. [DHU 직후 로그](../research/evidence/phase2-winusb-trial-20261120-225824.probe.jsonl) · [기본 USB 모드에서 재시험 로그](../research/evidence/phase2-winusb-clean-probe-20261120-230036.jsonl) |
| 초기 PC 열거 | 폰 연결 전 USB 항목 6, 액세서리 0. [열거 로그](../research/evidence/phase2-usb-enumeration.jsonl) |
| 실제 PC의 빈 포트 오류 | 연결 대상이 없는 테스트 ID를 지정했고 `No USB device on the specified port`와 종료 코드 1을 확인했다. [오류 로그](../research/evidence/phase2-usb-no-device.jsonl) |
| 정상 Mock | AOA 51/52/53, 같은 포트에서 재열거, 분할된 USB 읽기, TLS 1.2, 서비스 탐색 성공. 미디어 ACK 2회, peer ping 응답, 정상 종료 및 링크 반환. [정상 로그](../research/evidence/phase2-release-normal.jsonl) |
| 분리/재연결 Mock | 첫 합성 세션에서 분리를 유도했다. Error 및 Reconnecting 후 두 번째 세션을 열고 정상 종료했다. 링크 2개 반환. [재연결 로그](../research/evidence/phase2-release-reconnect.jsonl) |
| keepalive 손실 Mock | 세션 활성 후 pong 유실을 유도했다. 정해진 시간 안에 기한 만료, 링크 반환 및 종료 코드 1을 확인했다. [타임아웃 로그](../research/evidence/phase2-release-timeout.jsonl) |
| 공식 DHU 반복 연결 | 개선한 USB 재연결 절차에서 10회 모두 AOA 2, Android Auto 1.7, TLS 1.2 인증서 검증, 800×480 비단색 화면과 정상 종료를 확인했다. 실행 후 예약된 화면 샘플은 7.18–7.31초에 생성됐다. 이 시간에는 DHU 콘솔의 5초 대기가 포함된다. 최초 절차는 1회 연결 후 기본 USB 모드 재열거의 대기 시간이 부족해 중단됐다. [10회 반복 로그](../research/evidence/phase2-dhu-repeat-20261120-232305.jsonl) · [최초 절차 로그](../research/evidence/phase2-dhu-repeat-20261120-232017.jsonl) |
| 프로젝트 수신기 반복 USB 프로브 | 10회 모두 삼성 기본 모드에서 AOA 2, `18d1:2d00` 재열거, bulk 개방과 평문 Android Auto 1.7 응답을 확인했다. 각 회차 전 확인된 PC USB 포트를 다시 연결했고, 마지막에 기존 `dg_ssudbus` (`oem196.inf`)를 복원했다. [10회 프로브 로그](../research/evidence/phase2-receiver-repeat-20261120-232514.jsonl) |

## Windows에서 터치 시험

공식 DHU를 `--usb --config=config/default.ini --input=touch`로 실행하고 DHU 콘솔에 `tap X Y`를 입력한다. 새 탭 좌표는 현재 표시된 화면에서 확인한다. 시험 당시 800×480 화면에서 앱 런처는 `(44,440)`이었다. 입력 없이 비교한 두 화면에서는 표본 차이가 0%였다. 첫 탭 후 80.9%, 두 번째 탭 후 직전 화면과 80.8% 차이가 있었다. 실폰 프레임은 검증 직후 폐기했고 원래 삼성 Windows USB 드라이버를 복원했다. [실폰 터치 로그](../research/evidence/phase2-dhu-touch-20261120-231323.log) · [Google DHU 터치 명령](https://developer.android.com/training/cars/testing/dhu#touch-and-touchpad)

## 인증 자료와 실폰 통과 기준

- `--ca`는 테스트 폰이 TLS에서 제시하는 인증서를 검증할 신뢰 CA의 공개 인증서 PEM이다. `--peer-name`에는 인증서에 등록된 예상 이름을 넣는다. 사전에 신뢰할 수 있는 경로로 확인한 인증서 SHA-256 지문을 `--peer-sha256`에 지정하는 방식도 가능하다. 두 방식 모두 인증서 체인을 검증한다. [수신기 검증 코드](../src/i30_receiver/tls.py) · [Python TLS 문서](https://docs.python.org/3/library/ssl.html#ca-certificates)
- `--cert`와 `--key`는 휴대폰 측이 헤드유닛의 클라이언트 인증을 요구할 때 쓰는 테스트 수신기의 인증서 PEM과 대응 개인키다. 휴대폰이 신뢰하는 자격이어야 한다. 어떤 클라이언트 인증 정책이 적용되는지는 자체 수신기의 실폰 시험에서 아직 확인하지 못했다. 키는 런타임에서 로컬 경로로 읽고 로그에 남기지 않는다. [Python 인증서 로딩](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.load_cert_chain)
- TLS 통과는 실제 폰과 인증서 검증을 포함한 암호화 세션이 성립한 경우다. 서비스 검증은 그 세션에서 서비스 탐색과 채널 열기를 관찰한 경우다. USB 열거와 평문 버전 응답은 `probe` 단계로 기록한다.
- 영상 통과는 그 실폰 세션으로 들어온 영상이 PC에서 디코딩되어 실제 프레임이 표시된 경우다. 터치 통과는 PC에서 탭을 보내 해당 실폰 프로젝션 화면에 예상한 변화가 나타난 경우다. DHU로 관찰한 결과와 프로젝트 수신기로 관찰한 결과를 장치별로 기록한다. [Google DHU USB 시험](https://developer.android.com/training/cars/testing/dhu#connect-using-accessory-mode)

서브폰은 별도 USB 장치로 확인한 뒤 동일한 포트와 케이블에서 `probe`, 공식 DHU TLS, 화면, 터치 항목을 시험한다. 최초 연결 안내나 권한 선택이 폰에 표시되면 사용자 조작이 필요한 상태를 기록한다. 공식 DHU 시험에는 사용자가 별도로 제공하는 `--ca`, `--cert`, `--key` 파일이 필요하지 않다. [Google DHU 실행 안내](https://developer.android.com/training/cars/testing/dhu#run-the-dhu)

2026-11-20에 두 번째 삼성 폰을 포트 `1-2`에서 확인했다. Windows 장치 인스턴스는 첫 시험폰과 달랐다. 업데이트 전 첫 `probe`에서는 AOA 2 전환, `18d1:2d00` 재열거, bulk 인터페이스 개방까지 관찰됐다. 버전 요청의 USB 쓰기가 타임아웃으로 끝났다. 공식 DHU도 같은 시점에 `Failed to write to transport`로 종료됐다. [서브폰 프로브](../research/evidence/phase2-secondary-phone-20261120-233507.probe.jsonl) · [서브폰 DHU 로그](../research/evidence/phase2-secondary-phone-20261120-233507.dhu.stderr.log)

사용자가 서브폰 업데이트를 완료했다고 알린 뒤 첫 재시험에서 이전 시험의 삼성 드라이버를 복원했다. 이후 WinUSB를 적용하고 Windows의 장치 재시작을 요청했으나 폰이 USB 목록에서 사라져 DHU 실행 전에 중단됐다. [업데이트 직후 재시험](../research/evidence/phase2-secondary-updated-20261120-233830.jsonl)

다음 재시험에서는 서브폰이 다시 나타난 뒤 해당 PC 포트만 재연결했다. 공식 DHU가 Android Auto 1.7과 인증서 검증을 포함한 TLS 1.2 연결을 완료했고 800×480 프레임을 표시했다. 프로젝트 수신기의 `probe`도 종료 코드 0으로 Android Auto 1.7 응답을 기록했다. [업데이트 후 자체 수신기 로그](../research/evidence/phase2-secondary-retest-20261120-234150.probe.jsonl) · [업데이트 후 공식 DHU 로그](../research/evidence/phase2-secondary-retest-20261120-234150.dhu.stderr.log)

업데이트 후 첫 터치 시도에서 앱 런처 좌표로 두 번 탭을 보냈으나, PowerShell의 `diff` 별칭과 시험 함수 이름이 충돌해 화면 차이 수치가 저장되지 않았다. 함수 이름을 고친 재측정은 장치 재인식 중 연결이 끊겨 시작하지 못했다. 해당 Windows 장치 인스턴스는 분리 상태에서 WinUSB로 남아 있으며 삼성 드라이버 복원은 연결 후 재확인한다. [첫 터치 시도와 당시 복원](../research/evidence/phase2-secondary-retest-20261120-234150.jsonl) · [재측정과 복원 상태](../research/evidence/phase2-secondary-touch-verified-20261120-234316.jsonl)

## 실폰 연결 시

이번 PC에서는 삼성 기본 USB 모드에 WinUSB를 임시로 적용했을 때 USB AOA가 동작했다. 동일한 케이블로 수신기를 바꿔 시험할 경우, 폰이 기본 USB 모드로 다시 열거된 뒤 다음 프로브를 시작한다. 시험 후 PC 쪽 USB 포트를 다시 연결하고 삼성 복합 드라이버 `dg_ssudbus` (`oem196.inf`)를 복원했다. Windows는 MTP와 모뎀을 정상으로 표시했다. [복원 로그](../research/evidence/phase2-winusb-clean-probe-20261120-230036.log) · [Google DHU 연결 안내](https://developer.android.com/training/cars/testing/dhu#connect-using-accessory-mode)

1. Windows에서 [Google DHU](https://developer.android.com/training/cars/testing/dhu)의 공식 USB 시험을 먼저 한다. 휴대폰 Android Auto와 케이블이 작동하는지 기준을 남긴다.
2. 아래 `list`를 연결 전후에 실행해 새로 나타난 **폰의 물리 포트**를 확인한다. 장치가 나타났다는 사실만으로 Android Auto를 지원한다고 판정하지 않는다.
3. 해당 포트로 `probe`한다. AOA 응답과 재열거, bulk 인터페이스, 평문 버전 응답을 확인하며 테스트가 끝나면 링크를 반환한다. `probe`는 TLS 세션으로 계산하지 않는다.
4. 폰과 호스트가 승인한 인증·신뢰 정보를 사용할 수 있으면 `connect`를 시험한다. USB 연결 성공과 TLS 및 서비스 탐색 성공을 별도로 기록한다. 인증을 변경하는 방법은 사용하지 않는다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py build/i30-receiver.pyz list
& $py build/i30-receiver.pyz --log research/evidence/phone-probe.jsonl probe --device '<list에서 확인한 폰의 포트>'
& $py build/i30-receiver.pyz --log research/evidence/phone-session.jsonl connect --device '<같은 포트>' --ca '<신뢰 CA PEM>' --peer-name '<검증할 이름>' --cert '<승인된 호스트 인증서 PEM>' --key '<해당 키 PEM>'
```

`--peer-name` 대신 승인된 폰 인증서의 `--peer-sha256`을 사용할 수 있다. CA 검증은 두 모드에 모두 적용된다. 호스트 인증서가 필요 없는 지원 환경이면 `--cert`와 `--key`를 함께 생략한다. Windows에서는 일반 스마트폰 모드와 AOA 재열거 후 인터페이스에 접근 가능한 드라이버가 필요할 수 있다. 앱은 드라이버 설치·교체, 커널 드라이버 분리, 기본 구성 강제 변경을 하지 않는다. 장치 테이블이 보이고 전송이 실패하면 Windows 장치 관리자와 공식 DHU의 WinUSB 안내로 대상 인터페이스를 확인한다. [AOSP AOA 1.0](https://source.android.com/docs/core/interaction/accessories/aoa) · [libusb Windows](https://github.com/libusb/libusb/wiki/Windows)

AOA에서 PC는 USB 호스트로 유지된다. 폰은 USB 주변장치 상태에서 액세서리 데이터 인터페이스를 제공하는 구성으로 재열거된다. 실폰 최초 실행 시 기록할 항목은 휴대폰 모델/Android/Android Auto 버전, 포트와 VID/PID 변화, AOA 버전, bulk 개방, AA 버전, TLS 결과, 서비스/채널, keepalive, 정상 종료, 재연결이다. 시험 로그는 `source=usb` 또는 `source=mock`으로 구분한다.
