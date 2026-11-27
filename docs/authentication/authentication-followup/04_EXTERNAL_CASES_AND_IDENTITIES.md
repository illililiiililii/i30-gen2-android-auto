# 04 — 외부 구현·성공 사례·신원 저장소

작성: 2026-11-25 · 등급: **VERIFIED** (공개 저장소/이슈 원문 기준)
목적: 미조사 인증 구현, 커밋, 개발자 답변, 실제 성공 사례를 수집하고
헤드유닛 신원으로 사용 가능한 공개 자산을 식별한다.

---

## 0. 방향(role) 용어 정리

Android Auto TLS에서:

- **폰 = TLS 서버**. 폰이 `ServerHello`/`ServerHelloDone`을 보내고,
  헤드유닛에게 **클라이언트 인증서를 요구**한다.
- **헤드유닛 = TLS 클라이언트**. 헤드유닛이 자신의 인증서를 제시하고,
  폰이 그 체인을 검증한다.

이 문서에서 "폰 인증서"는 `O=CarService`(서버 역할),
"헤드유닛 인증서"는 `O=JVC Kenwood` / `O=Android-Auto-Internal` /
`O=Google-Android-Reference`(클라이언트 역할)를 뜻한다.

---

## 1. `khimaros/behead` — 실차 성공 사례 (2026-11-23)

저장소: <https://github.com/khimaros/behead>
이슈: <https://github.com/khimaros/behead/issues/2> ("Kia EV6 / Hyundai rejects self-signed certificates")

### 1.1 최초 보고 (2026-10-17)

- 차량: **Kia EV6** (E-GMP) 순정 헤드유닛, USB 유선 AA.
- behead(Pi)는 **폰 역할(서버)** 을 한다.
- 차량 헤드유닛이 제시한 인증서:
  `subject O=Hyundai Motor Group, OU=03`, `issuer O=Google Automotive Link`,
  유효기간 2014→2048, `TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384`.
- 자체 서명 폰 인증서로도 **TLS 핸드셰이크는 완료**된다.
- 그러나 auth 직후 차량이 `00 0b 00 02 00 ff`(2바이트 ENCRYPTED 프레임)를 보내고 침묵.
- `AUTH_COMPLETE` 본문이 `08 fd ff ff ff ff ff ff ff ff 01` = status **-3**.

### 1.2 개발자 답변 (2026-11-13)

> "this looks like a cert issue. you will need to extract the production certs:
> `tools/fetch-apk.py` → `khimaros/dexter` → `python dexter.py com.google.android.projection.gearhead`"

### 1.3 성공 보고 (2026-11-23)

> "the production certificate works. behead now projects to the EV6 end to end."

- 추출한 `carservice` 인증서를 `--cert-dir`에 넣고 재시작.
- 차량이 `O=CarService` 인증서를 받아들임.
- `headunit authenticated`, 10개 채널, `video started 1920x720@60`, 센서/GPS 스트림.
- **정정**: "자체 서명을 받아들인다"는 최초 해석은 틀렸다.
  TLS 계층은 관대하지만, **애플리케이션 계층(auth 이후)** 에서 GAL 체인을 강제한다.
  `AUTH_COMPLETE status -3` + `00 ff`가 인증서 거부 신호다.

### 1.4 의미

- 실제 Hyundai/Kia 순정 헤드유닛도 **GAL 발급** 인증서를 사용한다.
- 차량(헤드유닛)은 폰 인증서를 **GAL root로 검증**한다.
- 폰 방향(우리 프로젝트)에서도 동일한 GAL root가 신뢰 앵커라는 강한 정황이다.

---

## 2. `khimaros/behead` `docs/certificates.md` — 신뢰 모델 원문

저장소 경로: `docs/certificates.md`

| headunit | self-signed certificate |
| --- | --- |
| OpenAuto | accepted |
| 2021 Mercedes Sprinter | accepted |
| Nissan Micra K14 | accepted |
| Google DHU 2.0 | refused, after the handshake; Google's accepted |
| Kia EV6 | refused, after the handshake |

핵심 문장:

> "a headunit and the phone show each other a certificate before anything else happens.
> behead accepts any headunit's. the headunit may check the phone's against Google's
> Automotive Link authority, and only a certificate Google signed gets past such a headunit."

> "the Android Auto app carries a phone certificate Google signed, `carservice.crt`,
> with its key, and the root that signs it."

> "the key is not in the app in the clear. it sits AES encrypted in the app's code,
> keyed by a stream the app mixes from its own certificates, and dexter replays that."

> "the certificate expires: the current one on 2026-12-23, after which a newer app
> has to be extracted again."

### 2.1 추출 절차 (공식 문서화)

```bash
tools/fetch-apk.py                      # GrapheneOS 미러에서 AA APK 검증 다운로드
cd ../dexter
python3 dexter.py com.google.android.projection.gearhead
# -> ~/.cache/behead/certs/{ca.crt, carservice.crt, carservice.key}
```

`dexter` 설정의 root 지문은 우리 `gal-root.pem`과 동일하다:

```
49:E5:2E:FC:13:AD:2E:D0:9F:20:4C:3B:10:69:8B:D8:4B:B7:10:5F:51:05:58:AA:14:B8:11:9A:5C:4A:D1:7F
```

### 2.2 의미

- AA APK는 `ca.crt`(GAL root) + `carservice.crt` + key를 함께 운반한다.
- 즉 **폰은 GAL root를 신뢰 앵커로 보유**한다.
- `carservice`는 **폰 역할** 인증서이므로, 우리(헤드유닛)의 클라이언트 신원으로
  그대로 쓰는 것은 역할이 다르다. (체인은 통과할 수 있으나, 폰이 자기 인증서와
  동일한 클라이언트 인증서를 거부할 가능성이 있다.)

---

## 3. `andreknieriem/open-headunit` — `Google-Android-Reference` (핵심 발견)

저장소: <https://github.com/andreknieriem/open-headunit> (★3,489, 2026-11-25 활성)
토론: <https://github.com/andreknieriem/open-headunit/discussions/637>

### 3.1 원문

> "the repository includes a client certificate and private key with the subject
> `Google-Android-Reference`, issued by `Google Automotive Link`.
> ... in `app/src/main/res/raw/cert`, alongside `privkey`."

> (댓글) "these things are extracted from the DHU in Android Studio.
> It is the official pair to communicate with Android Auto."

### 3.2 파일

| 경로 | 크기 | SHA-256 |
| --- | --- | --- |
| `app/src/main/res/raw/cert` | 1,150 B | `851D80C86BF469A3DD121B7A7084CA97B91B3D2CC72922C451E0156B455F38C1` |
| `app/src/main/res/raw/privkey` | 1,703 B | `015D172A6E4D5B7F04A5C820A60A41673F99D6E01C2F658E2A0909EFBF6D49F7` |
| `cert` → DER | 806 B | `E323CC6DD52D1F2A280360A0E92EFA04AB3664DD68FAB3DD187F03D663FEED6D` |

다운로드 (재현용):

```
https://raw.githubusercontent.com/andreknieriem/open-headunit/main/app/src/main/res/raw/cert
https://raw.githubusercontent.com/andreknieriem/open-headunit/main/app/src/main/res/raw/privkey
```

### 3.3 실측 분석

```
Subject:  C=US, ST=CA, L=Mountain View, O=Google-Android-Reference
Issuer:   C=US, ST=California, L=Mountain View, O=Google Automotive Link
Serial:   0x7653
Version:  1 (확장 없음)
Sig:      sha256WithRSAEncryption
Validity: Jul  8 22:49:18 2014 GMT -> Jul  7 22:49:18 2044 GMT
UTCTime:  140708224918Z / 440707224918Z   (Z, 오프셋 아님)
SHA-256:  E3:23:CC:6D:D5:2D:1F:2A:28:03:60:A0:E9:2E:FA:04:AB:36:64:DD:68:FA:B3:DD:18:7F:03:D6:63:FE:ED:6D
```

검증:

```
openssl verify -CAfile gal-root.pem cert     -> OK   (strict)
cert_probe.exe gar.der                       -> err=0 pkey=present rsa_bits=2048
cert modulus == privkey modulus              -> PAIR OK
```

### 3.4 실제 사용 확인

- `ssl/SingleKeyKeyManager.kt`: `R.raw.cert` + `R.raw.privkey`를 KeyStore에 넣어
  `X509ExtendedKeyManager`로 사용.
- `ssl/SslContextFactory.kt`: 위 KeyManager를 `SSLContext.init`에 전달.
- 즉 open-headunit은 이 쌍을 **헤드유닛 클라이언트 신원**으로 실제 사용한다.
- `usertrust_ecc_root.pem` / `usertrust_rsa_root.pem`은 앱의 HTTPS 업데이트 확인용이며
  AA 인증과 무관하다 (`BundledRootTrustManager` 주석 참조).

### 3.5 의미

- **GAL 발급 + `Z` 시간 + 키 일치** → 현재 `ce_aa_tls.c`가 수정 없이 로드한다.
- open-headunit은 필드에서 동작하는 헤드유닛 앱이므로, 폰이 이 신원을 받아들인다는
  강한 실증이다.
- 출처가 **Android Studio DHU**이므로 "공식 개발/평가 신원"에 해당한다.

---

## 4. AASDK — JVC Kenwood 공개 쌍 (기존 자산)

저장소: <https://github.com/opencardev/aasdk> (`newdev`)

| 파일 | 내용 |
| --- | --- |
| `cert/headunit.crt` | `O=JVC Kenwood, OU=01`, issuer GAL, serial `0x1B`, 2014-07-04 07:00Z → 2045-04-29 21:28:38Z, **`-0700`** |
| `cert/headunit.key` | RSA 2048, cert와 modulus 일치 (`CF75D663...`) |
| `cert/README.md` | "publicly available certificate used in Android Auto head units. It is **not a secret**" |

`src/Transport/SSLWrapper.cpp`는 peer 검증을 비활성화한다(개발 편의).

### 4.1 `-0700` 문제

JVC 인증서는 `140704000000-0700` 형식이므로 BearSSL 0.6 디코더가 `err=48`로 거부한다.
현재 코드로는 로드할 수 없다 (03 문서 참조).

### 4.2 커뮤니티의 자격증명 회수

`zucch1/android-auto-jetson` PR #29 (2026-10):

> "credential containment (all 3 published copies of the third-party JVC Kenwood /
> Google Automotive Link head-unit keypair removed; `Cryptor.cpp` literals ->
> fail-closed `HU_KEY_PATH` loader ...)"

즉 공개 저장소들이 JVC 키를 회수하는 추세다. 테스트 단계 사용은 가능하지만
커밋·배포는 하지 않는다.

---

## 5. 기타 저장소

| 저장소/이슈 | 내용 | 판정 |
| --- | --- | --- |
| `josemalm32/bmw-cic-androidauto` #17 | "cert is included in the repository and in the zip" | 공개 쌍 존재, 출처 불명 |
| `prototux/AARE` | AA 리버스 엔지니어링, 인증서 관련 이슈 | 기존 조사 범위 |
| `f-io/LIVI` | MFi/CP 중심, AA 인증 구현은 제한적 | 기존 조사 범위 |
| `mrmees/open-android-auto` | `docs/decompiled_headunit_firmware/*` — Kenwood/Pioneer/Sony/Alpine 펌웨어 분석 | 06 문서 참조 |
| `khimaros/dexter` | APK에서 cert+key 추출 (AES 복호화 재현) | 도구 확보 |

---

## 6. 종합

1. **폰의 신뢰 앵커는 GAL root**이며, 우리가 가진 `gal-root.pem`과 동일하다.
2. **실제 Hyundai/Kia 헤드유닛도 GAL 발급 인증서**를 사용한다 (behead EV6).
3. **GAL 발급 헤드유닛 쌍이 공개**되어 있다:
   - `Google-Android-Reference` (open-headunit, DHU 유래, **`Z` 시간**) ← **권장**
   - `JVC Kenwood` (AASDK, `-0700` 시간) ← 파서 수정 필요
   - `Android-Auto-Internal` (DHU 2.1, `-0700` 시간) ← 파서 수정 필요
4. **`Google-Android-Reference`는 현재 코드로 로드 가능**하며, 필드에서 동작하는
   헤드유닛 앱이 사용 중이다.
5. 폰 APK의 `carservice` 쌍은 **폰 역할**이므로 헤드유닛 신원으로 쓰지 않는다.
