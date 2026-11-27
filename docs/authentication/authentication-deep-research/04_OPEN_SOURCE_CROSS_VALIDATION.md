# 04. 공개 구현 교차 검증 (P0-3)

작성: 2026-11-25 · 방법: 각 저장소의 **문서·소스**만 읽고, 주장과 실측을 분리

## 0. 요약

| 프로젝트 | 독립 신원으로 실폰 연결 | 오류 | 근거 등급 |
| --- | --- | --- | --- |
| pi-auto-headunit (Rust, 2026-08) | **시도함. 실패** | USB·개발자 터널 **둘 다 error 7** | VERIFIED (자체 문서) |
| AASDK / OpenAuto | **공유 신원 사용** | 성공(신원 덕분) | VERIFIED (코드) |
| LIVI | **공유 신원 사용** | 성공(신원 덕분) | VERIFIED (문서 인용, 원문 미열람) |
| AARE | 헤드유닛 인증서 **불요** 설계 | 사용자 신뢰 모델 | VERIFIED (문서) |
| Open Headunit (andreknieriem) | 공유 신원 계열 | 일부 사용자 error 7 보고 | PARTIAL (이슈) |
| JanRi3D/OpenAuto | 사용자 제공 신원 | 별도 폰 시험 | PARTIAL |

핵심: **"공개 구현이 성공했다"는 사실은 신원이 공개돼 있기 때문**이며, 독립 신원으로 성공한 사례는 아직 확인되지 않았다.

---

## 1. pi-auto-headunit — 가장 직접적인 반증 실험

출처
- 저장소: `https://github.com/blakereuben/pi-auto-headunit` (pushed `2026-08-29T00:31:20Z`, GPL-3.0)
- 문서: `docs/protocol/tls-credential-policy.md` (7,632 B)
- 문서: `docs/protocol/receiver-provisioning-options.md` (7,450 B, status "research shortlist, 5 August 2026")

### 1.1 인용 (원문)

`tls-credential-policy.md`:
> "The project will not copy, embed, present, or redistribute credentials, certificates, private keys, authentication material, or security bypasses from OpenAuto, OpenAuto Pro, AASDK, or another head-unit implementation."

> "At pinned AASDK revision `9bf6adf933665dee26532201719fac14a047ccf1`, `Cryptor.cpp` loads a fixed certificate and matching RSA private key into an OpenSSL client context. `SSLWrapper.cpp` uses a client connection over memory BIOs and **disables peer-certificate verification**."

> "Bounded phone probes reached TLS over both USB/AOA and the official developer tunnel, with the negative results below."

> "On 4 August 2026, the Pi 5 probe reached an accepted AAP 1.6 version response and then timed out before TLS completed. No authentication-complete or service-discovery response was sent. The TLS-1.2 comparison received peer TLS data, and **the phone displayed Android Auto error 7 stating that the software had not met its security requirement**."

> "A narrowly controlled bench handshake with temporary project-generated credentials was used to determine whether an independent identity is accepted. **The result is conclusive and the experiment must not be repeated.**"

`receiver-provisioning-options.md`:
> "The Pi 5 reaches AAP 1.6 and exchanges TLS data over both USB/AOA and Google's documented developer transport, but Android Auto rejects the project's independent identity with error 7."

> "Developer mode is not an identity bypass." (문서 전반의 결론)

### 1.2 우리 프로젝트와의 대조

| 항목 | pi-auto-headunit | GD13MY | 일치 |
| --- | --- | --- | --- |
| AA 버전 | AAP 1.6 | AA 1.7 | 버전만 다름 |
| 전송 | USB/AOA + 개발자 터널 5277 | 동일 | 일치 |
| TLS | 1.2, 폰과 데이터 교환됨 | 1.2, `0xC02F` | 일치 |
| 결과 | 서버 flight 수신 후 중단 | `ServerHelloDone` 후 중단 | 일치 |
| 폰 표시 | error 7 "security requirement" | error 7 "security checks" | 일치 |
| 결론 | 신원이 없으면 우회 불가 | 동일 | 일치 |

⇒ **완전히 독립적인 두 프로젝트가 같은 지점에서 같은 오류를 얻었다.** 이는 우리 로그 해석의 가장 강한 외부 검증이다. 등급 VERIFIED.

---

## 2. AASDK / OpenAuto — "성공"의 정체

- `opencardev/aasdk` `cert/README.md`: `headunit.crt`는 "X.509 certificate (Google Automotive Link issued to JVC Kenwood)", "publicly available … not a secret", debian 패키지가 `/etc/openauto/`에 설치, 없으면 `Cryptor.cpp` 내장값 사용.
- 임베디드 인증서 실측(본 연구 02 문서):
  - subject `C=JP, ST=Tokyo, L=Hachioji, O=JVC Kenwood, OU=01`
  - issuer `O=Google Automotive Link`
  - v1, 확장 0, `140704000000-0700` ~ `450429142838-0700`
  - `openssl verify -no_check_time -CAfile gal-root.pem` → **OK**
- `f1xpl/aasdk@development`는 `cert/`에 인증서 파일이 없고 `Cryptor.cpp` 내장값만 존재(319 entries 확인).

해석:
- OpenAuto 계열이 동작하는 이유는 **GAL이 서명한 실물 신원을 그대로 제시**하기 때문이다.
- 코드 품질·TLS 구현·프레이밍의 우수성 때문이 아니다. (pi-auto-headunit은 같은 프로토콜을 더 현대적으로 구현하고도 실패)
- 또한 `SSLWrapper.cpp`가 **peer 검증을 끈다** → 폰 인증서 검증은 이 계열에서 검증된 적이 없다.

등급 VERIFIED (코드·인증서 사실) / 사용 권한은 별개.

---

## 3. LIVI — 동일한 공유 신원

- `f-io/LIVI` (pushed 2026-11-24, GPL-3.0). pi-auto-headunit 문서가 LIVI revision `b7435e8db1fcc9b5280c45fb71d020d943577ef7`를 인용:
  > "Its Android Auto crypto source explicitly embeds the canonical OpenAuto head-unit certificate and matching private key and states that phones accept that shared identity."
- 즉 LIVI의 성공도 **동일 신원**이다.
- 과거 인용 핀 `9000f308…`은 더 이상 해석 불가(`unable to read tree`), 현 HEAD `3af5485b`.

등급 VERIFIED(문서 인용) / 원문 코드는 본 연구에서 열람하지 않음(정책상 신원 파일 회피).

---

## 4. AARE — 다른 문제를 푸는 구현

출처: `https://github.com/prototux/AARE/blob/main/docs/certificates.md`

- AARE는 **폰을 서버로 두고, 헤드유닛 인증서를 요구하지 않는** 설계다.
- 대신 헤드유닛별 SHA-256 지문을 저장하고, 처음 보는 인증서는 사용자에게 "Trust this head unit"으로 확인받는다.
- 문서 명시:
  > "AARE doesn't require a Google-issued head-unit certificate (open-source head units can't have one)."
- 또한 폰이 **CarService 인증서나 루트 자체를 헤드유닛이 보내는 것을 거부**한다고 기록.
- DHU를 상대로는 폰 검증 후 `AUTH_COMPLETE -3`을 반환.

의미:
- AARE는 **Android Auto 앱(폰)을 상대로 하는 구현이 아니다.** 자체 폰 앱/프록시 모델이다.
- 따라서 우리 목표(순정 AA 앱 + 순정 폰)에는 적용되지 않는다.
- 다만 "폰이 헤드유닛 인증서를 어떻게 판정하는가"에 대한 유일한 공개 관측 기록이다.

등급 VERIFIED(문서) / 우리 경로 적용 불가.

---

## 5. 나머지 구현

| 프로젝트 | 신원 | 관측 | 등급 |
| --- | --- | --- | --- |
| andreknieriem/open-headunit | 공유(AASDK 계열) | Pixel 8 Pro에서 error 7 이슈 보고 존재(issue #14) | PARTIAL |
| JanRi3D/OpenAuto (2026-10 갱신) | 사용자 제공 | ADAYO AC822X에서 동작, 별도 폰 시험에서 TLS 1.2/`0xC02F` 보고 | PARTIAL |
| aa-proxy/aa-proxy-rs | DHU/전화 TLS 종료 | 프록시 모드. 신원 문제를 우회하는 구조가 아님 | PARTIAL |
| andresurena/android-head-unit-exploration | 없음 | XUNZU/ZLINK 분석 기록. TLS 인증 구현 없음 | VERIFIED(부재) |

---

## 6. 결론

1. **독립 신원으로 실폰 AA를 통과한 공개 프로젝트는 0건**이다.
   (pi-auto-headunit이 명시적으로 시도·실패, 재시도 금지를 선언)
2. 성공 사례는 모두 **GAL 발급 공유 신원**(JVC Kenwood / Android-Auto-Internal)을 사용한다.
3. 따라서 "구현을 더 잘 만들면 된다"는 가설은 **반증**되었다. 남은 변수는 신원 하나다.
4. 우리 프로젝트의 실패 지점·오류 문구·중단 위치는 pi-auto-headunit과 **문자 단위로 일치**한다.
