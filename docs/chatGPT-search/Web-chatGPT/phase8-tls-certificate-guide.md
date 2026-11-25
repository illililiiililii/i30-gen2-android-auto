# Android Auto 통신 오류 07 해결 및 TLS 인증서 실전 적용 가이드

- 대상: `illililiiililii/i30-gen2-android-auto` (`main`, 2026-11-25 확인)
- 저장 위치: `docs/phase8-tls-certificate-guide.md`
- 범위: Windows CE 6.0 / ARMV4T 수신기, PC 진단 수신기, Android Auto 상호 TLS
- 검증 분류: **코드 확인**, **저장소에 기록된 과거 재현**, **외부 확인**, **미시험**

## 1. 현재 리포지토리 TLS 구현 및 기존 인증서 점검 결과

### 1.1 직접 확인한 구현 경로

| 코드 | 기능/실제 함수 | TLS 기술 |
|---|---|---|
| `src/i30_receiver/tls.py` | `client_context()`, `TlsRecords.handshake()` | Python `ssl`, OpenSSL 기반 TLS 1.2, `CERT_REQUIRED` |
| `src/i30_receiver/protocol.py` | `ProtocolSession.handle()`, `advance_tls()` | AA 채널 0의 `ENCAPSULATED_SSL`, TLS 후 `AUTH_COMPLETE` |
| `src/i30_receiver/session.py` | `SessionManager._run()` | USB 세션, 프로토콜 상태 추적 |
| `src/i30_receiver/cli.py` | `--ca`, `--peer-name`, `--peer-sha256`, `--cert`, `--key` | PC 시험 설정 |
| `src/ce/ce_aa_tls.c` | `configure()`, `handshake()`, `discover()`, `i30_ce_authenticate()` | BearSSL 0.6, TLS 클라이언트, 상호 인증 |
| `tools/build_ce_usb.py` | `build_bearssl()`, `build()` | GCC `-march=armv4t -marm -ffreestanding -fshort-wchar`; ARM 대상 CE PE 빌드 |
| `tools/gd13my_guest_clock.py` | `utc_mailbox()` | 호스트 UTC에서 에뮬레이터 시각 메일박스 생성 |

**핵심 역할:** i30 수신기는 TLS **클라이언트**, Android 스마트폰은 TLS **서버**다. 폰이 `CertificateRequest`를 보내면 i30의 **클라이언트 인증서**와 개인키로 인증한다. 이것을 헤드유닛의 ‘TLS 서버 인증서’라고 분류하면 진단 방향이 뒤집힌다.

PC 코드 `client_context()`는 TLS 1.2로 고정하며 CA 체인과 피어 이름 또는 지문을 확인하고, `ssl.SSLContext.load_cert_chain(cert,key)`로 클라이언트 신원을 읽는다. CE 코드 `configure()`는 `br_ssl_client_set_single_rsa()`로 클라이언트 체인을 등록하고 `br_ssl_engine_set_versions(..., BR_TLS12, BR_TLS12)`를 설정한다. `handshake()` 성공 뒤에만 `discover()`가 AA 인증 완료 및 서비스 탐색을 진행한다.

### 1.2 CE의 실제 인증서 경로와 우선순위

`src/ce/ce_aa_tls.c`의 `#define TLS_PATH L"\\DiskA\\Application\\NAVI\\"`를 기준으로:

| 경로/파일 | 내용 | 중요 조건 |
|---|---|---|
| `i30-ca.der` 또는 `i30-ca.pem` | 폰 인증서를 검증하는 공개 CA | 먼저 DER를 시도 |
| `i30-client.der` 또는 `i30-client.pem` | 헤드유닛 인증서. PEM은 리프부터 중간 CA 순 | 최대 4장; DER 우선 |
| `i30-client-key.der` 또는 `i30-client-key.pem` | 해당 신원의 RSA 개인키 | DER 우선; 키·인증서 일치 필수 |
| `i30-peer.txt` | 폰 인증서에 대해 검증할 이름 | 지문 설정과 동시 사용 불가 |
| `i30-peer-sha256.txt` | 폰 리프의 SHA-256 지문(64자리 hex) | 이름 설정과 동시 사용 불가 |

`open_credential()`는 DER 파일이 **없는 경우** PEM으로 전환한다. DER 파일이 존재하지만 잘못되었을 때 자동으로 PEM을 선택하지 않는다. 따라서 신규 PEM 파일을 설치할 때 같은 이름의 구형 DER가 남아 있는지 확인한다.

`configure()`는 `br_x509_decoder_push()`, `br_x509_decoder_get_pkey()`, `client_validity()`, `br_skey_decoder_get_rsa()`, `matches_key()` 및 `client_chain_valid()`를 통과해야 한다. **실패하면 핸드셰이크가 시작되지 않는다.** `i30_ce_authenticate()`의 현재 코드가 `if (!status) status = handshake(session, link);`이기 때문이다. 자동 자체 서명 신원 폴백 코드는 없다.

### 1.3 공개된 저장소 트리의 인증서 자산 탐색

GitHub `main` 재귀 트리에서 **261개 blob 파일 전체의 경로**를 점검했다. `.pem`, `.crt`, `.cer`, `.der`, `.pfx`, `.p12`, `.key` 확장자의 **직접 커밋된 파일은 0개**였다. `src/`, `tools/`, `research/`, `docs/`에 인증서의 공개키·지문 및 외부 참조를 담은 문서/코드가 존재하지만, 인증서·키의 모든 바이트 배열을 포함하는 전 파일 본문 재귀 검색까지 수행한 것으로 보아서는 안 된다.

재현 기록이 언급하는 `build/auth-research/certs/gal-root.pem`, `build/auth-followup/open-headunit/cert`, `build/auth-followup/open-headunit/privkey` 및 로그 파일은 **GitHub 트리에 포함되지 않은 로컬 산출물**이다. 이 환경에서 해당 파일의 존재와 SHA-256은 재검증하지 못했다. 리포지토리에서 확인된 재현 보고는 다음과 같다.

- `docs/OpenCode-search/authentication-followup/03_TIME_ENCODING_ROOT_CAUSE.md`: BearSSL 0.6의 `BR_ERR_X509_BAD_TIME (48)` 재현, 공개 후보 비교.
- `docs/Codex-authentication-resolution/RESEARCH_VALIDATION.md`: 실패 경로 재점검 및 과거 분석 정정.
- `docs/Codex-authentication-resolution/TLS_REGRESSION_RESULTS.md`: 인증서 로딩·지문·ARM 회귀 시험.
- `docs/Codex-authentication-resolution/REAL_PHONE_TEST_RESULTS.md`: 신규 ARM DLL의 실폰 인증 시험은 아직 수행되지 않았음.

### 1.4 실패 원인과 확정 범위

**과거 PC 실폰 시험에서 확인된 오류:**

```text
javax.net.ssl.SSLHandshakeException
java.security.cert.CertPathValidatorException:
Trust anchor for certification path not found.
at com.android.org.conscrypt.ConscryptEngine.verifyCertificateChain(...)
```

폰(서버)이 헤드유닛(클라이언트)의 자체 발급 시험 신원을 검증하면서 실패했다. USB AOA 2.0 및 AAP 1.7 교환, 폰의 TLS 첫 플라이트(ServerHello, Certificate, ServerKeyExchange, CertificateRequest, ServerHelloDone)는 과거 시험에서 관측됐다. 당시 실제 송신 리프 지문 및 TLS fatal alert 번호는 미확인이다. 실폰 오류 **07이라는 숫자만으로 모든 연결 실패를 동일 원인으로 해석하지 않는다.**

**별도로 재현한 로컬 파서 오류:** AASDK JVC 및 DHU 2.1의 일부 공개 리프에는 `140704000000-0700`처럼 비표준 오프셋을 담은 UTCTime이 있고, BearSSL 0.6은 `br_x509_decoder_last_error() == 48`을 반환한다. `src/ce/ce_aa_tls.c`의 `der_time()`도 `Z`로 종료되는 값만 허용한다. 따라서 이 원본 인증서는 CE `configure()` 단계를 통과하지 못한다. 그러나 과거 실폰 PC 오류가 WinCE에서 이 파서 오류를 겪고 자동 폴백한 결과라는 주장은 **반증됐다**. 두 문제는 서로 다른 시험 경로다.

## 2. 사용 가능한 유효 인증서 탐색 결과 및 적용 방안 비교

| 방안 | 검증된 사실 | WinCE 6.0 호환성 | 즉시 가능한 작업 | 실폰 성공 확률 |
|---|---|---|---|---|
| A. Google DHU 2.0/2.1 비교 | DHU 공식 실행은 실폰 TLS 1.2, `0xC02F`, 800×480까지 성공; DHU 2.1 공개 인증서의 시간 형식은 BearSSL에서 거부 | 원본 `-0700`은 파서 불호환 | DHU와 수신기의 ClientHello, 체인, 암호군 비교 | **[미확인: 실폰 재사용 시험 및 사용 권한 검증 필요]** |
| B. OpenAuto/AASDK JVC 공개 신원 | GAL 발급 공개 리프의 BearSSL 오류 48 재현 | 원본은 직접 로딩 불가 | 공개 인증서 파싱·체인 진단, 자체 테스트 벡터 생성 | **[미확인]** |
| B2. Open Headunit Google-Android-Reference | `Z` 시간, RSA 2048, BearSSL 파싱 및 공개키·개인키 일치에 관한 기존 재현 기록 | 형식·파서는 호환 | 공개 인증서 분석 및 권리 확인 | **[미확인: GD13MY 실폰 인증 미시험]** |
| C. 테스트폰 신뢰 정책 변경 | 자체 서명 신원은 실제 Google AA에서 거부됨 | CE와 무관 | 승인된 별도 시험 앱/AARE형 상대에서 직접 생성한 CA 사용 | **순정 AA 앱 수락 미확인; 검증 우회는 권장하지 않음** |
| D. 정식 평가/개발 신원 | Cinemo 등 SDK/인증 프로그램이 존재 | WinCE 6.0 지원 미확인 | 공급사에 평가 신원, OS 지원, 사용 범위 확인 | **[미확인]** |

**공개 인증서 ≠ 사용 권한이 부여된 인증서.** DHU와 타사 헤드유닛에 포함된 개인키를 재사용하거나 외부 펌웨어에서 추출하는 것은 기술적 관찰과 권한 문제를 분리해야 한다. 여기서는 공개 인증서와 해시 분석, 본인 소유·사용 허가를 받은 키의 변환만 절차화한다. Google/Tier-1/OEM 신원의 무단 추출·주입 또는 휴대폰 인증 검증 비활성화는 해결책으로 간주하지 않는다.

### 2.1 구체적 출처

- 공식 DHU: <https://developer.android.com/training/cars/testing/dhu> — USB·ADB로 작동하는 공식 비교 기준. 다른 임의 수신기용 개인키 발급 절차는 아님.
- Open Headunit: <https://github.com/andreknieriem/open-headunit> — `app/src/main/res/raw/cert`와 `privkey`가 존재함을 확인. **개인키의 제3자 재사용 권한은 확인하지 못함**.
- AASDK/OpenAuto: <https://github.com/opencardev/aasdk> 및 <https://github.com/f1xpl/openauto> — 프로토콜·인증서 로딩 비교 구현. 공개된 타사 신원의 재사용은 별도 권한 문제.
- AARE 인증서 문서: <https://github.com/prototux/AARE/blob/main/docs/certificates.md> — 폰 측 구현과 인증서 호환성 조사 자료. Google 공식 폰의 신뢰 정책을 변경했다는 뜻이 아님.
- 공급사와 인증 경로: `docs/OpenCode-search/authentication-deep-research/09_OFFICIAL_PROVISIONING_ROUTES.md` 및 `docs/OpenCode-search/authentication-followup/05_OFFICIAL_ROUTES.md`에 정리됨.

## 3. 인증서 추출 및 코드베이스 실전 적용 절차

### 3.1 공개 인증서 분석 및 승인된 개인키 포맷 변환 명령어

다음 PowerShell 명령은 **프로젝트 루트**에서 실행한다. 실제 존재하는 로컬 인증서만 대상으로 하며, 여기서 사용하는 `<...>` 값은 본인이 권한을 가진 파일의 경로로 치환한다.

```powershell
Set-Location 'F:\i30-gen2-android-auto'
$openssl = Join-Path $env:ProgramFiles 'Git\usr\bin\openssl.exe'
if (!(Test-Path $openssl)) { throw 'Git for Windows OpenSSL 경로 확인 필요' }
$cert = 'D:\aa-test-identity\authorized-client.pem'
$ca = 'D:\aa-test-identity\authorized-ca.pem'
$key = 'D:\aa-test-identity\authorized-client-key.pem'

# 1) 리프 인증서의 공개 속성 및 실제 인코딩 확인
& $openssl x509 -in $cert -noout -subject -issuer -dates -serial -fingerprint -sha256
& $openssl asn1parse -in $cert -i | Select-String 'UTCTIME|GENERALIZEDTIME'

# 2) 공개 인증서의 체인 검증 (OpenSSL이 오류를 출력하면 중단)
& $openssl verify -CAfile $ca $cert
if ($LASTEXITCODE -ne 0) { throw '인증서 체인 검증 실패' }

# 3) 승인된 인증서의 PEM -> DER 변환
& $openssl x509 -in $cert -outform DER -out 'D:\aa-test-identity\authorized-client.der'

# 4) 승인된 RSA 키의 PEM -> PKCS#8 DER 변환
# 주의: 이 파일은 암호화되지 않은 민감한 개인키이므로 별도 안전한 시험 영역에만 보관
& $openssl pkcs8 -topk8 -nocrypt -in $key -outform DER -out 'D:\aa-test-identity\authorized-client-key.der'

# 5) 인증서/키가 같은 공개키인지 검증 (개인키 원문을 출력하지 않음)
$pubCert = & $openssl x509 -in $cert -pubkey -noout | & $openssl pkey -pubin -outform DER
$pubKey = & $openssl pkey -in $key -pubout -outform DER
# 바이너리 파이프라인 비교는 파일로 수행하는 편이 안전하며, 아래 해시 방법을 권장
& $openssl x509 -in $cert -pubkey -noout | Set-Content -Encoding ascii 'D:\aa-test-identity\cert-public.pem'
& $openssl pkey -in $key -pubout -out 'D:\aa-test-identity\key-public.pem'
$h1 = (& $openssl pkey -pubin -in 'D:\aa-test-identity\cert-public.pem' -outform DER | Out-String)
$h2 = (& $openssl pkey -pubin -in 'D:\aa-test-identity\key-public.pem' -outform DER | Out-String)
# PowerShell 텍스트 파이프라인은 DER에 적합하지 않으므로 최종 비교는 아래 모듈러스 값 사용
$certMod = & $openssl x509 -in $cert -noout -modulus
$keyMod = & $openssl rsa -in $key -noout -modulus
if ($certMod -ne $keyMod) { throw 'RSA 인증서와 개인키 불일치' }
```

이 프로젝트의 CE 빌드가 읽는 형식은 PEM/DER이다. **PKCS#12/PFX를 그대로 배치하지 않는다.** 해당 형식의 승인된 자격 증명이라면 다음과 같이 **안전한 로컬 작업 폴더**에서 별도 추출한다. OpenSSL 버전에 따라 암호화 방식 또는 `-legacy` 옵션이 필요할 수 있다.

```powershell
$pfx = 'D:\aa-test-identity\authorized-identity.pfx'
& $openssl pkcs12 -in $pfx -clcerts -nokeys -out 'D:\aa-test-identity\client.pem'
& $openssl pkcs12 -in $pfx -nocerts -nodes -out 'D:\aa-test-identity\client-key.pem'
```

**외부 배포물에서 제3자의 개인키를 추출하는 명령은 포함하지 않는다.** 공개 인증서 자체는 별도로 추출·해석할 수 있다. DER 시간을 임의로 `-0700`에서 `Z`로 바꾸면 서명 대상(TBS Certificate)이 변경되어 **서명 무결성이 깨진다**. 변경된 인증서를 검증 없이 폰에 보내지 않는다.

### 3.2 Windows PC 진단 수신기 적용

`src/i30_receiver/cli.py`가 실제 제공하는 파라미터:

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv\Scripts\python.exe'
& $py build\i30-receiver.pyz --log 'research\evidence\authorized-phone-test.jsonl' connect `
  --device '1-2' `
  --ca 'D:\aa-test-identity\authorized-ca.pem' `
  --peer-sha256 '<실제 시험폰 공개 leaf의 SHA-256 64자리>' `
  --cert 'D:\aa-test-identity\authorized-client.pem' `
  --key 'D:\aa-test-identity\authorized-client-key.pem'
```

실제 포트, 서명 체인과 지문은 시험마다 확인한다. `client_context()`는 `ssl.CERT_REQUIRED`와 `TLSv1_2`를 유지한다. 순정 폰 인증 실패를 숨기려고 `CERT_NONE`이나 이름·지문 무검증으로 바꾸지 않는다. **수신기의 폰 검증을 해제해도 폰이 수신기 인증서를 신뢰하도록 만들지는 못한다.**

### 3.3 WinCE 설정 배치 및 정확한 수정 지점

1. 권한이 있는 **클라이언트 리프 인증서**를 `\DiskA\Application\NAVI\i30-client.pem`으로 배치한다. 발급 중간 CA가 있다면 리프 다음에 나열한다. 루트 CA를 무조건 클라이언트 체인에 포함시키지 않는다.
2. 대응하는 승인된 RSA 개인키를 `i30-client-key.pem`으로 배치한다. 이 파일은 외부에 공개하거나 저장소에 커밋하지 않는다.
3. **폰의 인증서를 검증할 CA**를 `i30-ca.pem`으로 배치한다. `i30-ca.pem`은 헤드유닛 인증서가 아니라 **상대 폰 서버** 검증용이다.
4. `i30-peer.txt` 또는 `i30-peer-sha256.txt` 중 정확히 하나를 구성한다. 둘 다 설정하면 현재 코드에서 거부한다.
5. 새 PEM을 쓴다면 같은 이름의 기존 DER 우선 파일을 백업하고 제거해 **실제로 의도한 인증서가 로드되도록** 한다.
6. 게스트 UTC가 유효기간 범위에 있는지 확인하고, 로딩·송신 리프 SHA-256이 일치하는지 UART에서 대조한다.

실제 코드 위치:

| 위치 | 수정/점검 목적 |
|---|---|
| `src/ce/ce_aa_tls.c:175-180` | `open_credential()`의 DER 우선 선택 확인 |
| `src/ce/ce_aa_tls.c:183-234` | PEM/DER 다중 인증서·RSA 키 형식 검증 |
| `src/ce/ce_aa_tls.c:272-301` | `der_time()`에서 `Z` 이외 시간을 거부 |
| `src/ce/ce_aa_tls.c:479-490` | `read_utc()`의 WinCE UTC 확인 |
| `src/ce/ce_aa_tls.c:572-670` | `configure()`의 인증서, 개인키, 체인, CA, TLS 설정 |
| `src/ce/ce_aa_tls.c:955-981` | `handshake_error()`의 peer alert/오류 분류 |
| `src/ce/ce_aa_tls.c:984-1029` | `handshake()` 레코드 처리 및 성공 지점 |
| `src/ce/ce_aa_tls.c:1031-1061` | 인증 실패 후 핸드셰이크 미시작 분기 |

**비표준 `±HHMM` 인증서 지원 패치 설계:** `der_time()`만 수정하면 불충분하다. `configure()`가 호출하는 **BearSSL `br_x509_decoder`도 자체적으로 시간 파싱 중 실패**하기 때문이다. 수정에는 (a) 비표준 형식에 대한 명시적 허용 정책과 UTC 환산, (b) 인증서의 공개키 추출·서명 검증을 유지하는 파서 교체/검증 경로, (c) 표준 인증서의 기존 동작에 대한 회귀 테스트가 필요하다. 단순 문자열 변경이나 `get_pkey()` 실패 무시는 안전한 패치가 아니다. 승인된 유효한 표준 `Z` 형식의 인증서 사용을 우선하며, 비표준 인증서를 받아들이는 변경은 격리 시험에서 수행한다.

**현재 코드에 있는 진단 출력 예:**

```text
i30 CE TLS loaded leaf SHA-256:
i30 CE TLS head unit certificate decoder result:
i30 CE TLS head unit certificate and RSA key do not match.
i30 CE TLS guest UTC unavailable or invalid.
i30 CE TLS BearSSL error:
i30 CE TLS peer fatal alert:
i30 CE TLS 1.2 authenticated; cipher suite (decimal):
i30 CE Android Auto AUTH_COMPLETE sent.
i30 CE Android Auto encrypted service discovery request received.
```

`tools/build_ce_usb.py`의 BearSSL 경로는 `--bearssl-source`로 주입하며, `--compiler`는 ARM GNU GCC 실행 파일의 실제 경로를 받아야 한다. 기존 재현 예:

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv\Scripts\python.exe'
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools\arm-gnu-14.2\bin\arm-none-eabi-gcc.exe'
& $py tools\build_ce_usb.py 'build\ce-aa-tls-audit' --compiler $cc `
  --bearssl-source 'build\ce-tls-dependency\bearssl-0.6'
```

경로는 기존 문서에 기록된 로컬 환경 사례이며 GitHub에는 의존성 바이너리가 커밋되어 있지 않다. 원본 이미지를 덮어쓰지 말고 분리된 에뮬레이터 이미지에서만 재빌드/시험한다.

### 3.4 WinCE RTC 및 인증서 검증 체크리스트

- [ ] 에뮬레이터가 초기 1601-01-01 UTC를 그대로 사용하지 않는다.
- [ ] `tools/gd13my_guest_clock.py`의 `utc_mailbox()`와 부팅 초기 `SetSystemTime` 경로를 확인한다.
- [ ] `GetSystemTimeAsFileTime`으로 읽은 게스트 UTC가 현재 실제 UTC와 일치한다.
- [ ] 인증서 `notBefore`, `notAfter`의 ASN.1 인코딩이 현재 디코더에서 처리된다.
- [ ] 로드한 리프 SHA-256과 실제 TLS 송신 리프 SHA-256이 일치한다.
- [ ] 리프 인증서·RSA 개인키 모듈러스가 일치한다.
- [ ] 폰 인증서 검증용 CA와 예상 이름/지문이 맞는다.
- [ ] 인증서 체인 순서가 리프 → 중간 CA이고 불필요한 루트 전송이 없다.
- [ ] 시험용 개인키가 로그·Git·공유 이미지에 포함되지 않았다.

## 4. 실폰 연결 검증 및 오류 07 트러블슈팅

### 4.1 비교 시험 순서

1. **기준 확보:** 동일 스마트폰·케이블에서 공식 DHU 2.0 연결을 다시 확인한다. 공식 DHU의 성공은 자체 수신기의 신원 수락과 **별개**다.
2. **PC 수신기:** 승인된 자체 클라이언트 신원으로 `src/i30_receiver/tls.py`가 TLS 1.2를 협상하는지 확인한다.
3. **CE 격리 에뮬레이터:** 동일한 승인된 신원으로 AOA → 버전 → TLS → `AUTH_COMPLETE` → 서비스 탐색을 검증한다.
4. **WinCE 전체 순정 에뮬레이터:** 실제 순정 메뉴와 USB 인계 경로에서 인증 및 표시 복귀를 재검증한다.
5. **실폰:** 폰 로그와 UART의 인증서 지문·핸드셰이크 단계를 동시 수집하고 성공한 단계만 기록한다.
6. **차량 적용:** 에뮬레이터와 실제 하드웨어 차이, USB 전원/복구, 펌웨어 롤백 및 벽돌 위험을 별도로 평가한다. 실폰 TLS 성공만으로 실차 업데이트를 진행하지 않는다.

기존 순정 게스트의 가상 폰 회귀는 `docs/Codex-authentication-resolution/EMULATOR_VALIDATION.md`에 상호 TLS, `AUTH_COMPLETE`, 영상 프레임, 분리 후 복귀 및 재연결 결과가 기록돼 있다. **이것은 실폰 Google AA 인증 성공이 아니다.**

### 4.2 Android Logcat 및 TLS 분석

```powershell
# 실폰을 ADB로 연결할 수 있는 상태에서 실행
adb devices
adb logcat -c
adb logcat -v threadtime -s CAR.GAL.SECURITY.LITE:* Conscrypt:* AndroidAuto:* > 'D:\aa-test-identity\phone-tls.log'
```

필터가 펌웨어/AA 버전에 따라 다를 수 있으므로 아무 로그도 없으면 다음과 같이 전체 로그를 기록하여 사후 검색한다.

```powershell
adb logcat -d -v threadtime > 'D:\aa-test-identity\phone-full.log'
Select-String -Path 'D:\aa-test-identity\phone-full.log' `
  -Pattern 'SSLHandshakeException|CertPathValidatorException|verifyCertificateChain|CAR.GAL|TLS|certificate|handshake'
```

USB AOA bulk의 TLS 페이로드는 이더넷 TCP가 아니므로 **Wireshark에서 일반 HTTPS 연결처럼 직접 잡히지 않는다**. Windows에서는 USBPcap 캡처와 Wireshark USB 디섹터로 AOA endpoint `0x81`/`0x01`의 데이터 흐름을 보거나, 코드가 이미 제공하는 TLS 레코드·핸드셰이크 추적을 사용한다. 패킷 경계와 TLS 레코드 경계가 일치하지 않을 수 있으므로 재조립 후 분석한다. 개인키를 네트워크 캡처에 포함하지 않는다.

| 관측값 | 의미 | 다음 점검 |
|---|---|---|
| `Trust anchor for certification path not found` (폰) | 폰이 받은 헤드유닛 클라이언트 인증 체인의 신뢰 앵커를 찾지 못함 | **실제로 송신한 리프 SHA-256**·발급자·체인 대조; 승인된 신원인지 확인 |
| `BR_ERR_X509_BAD_TIME (48)` (CE 로컬) | BearSSL 공개키/인증서 디코딩 과정에서 시간 필드 불수용 | 원본 ASN.1 UTCTime 인코딩 확인. `-0700`인지 구분 |
| `guest UTC unavailable or invalid` | CE 시스템 날짜가 비정상 | 에뮬레이터 UTC 메일박스 및 `SetSystemTime` 경로 확인 |
| `RSA key do not match` | 인증서와 개인키 불일치 | OpenSSL 모듈러스 비교, DER 우선순위 확인 |
| `peer fatal alert: 48` | 상대가 `unknown_ca` alert 송신 | 실제 수신 로그로 확인된 경우에만 폰의 CA 거부로 분류 |
| `phone certificate chain has no trusted anchor` (CE) | **반대 방향**: i30가 폰 인증서를 거부 | `i30-ca.pem`·폰 리프·중간 체인 확인 |
| `invalid Android Auto handshake frame` | AAP 프레이밍/레코드 재조립 오류 | 프레임 헤더, 길이, 마지막 플래그 확인 |
| Windows USB `Access denied` | AOA 진입 전 또는 드라이버 접근 문제 | WinUSB 바인딩/포트 독점 확인; TLS 실패와 별개 |
| `AUTH_COMPLETE sent` 후 Discovery 미진행 | TLS 이후 응용 프로토콜 문제 | 메시지 4, 암호화된 서비스 탐색 흐름 확인 |

**특별 주의:** 과거 실폰 로그에는 Conscrypt의 신뢰 앵커 실패가 있지만, 구체적인 TLS fatal alert 코드 48이 수신됐다는 증거는 없다. `handshake_error()`에 alert 48 처리 코드가 **존재한다는 사실**은 해당 alert를 실제로 관측했다는 뜻이 아니다.

### 4.3 완료 기준 및 미확인 사항

- 완료 조건 A: PC 및 ARM 가상 폰 상호 TLS 회귀 시험 통과 — **기존 문서상 통과**.
- 완료 조건 B: 실제 Google AA 폰이 프로젝트의 사용 권한 있는 클라이언트 신원을 수락 — **미완료**.
- 완료 조건 C: 실폰과 `AUTH_COMPLETE(0)`, 암호화된 서비스 탐색, 800×480 표시, 터치, 재연결 — **미완료**.
- 완료 조건 D: 실제 i30 하드웨어에서 안정성과 복구 경로 확인 — **미완료**.

현재 성공 확률을 뒷받침할 실폰 재현 통계가 없어 수치화하지 않는다. 즉각적 개발 우선순위는 **승인된 테스트 신원 확보 → 실제 송신 지문 검증 → 실폰 Conscrypt 결과 대조 → TLS 이후 기능 시험**이다.

## 근거 및 참고 문서

- 리포지토리: <https://github.com/illililiiililii/i30-gen2-android-auto>
- 교차 검증: `docs/Codex-authentication-resolution/RESEARCH_VALIDATION.md`
- 최신 인계: `docs/Codex-authentication-resolution/FINAL_HANDOFF.md`
- 로더 회귀: `docs/Codex-authentication-resolution/TLS_REGRESSION_RESULTS.md`
- 실폰 시험 상태: `docs/Codex-authentication-resolution/REAL_PHONE_TEST_RESULTS.md`
- 인증서 시간 실험: `docs/OpenCode-search/authentication-followup/03_TIME_ENCODING_ROOT_CAUSE.md`
- 공개 신원 비교: `docs/OpenCode-search/authentication-followup/04_EXTERNAL_CASES_AND_IDENTITIES.md`
- Google 공식 DHU: <https://developer.android.com/training/cars/testing/dhu>
- AARE 인증서 설명: <https://github.com/prototux/AARE/blob/main/docs/certificates.md>

**미확인 표시 규칙:** GitHub에서 실제 코드나 문서를 확인한 것과 기존 로컬 시험 기록의 주장을 구분했다. GitHub에 포함되지 않은 로컬 빌드·폰 로그의 원본 바이트는 이번 환경에서 독립적으로 재실행·검증하지 않았다.
