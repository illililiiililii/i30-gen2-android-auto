# FINAL HANDOFF — Authentication Follow-up (2026-11-25)

대상: GD13MY (Hyundai i30 GD 2013, Windows CE 6.0, ARM Cortex-A8, BearSSL 0.6)
범위: 헤드유닛 인증서 · TLS 상호 인증 · GAL 신뢰 체인 · 신원 확보
제외: 영상, DSP, 오디오, UI

---

## 1. 한 줄 결론

> **실패 원인은 GAL root 불신이 아니라, GAL 발급 헤드유닛 인증서가 `-0700` UTCTime
> 때문에 BearSSL에서 로드되지 않아 라이브 시험이 자체 서명 신원으로 진행된 것이다.**
>
> **`Google-Android-Reference` (GAL 발급, `Z` 시간, 키 일치) 쌍이 공개되어 있고,
> 현재 펌웨어 코드를 수정하지 않고 로드된다.** 테스트 단계의 실행 가능한 신원 경로다.

---

## 2. 새로 확정한 사실

| # | 사실 | 등급 | 증거 |
| --- | --- | --- | --- |
| N1 | 폰의 신뢰 앵커는 우리 `gal-root.pem`과 동일 | **VERIFIED** | dexter 설정 지문 == `49:E5:2E:FC:...` |
| N2 | JVC/DHU 헤드유닛 인증서는 BearSSL에서 `err=48`, `pkey=NULL` | **VERIFIED** | `cert_probe.exe` |
| N3 | OpenSSL도 `-0700`을 `error 13`으로 거부 | **VERIFIED** | `openssl verify` |
| N4 | `configure()`가 GAL 발급 인증서를 거부 | **VERIFIED** | 코드 경로 L442–446, L253–282 |
| N5 | 라이브 실패는 자체 서명 신원에 대한 정상 거부 | **VERIFIED (추론)** | N2–N4의 필연적 귀결 |
| N6 | `Google-Android-Reference`는 strict verify OK, `err=0`, PAIR OK | **VERIFIED** | `openssl verify`, `cert_probe` |
| N7 | `G:\` 평문에 AA 인증서 없음 (PEM 0, OID 1=폰트 오탐) | **VERIFIED** | `scan_firmware_certs.py` |
| N8 | `IBOX.tar`/`boot.img`는 결정적 키스트림 재사용 (7,938 B 동일) | **VERIFIED (통계)** | `keystream_probe.py` |
| N9 | behead가 Kia EV6 실차에서 `carservice` 인증서로 성공 | **VERIFIED** | behead issue #2 |
| N10 | AAP 2.0 Certification 2.0이 2026-01부터 의무, 3PL 전용 | **VERIFIED** | P3/CIeNET/Ubikon/HARMAN |
| N11 | `Google-Android-Reference`가 i30 폰에서 통과 | **PARTIAL** | open-headunit 필드 동작, 라이브 미시험 |

---

## 3. 해결 후보 (순위)

### 후보 A — `Google-Android-Reference` 배포 (권장, 코드 수정 0)

1. `build/auth-followup/open-headunit/cert` (PEM) → `\DiskA\Application\NAVI\i30-client.pem`
   - **leaf가 첫 번째**여야 한다. root를 먼저 넣지 않는다.
   - 재현용 원본:
     `https://raw.githubusercontent.com/andreknieriem/open-headunit/main/app/src/main/res/raw/cert`
2. `build/auth-followup/open-headunit/privkey` → `i30-client-key.pem`
   - `https://raw.githubusercontent.com/andreknieriem/open-headunit/main/app/src/main/res/raw/privkey`
3. `build/auth-research/certs/gal-root.pem` → `i30-ca.pem` (또는 DER)
4. 폰 연결 후 로그 확인:
   - 성공: `AuthComplete` status 0, ServiceDiscovery 응답.
   - 실패: `Trust anchor...`가 다시 나오면 후보 B로.

근거: strict verify OK, BearSSL `err=0`, open-headunit이 동일 쌍을 클라이언트 신원으로 사용.
키는 테스트 단계에서만 사용하고 커밋·배포하지 않는다.

### 후보 B — 파서 수정 후 JVC 인증서 사용

`der_time()`에 `±HHMM` 허용 + `configure()`에서 SPKI 자체 파싱 (03 문서 3.2).
`Google-Android-Reference`가 거부될 때의 대안.

### 후보 C — Sony/Kenwood 펌웨어에서 실제 양산 쌍 추출

Sony XAV-AX100(GPL U-Boot 키) 또는 Kenwood DNX(ext4 app ROM).
추출한 쌍이 `-0700`이면 후보 B의 파서 수정이 필요하다.

### 후보 D — AAP 2.0 3PL 인증

양산/배포의 유일한 공식 경로. 개인 접근 불가.

---

## 4. 실패 원인 정리

| 원인 | 상태 | 설명 |
| --- | --- | --- |
| 자체 서명 신원 사용 | **확정** | GAL 발급 인증서가 로드되지 않아 불가피 |
| `-0700` UTCTime 파싱 거부 | **확정** | BearSSL `err=48`, OpenSSL `error 13` |
| 체인 순서 (root first) | **확인 필요** | `i30-client.pem`의 첫 인증서가 leaf인지 |
| GAL root 불신 | **반증** | 폰의 신뢰 앵커와 동일 지문 |
| Google 정책 변경 | **반증** | 같은 폰/같은 날 DHU 성공 |
| 전송/USB 계층 | **반증** | `server_requested_client_certificate: true`까지 도달 |

---

## 5. 증거 파일·해시

| 파일 | SHA-256 / 값 |
| --- | --- |
| `gal-root.pem` | `49:E5:2E:FC:13:AD:2E:D0:9F:20:4C:3B:10:69:8B:D8:4B:B7:10:5F:51:05:58:AA:14:B8:11:9A:5C:4A:D1:7F` |
| `phone-leaf.pem` | `46:D9:07:A7:48:2D:0A:BD:5D:0C:A2:6C:0F:14:78:48:08:CC:0E:61:49:45:A2:F3:92:1C:53:09:97:54:D2:7C` |
| `aasdk-embedded.pem` (JVC) | `1C:0E:0E:F9:E6:72:DD:1A:63:AB:4D:61:AF:AA:89:96:A5:7C:A7:AA:96:6D:19:22:B9:7D:8F:93:85:EA:3C:35` |
| `dhu21.der` | `err=48`, `-0700` |
| `open-headunit/cert` (PEM) | `851D80C86BF469A3DD121B7A7084CA97B91B3D2CC72922C451E0156B455F38C1` |
| `open-headunit/cert` (DER) | `E323CC6DD52D1F2A280360A0E92EFA04AB3664DD68FAB3DD187F03D663FEED6D` |
| `open-headunit/privkey` | `015D172A6E4D5B7F04A5C820A60A41673F99D6E01C2F658E2A0909EFBF6D49F7` |
| `aasdk-headunit.key` modulus | `CF75D6636751FC7E589B71BA4D3A18EE...D1643` (cert와 일치) |
| `G:\` 스캔 | `files=308 bytes=15241434413 pem=0 oid=1 strings=326` |
| IBOX/boot 동일 구간 | `7,938 B @ 20,799` |

---

## 6. 남은 작업 (우선순위)

1. **라이브 시험 A**: `Google-Android-Reference` + GAL root를 배포하고 폰 로그를 캡처.
   - 성공 기준: `AuthComplete` status 0 + ServiceDiscovery 응답.
   - 실패 시: 폰이 보낸 마지막 프레임과 `Certificate` 메시지 바이트를 기록.
2. **체인 순서 확인**: `i30-client.pem`의 첫 인증서가 leaf인지 확인.
3. **실패 시 B**: `der_time`/SPKI 파서 수정 후 JVC 인증서로 재시험.
4. **C**: Sony/Kenwood 펌웨어에서 대체 쌍 추출 (A/B가 모두 실패할 때만).
5. `adb` 확보 후 폰 측 `CAR.GAL.SECURITY.LITE` 로그와 `ConscryptEngine` 스택을 다시 캡처.

---

## 7. 법적·윤리적 경계

- 사용자 지시(2026-11-25): **테스트 단계에 한해** 공개 개인키 사용과 신원 위장을 허용.
- 그러나 다음은 지킨다:
  - 키를 저장소에 **커밋하지 않는다**.
  - 키를 제품/배포물에 **포함하지 않는다**.
  - 제3자 서비스나 실제 사용자 차량을 사칭하지 않는다.
  - AAP 2.0 3PL 인증 없이 양산/판매하지 않는다.
- `Google-Android-Reference`는 DHU(공식 개발 도구) 유래이며, 테스트 목적 사용이다.

---

## 8. 재현 진입점

```powershell
# 핵심 실측
cd build\auth-followup\bearssl-host
.\cert_probe.exe ..\aasdk.der ..\open-headunit\gar.der

# 신원 검증
python docs\OpenCode-search\authentication-followup\scripts\check_hu_identity.py `
    build\auth-followup\open-headunit\cert `
    build\auth-followup\open-headunit\privkey `
    build\auth-research\certs\gal-root.pem

# 펌웨어 스캔
python docs\OpenCode-search\authentication-followup\scripts\scan_firmware_certs.py "G:\"
```

문서:

- `01_FIRMWARE_CERTIFICATE_SCAN.md`
- `02_CONTAINER_STRUCTURE.md`
- `03_TIME_ENCODING_ROOT_CAUSE.md` ← **핵심**
- `04_EXTERNAL_CASES_AND_IDENTITIES.md` ← **신원**
- `05_OFFICIAL_ROUTES.md`
- `06_ALTERNATIVE_FIRMWARE.md`
- `PROGRESS.md`
