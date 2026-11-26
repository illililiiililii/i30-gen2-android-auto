# 삼성 실폰 USB 시험

## 중단 전 순정 WinCE 실험

2026년 11월 26일 이전 세션은 Samsung SM-G996N, Android 15, 공식 AARE 1.6.0과 .061 순정 WinCE를 사용했다. AARE가 앱 로그에 `GD13MY-AARE.p12` 선택을 기록했다. WinCE가 USB AOA 2에서 AAP 1.7을 받았다.

| WinCE UART 줄 | 관측 결과 |
| --- | --- |
| 8288–8307 | TLS 1.2 `0xC02F` 협상 뒤 BearSSL 62, `i30 CE TLS phone certificate chain has no trusted anchor.` 순정 Android Auto가 해당 액세서리 인터페이스를 먼저 열었음이 동시간대 Android 활동과 AARE의 열기 실패 로그에 드러났다. |
| 8684–8716 | 서버 인증서와 `CertificateRequest`가 처리됐고 WinCE가 `CertificateVerify`를 보냈다. 다음 송신이 USB에서 끊겨 Finished에 도달하지 못했다. 첫 시험의 신뢰 앵커 오류와 실패 단계가 다르다. |
| 9034–9131 | 양쪽 ChangeCipherSpec 뒤 BearSSL이 TLS 1.2를 인증했다. `AUTH_COMPLETE`를 보냈고 암호화된 서비스 탐색 요청을 받아 응답했다. 직후 CE USB 드라이버가 `Device Not Responding`을 기록하고 첫 영상 전에 투사 표시를 반환했다. |
| 9933–9949, 12458–12474 | 두 번 더 BearSSL 62를 기록했다. 이 실행은 수신폰 리프 지문을 기록하지 않았으므로 어느 인증서가 전송됐는지 확정할 수 없다. AARE는 일부 TLS 종료를 폰 인증서 거절로 추정해 다음 접속의 인증서를 변경한다. |

원본은 `build/aare-integration/live/gd13my-window-20261126-000807-329970.serial.log`와 같은 이름의 `.usb-host.log`에 있다. 후자는 위 실행에서 bulk IN 및 OUT 타임아웃을 별도로 기록한다. 앱의 인증서 순환 로직은 `ProjectionService.onEnded()`와 `CertificateStore.pick()`에 있다. [AARE USB 세션 소스](https://github.com/prototux/AARE/blob/v1.6.0/app/src/main/java/net/prototux/aare/service/ProjectionService.kt) · [AARE 인증서 선택 소스](https://github.com/prototux/AARE/blob/v1.6.0/app/src/main/java/net/prototux/aare/cert/CertificateStore.kt)

## 기존 폰 인증서 대조

- 기존 `GD13MY-AARE.p12`를 재사용했다. OpenSSL `verify -purpose sslserver`에 리프와 WinCE 이미지의 전용 CA를 사용했고 성공했다. PKCS#12의 CA와 WinCE용 CA의 SHA-256도 같았다.
- 휴대폰 PKCS#12 키와 리프의 공개키가 일치했고, 수신기 인증서도 대응 키와 일치했다. 두 시험 DiskA의 `i30-aare.opt`와 네 전용 자격 파일을 로컬 파일과 대조했다.
- 리프는 RSA 2048, `sha256WithRSAEncryption`, `Digital Signature`, `Key Encipherment`, EKU `TLS Web Server Authentication`이다. 유효기간은 UTC 2026-11-25 14:50:23부터 2027-11-25 14:50:23까지다. 기존 성공·실패 시도의 UART 게스트 UTC는 이 기간에 있었다.
- WinCE AARE 모드는 BearSSL 체인 검증과 게스트 UTC 검증에 더해 해당 폰 리프 SHA-256을 확인한다. AARE 유선 연결은 사용자 승인으로 저장된 WinCE 리프 지문을 확인한다. 양쪽이 같은 TLS 핸드셰이크에서 앱 데이터를 송수신해야 `AUTH_COMPLETE`와 서비스 탐색에 도달한다.

## 재시험 변경

- USB 전환 시 게스트 시간은 유지하고, IRQ 폴링과 입출력 폴링의 CPU 단위 기한도 새 속도에 맞췄다. AARE 시험 이미지의 USB 구간 기본값은 12 MHz이며 `-UsbClockMHz`로 설정할 수 있다. 기존 실행 프로필의 기본값은 64 MHz다.
- Windows USB 전달에서 bulk IN의 libusb 타임아웃을 미응답으로 유지한다. 앱이 아직 데이터를 보내지 않은 경우에는 WinCE의 읽기 요청과 취소를 계속 처리한다. 장치 분리나 다른 I/O 오류에는 기존 오류 경로를 사용한다.
- WinCE UART에 수신 폰 리프, 등록 CA 및 기대 지문을 기록하고, 투사 단계에서 오류가 발생하면 AAP 채널·플래그·메시지 ID를 기록하도록 추가했다. 로그는 인증 데이터의 SHA-256과 메시지 식별자만 남긴다.

## 소프트웨어 재연결과 인증서 선택 확인

09:30:50부터 순정 WinCE에서 AOA 2와 AAP 1.7을 다시 확인했다. 폰 로그의 인증서 표시는 `Android Auto 18.1.664444-release`였다. AARE의 세션에서 WinCE `ClientHello` 수신과 다른 서버 인증서 송신이 기록됐고, 이어 WinCE는 BearSSL 62로 그 체인을 거부했다. AARE는 명시적인 TLS 경고를 받지 못해 끊김으로 해석했고 같은 인증서를 다시 선택했다. 원본은 `build/aare-integration/resume/android-first.log`와 `android-second.log`에 있다.

이제 AARE 모드에서 BearSSL이 신뢰 실패로 핸드셰이크를 중단했고 양방향 TLS가 암호화 상태로 전환되기 전이면, 수신기가 TLS 1.2 표준 fatal `unknown_ca` 또는 지문 불일치의 `access_denied`를 전송한다. AARE가 인증서 거절과 USB 끊김을 구별해 다음 등록 인증서를 시도할 수 있다. ARM PE 회귀에서 두 경고를 TLS 상대가 각각 받았고, 등록된 CA와 지문이 맞을 때 인증이 완료됐다. [TLS 1.2 경고](https://www.rfc-editor.org/rfc/rfc5246.html#section-7.2.2)

`adb shell svc usb setFunctions mtp`로 폰을 일반 USB로 전환한 뒤 가상 USB 재연결을 수행했다. Windows의 장치 재시작은 현재 권한에서 거부됐다. 가상 포트의 핸들을 반환한 뒤 순정 WinCE의 AOA 재요청으로 액세서리 모드와 AAP 1.7에 다시 도달했다.

| 시각 (KST) | 실폰 재시험 결과 |
| --- | --- |
| 09:52 | WinCE가 다른 리프를 받아 BearSSL 62와 `unknown_ca`를 기록했다. AARE가 TLS 경고를 받고 다음 연결에서 `GD13MY-AARE.p12`를 제공한다고 기록했다. 가상 포트만 다시 열었을 때는 AARE가 AAP 버전 응답을 기록했지만 WinCE까지 도착하지 않았다. |
| 09:55 | USB를 소프트웨어로 다시 열거한 뒤 양쪽에서 AAP 1.7을 확인했다. AARE가 `GD13MY-AARE.p12`를 선택했다. WinCE에서 실제 수신 리프와 기대 SHA-256이 일치했고 `ServerHello`와 `Certificate`를 받았다. AARE가 SSL 메시지 2,116바이트를 기록한 뒤 나머지 핸드셰이크를 WinCE에서 받지 못했다. UART는 USB 읽기 중단을 기록했고 이 세션에서 추가 인증서 검증 오류는 없었다. |
| 10:05–10:13 | 소프트웨어로 다시 열거해 같은 P12 세션을 두 차례 재현했다. 물리 USB에서 AAP 응답 2,122바이트를 모두 받았다. 물리 쪽에서 `ServerKeyExchange`, `CertificateRequest`, `ServerHelloDone`까지 확인했다. 가상 MUSB에서 512바이트 네 번과 마지막 74바이트를 이체했고, 마지막 DMA 잔량은 0이었다. WinCE의 TLS 메시지 기록은 여전히 `Certificate`에서 멈췄다. |
| 10:35 | 새 순정 부팅과 비동기 WinUSB 수신에서도 기존 P12의 지문을 확인했다. WinCE가 앞선 512바이트 패킷들의 전송을 완료했으며 DMA에 입력한 데이터와 완료 버퍼의 해시가 일치했다. 이어 `ServerKeyExchange` 본문 300바이트 중 269바이트를 읽고 나머지 31바이트를 요청했다. 이때 마지막 USB 패킷 74바이트가 MUSB에 들어왔지만 WinCE의 USB 전송 완료가 보고되지 않았다. |

인증서 선택과 현재 USB 수신 중단은 각각 재현됐다. 09:55 시험은 Finished에 도달하지 않았다. 중단 전 실폰 실행에서 `AUTH_COMPLETE`와 서비스 응답까지 기록한 구간은 이 문서의 첫 표에 있다. Windows를 통한 전달은 물리 USB 제어 및 바이트 전송만 담당한다. 검증과 AAP 처리는 WinCE에서 실행된다.

가상 MUSB의 짧은 DMA 수신에서 `RXPKTRDY`가 너무 일찍 자동 해제되는 동작도 하드웨어 규격에 맞췄다. 전체 패킷이나 DMA 마지막 워드에 맞닿은 패킷에는 기존 자동 해제를 적용한다. 이어 CPU가 읽는 `RXCOUNT`에 FIFO의 남은 바이트를 반영했다. 자동 해제 판단에는 처음 도착한 패킷 크기를 사용한다. WinCE 전송 완료가 확인되는지 같은 P12로 재시험한다. [MUSBMHDRC Programmer’s Guide](https://linux-sunxi.org/images/7/73/Musbmhdrc.pdf)

재개한 순정 이미지의 원본 로그는 로컬 `build/aare-integration/verified-alert/live/`의 `android-after-alert.log`, `android-matching-p12.log`, `gd13my-window-20261126-093907-417245.serial.log` 및 같은 이름의 `.usb-host.log`, `.bulk-trace.log`, `.tls-lengths.log`다. 재시동 후의 UART와 WinCE USB 전송 완료 계측은 `gd13my-window-20261126-102059-041030.serial.log` 및 같은 이름의 `.guest-calls.log`에 있다.
