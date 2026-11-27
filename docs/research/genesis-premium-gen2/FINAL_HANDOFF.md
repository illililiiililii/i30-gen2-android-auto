# FINAL HANDOFF — OpenCode 조사 (2026-11-24)

## 0. 한 문단 요약

이 프로젝트의 GD13MY 에러 07은 **HU 클라이언트 인증서가 phone의 신뢰 앵커(`O=Google Automotive Link`)로 이어지지 않아서** 발생한다. TLS 1.2/`0xC02F`는 이미 정상이고, 인증서 만료도 아니다. Phone은 HU의 조직명을 구분하지 않고 GAL 체인만 보므로, DHU의 내부 테스트 인증서도 통과한다. 따라서 기술적 해법은 "TLS 코드 수정"이 아니라 **GAL 체인 신원 확보**이며, 이는 코드로 해결할 수 없다. 동시에 2025~2026년에는 Google 정책 변경으로 기존에 동작하던 HU가 에러 07로 깨지는 사례가 있으므로, 인증/TLS 계층은 교체 가능하게 설계해야 한다. Genesis G80(DHPE) 펌웨어는 여전히 암호화 컨테이너 안에 있어 실제 AA 리시버 바이너리를 특정하지 못했고, Antigravity의 관련 주장은 대부분 미확인이다.

---

## 1. 핵심 결론

1. **에러 07 = 체인 미신뢰(A).** 근거: `BR_ERR_X509_NOT_TRUSTED`, TLS alert 48. TLS 버전/cipher 문제 아님.
2. **만료 아님.** DHU 2048, AASDK 2045, phone leaf 2027. 2026년 현재 모두 유효.
3. **Phone은 GAL 체인만 본다.** DHU(`Android-Auto-Internal`)도, JVC Kenwood leaf도 통과. 차량별 고유성 요구 없음.
4. **공유 신원은 기술적으로 통과하지만 사용 금지.** LIVI/OpenAuto가 그 예. 이 프로젝트는 윤리/법적으로 배제.
5. **에러 07은 하나가 아니다.** A(체인), B(정책 변경), C(만료), D(TLS 스택), E(오진)로 분류해야 한다. Jaycar(2025-09)는 B, open-headunit #66은 D, #252는 E.
6. **wolfSSL 교체 불필요.** BearSSL 0.6 유지.
7. **GD13MY는 OMAP3430/3530 계열**이고 DSP/VideoDev 디코드 경로가 있다. 단 H.264 지원 여부는 미확인.
8. **Genesis 컨테이너는 아직 복호화 불가.** 헤더는 평문 RSA 블록이 아니라 암호화 영역이다. 기존 스크립트의 "RSA 키 추출" 가정은 틀렸다. 다만 G80 HU 사용자공간은 i386 ELF로 확인됐고, `APPNAVI`가 MOST 기반 IBOX 모듈을 제어한다.
9. **`pi-auto-headunit`의 세 문서는 실제로 존재한다.** 독립 신원 거부, provisioning 부재를 정직하게 기록.
10. **확률 수치는 폐기.** 근거가 없다.

---

## 2. 이전 연구 대비 변경점

| 이전 | 이후 |
| --- | --- |
| "에러 07 = 체인" (때로 단정) | 체인/정책/만료/TLS/오진 5분류 |
| DHU 버전별 인증서 차이 | 2.1과 latest는 동일 파일 |
| Genesis keystore에 GAL 체인 | 미확인(디코드 실패) |
| IBOX가 AOA 처리 | 미확인, GD13MY LibUSB는 미디어 전용 |
| Genesis AA는 OpenSSL/mbedtls | 미확인(복호화 도구와 혼동) |
| Intel GMA 하드웨어 디코드 | 미확인(G80), GD13MY와 무관 |
| h264bsd 30fps 충분 | 측정 전 미확정 |
| 성공 확률 X% | 폐기, 차단 요인/작업으로 분해 |
| "인증서 무시" 우회 | 기각 |

---

## 3. 지금 해야 할 일 (순서대로)

1. **인증 계층 진단 정리** — `TlsDiagnostics` + 에러 07 분류 로그. (Codex, P0)
2. **HU 신원 공급자 분리** — `IHuIdentityProvider`, provisioning 없으면 명시적 실패. (Codex, P0)
3. **phone-role 테스트 하네스** — 차량 없이 T1~T8 검증. (Codex, P1)
4. **AAP-over-TLS 프레이밍/`AUTH_COMPLETE`** — 실제 연결 경로 완성. (Codex, P1)
5. **오디오/입력** — 사용자 가치가 큰 순서. (Codex, P2)
6. **Genesis 복호화 리서치** — 오프라인, 제품 코드와 분리. (Codex/GPT, P3)
7. **비디오 측정** — 기존 플레이어로 480p/720p 재생부터. (실기, P3)

---

## 4. 리스크

| 리스크 | 가능성 | 영향 | 대응 |
| --- | --- | --- | --- |
| GAL 체인 신원 확보 실패 | 높음 | 에러 07 영구 | provisioning 파트너 조사, 제품 로드맵 재검토 |
| Google 정책 변경(B) | 중간 | 기존 동작 무효화 | 인증/TLS 모듈 교체 가능하게, Play Services 모니터링 |
| Phone leaf 2027 만료 | 중간 | 일시적 연결 장애 | Google 업데이트 관찰, HU는 영향 없음 |
| Genesis 복호화 실패 | 중간 | G80 리시버 미확인 | 다른 경로(업데이트 서버, 진단 로그) 조사 |
| OMAP 비디오 미지원 | 중간 | AA 비디오 불가 | 480p/소프트웨어 디코드/오디오 우선 |
| WinCE USB/AOA 제약 | 중간 | 연결 자체 불가 | 별도 스파이크, 대체 보드 검토 |

---

## 5. 절대 하지 말 것

- DHU/AASDK/LIVI/OpenAuto 인증서+개인키를 제품/저장소에 넣지 않는다.
- 인증서 검증을 끄거나 "우회 플래그"를 찾지 않는다.
- `G:` 펌웨어를 수정/플래시하지 않는다.
- 복호화된 바이너리/키를 커밋하지 않는다.
- 측정 없이 "30fps 충분"이라고 주장하지 않는다.

---

## 6. 증거 위치

- 문서: `docs/OpenCode-search/genesis-premium-gen2/`
- 임시 증거: `%TEMP%\opencode\aa-research\`
  - `dhu21_cert.pem`, `dhu21_meta.json`
  - `aasdk_headunit.crt`, `aasdk_SSLWrapper.cpp`
  - `aare_certificates.md`
  - `piauto_*.md`
  - `headunit_*.kt`
  - `lgu_*.txt` (디스어셈블)
- 실측 로그: `build/gd13my-ce-projection/phone-tls-public.json`
- 펌웨어: `firmware/extracted/GD13MY/` (읽기 전용)

---

## 7. 미해결 질문

1. GAL root의 정확한 CA 속성/KeyUsage는?
2. Phone은 HU 인증서에서 DN/EKU를 정말 보지 않는가?
3. Google의 공식 receiver provisioning 경로는 존재하는가? (현재 공개 자료 없음)
4. Genesis IBOX의 LGE 컨테이너 키는 기기 고유값인가 빌드 상수인가?
5. GD13MY VideoDev가 H.264 어느 프로파일까지 지원하는가?
6. AAP 비디오 해상도를 HU가 낮춰 협상할 수 있는가?

---

## 8. 인수인계 메모

- 이 문서는 "정답"이 아니라 **증거 등급이 붙은 현재 상태**다. `[미검증 가설]`을 사실처럼 인용하지 말 것.
- 특히 Antigravity의 Genesis 관련 서술은 `EVIDENCE_VERIFICATION.md`의 미확인 목록과 함께 읽어야 한다.
- 외부 사례의 "error 7 해결"은 대부분 우리 원인(A)과 다르다. 13번 문서의 분류표를 먼저 볼 것.
- 새 증거가 나오면 `PROGRESS.md`의 검증 상태표를 갱신하고, 문서 10/12/13의 해당 등급을 승격/기각할 것.
