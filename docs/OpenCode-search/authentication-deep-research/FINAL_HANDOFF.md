# FINAL HANDOFF — 9개 질문에 대한 답

작성: 2026-11-25 · 근거 문서: `01`~`12`

---

## Q1. 오류 07은 정확히 어느 단계에서 발생하는가?

**TLS 상호 인증 중, 헤드유닛이 Client Certificate를 전송한 직후,
폰의 `ConscryptEngine.verifyCertificateChain`에서.** (VERIFIED)

- 헤드유닛 = TLS **클라이언트**, 폰 = TLS **서버**.
- 폰이 보낸 서버 flight: `[ServerHello(2), Certificate(11), ServerKeyExchange(12), CertificateRequest(13), ServerHelloDone(14)]`.
- 마지막으로 정상 수신한 메시지 = `ServerHelloDone(14)`.
- 우리가 클라이언트 flight 1,230바이트를 전송한 뒤, 폰이 그 체인을 검증하다 실패.

폰 로그 (`build/gd13my-native-oem-screen/live-phone-usb-trust-android.log`):
```
E/CAR.GAL.SECURITY.LITE: javax.net.ssl.SSLHandshakeException:
    java.security.cert.CertPathValidatorException: Trust anchor for certification path not found.
E/CAR.GAL.SECURITY.LITE:   at com.android.org.conscrypt.ConscryptEngine.verifyCertificateChain(ConscryptEngine.java:1561)
E/CAR.GAL.SECURITY.LITE:   at com.android.org.conscrypt.NativeCrypto.ENGINE_SSL_read_direct(Native Method)
```

즉 **폰이 우리를 거부**하는 방향이다. 우리가 폰을 거부하는 방향이 아니다.

> 정정: 기존 문서의 "`BR_ERR_X509_NOT_TRUSTED` + alert 48"은 **근거 없음**.
> 그 코드는 반대 방향(수신기가 폰 인증서를 거부)의 로컬 오류이고, alert 48은 로그에 없다.

---

## Q2. 인증서 문제 외에 다른 TLS 문제가 있는가?

**현재 증거로는 없다.** (VERIFIED)

| 항목 | 상태 | 근거 |
| --- | --- | --- |
| TLS 버전 | 1.2 고정, DHU와 동일 | DHU `SSL version=TLSv1.2` |
| Cipher | `ECDHE-RSA-AES128-GCM-SHA256` (`0xC02F`) | ARM 시험 `arm-usb-tls-dhu-cipher.json` |
| 프레이밍 | AA 채널 0 / 메시지 3, 재조립 정상 | CE 시험 |
| 서버(폰) 인증서 검증 | 성공 (지문 일치 + CA 검증) | `Phone chain matched...` |
| `AUTH_COMPLETE` 송신 경로 | 구현 완료, 가상 폰에서 도달 | `ce_aa_tls.c` L714 |
| alert 처리 | 수신 시 로깅 구현됨, 실폰에선 alert 미관측 | PARTIAL |

남은 미확정은 **alert가 실제로 전송됐는지** 하나이며, 이는 원인이 아니라 **진단 공백**이다.
→ `11_NEXT_TEST_PLAN.md` Test A로 해소.

---

## Q3. 성공한 프로젝트와의 차이는 무엇인가?

**오직 하나: 헤드유닛 신원이 GAL(Google Automotive Link) root의 서명을 받았는가.** (VERIFIED)

| | 우리 GD13MY | AASDK/OpenAuto/LIVI | Google DHU |
| --- | --- | --- | --- |
| 인증서 발급자 | 자체/실험 | GAL | GAL |
| Subject | 임의 | JVC Kenwood | Android-Auto-Internal |
| 체인 검증 | 실패 | 통과 | 통과 |
| TLS 구현 | BearSSL | OpenSSL | BoringSSL |
| 결과 | error 07 | 정상 | 정상 |

핵심 반증:
- 폰은 **조직명(DN)을 구분하지 않는다** — Google 내부명과 OEM명 모두 통과.
- 폰은 **확장 필드를 요구하지 않는다** — DHU 인증서는 v1, 확장 0개.
- 폰은 **DER 비준수 `-0700` 시간 인코딩도 수락한다** — DHU/AASDK 실사용.
- 폰은 **TLS 구현을 구분하지 않는다** — BearSSL로도 서버 flight 수신·검증까지 성공.

⇒ 통과 조건은 사실상 **"GAL이 서명한 인증서 + 그 개인키 보유"** 하나다.

pi-auto-headunit(2026-08)은 우리와 무관한 Rust 구현으로 **USB와 개발자 터널 모두에서 동일한 error 7**을
얻었다. 이는 "구현 차이"가 원인이 아님을 독립적으로 증명한다.

---

## Q4. Genesis 순정 헤드유닛 공개 인증서를 찾았는가?

**찾지 못했다. 그리고 존재하지 않는 것으로 판정한다.** (평문 VERIFIED / 암호문 UNKNOWN)

`G:\` 전수 조사 결과:
- 40MB 이하 모든 파일에서 `-----BEGIN ` **0건**.
- `BIN/APPNAVI`(순정 내비 ELF): `Android`, `Google`, `TLS`, `cert` 문자열 **0건**.
- `vr.img`의 `"Android Auto"` 문자열은 **다국어 경고 문구**일 뿐, 프로토콜 코드가 아니다.
- `GENESIS_G80_DIS_Bluelink.ver` 매니페스트에 **AA/CarPlay/Projection 모듈 항목 없음**.
- `essentials`는 **복호화 도구만** 포함 → 나머지 이미지는 암호화 상태.

결론:
1. 이 펌웨어는 **AA 수신 기능을 탑재하지 않은 빌드**다.
2. GD13MY(2013)는 AA 지원 세대가 아니다.
3. 따라서 "순정 인증서를 추출해 재사용"이라는 경로는 **처음부터 존재하지 않았다.**

암호화된 `rootfs.img` 내부는 확인하지 않았다. 매니페스트 근거상 AA 모듈이 있을 가능성은 낮다고 판단하며,
복호화 키 역공학은 본 연구 범위를 벗어난다.

---

## Q5. 공식 개발/평가 신원 발급 경로가 존재하는가?

**공개된 self-service 경로는 없다.** (VERIFIED 부재)

| 경로 | 상태 |
| --- | --- |
| Google 공개 문서의 수신기 신원 발급 | **없음.** DHU는 앱 개발자용 테스트 도구 |
| Android for Cars 파트너십 | 자동차 제조사/Tier1 대상, 개인 프로젝트 진입로 없음 |
| AAP 인증 프로그램 | 존재. 2026-10 P3가 **AAP 2.0** 3PL 파트너로 인증 |
| Cinemo CORE Projection | SDK 존재. **WinCE 6.0 지원·평가 신원 미확인**, 문의 발송됨(재문의 금지) |
| ART SDK / ECORE KOREA / NXP | 존재. 조건 미확인, NXP는 i.MX 전용 |

핵심 구분:
- **DHU가 동작한다** ≠ **제3자가 DHU 신원을 쓸 권한이 있다**
- **인증서가 공개돼 있다** ≠ **사용 권한이 있다**

DHU/AASDK/LIVI 신원 재사용은 **기술적으로는 통과하지만 정책상 금지**다
(Google 내부 테스트 신원 또는 타사 신원의 위장).

---

## Q6. 가장 현실적인 방법은 무엇인가?

정직한 답: **엄격한 목표(순정 AA + 순정 폰 + 자체 수신기)를 만족하는 방법은 현재 없다.**

현실적 순서:

1. **상용 SDK 라이선스 확인 (유일한 정공법)**
   - Cinemo/ART/ECORE 중 하나가 ①WinCE 6.0 또는 ARMv7 Linux ②평가용 신원 ③GPL 분리 배포를 제공하는지.
   - 답변 대기 중. **재문의하지 않는다.**

2. **목표 재정의 (가장 확실히 동작하는 방법)**
   - 자체 폰 앱/프록시(AARE 방식)를 허용하면 GAL 신원이 **불필요**하다.
   - 단, "폰 측 앱 없음" 조건을 포기해야 한다.

3. **프로젝트 종료 (정직한 마무리)**
   - 1·2가 모두 막히면 오류 07은 **해결 불가**로 확정하고 실패 기록을 남긴다.

하지 말 것:
- 자체 서명 신원 재시도 (이미 반증, pi-auto-headunit도 재시도 금지 선언)
- DHU/AASDK/LIVI 개인키 사용
- BearSSL 전체 교체
- 성공 확률 수치화

---

## Q7. BearSSL 변경이 필요한가?

**전체 교체는 불필요하다. 조건부로 작은 수정 2곳이 필요하다.** (VERIFIED)

| # | 위치 | 문제 | 조치 |
| --- | --- | --- | --- |
| 1 | `src/ce/ce_aa_tls.c` `der_time()` L253–283 | `Z`만 허용. GAL 발급 인증서가 `-0700`이면 **로컬에서 거부** | `±HHMM` 오프셋 허용 |
| 2 | `src/ce/ce_aa_tls.c` `read_credentials()` L165–209 + L438 | PEM의 모든 인증서를 전송 → **루트까지 전송 가능** | leaf 1장만 유지 또는 self-signed 제외 |

추가 조건:
- 게스트 UTC가 인증서 유효기간(2014~2045) 내여야 한다. `configure()`가 로컬에서 먼저 검사한다.
- 다중 CA/중간 CA 지원은 **미래 대비**이며 현재 실패 원인이 아니다.

BearSSL 자체(`asn1.t0` L694–698)도 `Z`만 허용하지만, 이는 **폰 인증서 검증**에만 쓰이고
폰은 `Z`를 쓰므로 문제없다. **BearSSL 소스는 건드릴 필요가 없다.**

---

## Q8. Codex가 쿼터 리셋 후 가장 먼저 할 시험은?

**Test D(DHU 대조) → Test C(시계) → Test A(원시 바이트 캡처).** 총 1시간 이내.

### 1) Test D — DHU 대조 (5분, 필수)
```powershell
& "$env:LOCALAPPDATA\i30-gen2-android-auto\google-dhu\r02.0\desktop-head-unit.exe"
```
기대: `Phone reported protocol version 1.7`, `Verify returned: ok`.
실패하면 폰/케이블/ADB 문제이므로 이후 시험은 무효.

### 2) Test C — 게스트 UTC 확인 (10분)
CE 로그에서 다음 중 하나가 나오는지 확인:
```
i30 CE TLS guest UTC unavailable or invalid.
i30 CE TLS head unit certificate is not yet valid at guest UTC.
i30 CE TLS head unit certificate expired at guest UTC.
```
나오면 시계 문제 → 수정 후 재시험.

### 3) Test A — flight 이후 원시 캡처 (15분, 핵심)
`test-phone-debug-trust.py`를 복제해, 클라이언트 flight 송신 직후
**프레임 파서를 우회하고 10초간 원시 바이트를 수집**한다.

```python
send(stream, Message(0, 0, 3, response))
deadline = time.monotonic() + 10.0
raw = bytearray()
while time.monotonic() < deadline:
    try: chunk = stream.read(2000)
    except Timeout: continue
    except Disconnected: break
    if not chunk: break
    raw += chunk
```

동시에 `adb logcat -s CAR.GAL.SECURITY.LITE:V`를 캡처한다.

**판정**
- `15 03 03 00 02 02 XX` 발견 → 폰이 fatal alert 전송 (alert 존재 VERIFIED)
- 0바이트 → alert 없음 확정 (PARTIAL 유지)
- alert 값 42/46/48 → 원인 세분화

이 시험은 **성공을 만들지 않는다.** 남은 진단 공백 하나를 닫을 뿐이다.

---

## Q9. 남은 조건은 무엇인가?

### 성공을 위한 필수 조건 (모두 충족해야 함)

| # | 조건 | 현재 |
| --- | --- | --- |
| C1 | GAL root가 서명한 헤드유닛 인증서 + 대응 개인키 **사용 권한** 확보 | **미충족 (핵심)** |
| C2 | 클라이언트 체인을 leaf 1장으로 구성 | 코드/운영으로 충족 가능 |
| C3 | 게스트 UTC가 인증서 유효기간 내 | 설정으로 충족 가능 |
| C4 | 인증서 시간 형식(`-0700`) 수용 | `der_time` 수정으로 충족 가능 |
| C5 | AAP 세대(1.7/2.0)와의 정합 | DHU 1.7로 현재 충족 |

### 외부 의존 조건

- Cinemo/ART/ECORE 답변 (WinCE 6.0, 평가 신원, GPL 경계)
- Google AAP 2.0 인증 요건의 실제 적용 범위
- 폰 AA 앱 업데이트에 따른 leaf 회전·검증 규칙 변경

### 명시적 비조건 (해결해도 성공하지 못하는 것)

- BearSSL 교체
- TLS 버전/cipher 조정
- USB/AOA 프레이밍 개선
- `AUTH_COMPLETE` 타이밍 조정
- 개발자 모드/개발자 터널 사용

### 최종 판정

> **C1이 충족되지 않는 한, 순정 Android Auto는 GD13MY에서 동작하지 않는다.**
> C1은 코드로 만들 수 없으며, 공개된 공식 발급 경로도 없다.
> 따라서 현재 상태는 **"신원 확보 대기(blocked)"** 이며,
> 유일한 진행 방향은 상용 SDK 라이선스 확인 또는 목표 재정의다.

---

## 부록: 이 연구가 남긴 재사용 가능 자산

1. **인증서 4종 실측 세트** (`build/auth-research/certs/`) — 해시·체인·시간 인코딩 포함
2. **재현 스크립트 3종** (`scan_genesis*.py`) — 펌웨어 신원 탐색
3. **판정 원장 24항목** (`12_EVIDENCE_INDEX.md` §5) — 등급별 근거
4. **정정된 실패 서사** — alert 48 오류, v1 오류, Genesis 인증서 가설 폐기
5. **1시간 시험 계획** (`11_NEXT_TEST_PLAN.md`) — 다음 담당자용
