# 11. 쿼터 리셋 후 첫 시험 계획

작성: 2026-11-25 · 대상: 실폰 + GD13MY/PC 수신기 · 전제: **신원 미확보 상태**

## 0. 왜 이 시험을 먼저 하는가

신원이 없으므로 "성공" 시험은 불가능하다. 대신 **남은 PARTIAL 1건**을 VERIFIED로 바꾸는 것이
가장 가치 있는 다음 행동이다.

| 미확정 항목 | 현재 등급 | 이 시험으로 |
| --- | --- | --- |
| 클라이언트 flight 후 폰이 TLS alert를 보내는가 | PARTIAL | VERIFIED(예/아니오) |
| 체인에 루트를 포함하면 거부 양상이 달라지는가 | UNKNOWN | VERIFIED(비교) |
| 게스트 UTC가 인증서 유효기간 내인가 | PARTIAL | VERIFIED |

우선순위: **Test A → Test C → Test B**. (A가 가장 결정적이고 부작용이 없다)

---

## 1. Test A — 클라이언트 flight 이후 원시 바이트 캡처

### 목적
현재 진단기는 AA 프레임을 기대하며 읽다가 `Timeout`으로 끝난다.
폰이 TLS alert 레코드를 보냈는지 **바이트 수준에서** 확인한다.

### 현재 한계 (코드 근거)
`build/gd13my-native-oem-screen/test-phone-debug-trust.py` L142–158:
```python
for message in chain(captured, incoming):
    ...
    if tls.ready:
        ...
raise ProtocolError("The phone closed before completing mutual TLS")
```
- `incoming` 제너레이터는 `FrameReader`/`Reassembler`를 거치므로
  **프레임이 아닌 바이트는 버려진다.**
- USB 읽기 타임아웃이 나면 `TransportError`로 종료된다.

### 시험 방법
`test-phone-debug-trust.py`를 복제해 **flight 송신 직후** 다음 루프로 교체한다.

```python
# build/auth-research/capture-after-flight.py (신규, 기존 파일 수정 금지)
from i30_receiver.transport import Timeout, Disconnected
import hashlib, json, time
from pathlib import Path

send(stream, Message(0, 0, 3, response))
deadline = time.monotonic() + 10.0          # 10초 창
raw = bytearray()
while time.monotonic() < deadline:
    try:
        chunk = stream.read(2000)           # 2초 단위
    except Timeout:
        continue
    except Disconnected:
        break
    if not chunk:
        break
    raw += chunk
Path("build/auth-research/capture.json").write_text(json.dumps({
    "port": port, "bytes": len(raw), "hex": raw.hex(),
    "sha256": hashlib.sha256(raw).hexdigest(),
}, indent=2))
```

### 기록할 것
- `bytes`, `hex`, `sha256`
- 마지막 수신 시각
- 폰 logcat 동시 캡처:
  ```powershell
  adb logcat -c
  adb logcat -s CAR.GAL.SECURITY.LITE:V > build\auth-research\phone.log
  ```

### 판정 기준

| 관측 | 해석 | 등급 상승 |
| --- | --- | --- |
| 21바이트 `15 03 03 00 02 02 XX` 형태 | **폰이 fatal alert 전송** | alert 존재 VERIFIED |
| 바이트 0, 연결 유지 | alert 없음(또는 flush 안 됨) | alert 부재 PARTIAL 유지 |
| 즉시 EOF | 폰이 소켓/액세서리 종료 | abort 방식 VERIFIED |
| alert 값 42/46/48 | `bad_certificate` / `certificate_unknown` / `unknown_ca` | 원인 세분화 |

**중요**: alert가 나와도 그것은 **결과**이지 원인이 아니다. 원인은 여전히 A(체인 미신뢰)다.

### 중단 규칙
- 3회 반복해도 바이트 0이면 중단하고 PARTIAL로 확정.
- 개인키/PEM을 로그에 남기지 않는다.

---

## 2. Test C — 게스트 UTC 및 유효기간 감사

### 목적
`ce_aa_tls.c`가 **자체 인증서를 로컬에서 거부**하는 경우를 배제한다(§08 1.4).

### 방법
1. CE 수신기 부팅 후 `i30 CE TLS` 디버그 출력 수집:
   ```
   i30 CE TLS guest UTC unavailable or invalid.
   i30 CE TLS head unit certificate is not yet valid at guest UTC.
   i30 CE TLS head unit certificate expired at guest UTC.
   ```
2. 사용 인증서의 notBefore/notAfter를 OpenSSL로 확인:
   ```powershell
   & 'C:\Program Files\Git\usr\bin\openssl.exe' x509 -in <cert> -noout -dates
   ```
3. 게스트 UTC와 비교.

### 판정
- 게스트 UTC가 2014~2045 범위 밖이면 → **시계 문제**. 즉시 수정 후 재시험.
- 범위 내이면 → 시계 가설 폐기.

### 주의
WinCE RTC 리셋 시 1601년이 될 수 있다. 이 경우 `configure()`가 **핸드셰이크 전에** 실패하므로
로그에 TLS ClientHello가 없다. 이는 폰 문제와 구분해야 한다.

---

## 3. Test B — 체인 구성 A/B 비교

### 목적
`read_credentials`가 PEM의 모든 CERTIFICATE를 전송한다(§08 1.3).
루트 포함 여부가 폰의 거부 양상을 바꾸는지 확인한다.

### 준비 (자체 생성 신원만 사용, 제3자 신원 금지)
```
build/auth-research/chain-ab/
├─ a-leaf-only/     i30-dev-cert.pem (leaf 1장), i30-dev-key.pem
└─ b-leaf-root/     i30-dev-cert.pem (leaf + self-signed root), i30-dev-key.pem
```
생성:
```powershell
$o='C:\Program Files\Git\usr\bin\openssl.exe'
& $o req -x509 -newkey rsa:2048 -nodes -keyout root.key -out root.pem -days 3650 -subj "/O=i30-test/CN=i30-test-root"
& $o req -newkey rsa:2048 -nodes -keyout leaf.key -out leaf.csr -subj "/O=i30-test/CN=i30-test-leaf"
& $o x509 -req -in leaf.csr -CA root.pem -CAkey root.key -CAcreateserial -out leaf.pem -days 3650
```

### 실행
```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py build\gd13my-native-oem-screen\test-phone-debug-trust.py build\auth-research\chain-ab\a-leaf-only --usb
& $py build\gd13my-native-oem-screen\test-phone-debug-trust.py build\auth-research\chain-ab\b-leaf-root --usb
```

### 판정

| A 결과 | B 결과 | 해석 |
| --- | --- | --- |
| anchor 미발견 | anchor 미발견 | 폰은 체인 길이와 무관하게 anchor만 본다 → 루트 포함은 무해(그러나 관행상 leaf-only 유지) |
| anchor 미발견 | 다른 예외(파싱/형식) | **루트 포함이 해롭다** → leaf-only 강제 필요 |
| 둘 다 다른 오류 | — | USB/프레이밍 문제 재점검 |

### 기대
두 경우 모두 `Trust anchor for certification path not found`가 나올 것으로 예상한다.
그럴 경우 **체인 구성은 원인이 아니며**, §08 1.3의 권고는 "예방적" 조치로 남는다.

---

## 4. Test D — DHU 대조군 (필수)

모든 시험 전후에 동일 폰으로 DHU를 1회 실행해 **폰 상태가 정상**임을 확인한다.

```powershell
& "$env:LOCALAPPDATA\i30-gen2-android-auto\google-dhu\r02.0\desktop-head-unit.exe"
```
기대 로그:
```
Phone reported protocol version 1.7
SSL version=TLSv1.2 Cipher name=ECDHE-RSA-AES128-GCM-SHA256
Verify returned: ok
```

DHU가 실패하면 **폰/케이블/ADB 문제**이므로 우리 시험 결과는 무효다.

---

## 5. 시험 순서 및 소요

| 순서 | 시험 | 소요 | 선행 조건 |
| --- | --- | --- | --- |
| 1 | Test D (DHU 대조) | 5분 | ADB |
| 2 | Test C (시계) | 10분 | CE 부팅 |
| 3 | Test A (원시 캡처) | 15분 | USB, 스크립트 |
| 4 | Test B (체인 A/B) | 20분 | 인증서 생성 |
| 5 | 결과를 `PROGRESS.md`에 기록 | 5분 | — |

총 1시간 이내.

---

## 6. 이 시험이 바꾸지 않는 것

- 신원 없이 오류 07이 해결되지 않는다.
- Test A/B/C는 **진단 정밀도**를 높일 뿐, 성공 경로를 만들지 않는다.
- 성공 경로는 §09의 신원 확보뿐이다.

---

## 7. 결과 기록 템플릿

```markdown
## YYYY-MM-DD 실폰 시험
- 폰: <모델>/<Android>/AA <버전>
- DHU 대조: OK / FAIL
- 게스트 UTC: <값> / 인증서 유효기간: <notBefore>~<notAfter>
- Test A: bytes=<n>, sha256=<...>, alert=<값|없음>
- Test B: A=<예외>, B=<예외>
- 판정 변경: <PARTIAL→VERIFIED 등>
- 증거: build/auth-research/...
```
