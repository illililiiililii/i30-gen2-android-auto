# 05. 외부 오류 07 사례 재분석 (P0-5)

작성: 2026-11-25 · 목적: "같은 오류 07"을 원인별로 분리하고, 우리 사례의 위치를 확정

## 0. 먼저 정정할 것

`docs/OpenCode-search/genesis-premium-gen2/13_ERROR07_EXTERNAL_CASE_ANALYSIS.md`의 두 서술은 근거가 없다.

| 기존 서술 | 실제 |
| --- | --- |
| "이 프로젝트 GD13MY 사례는 `BR_ERR_X509_NOT_TRUSTED` + alert 48" (§1 표 A행, §2 표 #9) | **둘 다 관측된 적 없음.** 실제는 폰 측 `CertPathValidatorException` + USB 읽기 타임아웃 |
| "A = HU 체인 미신뢰, 대표 관측 alert 48" | alert 48은 **폰→HU 방향**의 이론적 표시이며 이 프로젝트 로그에 없음 |

`BR_ERR_X509_NOT_TRUSTED`는 **수신기가 peer(폰) 인증서를 거부**할 때의 BearSSL 로컬 오류다.
우리 실패는 **폰이 우리를 거부**하는 반대 방향이므로 애초에 이 코드가 나올 수 없다.
(상세: `01_TLS_FAILURE_TRACE.md` §4)

---

## 1. 원인 분류 (수정판)

| 코드 | 원인 | 판별 신호 | GD13MY 해당 |
| --- | --- | --- | --- |
| **A** | HU 체인이 phone trust anchor로 이어지지 않음 | 폰 로그 `Trust anchor for certification path not found`, `verifyCertificateChain` | **해당 (확정)** |
| **B** | Google phone/Play Services 정책·검증 변경 | 어제까지 되던 HU가 갑자기, 동시기 다수, 벤더 펌웨어로 해결 | **부분 해당 가능** (V1.7 시절 정상이었음) |
| **C** | 인증서 만료/시계 오류 | `expired` 계열, notAfter 경과 | 아님 (HU 2045/2048) |
| **D** | TLS 스택/프로바이더 호환 | 핸드셰이크 초반, 특정 Android 버전만 | 아님 (DHU 동일 조건 정상) |
| **E** | 오진 (USB 권한·앱 버전·코덱) | TLS alert 자체가 없고 설정 변경으로 해결 | 아님 (폰 로그에 TLS 예외 존재) |

중요: A와 B는 **배타적이지 않다.** B(정책 강화)가 A(기존 신원 무효화)를 유발할 수 있다.

---

## 2. 사례표 (검증 등급 포함)

| # | 사례 | 시기 | 관측 | 원인 | 등급 | 출처 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Jaycar QM3793 | 2025-09-24 | "Communication Error 7", "The software does not pass Android security checks" | **B** (폰 업데이트 → HU 펌웨어 `ISP_UPDT.BIN` 필요) | VERIFIED(공지 원문) | `https://help.jaycar.com.au/hc/en-us/articles/50355885912217` |
| 2 | Google 지원 포럼 25.34.34 | 2025-09 | 특정 Play Services 버전 이후 상용 HU 다발 | **B** | PARTIAL (본문 JS 렌더링) | `https://support.google.com/androidauto/thread/371804348` |
| 3 | Google 지원 포럼 (2) | 2025-09 | 동일 계열 | **B** | PARTIAL | `https://support.google.com/androidauto/thread/369324198` |
| 4 | WebAA | 2025~2026 | "Latest Google Play Service update breaks WebAA … options are limited" | **B** | PARTIAL(배포자 진술) | WebAA 배포 페이지 |
| 5 | pi-auto-headunit | 2026-08-04 | 독립 신원, USB·개발자 터널 모두 error 7 | **A** | VERIFIED(자체 문서) | `docs/protocol/tls-credential-policy.md` |
| 6 | open-headunit #14 | 2025-12-30 | "could not start transport" 반복 | A/E 혼재 | PARTIAL | GitHub issue |
| 7 | open-headunit #66 | 2026-01-23 | 구버전 Android에서 error 7, Conscrypt로 해결 | **D** | PARTIAL | PR #66 |
| 8 | open-headunit #252 | 2026-03-18 | 사용자는 error 7 주장, 실제 설정 문제 | **E** | PARTIAL | issue #252 |
| 9 | AASDK/OpenAuto | 2018~ | 정상 | GAL 공유 신원 | VERIFIED | `Cryptor.cpp` |
| 10 | Google DHU | 현재 | 정상 | GAL 내부 테스트 신원 | VERIFIED | DHU 로그 |
| 11 | **GD13MY (이 프로젝트)** | 2026-11 | `ServerHelloDone` 후 폰이 체인 거부 | **A** (+B 가능성) | VERIFIED(로그) | `live-phone-usb-trust-android.log` |

---

## 3. Jaycar 사례가 우리에게 주는 실제 정보

원문 (인용):
> "A small number of Android phones have recently received updates from Google that may impact the phone's ability to connect … The affected phones will have a message when connected stating 'Communication Error 7' and 'The software does not pass Android security checks'."

해석상 한계:
1. Jaycar는 **원인을 공개하지 않았다.** "Google phone update"만 말한다.
2. 해결책이 **HU 펌웨어 20MB 업데이트**라는 사실만 확인된다.
3. 그 펌웨어가 ① 새 인증서를 넣었는지 ② TLS 스택을 바꿨는지 ③ 버전 협상을 바꿨는지 **알 수 없다.**

따라서 Jaycar 사례를 "인증서 정책 변경"의 증거로 쓰는 것은 **과잉 해석**이다.
우리 프로젝트에서 확인 가능한 것은 "폰 쪽 검증이 HU 소프트웨어 교체 없이는 통과하지 않는다"는 행동 패턴뿐이다.

등급: VERIFIED(공지 문구) / HYPOTHESIS(원인 메커니즘)

---

## 4. 왜 우리 사례는 B 단독이 아닌가

"V1.7 시절에는 정상 동작했다"는 프로젝트 기록이 있다면 B를 의심할 수 있다. 그러나:

- V1.7 정상 동작 기록은 **DHU(공식 신원)** 또는 **자체 가상 폰**과의 시험이며,
  **실폰 + 우리 신원**으로 성공한 기록은 없다.
- 즉 "예전엔 됐는데 지금 안 된다"는 비교 대상이 **서로 다른 신원**이다.

⇒ 현재 오류 07의 **필요충분 원인은 A**다. B는 "A를 더 엄격하게 만든 외부 요인"으로 남는다.
(B가 없었다면 우리 신원이 통과했을 가능성은 **별도 증거 없음** = UNKNOWN)

---

## 5. 2026년 정책 동향 (확인된 것만)

| 항목 | 사실 | 등급 |
| --- | --- | --- |
| AAP 2.0 인증 프로그램 | P3가 2026-10-06 Google AAP 2.0 **3PL 인증 파트너**로 인증. "newest generation of AAP standards and protocols, AAP 2.0" | VERIFIED (`p3-group.com` 보도자료) |
| Google 공개 문서 | DHU는 **앱 개발자용 테스트 도구**이며 수신기 신원 발급을 설명하지 않음 | VERIFIED (`developer.android.com/training/cars/testing/dhu`) |
| 공개 self-service 수신기 신원 | 존재 확인 안 됨 | UNKNOWN(부재 확인 범위 내) |
| AA 앱 버전별 leaf 회전 | 17.7 → 2026-12-31, 18.0 → 2027-02-17 | VERIFIED (AARE 문서 vs 실캡처) |

AAP 2.0의 등장은 **인증 요건이 세대 교체 중**임을 뜻한다. 이는 우리가 확보해야 할 것이
"아무 GAL 서명 인증서"가 아니라 **현행 AAP 세대에 유효한 프로비저닝**임을 시사한다. (HYPOTHESIS)

---

## 6. 결론

1. 오류 07은 단일 원인이 아니다. 최소 A~E 5종이 같은 문구로 표시된다.
2. 우리 사례는 **A(체인 미신뢰)**로 확정됐고, 로그 증거는 폰 측 Conscrypt 예외 한 건이다.
3. 외부 사례 중 우리와 **동일 조건**인 것은 pi-auto-headunit 하나뿐이며, 결과도 동일하다.
4. Jaycar/WebAA 사례는 "폰 정책이 HU 소프트웨어를 무효화할 수 있다"는 **리스크 증거**이지,
   우리 실패의 직접 원인 증거가 아니다.
5. alert 48 / `BR_ERR_X509_NOT_TRUSTED`를 우리 근거로 인용하지 않는다.
