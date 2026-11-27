# Authentication Follow-up — Progress

작성: 2026-11-25 · 대상: GD13MY (Hyundai i30 GD 2013, Windows CE 6.0, ARM Cortex-A8, BearSSL 0.6)
범위: 헤드유닛 인증서 · TLS 상호 인증 · GAL 신뢰 체인 · 신원 확보 경로
제외: 영상, DSP, 오디오, UI

이 문서는 `authentication-deep-research/`의 후속 세션 기록이다. 이전 보고서의 결론을
반복하지 않고, **새로 확인된 증거와 정정**만 기록한다.

---

## 세션 목표 (6개 작업)

1. `G:\` 전체에서 PEM/DER/ASN.1/PKCS#7 및 내장 공개 인증서 스캔 + 함수 참조로 실제 AA 사용 검증
2. IBOX/rootfs 컨테이너 구조와 공식 추출 방법 분석 (실패한 복호화 반복 금지)
3. DHU/AASDK ASN.1 시간 필드와 BearSSL의 `-0700` 파싱 호환성 실측
4. 미조사 인증 구현·커밋·개발자 답변·성공 사례 탐색
5. 이미 확인한 벤더 외의 공식 개발/평가 신원 경로 조사
6. Genesis 펌웨어로 부족할 경우 대체 순정 AA 펌웨어 후보 (다운로드 경로·크기·플랫폼·선정 근거)

---

## 핵심 결과 (한 줄)

> **실패 원인은 "GAL root를 신뢰하지 않아서"가 아니라, GAL 발급 헤드유닛 인증서가
> `-0700` UTCTime 때문에 BearSSL 디코더에서 로드되지 않아, 라이브 시험이
> 자체 서명(self-signed) 신원으로 진행되었기 때문이다.**
>
> 그리고 **`Google-Android-Reference` (GAL 발급, `Z` 시간, 키 일치) 쌍이 공개되어 있으며
> 현재 펌웨어 코드를 한 줄도 고치지 않고 로드된다.** 이것이 이번 세션의 실행 가능한 신원 경로다.

---

## 작업별 상태

| # | 작업 | 상태 | 핵심 증거 |
| --- | --- | --- | --- |
| 1 | 펌웨어 인증서 스캔 | **완료** | 308 파일 / 15.24 GB, PEM 0, OID 1(폰트 오탐) |
| 2 | 컨테이너 구조 | **완료(부분)** | boot/rootfs 동일 magic, IBOX와 7,938 B 암호문 공유 → 결정적 키스트림 |
| 3 | `-0700` / BearSSL | **완료(결정적)** | `err=48`, `pkey=NULL`; OpenSSL도 `error 13` |
| 4 | 외부 사례·도구 | **완료** | behead #2 실차 성공, dexter, open-headunit `Google-Android-Reference` |
| 5 | 공식 경로 | **완료** | AAP 2.0 Certification 2.0 (2026-01 의무화), 3PL 전용 |
| 6 | 대체 펌웨어 | **완료** | Sony XAV-AX100(GPL 키), Kenwood DNX(ext4) 유력 |

---

## 결정적 증거 (작업 3)

### 실측

```
build/auth-followup/bearssl-host> time_test.exe ..\phone-leaf.der ..\aasdk.der ..\dhu21.der ..\gal-root.der
..\phone-leaf.der    bytes=881  decoder_error=0   (OK)
..\aasdk.der         bytes=814  decoder_error=48  (BR_ERR_X509_BAD_TIME)
..\dhu21.der         bytes=835  decoder_error=48  (BR_ERR_X509_BAD_TIME)
..\gal-root.der      bytes=909  decoder_error=0   (OK)

build/auth-followup/bearssl-host> cert_probe.exe ..\aasdk.der ..\aasdk-z.der ..\phone-leaf.der ..\gal-root.der
..\aasdk.der         err=48  pkey=NULL     isCA=0
..\aasdk-z.der       err=0   pkey=present  isCA=0  rsa_bits=2048
..\phone-leaf.der    err=0   pkey=present  isCA=0  rsa_bits=2048
..\gal-root.der      err=0   pkey=present  isCA=1  rsa_bits=2048
```

### OpenSSL 교차 확인

```
openssl verify -CAfile gal-root.pem aasdk-embedded.pem
  error 13 at 0 depth lookup: format error in certificate's notBefore field

openssl verify -no_check_time -CAfile gal-root.pem aasdk-embedded.pem
  aasdk-embedded.pem: OK
```

### 코드 경로

`src/ce/ce_aa_tls.c`:

- `configure()` L442–446:
  `br_x509_decoder_push(&s->client_decoder, s->identity[0].data, ...)`
  → `key = br_x509_decoder_get_pkey(...)`
  → `if (!key || key->key_type != BR_KEYTYPE_RSA || !client_validity(...)) return "... invalid"`
- `client_validity()` L289–299 → `der_time()`
- `der_time()` L253–282: `field.length != year_length + 11 || field.bytes[last] != 'Z'` → `return 0`

즉 JVC/DHU 인증서는 **공개키를 얻기 전에** 디코더가 멈추고, 설령 디코더를 우회해도
`der_time()`이 거부한다. 따라서 현재 코드로는 GAL 발급 인증서를 **로드할 수 없다**.

### 귀결

- 라이브 폰 로그의 `Trust anchor for certification path not found`는 **자체 서명 신원**에
  대한 정상적인 거부다.
- "Google 정책 변경"이나 "GAL root 불신"을 가정할 필요가 없다.
- 폰의 신뢰 저장소는 GAL root를 포함한다 (아래 작업 4의 dexter 설정 지문과 일치).

---

## 새로 발견한 실행 가능 신원 (작업 4)

`andreknieriem/open-headunit` (`app/src/main/res/raw/cert`, `privkey`):

| 항목 | 값 |
| --- | --- |
| Subject | `C=US, ST=CA, L=Mountain View, O=Google-Android-Reference` |
| Issuer | `C=US, ST=California, L=Mountain View, O=Google Automotive Link` |
| Serial | `0x7653` |
| Version | v1 (확장 없음) |
| Signature | `sha256WithRSAEncryption` |
| Validity | 2014-07-08 22:49:18Z → 2044-07-07 22:49:18Z |
| 시간 인코딩 | **`Z`** (`140708224918Z`, `440707224918Z`) |
| SHA-256 (DER) | `E3:23:CC:6D:D5:2D:1F:2A:28:03:60:A0:E9:2E:FA:04:AB:36:64:DD:68:FA:B3:DD:18:7F:03:D6:63:FE:ED:6D` |
| 키 일치 | `openssl modulus` 일치 (`PAIR OK`) |
| 체인 | `openssl verify -CAfile gal-root.pem cert` → **OK** (strict, `-no_check_time` 불필요) |
| BearSSL | `cert_probe` → **err=0, pkey=present, 2048-bit** |
| 출처 | open-headunit discussion #637: "extracted from the DHU in Android Studio. It is the official pair" |
| 사용 확인 | `SingleKeyKeyManager` + `SslContextFactory`가 `R.raw.cert`/`R.raw.privkey`를 클라이언트 신원으로 사용 |

→ **현재 `ce_aa_tls.c`의 `configure()`가 그대로 받아들인다.** 코드 수정 불필요.

---

## 이전 결론 정정

| 이전 서술 | 정정 | 근거 |
| --- | --- | --- |
| "DHU/AASDK 인증서는 `-0700`이라 OpenSSL 표시값이 실제 UTC와 7시간 다르다" | **표시값이 맞다.** `00:00-0700` = `07:00Z` | `der_time_normalize.py` + `asn1parse` |
| "실폰 실패는 GAL root 불신/정책 문제" | **아니다.** GAL 발급 인증서가 로드되지 않아 자체 서명으로 시험됨 | `cert_probe`, `time_test` |
| "DHU/AASDK/LIVI 공유 신원은 정책상 금지" | **테스트 단계에 한해 사용 허용** (사용자 지시). 단, 커밋·배포 금지 | 사용자 메시지 |

---

## 남은 불확실성

- **실폰 재시험 불가**: 이번 세션에 `adb`/폰 연결이 없다. `Google-Android-Reference`가
  실제 i30 폰에서 통과하는지는 아직 라이브로 확인하지 못했다.
- **전송 체인 순서**: `i30-client.pem`에 leaf가 첫 번째인지 확인 필요. root를 먼저 넣으면
  폰이 root를 leaf로 보고 실패할 수 있다.
- **컨테이너 내부**: `boot.img`/`rootfs.img`/`IBOX.tar`는 암호화되어 있어 인증서 유무는
  평문 스캔으로 단정할 수 없다. 다만 `Google-Android-Reference` 경로가 확보되어 무의미해졌다.

---

## 재현 명령

```powershell
# BearSSL 시간 파싱 실측
cd build\auth-followup\bearssl-host
.\time_test.exe ..\aasdk.der ..\dhu21.der ..\phone-leaf.der ..\gal-root.der
.\cert_probe.exe ..\aasdk.der ..\aasdk-z.der ..\open-headunit\gar.der

# 신원 검증
$o='C:\Program Files\Git\usr\bin\openssl.exe'
& $o verify -CAfile build\auth-research\certs\gal-root.pem build\auth-followup\open-headunit\cert
& $o x509 -in build\auth-followup\open-headunit\cert -noout -subject -issuer -dates
& $o asn1parse -in build\auth-followup\open-headunit\cert -i | Select-String 'UTCTIME'

# 펌웨어 스캔
python docs\OpenCode-search\authentication-followup\scripts\scan_firmware_certs.py "G:\" --json build\auth-followup\firmware_scan.json
```
