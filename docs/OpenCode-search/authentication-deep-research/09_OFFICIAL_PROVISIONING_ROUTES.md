# 09. 공식 신원·프로비저닝 경로 조사 (P0-6)

작성: 2026-11-25 · 질문: "합법적으로 GAL 발급 수신기 신원을 받을 수 있는 경로가 존재하는가?"

## 0. 결론

| 경로 | 존재 | 실현 가능성 | 등급 |
| --- | --- | --- | --- |
| Google self-service 수신기 신원 발급 | **없음** | — | VERIFIED(부재 확인) |
| Google Android for Cars 파트너(자동차 제조사) | 있음 | 개인 프로젝트 불가 | VERIFIED |
| AAP 인증 프로그램(3PL: P3 등) | 있음, 2026-10 AAP 2.0 확대 | 제품 단위 인증, 비용·계약 필요 | VERIFIED |
| Cinemo CORE Projection | SDK 존재 | 평가 접근 미확인, 문의 발송됨 | PARTIAL |
| ART SDK / ECORE KOREA / NXP | 존재 | 조건 미확인, NXP는 i.MX 전용 | PARTIAL |
| DHU/AASDK/LIVI 공유 신원 재사용 | 기술적으로 가능 | **정책상 금지** | 금지 |
| Genesis/Hyundai 순정 신원 | **없음** | — | VERIFIED(07 문서) |

핵심: **기술적 경로는 "상용 라이선스"뿐이고, 독립·무료·자체 하드웨어 경로는 공개돼 있지 않다.**

---

## 1. Google 공개 문서가 말하는 것

### 1.1 DHU는 앱 테스트 도구다

`https://developer.android.com/training/cars/testing/dhu` (2026-11 확인):

> "The Desktop Head Unit (DHU) lets your development machine emulate an Android Auto head unit so that you can run and test Android Auto apps."

- 대상: **Android 앱 개발자**
- 목적: 앱의 AA 투영 동작 테스트
- 수신기 신원 발급·이전·재사용에 대한 언급 **없음**
- "developer mode on a mobile device"는 폰 설정이지 수신기 권한이 아니다

⇒ DHU가 동작한다는 사실은 **Google 내부 테스트 신원이 폰에 허용된다**는 뜻일 뿐,
제3자에게 그 신원을 쓸 권한을 주는 문서는 없다. 등급 VERIFIED.

### 1.2 파트너 경로

- Android for Cars는 **자동차 제조사/Tier1** 대상 파트너 관계를 안내한다.
- 공개 문서에 **수신기 SDK, 테스트 신원, 취미용 프로비저닝, 공개 파트너 신청서**가 없다.
  (pi-auto-headunit 문서도 동일 결론: "does not publish a self-service receiver SDK, test identity,
  hobbyist provisioning process, or public head-unit partner application")

등급 VERIFIED(공개 문서 범위 내 부재).

### 1.3 AAP 2.0 인증 프로그램 (2026)

P3 보도자료 (2026-10-06):
> "Google has recognized P3 as Android Auto™ Projection (AAP) 3PL Partner … accredited to certify products and solutions as compliant with the newest generation of AAP standards and protocols, **AAP 2.0**."

의미:
- 수신기 제품은 **제3자 인증 파트너를 통해 AAP 적합성 인증**을 받는 구조다.
- 이는 "신원만 받으면 끝"이 아니라 **제품·펌웨어·보안 요건 전체**를 인증하는 절차다.
- 개인 GPL 프로젝트가 이 절차를 통과할 수 있는지는 **공개 정보 없음** → UNKNOWN.

---

## 2. 상용 SDK 후보 (기존 조사 + 재확인)

| 후보 | 공개 설명 | 우리 적합성 | 미확인 |
| --- | --- | --- | --- |
| **Cinemo CORE Projection** | "platform-agnostic projection solution", Android Auto/CarPlay/CarLife, USB+무선, "all operating systems and SoC platforms" | WinCE 6.0/ARM Cortex-A8는 **명시 지원 없음** | CE 6.0 지원, 평가 신원, 가격, 재배포, GPL 경계 |
| **ART SDK** | Linux 기반 IVI SDK, 유선/무선 AA | Linux 전제 → WinCE 부적합 | 라이선스, 수신기 프로비저닝 |
| **ECORE KOREA** | Linux/Android/RTOS 인증 통합 | 자동차 SoC 중심 | 최소 물량, 비용, 소스 경계 |
| **NXP Professional Services** | 완전한 AA 솔루션 + 통합 서비스 | **i.MX 전용** → 하드웨어 교체 필요 | — |

### 2.1 Cinemo 문의 상태

- 기존 WinCE ARM 평가 문의 **발송 확인** (2026-11-23 기준).
- 답변·CE 6.0 지원·평가용 신원 제공 여부 **미확인**.
- **재발송하지 않는다** (기존 결정).

등급: PARTIAL.

### 2.2 근본적 문제

이들 SDK는 **자체 수신기 스택 전체**를 제공한다. 즉:
- 우리가 만든 CE 수신기(BearSSL, AOA, H.264)를 **대체**하거나
- 그 위에 **프로프라이어터리 레이어**를 얹어야 한다.

이는 "순정 AA를 GD13MY 펌웨어에서 직접 실행"이라는 목표와 **충돌**한다.
목표를 "GD13MY에서 AA 화면이 나온다"로 완화하면 성립할 수 있으나,
그 경우에도 WinCE 6.0/ARMv7 지원이 관건이다. 등급: HYPOTHESIS.

---

## 3. 금지된 경로 (기술적으로 가능하지만 하지 않는다)

| 경로 | 왜 금지인가 | 근거 |
| --- | --- | --- |
| DHU 2.1 인증서+키 사용 | `Android-Auto-Internal` = **Google 내부 테스트 신원 위장** | iscle 아카이브, DHU 배포물 |
| AASDK JVC Kenwood 인증서+키 | **타사(OEM) 신원 위장** | `Cryptor.cpp` |
| LIVI 공유 신원 | 동일 (AASDK 신원 재사용) | LIVI 문서 |
| 폰의 CarService 인증서 사용 | 폰 자신의 신원 도용, 폰이 거부 | AARE |
| 공개 키로 자체 서명 체인 구성 | GAL 서명이 아니므로 폰이 거부(기술적 불가) | §03 |

핵심 구분:
- **"공개돼 있다" ≠ "사용 권한이 있다"**
- **"체인 검증을 통과한다" ≠ "합법적 신원이다"**

이 구분이 본 연구의 윤리적 경계다.

---

## 4. 그럼 남는 경로는 무엇인가

실현 가능성 순으로:

### 경로 1 — 상용 SDK 라이선스 (조건부)
- Cinemo/ART/ECORE 중 하나가 **WinCE 6.0 또는 ARMv7 Linux**를 지원하고,
  **평가용 신원**을 제공하며, **GPL 앱과 분리 배포**가 가능해야 한다.
- 현재 미확인. 답변 대기.

### 경로 2 — Google 파트너십 (사실상 불가)
- 개인/취미 프로젝트가 자동차 제조사 파트너가 되는 것은 현실적이지 않다.
- 다만 "제품"이 아니라 "연구/평가" 목적의 예외가 있는지는 **공개 정보 없음**.

### 경로 3 — 목표 재정의 (가장 현실적)
- "순정 AA 앱 + 순정 폰"을 포기하고,
  **자체 폰 앱/프록시**(AARE 방식)로 GD13MY에 화면을 띄운다.
- 이 경우 GAL 신원이 **불필요**하다.
- 단, 사용자가 요구한 "폰 측 앱 없음" 조건과 충돌한다.

### 경로 4 — 프로젝트 중단 (정직한 종료)
- 위 세 경로가 모두 막히면, 오류 07은 **해결 불가**로 문서화하고
  재현 가능한 실패 기록을 남긴다.
- 이는 실패가 아니라 **경계의 확정**이다.

---

## 5. 판정

1. **공식 self-service 신원 발급은 존재하지 않는다.** (VERIFIED)
2. 공식 경로는 **제품 인증 프로그램**(AAP 2.0, 3PL)이며, 개인 프로젝트에 열려 있다는 증거가 없다. (VERIFIED 부재 / UNKNOWN 가능성)
3. 상용 SDK는 존재하지만 **WinCE 6.0 지원과 평가 신원 제공이 미확인**이다. (PARTIAL)
4. 공유 신원 재사용은 **기술적으로 가능하나 정책상 금지**다. (확정)
5. 따라서 현재 시점의 정직한 상태는 **"신원 확보 대기(blocked)"**이며,
   이를 성공 확률로 표현하지 않는다.
