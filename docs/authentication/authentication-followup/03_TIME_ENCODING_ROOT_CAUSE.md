# 03 — `-0700` UTCTime이 실패의 실제 원인이었다

작성: 2026-11-25 · 등급: **VERIFIED** (실측 재현 가능)
관련: `src/ce/ce_aa_tls.c`, `build/auth-followup/bearssl-host/`

---

## 1. 질문

이전 세션의 실폰 로그는 다음 한 줄로 끝났다.

```
E/CAR.GAL.SECURITY.LITE: javax.net.ssl.SSLHandshakeException:
java.security.cert.CertPathValidatorException: Trust anchor for certification path not found.
  at com.android.org.conscrypt.ConscryptEngine.verifyCertificateChain(ConscryptEngine.java:1561)
```

이전 보고서는 이를 "폰이 GAL root를 신뢰하지 않는다" 또는 "정책 변경"으로 해석했다.
이번 세션은 **폰에 도달한 인증서가 무엇이었는지**를 코드 경로로 역추적했다.

---

## 2. 확인된 사실

### 2.1 GAL root는 폰이 실제로 신뢰한다

`khimaros/behead`의 `docs/certificates.md`와 `khimaros/dexter`의
`configs/template.toml`은 Android Auto APK에서 추출한 신뢰 앵커의 지문을 명시한다.

```
fingerprint = "49:E5:2E:FC:13:AD:2E:D0:9F:20:4C:3B:10:69:8B:D8:4B:B7:10:5F:51:05:58:AA:14:B8:11:9A:5C:4A:D1:7F"
```

이 값은 우리가 보유한 `build/auth-research/certs/gal-root.pem`의 SHA-256 지문과 **완전히 일치**한다.
즉 폰(AA 앱)은 우리가 가진 바로 그 GAL root를 신뢰한다.

또한 폰의 leaf(`O=CarService`)와 JVC 헤드유닛 leaf(`O=JVC Kenwood, OU=01`)는
**동일한 issuer/AKI**를 가진다.

```
phone-leaf  issuer = C=US, ST=California, L=Mountain View, O=Google Automotive Link
            AKI    = B9:76:AB:EF:F0:33:D0:8B:0A:CC:7E:09:FC:C4:A4:7D:D6:4E:F0:82
aasdk       issuer = C=US, ST=California, L=Mountain View, O=Google Automotive Link
gal-root    SKI    = B9:76:AB:EF:F0:33:D0:8B:0A:CC:7E:09:FC:C4:A4:7D:D6:4E:F0:82
```

따라서 "GAL root를 신뢰하지 않아서"라는 설명은 성립하지 않는다.

### 2.2 GAL 발급 헤드유닛 인증서는 BearSSL 0.6에서 로드되지 않는다

`build/auth-followup/bearssl-host/`에 BearSSL 0.6을 Visual Studio 2026으로 빌드하고
두 개의 호스트 테스트를 작성했다.

- `time_test.c`: `br_x509_decoder_last_error()`만 확인
- `cert_probe.c`: `configure()`와 동일하게 `br_x509_decoder_get_pkey()`까지 확인

```
> time_test.exe ..\phone-leaf.der ..\aasdk.der ..\dhu21.der ..\gal-root.der
..\phone-leaf.der    bytes=881  decoder_error=0   (OK)
..\aasdk.der         bytes=814  decoder_error=48  (BR_ERR_X509_BAD_TIME)
..\dhu21.der         bytes=835  decoder_error=48  (BR_ERR_X509_BAD_TIME)
..\gal-root.der      bytes=909  decoder_error=0   (OK)

> cert_probe.exe ..\aasdk.der ..\aasdk-z.der ..\phone-leaf.der ..\gal-root.der
..\aasdk.der         err=48  pkey=NULL     isCA=0
..\aasdk-z.der       err=0   pkey=present  isCA=0  rsa_bits=2048
..\phone-leaf.der    err=0   pkey=present  isCA=0  rsa_bits=2048
..\gal-root.der      err=0   pkey=present  isCA=1  rsa_bits=2048
```

`BR_ERR_X509_BAD_TIME`는 `inc/bearssl_x509.h` L183에서 `48`이다.

### 2.3 OpenSSL도 같은 지점에서 거부한다

```
> openssl verify -CAfile gal-root.pem aasdk-embedded.pem
error 13 at 0 depth lookup: format error in certificate's notBefore field
aasdk-embedded.pem: verification failed

> openssl verify -no_check_time -CAfile gal-root.pem aasdk-embedded.pem
aasdk-embedded.pem: OK
```

`error 13`은 X509_V_ERR_ERROR_IN_CERT_NOT_BEFORE_FIELD이다. 체인 자체는 유효하고,
**시간 필드의 인코딩만** 문제라는 뜻이다.

### 2.4 코드 경로가 정확히 이 지점에서 멈춘다

`src/ce/ce_aa_tls.c`:

```c
/* configure(), L442-446 */
br_x509_decoder_init(&s->client_decoder, 0, 0);
br_x509_decoder_push(&s->client_decoder, s->identity[0].data, s->identity[0].data_len);
key = br_x509_decoder_get_pkey(&s->client_decoder);
if (!key || key->key_type != BR_KEYTYPE_RSA || !client_validity(&s->identity[0], &start, &end))
    return L"i30 CE TLS head unit certificate missing, unreadable or invalid.\r\n";
```

```c
/* client_validity(), L289-299 -> der_time(), L253-282 */
if (!der_read(source, short_year ? 0x17 : 0x18, &field) ||
    field.length != year_length + 11 || field.bytes[field.length - 1] != 'Z')
    return 0;
```

`br_x509_decoder`는 Validity를 SPKI보다 먼저 파싱하므로, `-0700`을 만나면
공개키를 얻기 전에 `err=48`로 멈춘다. `get_pkey()`는 `NULL`을 반환하고,
`configure()`는 위 문자열로 실패한다.

### 2.5 따라서 라이브 시험은 자체 서명 신원으로 진행되었다

- GAL 발급 JVC/DHU 인증서는 `configure()`를 통과할 수 없다.
- TLS가 시작되었다는 것은 **다른 인증서**(자체 서명, `Z` 시간)가 배포되었다는 뜻이다.
- 폰은 자체 서명 leaf를 GAL root로 검증할 수 없으므로
  `Trust anchor for certification path not found`를 던진다.

이 설명은 추가 가정 없이 로그 전체와 일치한다.

---

## 3. 해결 경로

### 3.1 (권장) 코드 수정 없이 `Google-Android-Reference` 사용

`andreknieriem/open-headunit`의 `app/src/main/res/raw/cert` + `privkey`는
GAL 발급이며 **`Z` 시간**을 사용한다.

```
Subject:  C=US, ST=CA, L=Mountain View, O=Google-Android-Reference
Issuer:   C=US, ST=California, L=Mountain View, O=Google Automotive Link
Serial:   0x7653
Version:  1
Validity: 140708224918Z -> 440707224918Z
SHA-256:  E3:23:CC:6D:D5:2D:1F:2A:28:03:60:A0:E9:2E:FA:04:AB:36:64:DD:68:FA:B3:DD:18:7F:03:D6:63:FE:ED:6D
```

검증:

```
openssl verify -CAfile gal-root.pem cert          -> OK   (strict)
cert_probe.exe gar.der                            -> err=0 pkey=present rsa_bits=2048
openssl x509 -modulus / openssl rsa -modulus      -> PAIR OK
```

`configure()`의 모든 조건을 만족하므로 **펌웨어 코드를 수정하지 않고** 배포 가능하다.
`open-headunit`은 이 쌍을 실제 헤드유닛 앱의 클라이언트 신원으로 사용하며
(`SingleKeyKeyManager` + `SslContextFactory`), 필드에서 동작하는 구현이다.

배포 시 주의:

1. `i30-client.pem`의 **첫 번째 인증서가 leaf**여야 한다. root를 먼저 넣지 않는다.
2. `i30-ca.pem`/`.der`는 GAL root여야 한다 (지문 `49:E5:2E:FC:...`).
3. `i30-client-key.pem`은 위 cert와 쌍이어야 한다 (`PAIR OK`).
4. 키는 커밋·배포하지 않는다 (테스트 단계 한정).

### 3.2 (대안) 파서를 고쳐 JVC 인증서 사용

`-0700`을 허용하려면 두 곳을 고쳐야 한다.

**(a) `der_time()` — 오프셋 허용 및 UTC 변환**

```c
/* field.bytes[field.length-1] == 'Z' 이거나 ±HHMM으로 끝나야 한다 */
int offset_seconds = 0;
if (field.length >= 5 && (field.bytes[field.length-5] == '+' || field.bytes[field.length-5] == '-')) {
    unsigned oh = date_number(field.bytes + field.length - 4, 2);
    unsigned om = date_number(field.bytes + field.length - 2, 2);
    if (oh > 23 || om > 59)
        return 0;
    offset_seconds = (int)(oh * 3600U + om * 60U);
    if (field.bytes[field.length-5] == '-')
        offset_seconds = -offset_seconds;
    offset_seconds = -offset_seconds;   /* UTC = local - offset */
    field.length -= 5;
} else if (field.length && field.bytes[field.length-1] == 'Z') {
    field.length -= 1;
} else {
    return 0;
}
if (field.length != year_length + 11)
    return 0;
```

이후 `out->day`/`out->second`를 계산한 뒤:

```c
int64_t total = (int64_t)out->day * 86400 + out->second + offset_seconds;
if (total < 0)
    return 0;
out->day = (uint32_t)(total / 86400);
out->second = (uint32_t)(total % 86400);
```

**(b) 클라이언트 인증서 공개키 추출 — BearSSL 디코더 우회**

`configure()`에서 `br_x509_decoder_push`/`get_pkey` 대신 자체 DER walk로 SPKI를 읽는다.

```
Certificate      SEQUENCE
  TBSCertificate SEQUENCE
    [0] version (optional)
    serialNumber INTEGER
    signature    SEQUENCE
    issuer       SEQUENCE
    validity     SEQUENCE
    subject      SEQUENCE
    SPKI         SEQUENCE { AlgorithmIdentifier, BIT STRING }
                   BIT STRING -> RSAPublicKey SEQUENCE { modulus INTEGER, exponent INTEGER }
```

기존 `der_read()`를 그대로 사용해 `br_rsa_public_key`를 채우고 `matches_key()`에 넘긴다.
이렇게 하면 BearSSL 소스를 건드리지 않고 `ce_aa_tls.c`만 수정한다.

**(c) 선택: BearSSL `asn1.t0` 패치**

`build/ce-tls-dependency/bearssl-0.6/src/x509/asn1.t0`의 `read-date`를 고쳐
오프셋을 허용하고 UTC로 정규화할 수도 있다. 이 경우 `br_x509_minimal`의 peer 검증도
오프셋을 받아들이게 되지만, 벤더 의존성을 수정하므로 (b)보다 파급이 크다.

---

## 4. 판정

| 주장 | 등급 | 근거 |
| --- | --- | --- |
| GAL root가 폰의 신뢰 앵커와 동일 | **VERIFIED** | dexter 설정 지문 == `gal-root.pem` 지문 |
| JVC/DHU 인증서는 BearSSL에서 `err=48`, `pkey=NULL` | **VERIFIED** | `cert_probe.exe` |
| OpenSSL도 `-0700`을 `error 13`으로 거부 | **VERIFIED** | `openssl verify` |
| `configure()`가 GAL 발급 인증서를 거부 | **VERIFIED** | 코드 경로 + 실측 |
| 라이브 실패는 자체 서명 신원 때문 | **VERIFIED (추론 포함)** | 위 사실들의 필연적 귀결 |
| `Google-Android-Reference`가 현재 코드로 로드됨 | **VERIFIED** | `cert_probe` err=0, strict verify OK, PAIR OK |
| `Google-Android-Reference`가 i30 폰에서 통과 | **PARTIAL** | open-headunit 필드 동작 + DHU 기준 성공. i30 라이브 미시험 |

---

## 5. 재현

```powershell
# 1) BearSSL 빌드 (Visual Studio 2026)
cmd /c build\auth-followup\build_bearssl.bat
cmd /c build\auth-followup\build_time_test.bat
cmd /c build\auth-followup\build_cert_probe.bat

# 2) DER 준비
$o='C:\Program Files\Git\usr\bin\openssl.exe'
& $o x509 -in build\auth-research\certs\aasdk-embedded.pem -outform DER -out build\auth-followup\aasdk.der
& $o x509 -in build\auth-research\certs\phone-leaf.pem     -outform DER -out build\auth-followup\phone-leaf.der
& $o x509 -in build\auth-research\certs\gal-root.pem       -outform DER -out build\auth-followup\gal-root.der

# 3) 실측
cd build\auth-followup\bearssl-host
.\time_test.exe ..\aasdk.der ..\phone-leaf.der ..\gal-root.der
.\cert_probe.exe ..\aasdk.der ..\phone-leaf.der ..\gal-root.der

# 4) Google-Android-Reference 검증
cd F:\i30-gen2-android-auto
& $o verify -CAfile build\auth-research\certs\gal-root.pem build\auth-followup\open-headunit\cert
& $o asn1parse -in build\auth-followup\open-headunit\cert -i | Select-String 'UTCTIME'
```

---

## 6. 주의

- `der_time_normalize.py`로 `-0700`을 `Z`로 바꾸면 **TBS 서명이 깨진다.**
  이 출력은 파서 시험용 벡터일 뿐, 실제 신원으로 사용할 수 없다.
- `Google-Android-Reference`의 private key는 테스트 단계에서만 사용하고,
  저장소에 커밋하거나 제품에 포함하지 않는다.
