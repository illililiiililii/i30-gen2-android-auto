# 15. Codex 구현 권고

작성일: 2026-11-24
대상: `F:\i30-gen2-android-auto` (GD13MY WinCE/ARM, BearSSL 0.6 기반)
전제: 인증서 위조/우회/개인키 재배포는 하지 않는다. 펌웨어 쓰기/플래시도 하지 않는다.

---

## 0. 우선순위

| 순위 | 작업 | 이유 |
| --- | --- | --- |
| P0 | TLS/인증서 진단 계층 정리 | 에러 07 원인을 코드/로그에서 즉시 분류 |
| P0 | HU 신원 공급자 인터페이스 | 인증서 교체 가능하게, 제품 로직과 분리 |
| P1 | AAP-over-TLS 프레이밍/`AUTH_COMPLETE` | 실제 연결 경로의 핵심 |
| P1 | phone-role 테스트 하네스 | 차량 없이 HU 동작 검증 |
| P2 | 오디오/입력/센서 채널 | 사용자 가치 |
| P2 | 미디어/USB(AOA) | 별도 스택 필요 |
| P3 | 비디오 디코드 최적화 | 14번 문서, 측정 후 |
| P3 | Genesis 컨테이너 복호화 | 오프라인 리서치, 제품 코드와 분리 |

---

## 1. 절대 하지 말 것 (가드레일)

1. DHU/AASDK/LIVI/OpenAuto의 인증서+개인키를 코드/리소스/테스트에 넣지 않는다.
2. `SSL_VERIFY_NONE`으로 phone 검증을 "해결"하지 않는다. phone은 우리 통제 밖이다.
3. "unknown sources", "ignore certificate", "developer bypass" 플래그를 찾지 않는다. 존재하지 않는다.
4. `G:` 드라이브에 쓰지 않는다. 펌웨어 이미지를 수정/플래시하지 않는다.
5. 복호화된 Genesis 바이너리/키를 저장소에 커밋하지 않는다. 임시 디렉터리에서만 다룬다.
6. Google의 상표/인증을 실제 획득 없이 표기하지 않는다.

---

## 2. P0: TLS/인증서 진단 계층

### 목표

에러 07이 발생했을 때, 로그만 보고 아래를 구분한다.

- 체인 미신뢰 (`X509_NOT_TRUSTED`, alert 48)
- 만료 (`expired`, alert 45)
- TLS 버전/cipher 불일치 (`protocol_version`/`handshake_failure`)
- 전송/USB/AOA 단계 실패 (TLS 이전)
- 인증서 없음/키 불일치

### 구현

- `src/tls/TlsDiagnostics.{h,cpp}` 신설:
  - `enum class TlsFailure { None, ChainUntrusted, Expired, NotYetValid, BadSignature, UnsupportedVersion, CipherMismatch, NoCertificate, KeyMismatch, Transport, Unknown }`
  - BearSSL `br_ssl_engine_last_error()`와 X509 검증 콜백을 매핑.
  - peer chain을 DER로 덤프(선택, 디버그 빌드만).
- 로그 포맷(JSON lines, WinCE에서도 파싱 가능한 단순 형식):

```json
{"ts":"...","stage":"tls","event":"client_cert_sent","subject":"...","issuer":"...","sha256":"...","notAfter":"...","result":"chain_untrusted","alert":48}
```

- `scripts/classify_error7.py`: 로그를 읽어 A~E 원인 코드를 출력(13번 문서의 분류와 동일).

### 수용 기준

- self-signed 인증서 → `chain_untrusted`
- 만료 인증서 → `expired`
- 인증서 없음 → `no_certificate`
- 정상 GAL 테스트 체인 → `none`
- 각 케이스가 단위 테스트로 고정됨.

---

## 3. P0: HU 신원 공급자

### 설계

```cpp
class IHuIdentityProvider {
public:
    virtual ~IHuIdentityProvider() = default;
    virtual bool loadCertificateChain(std::vector<std::vector<uint8_t>>& derChain) = 0;
    virtual bool sign(const uint8_t* hash, size_t hashLen, std::vector<uint8_t>& sig) = 0;
    virtual std::string describe() const = 0; // subject/issuer/expiry, no key material
};
```

- 구현체:
  - `FileIdentityProvider`: 배포 시 주입되는 PEM/DER + 키 경로.
  - `NullIdentityProvider`: 개발용. 항상 `chain_untrusted`를 반환해 "아직 provisioning 안 됨"을 명시.
- **개발용 DHU 인증서 로더를 만들지 않는다.** 테스트 벡터로만 사용하고, 제품 경로에는 연결하지 않는다.
- 키는 코드/리소스에 하드코딩하지 않는다. WinCE 보안 저장소 또는 외부 주입 파일.

### 수용 기준

- 신원이 없으면 HU가 "provisioning required" 상태로 뜨고, phone 연결 시도 시 명확한 진단을 남긴다.
- 신원이 있으면 체인/만료/키 일치를 시작 시 검증한다.
- 로그에 개인키/키 파일 내용이 절대 나오지 않는다.

---

## 4. P1: AAP-over-TLS 프레이밍과 `AUTH_COMPLETE`

### 구현 항목

1. TLS 레코드가 AAP 프레임 바디 안에 캡슐화되는 구조를 명시적으로 처리.
   - 참조: open-headunit `TlsUnwrapLoop.kt`의 "프레임 바디 = 1개 이상 TLS 레코드" 모델.
   - AGPL 코드 복사 금지. 동작만 참고해 자체 구현.
2. `AUTH_COMPLETE`(message type 4, `AuthResponse`) status 처리:
   - `0`: 수락 → 서비스 디스커버리 진행.
   - 음수: 거부 → `TlsDiagnostics`와 별도로 `auth_rejected` 이벤트 기록.
3. 핸드셰이크 순서 고정:
   - version exchange → TLS handshake → client cert 전송 → `AUTH_COMPLETE` → service discovery.
4. 타임아웃/재시도 정책: TLS 실패는 재시도해도 동일하므로 즉시 진단 후 중단. 전송 실패만 재시도.

### 수용 기준

- phone-role 하네스에서 `AUTH_COMPLETE 0`까지 도달.
- 인증서 거부 시 `auth_rejected`와 `chain_untrusted`가 모두 남는다.
- 프레임 경계가 깨진 입력에서 무한 루프/spin이 없다(최소 1바이트 또는 1태스크 진행 보장).

---

## 5. P1: phone-role 테스트 하네스

차량/phone 없이 HU를 검증하려면 **phone 역할의 TLS 서버**가 필요하다.

- 위치: `tools/phone-sim/` (호스트 PC, Python/OpenSSL).
- 기능:
  - AAP version exchange 흉내.
  - TLS 1.2 서버, client certificate 요청.
  - 신뢰/거부 모드:
    - `trusted`: 테스트 CA 체인으로 HU 검증.
    - `untrusted`: self-signed 거부.
    - `expired`: 만료 체인 거부.
  - `AUTH_COMPLETE` 응답 코드 선택.
- 테스트 체인은 **테스트 전용 CA**로 생성하며, GAL/DHU 인증서를 사용하지 않는다.
- 목적: HU의 클라이언트 동작(체인 전송, 서명, alert 처리)을 검증. phone의 실제 정책을 복제하는 것이 아니다.

### 수용 기준

- 4개 모드가 HU 로그에서 정확히 구분됨.
- 하네스는 인터넷/외부 인증서 없이 재현 가능.
- CI(또는 로컬 스크립트)에서 실행 가능.

---

## 6. P2: 오디오/입력/센서

- 오디오: AAP audio sink 채널, 48kHz/16-bit stereo 우선. WinCE WaveOut/DirectSound 경로 확인.
- 입력: touch/key 이벤트를 AAP `InputSource`로 매핑. 좌표계/스케일 테스트.
- 센서: GPS/차속/주차 브레이크 등은 후순위. 없으면 phone이 일부 기능을 제한할 수 있음을 문서화.
- 수용 기준: 오디오 끊김 없이 10분, 터치 좌표 오차 ±2px, 키 이벤트 왕복 지연 < 100ms.

---

## 7. P2: 미디어/USB(AOA)

- GD13MY `LibUSB.dll`은 미디어 파일 브라우징/재생만 한다(`lUSBFB*`, `lUSBmm*`). AOA가 아니다.
- AOA 스택은 프로젝트가 소유한다:
  - USB descriptor 확인, AOA version 협상, accessory start, bulk endpoint 설정.
  - WinCE USB host 드라이버(`omap3430_musbhcd`) 위에서 동작 확인.
- 수용 기준: phone 인식 → AOA 인터페이스 열림 → AAP 시작까지.
- 리스크: WinCE USB 호스트 스택의 endpoint/전송 제약. 별도 스파이크 필요.

---

## 8. P3: 비디오

14번 문서의 E1~E4를 따른다.

- 1단계: 기존 플레이어로 H.264 480p/720p 재생 측정(코드 변경 없음).
- 2단계: VideoDev IOCTL 추적.
- 3단계: 소프트웨어 디코더 벤치마크.
- 4단계: AAP `VideoConfig` 협상.
- **측정 전 최적화 금지.** "30fps 충분" 가정 금지.

수용 기준(잠정):

- 480p 30fps에서 프레임 드롭 < 5%.
- 오디오-비디오 싱크 오차 < 100ms.
- CPU 점유 < 80%, 발열/스로틀링 없음.

---

## 9. P3: Genesis 컨테이너 리서치

- `research/genesis-premium-gen2/`의 기존 스크립트는 128KB 헤더를 평문 RSA 블록으로 가정하지만, 엔트로피 분석 결과 **암호화 영역**이다.
- Codex 작업:
  1. `DecryptToFile`(x86 ELF)의 `LGUInitDecrypt`/`LGUDecryptData`/`Cryptor_CbcPadDecrypt` 호출 흐름을 의사코드로 복원.
  2. 키 유도가 기기 고유값인지 빌드 상수인지 판별.
  3. Python 재구현으로 `G:\IBOX.tar` 사본 복호화 시도(읽기 전용).
  4. 성공 시 `tar tf`로 목록만 확인하고, AA 관련 문자열(`Google Automotive Link`, `CarService`, `AAP`, `TLS`) 검색.
- 산출물: `research/genesis-premium-gen2/DECRYPT_FINDINGS.md` (성공/실패, 근거, 재현 명령).
- 금지: 원본 이미지 수정, 저장소에 바이너리 커밋, 개인키 추출/공개.

---

## 10. 테스트 매트릭스

| 테스트 | 입력 | 기대 |
| --- | --- | --- |
| T1 정상 체인 | 테스트 CA 체인 | handshake 성공, `AUTH_COMPLETE 0` |
| T2 self-signed | 자체 서명 | `chain_untrusted`, alert 48 |
| T3 만료 | notAfter 과거 | `expired` |
| T4 체인 누락 | leaf만 | `chain_untrusted` |
| T5 키 불일치 | cert/key 불일치 | 시작 시 실패 |
| T6 프레임 분할 | TLS 레코드 분할 | 정상 재조립, spin 없음 |
| T7 잘린 레코드 | 중간 절단 | 오류 후 종료, 무한 대기 없음 |
| T8 인증 거부 | `AUTH_COMPLETE -1` | `auth_rejected` |
| T9 전송 실패 | USB 분리 | 재시도 후 진단 |
| T10 비디오 없음 | video 미구현 | 나머지 채널 정상 |

---

## 11. 첫 10개 티켓(제안)

1. `TlsDiagnostics` 인터페이스 + BearSSL 매핑.
2. 로그 스키마/JSON lines + `classify_error7.py`.
3. `IHuIdentityProvider` + `NullIdentityProvider`.
4. 시작 시 체인/만료/키 검증.
5. AAP-over-TLS 프레이밍 리팩터링(프레임 경계 보장).
6. `AUTH_COMPLETE` 처리 + 이벤트.
7. `tools/phone-sim` trusted 모드.
8. `tools/phone-sim` untrusted/expired 모드.
9. 오디오 sink 최소 구현.
10. 터치 입력 최소 구현.

각 티켓은 "코드 + 단위 테스트 + 로그 예시"까지가 완료 조건이다.

---

## 12. Definition of Done

- 에러 07 발생 시 로그 한 줄로 A~E 원인 코드가 나온다.
- 신원이 없을 때 제품이 "provisioning required"를 명확히 표시한다.
- phone-role 하네스로 차량 없이 T1~T8을 재현한다.
- 개인키/펌웨어 바이너리가 저장소에 없다(`git status`/secret scan).
- 비디오는 측정 결과 없이 "충분하다"고 주장하지 않는다.
- Genesis 리서치는 오프라인 산출물로 분리되어 제품 빌드에 포함되지 않는다.
