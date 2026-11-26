# 01. 실제 TLS 실패 지점 추적 (P0-1)

작성: 2026-11-25 · 범위: GD13MY 실폰 연결 로그 vs 공식 DHU 2.0 정상 로그

## 0. 결론 요약

| 질문 | 답 | 등급 |
| --- | --- | --- |
| 실패는 어느 단계인가 | 헤드유닛이 Client Certificate를 보낸 직후, **폰이 그 체인을 검증하는 단계** | VERIFIED |
| 마지막으로 정상 수신한 메시지 | `ServerHelloDone(14)` | VERIFIED |
| 실패를 만든 주체 | 폰(삼성, `GmsCore_OpenSSL` provider) | VERIFIED |
| 폰이 남긴 원인 | `CertPathValidatorException: Trust anchor for certification path not found` | VERIFIED |
| TLS alert 관측 여부 | **관측되지 않음.** USB 읽기 시간 초과로 종료 | PARTIAL |
| `BR_ERR_X509_NOT_TRUSTED` 발생 여부 | **이 시도에서는 없음.** 다른 방향(수신기가 폰을 거부) 시험의 오류다 | VERIFIED |
| alert 48 수신 여부 | **없음.** 기존 문서의 "alert 48" 서술은 근거 없음 | VERIFIED(부재 확인) |
| 오류 07 = 인증서 체인 문제 | 폰 로그 수준에서 확정. 다만 "USB 타임아웃"의 세부 원인은 미확정 | VERIFIED + PARTIAL |

> **기존 연구 정정**: `docs/OpenCode-search/genesis-premium-gen2/13_ERROR07_EXTERNAL_CASE_ANALYSIS.md` §6은
> "증거는 `BR_ERR_X509_NOT_TRUSTED`와 alert 48"이라고 썼다. 이는 사실이 아니다.
> `BR_ERR_X509_NOT_TRUSTED`는 **수신기가 폰 인증서를 거부**할 때 나오는 로컬 오류(반대 방향)이고,
> alert 48은 실폰 로그 어디에도 없다. 실제 증거는 폰 측 Java 예외 한 건이다.

---

## 1. 역할과 전제

- 헤드유닛 = **TLS 클라이언트**, 폰 = **TLS 서버** (AARE 문서 및 DHU 로그의 `ssl state=TLS client ...`와 일치).
- 전송: AOA 재열거 후 bulk. AA 제어 채널 0, 메시지 3이 TLS 레코드를 운반.
- TLS 1.2 고정. DHU 실측 cipher `ECDHE-RSA-AES128-GCM-SHA256` = `0xC02F`.
- 상호 TLS: 폰이 `CertificateRequest(13)`를 보내고, 헤드유닛이 클라이언트 체인을 제시.

증거:
- `build/gd13my-aa-error07/dhu-20261123-222431/stderr.log`
  `BoringSSL ... ssl state=TLS client read_server_hello`, `SSL version=TLSv1.2 Cipher name=ECDHE-RSA-AES128-GCM-SHA256`, `Verify returned: ok`
- `build/gd13my-ce-projection/phone-tls-public.json` — `tls_server_handshake_types: [2,11,12,13,14]`, `server_requested_client_certificate: true`

---

## 2. 단계별 추적표 (실폰 + GD13MY 자체 수신기)

| # | 메시지 | 송신 | 수신 | 관측 | 판정 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | AOA 51/52/53 → 재열거 | HU | 폰 | `controls [51,52,52,52,52,53]`, `04e8:6860` → `18d1:2d01` | 성공 | `build/gd13my-native-oem-screen/live-phone-aoa-reenumeration.log` |
| 1 | AA 버전 교환 | HU↔폰 | | `1.7` | 성공 | 같은 파일 `arm_aa_version_verified`, `live-phone-*` 로그 `Version: 1.7` |
| 2 | ClientHello | HU | 폰 | CE/virtual-phone 로그 `i30 CE TLS ClientHello sent.` | 성공 | `src/ce/ce_aa_tls.c` L798 부근 |
| 3 | ServerHello (2) | 폰 | HU | 수신 | 성공 | `live-phone-aoa-auth-stage.json` `server_messages` |
| 4 | Certificate (11) | 폰 | HU | leaf+root 2장 수신·지문 일치 | 성공 | `phone-tls-public.json`, `live-phone-usb-trust-root-cause.log` |
| 5 | ServerKeyExchange (12) | 폰 | HU | 수신 | 성공 | 동일 |
| 6 | CertificateRequest (13) | 폰 | HU | `client_certificate_requested: true` | 성공 | 동일 |
| 7 | ServerHelloDone (14) | 폰 | HU | 수신 | **마지막 정상 수신** | 동일 |
| 8 | Client Certificate | HU | 폰 | 서버 flight에 대한 응답 1230 bytes 송신 | 송신은 됨 | `live-phone-usb-trust-root-cause.log` |
| 9 | ClientKeyExchange | HU | 폰 | 위 flight에 포함(관측 불가) | 미확인 | — |
| 10 | CertificateVerify | HU | 폰 | 폰이 검증 단계에서 실패 → 도달 여부 미확인 | 미확인 | 폰 로그 |
| 11 | ChangeCipherSpec / Finished | 양방향 | | 관측 없음 | 실패 | — |
| 12 | `AUTH_COMPLETE` | HU | 폰 | 미송신 | 미도달 | `live-phone-aoa-auth-stage.json` `"authorization": "stopped before client authentication"` |
| 13 | Service Discovery | 폰 | HU | 없음 | 미도달 | — |

- `live-phone-aoa-auth-stage.json`의 `authorization` 문자열은 **자체 수신기 시험**의 기록이고,
  같은 파일의 `server_messages`/`client_certificate_requested`는 폰이 실제로 보낸 값이다.
- 8~10단계는 TLS 레코드 단위로 분해해 기록된 로그가 없다. **추정으로 채우지 않는다.**

---

## 3. 폰 측 원인 (결정적 증거)

`build/gd13my-native-oem-screen/live-phone-usb-trust-android.log` (logcat, 28585):

```
I/CAR.GAL.SECURITY.LITE: Successfully initialized SSL context for protocol: TLSv1.2 using provider: GmsCore_OpenSSL
W/CAR.GAL.SECURITY.LITE: Phone will wait for car to send more SSL handshake data
E/CAR.GAL.SECURITY.LITE: Error in SSL handshake
E/CAR.GAL.SECURITY.LITE: javax.net.ssl.SSLHandshakeException:
    java.security.cert.CertPathValidatorException: Trust anchor for certification path not found.
E/CAR.GAL.SECURITY.LITE:   at com.android.org.conscrypt.SSLUtils.toSSLHandshakeException(SSLUtils.java:369)
E/CAR.GAL.SECURITY.LITE: Caused by: java.security.cert.CertificateException: ...
E/CAR.GAL.SECURITY.LITE:   at com.android.org.conscrypt.ConscryptEngine.verifyCertificateChain(ConscryptEngine.java:1561)
E/CAR.GAL.SECURITY.LITE:   at com.android.org.conscrypt.NativeCrypto.ENGINE_SSL_read_direct(Native Method)
```

해석 (근거 있는 범위):

1. `verifyCertificateChain`은 **peer 체인 검증** 지점이다. 폰은 서버이므로 peer = 헤드유닛.
2. `ENGINE_SSL_read_direct`에서 발생 → 폰이 클라이언트 flight를 **읽는 중** 실패.
3. `Trust anchor for certification path not found`는 "서명 불일치"나 "만료"가 아니라 **체인 종결 실패**다.
   → 우리가 보낸 self-issued/사설 CA 체인이 폰의 trust store(GAL root)로 이어지지 않았다.
4. 로그 상단의 `Phone will wait for car to send more SSL handshake data`는 폰이 정상적으로
   클라이언트 인증서를 기다렸음을 보여준다. 즉 **CertificateRequest까지는 정상**.

이 로그만으로 확정할 수 없는 것:
- 폰이 `CertificateVerify`까지 갔는지 (체인 검증이 먼저 실패하므로 도달 불가로 보이나 로그에 없음)
- 어떤 alert를 생성했는지 (아래 4절)

---

## 4. TLS alert / USB 종료의 정확한 상태

### 4.1 관측된 것

`build/gd13my-native-oem-screen/live-phone-usb-trust-root-cause.log`:
```
Version: 1.7
Phone chain matched the recorded public fingerprints.
Client TLS flight sent over USB: 1230 bytes.
Independent development identity result: Timeout: USB I/O timed out
```

`test-phone-debug-trust.py` L142-158 구조상, 클라이언트 flight 송신 후 `incoming` 제너레이터가
`stream.recv()`로 다음 AA 프레임을 기다린다. USB 읽기 타임아웃(3500 ms)이 `TransportError`로 올라온 것이다.
즉 **"타임아웃"은 폰이 아니라 우리 진단기의 읽기 제한 시간**이다.

### 4.2 alert 부재를 어디까지 말할 수 있나

- 계측기가 alert를 **표현할 수 있는가**: 가능하다. 가상 폰 시험에서 실제로 잡았다.
  `build/gd13my-ce-tls-diagnostics/early-startup/arm-projection.log`:
  `"tls_alert": ["i30 CE TLS BearSSL error: 326", "i30 CE TLS peer fatal alert: 70", "i30 CE TLS phone sent a fatal alert."]`
  (alert 70 = protocol_version, 의도적 버전 불일치 시험)
- 따라서 실폰 시험에서 alert가 안 보인 것은 **계측 공백이 아니라 실제로 AA 프레임이 오지 않았음**을 뜻한다.
- 그러나 다음 두 경우를 구분할 수 없다:
  1. 폰이 alert 레코드를 생성했지만 AA 전송 계층이 abort 시점에 flush하지 않았다.
  2. 폰이 alert 없이 소켓/액세서리 스트림을 닫았다.
- Conscrypt는 체인 검증 실패 시 보통 `certificate_unknown(46)`/`bad_certificate(42)` 계열 fatal alert를
  생성하지만, 이 환경에서 **USB로 전달됐다는 증거는 없다**. → `PARTIAL`.

### 4.3 오류 07 표시와의 관계

- 폰 UI의 오류 07("The software does not pass Android security checks")은 위 예외와 같은 시점에 표시됐다
  (`docs/ANDROID_AUTO_AUTH_STATUS.md` §"실폰에서 확인한 실패 단계").
- 오류 07 코드 자체의 정의표는 Google이 공개하지 않았다. 코드 번호와 원인을 1:1로 매핑하지 않는다.

---

## 5. 혼동 금지: 6가지 서로 다른 실패

| 현상 | 실제 의미 | 이 프로젝트에서 관측된 적 | 근거 |
| --- | --- | --- | --- |
| `BR_ERR_X509_NOT_TRUSTED` | **수신기가 peer(폰) 인증서를** 신뢰 못함 | 있음. 단, PC 수신기가 일부러 untrusted CA를 쓴 시험 | `build/gd13my-phase78/boot-projection-untrusted.projection.jsonl` |
| alert 48 (`unknown_ca`) | **폰이 우리 체인을** 거부하며 명시적 alert 전송 | **없음** | 실폰 로그 |
| 로컬 인증서 검증 실패 | 위와 동일 계열(우리 쪽 판정) | 시험에서만 | 위와 같음 |
| 폰의 헤드유닛 인증서 검증 실패 | 폰 내부 `CertPathValidatorException` | **있음(현재 오류 07의 원인)** | `live-phone-usb-trust-android.log` |
| 핸드셰이크 타임아웃 | 우리 쪽 읽기 제한 초과 | 있음(증상) | `live-phone-usb-trust-root-cause.log` |
| USB 연결 종료 | AOA/드라이버/케이블 계층 | 별도 사례 있음(Windows 접근 거부) | `build/gd13my-aa-error07/pc-live-probe.jsonl` |

`build/gd13my-aa-error07/pc-live-probe.jsonl` / `-recheck.jsonl`의 Windows 직접 USB 접근 거부는
**인증과 무관한 USB 계층 문제**다. 이 항목을 오류 07 원인으로 합산하면 안 된다.

---

## 6. 공식 DHU 정상 로그와의 대조

`build/gd13my-aa-error07/dhu-20261123-222431/stderr.log` (DHU 2.0-windows, ADB tunnel, 같은 폰):

```
Starting link. Requested protocol version: 1.7
Phone reported protocol version 1.7
ssl state=TLS client read_server_hello -1
ssl state=TLS client process_change_cipher_spec -1
ssl state=SSL negotiation finished successfully 1
SSL version=TLSv1.2 Cipher name=ECDHE-RSA-AES128-GCM-SHA256
Verify returned: ok
Audio stream close, buffered = 167936
```

대조 결과:

| 항목 | GD13MY | DHU 2.0 |
| --- | --- | --- |
| 전송 | USB AOA (재열거 성공) | ADB tunnel (5277) |
| AA 버전 | 1.7 | 1.7 |
| TLS 버전/cipher | 1.2 / 0xC02F (ARM 시험에서 동일) | 1.2 / 0xC02F |
| 폰 체인 검증(수신기→폰) | 성공(지문 일치) | `Verify returned: ok` |
| 폰의 수신기 체인 검증 | **실패** | 성공 |
| 도달 지점 | ServerHelloDone 후 | Finished, 오디오 스트림 |

⇒ **전송·버전·cipher·프레이밍은 동일 조건에서 정상**. 유일한 차이는 헤드유닛 신원이다.
이는 pi-auto-headunit의 2026-08 결론(§04 문서)과 독립적으로 일치한다.

---

## 7. 개발자 터널(ADB 5277) 시험

- `build/gd13my-native-oem-screen/live-phone-trust-root-cause.log`:
  `ProtocolError: The developer tunnel closed without a TLS certificate chain`
  (폰이 `Certificate`를 보내기 전에 종료 — 이 실행은 터널 상태 문제)
- `build/gd13my-native-oem-screen/live-phone-native-identity-fresh.log`:
  `Version: 1.7` → `Phone chain matched the recorded public fingerprints.` →
  `ProtocolError: The phone closed before completing mutual TLS`
- 즉 **개발자 모드는 신원 우회가 아니다.** 폰은 터널에서도 우리 체인을 거부하고 연결을 닫았다.
- pi-auto-headunit도 동일 결론(§04). 두 독립 프로젝트가 같은 결과를 얻었다.

---

## 8. 최종 판정

1. **오류 07의 발생 단계**: TLS 상호 인증 중, 헤드유닛이 클라이언트 체인을 제시한 직후
   폰의 `ConscryptEngine.verifyCertificateChain`에서. (VERIFIED)
2. **원인**: 체인이 폰의 유일한 trust anchor(`O=Google Automotive Link`)로 이어지지 않음. (VERIFIED)
3. **인증서 문제 외 추가 TLS 구현 문제**: 현재 증거로는 **없음**.
   - 버전/cipher/프레이밍/서버 인증서 검증/`AUTH_COMPLETE` 송신 경로는 시험에서 정상 동작.
   - 미확정: 클라이언트 flight 이후 alert 처리(4절). 이는 인증 실패의 **원인**이 아니라 **진단 공백**이다.
4. **미확정 사항**: alert 생성·전달 여부, `CertificateVerify` 도달 여부, USB 타임아웃이
   폰의 abort인지 우리 read 로직인지(현재는 우리 timeout이 먼저 걸린 것으로 확인됨).

---

## 9. 재현 명령

```powershell
# 1) 폰 logcat (개발자 옵션 + USB 디버깅)
adb logcat -c
adb logcat -s CAR.GAL.SECURITY.LITE:V

# 2) 자체 수신기 USB 시험 (기존)
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py build\gd13my-native-oem-screen\test-phone-debug-trust.py `
      build\gd13my-native-oem-screen\cert-chain --usb

# 3) 공식 DHU 기준시험
& "$env:LOCALAPPDATA\i30-gen2-android-auto\google-dhu\r02.0\desktop-head-unit.exe"
```

증거 파일 SHA-256은 `PROGRESS.md`의 증거 색인 참조.
