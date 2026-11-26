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
