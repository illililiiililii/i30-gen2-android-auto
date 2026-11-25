# 02. 공개 헤드유닛 인증서 심층 분석 (P0-2)

작성: 2026-11-25 · 대상: DHU 2.1, AASDK(JVC Kenwood), CarService leaf, GAL root
원칙: **공개 인증서만** 분석. 개인키는 열람·추출·사용하지 않는다.

## 0. 이번 분석의 새로운 사실 (기존 연구 대비)

| 항목 | 기존 연구 | 이번 검증 | 등급 |
| --- | --- | --- | --- |
| 폰 leaf X.509 버전 | v1 | **v3** (SKI/AKI 확장 존재) | VERIFIED |
| GAL root | "확인 범위 밖" | **v3, `CA:TRUE`, sha1WithRSA, self-signed** | VERIFIED |
| DHU/AASDK 인증서가 GAL root로 연결 | 추정 | **`openssl verify` 통과로 확인** | VERIFIED |
| 중간 CA | 미확인 | **없음** (2장 체인) | VERIFIED |
| DHU/AASDK 인증서 시간 인코딩 | 미기록 | **UTCTime + `-0700` 오프셋 (DER 비준수)** | VERIFIED |
| "X.509 v1이 요구된다" | 가설 | **근거 없음.** v1은 Google HU 인증서의 관행일 뿐 | HYPOTHESIS 폐기 |
| "특정 확장 필드 필요" | 가설 | **폐기.** DHU 인증서에 확장이 0개인데 폰이 수락 | VERIFIED(반증) |
| 현재 오류 07의 원인 = 만료 | 일부 문서 | **폐기.** HU 인증서는 2045/2048까지 유효 | VERIFIED |

---

## 1. 분석 대상과 출처

| # | 자료 | 출처 URL | 로컬 사본 | 파일 SHA-256 |
| --- | --- | --- | --- | --- |
| C1 | 폰 체인 (AA 18.0.664264-release, 2장) | `https://raw.githubusercontent.com/iscle/android-auto-certificates/main/android-auto/18.0.664264-release/certificate.pem` | `build/auth-research/certs/android-auto__18.0.664264-release__certificate.pem` | `43c05285265d83a9e1ae74da7359f07c081c711354a2c397292419169d8c360f` |
| C2 | DHU 2.1 인증서 | `.../main/dhu/2.1/certificate.pem` | `build/auth-research/certs/dhu__2.1__certificate.pem` | `9c5a28e2c9bf29572f398f717c1f9731b515886de26b448b5ebf3fb063d21f2d` |
| C3 | AASDK 임베디드 인증서 | `research/sources/opencardev__aasdk/src/Messenger/Cryptor.cpp` (`cCertificate`) | `build/auth-research/certs/aasdk-embedded.pem` | `85b5043a09b1ba9464f745e6917bdbaa2bc582fe48cb727a7787c1a832a773e4` |
| C4 | 실폰 캡처 체인 메타데이터 | 자체 USB 캡처 | `build/gd13my-ce-projection/phone-tls-public.json` | (JSON) |
| C5 | DHU 2.0 실행 파일 | Google DHU r02.0 배포 zip | `%LOCALAPPDATA%\i30-gen2-android-auto\google-dhu\r02.0\desktop-head-unit.exe` | 10,257,440 B |

교차검증: **C1의 두 지문이 C4(실폰 캡처)와 정확히 일치**한다.
- leaf `46d907a7…d27c`, root `49e52efc…d17f`
⇒ 캡처 무결성과 iscle 아카이브의 신뢰성을 상호 확인. (VERIFIED)

iscle 저장소는 `pushed_at = 2026-11-08`, 설명: "Android Auto embedded CarService and Google Automotive Link certificate archive".
`android-auto/latest/certificate.pem`은 18.0.664264-release와 **바이트 동일**(같은 SHA-256).

---

## 2. 인증서별 상세

### 2.1 GAL root (`gal-root.pem`)

```
Version: 3 (0x2)
Serial Number: c1:4e:e7:a5:a4:54:4d:42
Signature Algorithm: sha1WithRSAEncryption
Issuer:  C=US, ST=California, L=Mountain View, O=Google Automotive Link
Subject: C=US, ST=California, L=Mountain View, O=Google Automotive Link
Not Before: Jun  6 18:28:19 2014 GMT
Not After : Jun  5 18:28:19 2044 GMT
Public Key: RSA 2048, e=65537
X509v3 Subject Key Identifier:      B9:76:AB:EF:F0:33:D0:8B:0A:CC:7E:09:FC:C4:A4:7D:D6:4E:F0:82
X509v3 Authority Key Identifier:    B9:76:AB:EF:...  (동일)
X509v3 Basic Constraints: CA:TRUE
sha256 Fingerprint = 49:E5:2E:FC:13:AD:2E:D0:9F:20:4C:3B:10:69:8B:D8:4B:B7:10:5F:51:05:58:AA:14:B8:11:9A:5C:4A:D1:7F
```

- **자체 서명**, `CA:TRUE`, SKI=AKI. `keyUsage`/`pathLen`/`EKU` 없음.
- 서명 해시가 **SHA-1**이다. 폰은 이 루트를 trust anchor로 보유한다.

### 2.2 CarService leaf (`phone-leaf.pem`)

```
Version: 3 (0x2)
Serial Number: 15507082929371141 (0x37179c1981f805)
Signature Algorithm: sha256WithRSAEncryption
Issuer:  ... O=Google Automotive Link
Subject: C=US, ST=California, L=Mountain View, O=CarService
Not Before: Jul  4 00:00:00 2014 GMT
Not After : Feb 17 19:01:30 2027 GMT
Public Key: RSA 2048
X509v3 Subject Key Identifier: B3:C4:9A:B0:...
X509v3 Authority Key Identifier: B9:76:AB:EF:...   (= GAL root SKI)
sha256 Fingerprint = 46:D9:07:A7:...:54:D2:7C
```

- 확장은 SKI/AKI **2개뿐**. `basicConstraints` 없음, `keyUsage` 없음, `EKU` 없음, SAN 없음.
- 발급 후 12년 넘게 같은 인증서를 쓴다(2014 notBefore). 회전은 **새 시리얼/만료로 교체**하는 방식.

> AARE 문서(AA 17.7 기준)는 leaf 만료를 **2026-12-31**로 기록한다. 우리 캡처(AA 18.0.664264)는
> **2027-02-17**이다. ⇒ 폰 앱 버전에 따라 leaf가 다르며, **만료일을 프로젝트 상수로 쓰면 안 된다**.
> (VERIFIED: 두 출처가 서로 다른 값을 기록)

### 2.3 DHU 2.1 인증서 (`dhu__2.1__certificate.pem`)

```
Version: 1 (0x0)                      <-- v1, 확장 필드 없음
Serial Number: 273 (0x111)
Signature Algorithm: sha256WithRSAEncryption
Issuer:  ... O=Google Automotive Link
Subject: C=US, ST=California, L=Mountain View, O=Android-Auto-Internal, OU=01
Not Before: Jul  4 07:00:00 2014 GMT
Not After : Aug  1 17:21:23 2048 GMT
Public Key: RSA 2048
sha256 Fingerprint = 4E:B5:81:DC:...:CF:FA:7E:7C
```

ASN.1 원문 (Validity):
```
122:d=3  UTCTIME :140704000000-0700
141:d=3  UTCTIME :480801102123-0700
```
- `Z`가 아니라 **`-0700`(PDT) 오프셋**. RFC 5280/DER은 `Z`만 허용한다.
- 주의: `openssl x509 -text`의 `Jul 4 07:00:00 2014 GMT` / `Aug 1 17:21:23 2048 GMT`는
  **오프셋을 적용한 실제 UTC 값**이다(`00:00-0700` = `07:00Z`). 즉 DER의 숫자와 표시값이 7시간 다르며,
  표시값이 맞다. (2026-11-25 후속 연구에서 `der_time_normalize.py`로 재확인)
- 그래서 OpenSSL은 기본 검증에서 거부한다:
  `error 13 at 0 depth lookup: format error in certificate's notBefore field`
- 시간 검사를 끄면 **서명·체인은 정상**:
  `openssl verify -no_check_time -CAfile gal-root.pem dhu__2.1__certificate.pem` → `OK`

### 2.4 AASDK (JVC Kenwood) 인증서

```
Version: 1 (0x0)
Serial Number: 27 (0x1b)
Signature Algorithm: sha256WithRSAEncryption
Issuer:  ... O=Google Automotive Link
Subject: C=JP, ST=Tokyo, L=Hachioji, O=JVC Kenwood, OU=01
Not Before: Jul  4 07:00:00 2014 GMT
Not After : Apr 29 21:28:38 2045 GMT
Public Key: RSA 2048
sha256 Fingerprint = 1C:0E:0E:F9:E6:72:DD:1A:63:AB:4D:61:AF:AA:89:96:A5:7C:A7:AA:96:6D:19:22:B9:7D:8F:93:85:EA:3C:35
```

- DHU와 **동일한 `-0700` UTCTime 인코딩**, 동일 발급자, 동일 키 길이, v1.
- `openssl verify -no_check_time -CAfile gal-root.pem` → `OK`
- 출처: `Cryptor.cpp`의 `cCertificate` C 문자열(줄바꿈 이스케이프). 저장소 `cert/`에는 README만 남아 있고
  실제 `.crt/.key`는 제거되어 있다(`cert/README.md`: "installed by debian package ... falls back to embedded").

---

## 3. 체인 검증 결과

```
phone leaf  ──(sha256WithRSA, AKI=B976…)──▶ GAL root (CA:TRUE, self-signed)
DHU 2.1     ──(sha256WithRSA)────────────▶ GAL root   [verify OK, -no_check_time]
AASDK JVC   ──(sha256WithRSA)────────────▶ GAL root   [verify OK, -no_check_time]
```

- **중간 CA 없음.** 폰이 보낸 체인도 2장(leaf+root), DHU/AASDK도 단일 인증서 + 루트.
- ⇒ 폰의 trust store는 사실상 **GAL root 1개**이며, 우리가 별도 중간 CA를 만들 여지는 없다.
- 두 HU 인증서 모두 **조직명이 다르고**(Android-Auto-Internal / JVC Kenwood) **확장이 0개**인데도
  실제 폰에서 동작한다. ⇒ 폰은 DN·EKU·SAN을 요구하지 않는다. (VERIFIED: 실사용 + 인증서 구조)

재현 명령:
```powershell
$o = 'C:\Program Files\Git\usr\bin\openssl.exe'
& $o x509 -in dhu__2.1__certificate.pem -noout -text
& $o asn1parse -inform DER -in dhu21.der -i | Select-String 'UTCTIME'
& $o verify -CAfile gal-root.pem phone-leaf.pem                     # OK
& $o verify -CAfile gal-root.pem dhu__2.1__certificate.pem          # error 13 (시간 형식)
& $o verify -no_check_time -CAfile gal-root.pem dhu__2.1__certificate.pem   # OK
```

---

## 4. 제기된 7개 질문에 대한 답

**Q1. DHU/AASDK 인증서는 실제로 동일한 GAL Root CA에 연결되는가?**
YES. 서명 검증 통과. 등급 VERIFIED. (시간 형식 때문에 `-no_check_time` 필요)

**Q2. 중간 인증기관이 존재하는가?**
관측 범위에서 **없음**. 폰이 보낸 체인은 leaf+root 2장이고, HU 인증서는 루트가 직접 서명.
등급 VERIFIED(현재 시점). 미래에 중간 CA가 도입되면 우리 수신기의 단일 anchor 구조가 문제가 된다(§08).

**Q3. X.509 v1이 사용되는 이유에 기술적 근거가 있는가?**
없다. v1은 **확장 필드가 필요 없던 2014년 생성 관행**으로 보인다. 같은 발급자가 만든 폰 leaf는 v3다.
v1이 검증 요건이라는 증거는 어디에도 없다. 등급: HYPOTHESIS(폐기).

**Q4. "Google Android Auto가 특정 확장 필드를 요구한다"는 가설은 폐기 가능한가?**
폐기 가능. DHU 인증서는 **확장 필드가 하나도 없고**, `basicConstraints`도 `keyUsage`도 없다.
등급 VERIFIED(반증 성립).

**Q5. 인증서 주체의 제조사명과 인증 성공 여부의 관계는?**
관계없음. `Android-Auto-Internal`(Google 내부), `JVC Kenwood`(OEM) 둘 다 통과.
판정 기준은 **발급자가 GAL인지** 하나다. 등급 VERIFIED.

**Q6. 인증서 유효기간과 폰의 현재 검증 정책은?**
- 폰은 유효기간을 **검사한다**(AARE: 만료 시 `STATUS_AUTHENTICATION_FAILURE_CERT_EXPIRED(-24)`).
- 그러나 현재 오류 07은 만료가 아니다: HU 인증서 2045/2048, 폰 leaf 2027-02-17.
- 폰 leaf는 앱 업데이트로 교체된다(17.7 → 2026-12-31, 18.0 → 2027-02-17).
등급 VERIFIED(사실) / HYPOTHESIS(교체 메커니즘 세부).

**Q7. 공개 체인 검증 결과와 실제 폰의 허용 여부는 어떻게 다른가?**
- 공개 체인 검증(OpenSSL)은 **수학적 서명·체인**만 본다.
- 폰은 추가로 ① trust store에 GAL root 존재 ② 유효기간 ③ (아마) 서버 인증서와의 관계를 본다.
- 결정적 차이: **폰은 우리가 만든 체인을 trust store에 추가해 주지 않는다.**
- 그리고 DHU/AASDK 인증서는 체인상 유효하지만, **그 개인키를 우리가 쓰는 것은 신원 위장**이다.
  "검증 통과"와 "사용 권한"은 별개다.

---

## 5. 부수 발견: BearSSL과 `-0700`

BearSSL 0.6 `src/x509/asn1.t0`의 `read-date`는 시간대를 **`Z`만** 허용한다:

```
\ The time zone should be 'Z', not followed by anything. Other
\ time zone indications are not DER and thus not supposed to
\ appear in certificates.
`Z <> if ERR_X509_BAD_TIME fail then
```

- 우리 수신기가 폰 인증서를 검증할 때는 문제없다(폰 체인은 `Z` 사용).
- 그러나 **우리 프로젝트가 받게 될 GAL 발급 인증서가 DHU/AASDK와 같은 생성기로 만들어진다면**
  `-0700` 형식일 가능성이 높고, 그때는 `src/ce/ce_aa_tls.c`의 `der_time()`이 **로컬에서 거부**한다.
  (`ce_aa_tls.c` L262: `field.bytes[field.length-1] != 'Z'` → return 0)
- 이 항목은 §08의 실제 수정 후보 1번이다. 등급 VERIFIED(코드 사실) + HYPOTHESIS(향후 인증서 형식).

---

## 6. 하지 않은 것 / 하면 안 되는 것

- 개인키 추출·복제·사용: **하지 않았다.** DHU/AASDK/iscle의 개인키는 공개돼 있으나
  사용하는 순간 Google 내부 테스트 신원 또는 타 OEM 신원의 위장이 된다.
- 공개 인증서를 제품에 포함해 "GAL 발급"으로 보이게 하는 행위: 금지.
- 인증서만으로 폰의 trust store를 바꾸는 행위: 불가능(사용자 통제 밖, 시스템 CA).

---

## 7. 남은 확인

| 항목 | 이유 | 다음 방법 |
| --- | --- | --- |
| 폰이 실제로 검사하는 필드 목록 | v1/무확장 통과는 확인, 그러나 "무엇을 안 보는지"의 완전한 목록은 미확인 | AARE식 폰 측 구현 분석 + 폰 앱 디컴파일(정책 허용 범위 내) |
| GAL root의 `keyUsage` 부재 영향 | BearSSL `br_x509_decoder_isCA`는 basicConstraints만 확인 | 코드 확인 완료(문제 없음) |
| 미래 중간 CA 도입 가능성 | 단일 anchor 하드코딩 리스크 | §08 개선안 |
| DHU 2.0 자체 인증서 | r02.0 exe에 DN 문자열/DER이 없음(난독화 추정) | 불필요. 2.1 공개 인증서로 대체 |
