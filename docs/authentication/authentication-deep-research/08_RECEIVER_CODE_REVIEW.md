# 08. 수신기 TLS 코드 리뷰 (P0-7)

작성: 2026-11-25 · 대상: `src/ce/ce_aa_tls.c` (32,938 B), `src/ce/ce_aa_usb_client.c` (12,695 B)
목적: 신원 확보 이후 **실제로 통과시키기 위해 코드에서 고쳐야 할 것**을 특정

## 0. 결론 요약

| 항목 | 현재 상태 | 조치 필요? | 근거 |
| --- | --- | --- | --- |
| TLS 1.2 고정 | `BR_TLS12, BR_TLS12` | 아니오 (DHU와 동일) | L461 |
| cipher suite | BearSSL full 기본(0xC02F 포함) | 아니오 (ARM 시험 통과) | `arm-usb-tls-dhu-cipher.json` |
| 클라이언트 인증서 전송 | `br_ssl_client_set_single_rsa` | 아니오 | L460 |
| **체인 구성(루트 포함 여부)** | PEM에 든 것을 **전부** 전송 | **예** | L165–209, L438–439 |
| **인증서 시간 파싱** | **`Z`만 허용** | **예 (GAL 발급 인증서가 `-0700`일 경우)** | L253–283 |
| 서버 인증서 검증 | CA 1개 또는 SHA-256 pin | 아니오 | L420–437 |
| 시계 | guest UTC, `GetSystemTimeAsFileTime` | 조건부 | L345 |
| alert 처리 | 수신 alert 로깅(48 특수 처리) | 아니오(진단만) | L757–782 |
| `AUTH_COMPLETE` | 메시지 4 `AuthResponse(0)` 전송 | 아니오 | L714, L722 |

핵심: **프로토콜 구현에는 결함이 없다.** 고칠 것은 ①체인 구성 ②시간 파서 두 가지이며,
둘 다 "GAL 발급 인증서를 받았을 때" 표면화되는 문제다.

---

## 1. 구성 단계 (`configure`, L397–474)

### 1.1 신뢰 앵커

```c
ca_size = read_credential(s, TLS_PATH L"i30-ca.der", TLS_PATH L"i30-ca.pem",
                          s->ca, sizeof(s->ca), 0);
...
br_x509_decoder_init(&s->cert, append_dn, s);
br_x509_decoder_push(&s->cert, s->ca, ca_size);
key = br_x509_decoder_get_pkey(&s->cert);
if (!ca_size || !key || !br_x509_decoder_isCA(&s->cert) || ...)
    return L"i30 CE TLS trust CA missing, unreadable or invalid.\r\n";
s->anchor.flags = BR_X509_TA_CA;
br_ssl_client_init_full(&s->client, &s->validation, &s->anchor, 1);
```

- **단일 CA만 지원**한다. `br_ssl_client_init_full(..., &anchor, 1)`의 마지막 인자는 앵커 1개.
- 현재 GAL root는 self-signed 1개이므로 문제없다.
- 그러나 미래에 중간 CA가 도입되면 폰 체인이 3장이 되고, 그때는 앵커/체인 구성 변경이 필요하다.
  → **P2 항목** (지금 당장의 실패 원인 아님).

### 1.2 peer 검증: CA 또는 pin (배타)

```c
if ((name_size != 0) == (pin_size != 0) || ...)
    return L"i30 CE TLS peer hostname or fingerprint configuration invalid.\r\n";
```

- `i30-peer.txt`(호스트명) 또는 `i30-peer-sha256.txt`(지문) **둘 중 하나만** 허용.
- pin 사용 시 `PinnedChain` 래퍼가 BearSSL 검증기를 감싸 지문을 비교한다(L75–129).
- 폰 인증서는 `Z` 형식이고 지문이 고정 가능하므로 **이 방향은 이미 견고**하다.

### 1.3 클라이언트 체인

```c
identity_count = read_credentials(s, L"i30-client.der", L"i30-client.pem",
                                  s->client_cert, sizeof(s->client_cert),
                                  s->identity, CLIENT_CHAIN_MAX, 0);
...
br_ssl_client_set_single_rsa(&s->client, s->identity, identity_count,
                             client_key, br_rsa_pkcs1_sign_get_default());
```

**발견 1 (조치 필요): `read_credentials`는 PEM 안의 CERTIFICATE 블록을 최대 4개까지 전부 디코드하고,
그 전부를 `br_ssl_client_set_single_rsa`의 체인으로 넘긴다.** (L165–209, L438–460)

의미:
- `i30-client.pem`에 `leaf + GAL root`를 넣으면 **루트까지 전송**한다.
- AARE 문서는 폰이 **루트 자체를 헤드유닛 인증서로 보내는 것을 거부**한다고 기록한다.
- DHU/AASDK가 실제로 몇 장을 보내는지는 미확인이나, 관행상 **leaf만** 보내는 것이 안전하다.

권고:
```
i30-client.der/pem  →  leaf 1장만
(루트는 i30-ca.pem에 별도 보관, 전송하지 않음)
```
또는 코드에서 마지막 인증서가 self-signed(issuer==subject)면 제외하는 로직 추가.

등급: VERIFIED(코드 사실) / HYPOTHESIS(폰이 루트 포함을 거부하는지 — AARE 문서 기반)

### 1.4 시간

```c
if (!read_utc(&now)) return L"... guest UTC unavailable or invalid.\r\n";
...
if (utc_before(now, start)) return L"... not yet valid at guest UTC.\r\n";
if (utc_before(end, now))  return L"... expired at guest UTC.\r\n";
...
br_x509_minimal_set_time(&s->validation, now.day, now.second);
```

- **클라이언트 자신의 인증서 유효기간을 로컬에서 검사**한다(L445–450).
- 즉 게스트 시계가 2014 이전이거나 2045 이후면 **우리 코드가 먼저 거부**한다.
- `read_utc`는 `GetSystemTimeAsFileTime` 기반(L345)이며, WinCE RTC가 리셋되면 1601년이 될 수 있다.
  → `docs/ANDROID_AUTO_AUTH_STATUS.md`에 "과거 UTC를 1601로 얻었으나 현재 수신기에서는 시작 시 게스트 UTC를 읽는다"고 기록됨.

권고: 신원 확보 후 첫 시험 전에 **게스트 시계를 실제 날짜로 설정**하고,
`i30-client.pem`의 notBefore/notAfter를 로그로 남긴다.

### 1.5 엔트로피

```c
if (!CeGenRandom(sizeof(seed), seed)) return L"i30 CE TLS secure randomness unavailable.\r\n";
br_ssl_engine_inject_entropy(&s->client.eng, seed, sizeof(seed));
```

- WinCE `CeGenRandom` 사용. ARM 시험에서 핸드셰이크가 진행됐으므로 동작 확인됨.
- 조치 불필요.

---

## 2. 인증서 시간 파서 (`der_time`, L253–283)

```c
int short_year = source->bytes[0] == 0x17;
unsigned year_length = short_year ? 2U : 4U;
Der field;
if (!der_read(source, short_year ? 0x17 : 0x18, &field) ||
    field.length != year_length + 11 ||
    field.bytes[field.length - 1] != 'Z')
    return 0;
```

- UTCTime은 `YYMMDDHHMMSSZ` = 13바이트, GeneralizedTime은 `YYYYMMDDHHMMSSZ` = 15바이트만 허용.
- **마지막 바이트가 `Z`가 아니면 즉시 실패.**

### 2.1 왜 중요한가

GAL이 서명한 실물 인증서 3장의 실제 인코딩:

| 인증서 | notBefore (DER) | notAfter (DER) |
| --- | --- | --- |
| DHU 2.1 | `140704000000-0700` | `480801102123-0700` |
| AASDK JVC | `140704000000-0700` | `450429142838-0700` |
| 폰 leaf | `140704000000Z` | `270217190130Z` |

- HU 인증서는 **`Z`가 아니라 `-0700` 오프셋**을 쓴다(17바이트, `year_length + 11` 조건 위반).
- OpenSSL도 이 형식을 기본 거부한다(`error 13 ... notBefore field`), `-no_check_time`에서만 통과.

⇒ 만약 우리가 받을 GAL 발급 인증서가 같은 생성기로 만들어지면:
1. `der_time()`이 **로컬에서 거부** → `i30-client.pem`을 읽지 못함
2. `configure()`가 `"head unit certificate missing, unreadable or invalid"` 반환
3. 핸드셰이크 시작조차 못 함

### 2.2 BearSSL 자체도 같은 제약

`build/ce-tls-dependency/bearssl-0.6/src/x509/asn1.t0` L694–698:

```
\ The time zone should be 'Z', not followed by anything. Other
\ time zone indications are not DER and thus not supposed to
\ appear in certificates.
`Z <> if ERR_X509_BAD_TIME fail then
```

- 이 코드는 **peer(폰) 인증서**를 검증할 때 실행된다. 폰은 `Z`를 쓰므로 문제없다.
- 우리 쪽 인증서는 BearSSL 파서를 거치지 않는다(`der_time`이 직접 파싱).
  → **수정 지점은 `src/ce/ce_aa_tls.c`의 `der_time` 하나뿐**이다. BearSSL 패치는 불필요.

### 2.3 최소 수정안 (개념)

```c
/* 현재: field.length != year_length + 11 || last != 'Z' */
/* 필요:  Z 또는 ±HHMM 오프셋 허용 */
unsigned base = year_length + 10;      /* YYMMDDHHMMSS */
if (field.length == base + 1 && field.bytes[base] == 'Z') { /* UTC */ }
else if (field.length == base + 5 && (field.bytes[base]=='+'||field.bytes[base]=='-')) {
    /* 오프셋을 초 단위로 환산해 UTC로 보정 */
}
```

이 수정은 **인증서 형식 호환성**만 다룬다. 폰의 신뢰 판정을 바꾸지 않는다.

등급: VERIFIED(현재 코드가 `-0700`을 거부) / HYPOTHESIS(우리가 받을 인증서의 형식)

---

## 3. 핸드셰이크 루프 (`handshake`, L784–826)

```c
for (unsigned step = 0; step < 256U; ++step) {
    unsigned state = br_ssl_engine_current_state(engine);
    if (state & BR_SSL_CLOSED) return handshake_error(s);
    if (state & BR_SSL_SENDREC) { ... send_record ... }
    else if (state & BR_SSL_SENDAPP) { ... return 0; }   /* 완료 */
    else if (state & BR_SSL_RECVREC) { ... receive_record ... }
    else { return handshake_error(s); }
}
```

- 송신/수신 버퍼를 AA 프레임 경계에 맞춰 처리한다(L503–567).
- ClientHello 송신, 첫 폰 레코드 수신, 완료 시 cipher suite 기록.
- 256 스텝 제한은 정상 핸드셰이크에 충분하다.

**발견 2 (진단 한정): `handshake_error`는 alert 48을 특수 처리하지만,
실폰 시험에서는 alert 자체가 USB로 오지 않아 이 분기를 탄 적이 없다.**
(L764–766). 즉 이 코드가 "alert 48을 받았다"는 증거로 오독되면 안 된다.

---

## 4. AUTH_COMPLETE 경로 (`discover`, L712–755)

```c
static const uint8_t verified[] = {0, 3, 0, 4, 0, 4, 8, 0}; /* AuthResponse(status=0). */
...
if (link->write(link->context, verified, sizeof(verified)) != (int)sizeof(verified)) return 0;
OutputDebugStringW(L"i30 CE Android Auto AUTH_COMPLETE sent.\r\n");
```

- TLS 완료 직후 **메시지 4 `AuthResponse(status=0)`**를 평문 제어 채널로 송신.
- 이후 `ServiceDiscoveryRequest`(메시지 5)를 암호화 채널로 수신.
- 시험 로그에서 `i30 CE Android Auto AUTH_COMPLETE sent.`까지 도달한 사례가 있다
  (가상 폰 시험). 실폰에서는 TLS 자체가 완료되지 않아 도달 불가.

조치 불필요.

---

## 5. USB 계층 (`ce_aa_usb_client.c`)

| 항목 | 구현 | 비고 |
| --- | --- | --- |
| AOA | control 51/52/53, 재열거 | 실폰에서 성공 |
| 버전 프레임 | 12바이트, 코드 1/2 | AA 1.7 확인 |
| bulk | `USB_NO_WAIT` + 폴링 | 시간 초과는 상위 read 루프 |
| TLS 전환 | 재열거 후 `write_tls`/`read_link` 교체 | 성공 |
| 타임아웃 | `USB_TLS_MS` | 실패 시 `USB I/O timed out` |

- USB 계층 결함은 관측되지 않았다. 실패는 항상 TLS 인증 단계다.
- Windows 직접 접근 거부(`pc-live-probe.jsonl`)는 **별개 문제**(드라이버/독점 접근)이며
  인증 실패와 합산하면 안 된다.

---

## 6. 조치 목록 (우선순위)

| 순위 | 항목 | 조건 | 난이도 |
| --- | --- | --- | --- |
| 1 | `i30-client.pem`을 **leaf 1장만**으로 유지 | 즉시 | 낮음(운영) |
| 2 | `der_time`에 `±HHMM` 오프셋 허용 | GAL 인증서가 `-0700`일 때 | 중간(코드) |
| 3 | 게스트 UTC를 실제 날짜로 설정 | 시험 전 | 낮음(운영) |
| 4 | 다중 CA/중간 CA 지원 | 폰이 3장 체인을 보낼 때 | 중간(코드) |
| 5 | alert 수신 시 원문 로깅 강화 | 진단 | 낮음(코드) |

**하지 말 것**: BearSSL 전체 교체, `SSL_VERIFY_NONE`식 검증 비활성화(우리는 이미 peer 검증이 필요 없지만,
비활성화해도 폰의 판정은 바뀌지 않는다 — 실패 방향이 반대다).
