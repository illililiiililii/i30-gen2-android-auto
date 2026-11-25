# WinCE TLS 로딩 변경과 회귀 결과

## 변경

- `ce_aa_tls.c`의 `open_credential()`은 DER 파일이 없을 때만 같은 신원의 PEM 경로를 사용한다. 접근 거부, 빈 파일, 초과 크기, PEM 형식 오류와 디코더 오류를 기록한다. 등록된 CA가 없으면 기존 인증 설정 대기 상태를 반환한다. 정상 CA 핸들은 한 번 열어 `configure()`에 전달한다.
- `configure()`는 리프의 SHA-256과 BearSSL 디코더 결과를 기록하고 기존 RSA 키 일치 검사와 UTC 유효기간을 적용한다. `client_chain_valid()`는 PEM에 포함된 중간 CA의 시간과 CA 제약을 확인하고 BearSSL로 각 체인 접두사의 서명과 순서를 검증한다. 로컬 검사는 제공된 발급자 사이의 관계를 확인한다. 폰이 사용하는 신뢰 저장소는 별도다. 폰의 CA·호스트명 또는 CA·지문 검증은 기존 정책을 유지한다.
- `handshake()`는 TLS 레코드와 AAP 프레임 분할을 거친 실제 송신 리프의 DER를 해시한다. 송수신 핸드셰이크 메시지 번호, ChangeCipherSpec, 협상 버전 및 cipher suite, 확인된 fatal alert와 방향을 기록한다. TLS 엔진이 애플리케이션 데이터를 허용한 뒤에만 인증 완료를 기록한다. `discover()`는 `AUTH_COMPLETE` 전송과 응답형 서비스 탐색 완료를 기록한다.
- `ce_aa_usb_client.c`는 USB 제출, 상태, 길이, 타임아웃, 취소 및 정리 실패를 구분한다. `ce_minimal.h`는 공통 WinCE API 선언을 제공한다. `build_ce_usb.py`는 TLS 없는 USB DLL에도 진단 함수의 기존 WinCE import를 제공한다.

시간 오프셋 샘플은 BearSSL에서 수정 전후 `BR_ERR_X509_BAD_TIME`으로 종료된다. 수정 후에는 로딩 지문과 `48`을 UART에서 직접 확인할 수 있고 `ClientHello`가 발생하지 않는 것을 합성 인증서로 확인했다. 원본 DER과 BearSSL 0.6의 시간 처리는 그대로 사용한다. [파싱 근거](RESEARCH_VALIDATION.md)

호출 경로는 `USBDeviceAttach()` → `negotiate()` → `i30_ce_authenticate()`다. `configure()`가 성공해야 `handshake()`를 호출하고, 상호 TLS가 성공해야 `discover()`와 영상 채널로 진행한다. 함수가 반환할 때 세션 메모리를 지우고, USB 계층이 전송과 파이프 및 영상 이벤트를 정리한다. 영향 범위는 구성을 시작하는 버전 교환부터 AuthComplete 및 서비스 탐색 후 영상까지 기존 ARM 시험에서 확인했다. [USB 연결·종료](../../src/ce/ce_aa_usb_client.c) · [인증 및 서비스](../../src/ce/ce_aa_tls.c)

## 빌드 및 시험

| 검증 | 결과 |
| --- | --- |
| Python `unittest discover -s tests` | 84개 통과 |
| GCC ARM/Thumb WinCE 6.0, BearSSL 0.6 + h264bsd | `i30usb.dll`, `i30nav.dll`, `i30aa.exe` 생성 |
| TLS 없는 ARM USB 빌드 | AOA, 버전, 타임아웃과 정리, 설정 및 소유권 회귀 통과 |
| ARM USB + TLS + 투사 회귀 | PEM/DER, TLS 1.2 `0xC02F`, 상호 인증 및 `AUTH_COMPLETE`, 서비스 탐색, 정상 종료 통과 |
| 등록 및 체인 오류 | 누락, 파일 접근 거부, 잘못된 PEM/DER, 키 불일치, 중간 CA 누락과 순서 오류, 변조 서명, 잘못된 CA 또는 이름·지문 거부 |
| 시간 입력 | `Z` 정상. `-0700`과 잘못된 달력 날짜는 디코더 48. UTC 2049/2050 자정 경계의 UTCTime/GeneralizedTime 양 끝점 통과. 시작 전 및 만료 후 거부 |
| 연결 및 미디어 | AAP 분할 ID와 TLS 레코드 재조립, 불일치 총 길이 거부, 수신 fatal alert, 무응답 USB 타임아웃, 채널 교차 ping, 영상 응답과 순정 표시 선점·복귀 통과 |
| 지문 | 로딩 지문, 실제 송신 지문, 가상 상대가 독립적으로 받은 리프 지문이 일치 |

ARM 시험은 실제 ARM PE를 Unicorn과 WinCE API 대역으로 실행한다. RTC 경계 시험을 위한 변경 DER는 로컬 시간 파서만 거치고 폰이나 가상 TLS 상대에 등록하지 않는다. 상호 TLS는 유효한 합성 인증서를 사용한다. 별도의 실폰·순정 전체 부팅 시험과 구별한다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$openssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'
$out = 'build/codex-authentication-resolution'
& $py -m unittest discover -s tests
& $py tools/build_ce_usb.py "$out/ce-verified" --compiler $cc `
    --bearssl-source build/ce-tls-dependency/bearssl-0.6 --h264-source build/ce-video-dependency/h264bsd
& $py tools/emulate_ce_usb.py "$out/ce-verified" --tls-openssl $openssl --projection
& $py tools/build_ce_usb.py "$out/ce-usb-only" --compiler $cc
& $py tools/emulate_ce_usb.py "$out/ce-usb-only"
```

REA에서 `i30usb.dll`의 ARM PE32, machine `0x01c2`, `COREDLL.dll` ordinal import를 확인했다. 최종 ARM DLL SHA-256은 `3f143b6de89f58c17dca0ffbe20ba3f756c057eee7e68c45a8bb1ec2b1349d9a`다. [ARM ABI](../../build/codex-authentication-resolution/ce-verified/abi.json) · [ARM TLS 결과](../../build/codex-authentication-resolution/ce-verified-regression.json) · [USB 전용 결과](../../build/codex-authentication-resolution/arm-usb-only-regression.json) · [REA 증거](../../build/codex-authentication-resolution/rea-pe-imports.json)

UART의 TLS 핸드셰이크 번호는 `1` ClientHello, `2` ServerHello, `11` Certificate, `12` ServerKeyExchange, `13` CertificateRequest, `14` ServerHelloDone, `15` CertificateVerify, `16` ClientKeyExchange다. 송수신 번호는 레코드에서 관측한 메시지다. 암호화된 Finished의 검증은 엔진 인증 완료 로그로 확인한다.
