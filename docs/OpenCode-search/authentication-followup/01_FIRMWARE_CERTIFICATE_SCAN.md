# 01 — Genesis 펌웨어 인증서·ASN.1 전수 스캔

작성: 2026-11-25 · 등급: **VERIFIED** (재현 스크립트 포함)
대상: `G:\` (읽기 전용 Genesis G80 순정 펌웨어)

---

## 1. 목적

이전 조사는 PEM 헤더(`-----BEGIN`)와 일부 문자열만 확인했다. 이번에는
**DER OID, PKCS#7, X.509 확장, 개인키 흔적**까지 포함해 다시 스캔하고,
발견된 후보가 실제 AA 인증에 사용되는지를 함수 참조로 검증한다.

---

## 2. 방법

스크립트: `scripts/scan_firmware_certs.py`

- 308개 파일, 15,241,434,413 바이트를 순회.
- 64 MB 이하는 전체 읽기, 초과는 32 MB 청크 + 64 B 오버랩.
- 탐색 패턴:
  - PEM armour `-----BEGIN `
  - DER OID: `rsaEncryption`, `sha1WithRSA`, `sha256WithRSA`, `signedData`,
    `pkcs7_data`, `commonName`, `organizationName`, `countryName`,
    `subjectKeyIdentifier`, `authorityKeyIdentifier`, `basicConstraints`,
    `extKeyUsage`, `serverAuth`, `clientAuth`
  - 문자열: `Google Automotive Link`, `Android-Auto-Internal`, `CarService`,
    `AndroidAuto`, `Android Auto`, `Google Automotive`, `headunit`, `mbedtls_x509`,
    `X509_verify_cert`, `SSL_CTX_use_certificate`, `TLSv1.2`, `clientAuth`, `PKCS7`
- 원본 트리는 쓰지 않는다.

실행:

```powershell
python docs\OpenCode-search\authentication-followup\scripts\scan_firmware_certs.py "G:\" `
    --json build\auth-followup\firmware_scan.json
```

---

## 3. 결과

```
files=308 bytes=15241434413
pem_hits=0 oid_hits=1 string_hits=326
```

### 3.1 PEM

**0건.** `G:\` 평문 파일에는 PEM 인증서/키가 없다.

### 3.2 DER OID

**1건**, 그러나 오탐:

```
G:\DATA\COMMON\FONT\30_CUBEB_FORANDROID(2.3).ttf  offset 2038275
oid = organizationName (06 03 55 04 0A)
```

TTF 글리프 데이터에서 우연히 일치한 5바이트 패턴이다. 인증서가 아니다.

### 3.3 문자열

326건. 대부분 `G:\HU\images\vr.img`의 **UI 경고 번역 문자열**("Android Auto")이다.
`vr.img`는 `partclone-imageEXTFS`(비암호화)이지만, 해당 문자열은 화면 표시용이다.

주목할 만한 3건:

```
G:\AppUpgrade   offset 1155730   "clientAuth"
G:\essentials   offset 14741970  "clientAuth"
G:\essentials   offset 14928434  "clientAuth"
```

이 문자열은 **OpenSSL의 OID short-name 테이블**(`objects.txt` → `obj_dat.h`)에 있는
`clientAuth`(`1.3.6.1.5.5.7.3.2`)이다. `essentials`의 `decrypt/DecryptToFile`,
`DecryptToPIPE`가 OpenSSL을 정적 링크한 결과이며, AA 인증서와 무관하다.

`Android-Auto-Internal`, `Google Automotive Link`, `CarService`, `PKCS7`은 **0건**이다.

### 3.4 함수 참조 검증

`G:\BIN\APPNAVI`(ELF)에는 `Android`, `Google`, `TLS`, `cert` 문자열이 없고,
`vr.img`의 "Android Auto"는 UI 문자열뿐이다. 따라서 문자열 후보를 AA 인증
함수에 연결할 근거가 없다. (이전 조사와 동일 결론, 이번에 DER 수준까지 확장.)

---

## 4. 한계

- `boot.img`(45,565,256 B), `rootfs.img`(2,567,399,572 B), `IBOX.tar`(402,335,780 B)는
  **암호화/고엔트로피**이므로 평문 스캔으로 내부 인증서 유무를 단정할 수 없다.
- 다만 02 문서에서 이 컨테이너들을 분석했고, 03/04 문서에서 **컨테이너와 무관한
  실행 가능한 신원 경로**를 확보했다.

---

## 5. 판정

| 주장 | 등급 |
| --- | --- |
| `G:\` 평문 파일에 PEM 인증서/키가 없다 | **VERIFIED** |
| `G:\` 평문 파일에 AA용 DER 인증서가 없다 | **VERIFIED** |
| `clientAuth` 문자열은 OpenSSL OID 테이블이다 | **VERIFIED** |
| 암호화 컨테이너 내부에 인증서가 없다 | **UNKNOWN** (열 수 없음) |
| Genesis 펌웨어에서 헤드유닛 신원을 추출할 수 있다 | **FAILED / 근거 없음** |

---

## 6. 재현

```powershell
python docs\OpenCode-search\authentication-followup\scripts\scan_firmware_certs.py "G:\"
# 출력: files=308 bytes=15241434413 pem_hits=0 oid_hits=1 string_hits=326
```
