# 05 — 공식 개발/평가 신원 경로

작성: 2026-11-25 · 등급: **VERIFIED** (공개 자료 기준)
목적: Cinemo/ART/ECORE/NXP 외에, 개인 또는 소규모 팀이 접근 가능한 공식 경로가 있는지 확인.

---

## 1. AAP 2.0 Certification 2.0 — 2026년 1월부터 의무화

공개 자료:

- P3, 2026-10-06: <https://p3-group.com/Insights/google-expands-p3s-3pl-accreditation-to-embrace-next-gen-android-autoprojection-aap-technology-certification/>
- CIeNET: <https://cienet.com/news-insights/cienet-android-auto-projection-3pl-certification.html>
- Ubikon: <https://ubikon.com/products-and-services/android-auto-certification>
- HARMAN: <https://car.harman.com/insights/blog/harman-automotive-engineering-services-labs-become-google-accredited-for-aaos-and-gas-certification>

핵심:

> "As of January 2026, Google requires all new vehicle programs launching in 2026 or later
> to complete Certification 2.0 before shipping."

> "From January 2026 ... all new vehicle projects must complete Android Auto certification
> through third-party authorised labs (3PL). The old route where manufacturers ran tests
> themselves and submitted reports to Google is no longer available."

> "Manufacturers only have PCTS self-test tools ... Formal CTS-Auto testing must be
> performed by a 3PL."

### 1.1 3PL 파트너 (공개 확인)

| 파트너 | AAP 자격 | 비고 |
| --- | --- | --- |
| **P3** | AAP 3PL (2026-10-06) | AAOS 3PL (2024-10) |
| **Ubikon** | AA 3PL (2016~) | AAOS 3PL (2024) |
| **HARMAN** | AAP + GAS 3PL | 350+ 헤드유닛 인증 |
| **CIeNET** | AAP 2.0 3PL | AAOS/GAS 3PL (2024-08) |

### 1.2 절차 (HARMAN 공개 설명)

1. OEM/Tier-1과 3PL 간 NDA·인증 계약.
2. Pre-certification 분석 (SOP 18~21개월 전 시작 권장).
3. 헤드유닛/소프트웨어를 3PL 랩에 전달 + xTS 자체 결과.
4. 3PL이 CTS-Auto/PCTS 전체 실행.
5. 3PL이 Google에 결과 제출, Google이 검토·승인·인증서 발급.

### 1.3 개인 접근성

- **불가**. OEM/Tier-1 제품 프로그램이 전제이며, NDA·계약·양산 일정이 필요하다.
- 개인/취미 프로젝트를 위한 self-service 신원 발급은 **없다**.
- "developer mode"는 신원 우회가 아니다 (이전 조사에서 확인).

---

## 2. Android Studio DHU — 공식 개발/평가 신원

Google의 **Desktop Head Unit (DHU)** 은 Android Studio에 포함된 공식 헤드유닛
에뮬레이터이며, AA 통신용 **GAL 발급 인증서+키**를 운반한다.

- open-headunit 토론 #637: "extracted from the DHU in Android Studio.
  It is the official pair to communicate with Android Auto."
- 해당 쌍: `O=Google-Android-Reference`, issuer GAL, serial `0x7653`,
  2014-07-08 → 2044-07-07, **`Z` 시간**, SHA-256 `E3:23:CC:6D:...:ED:6D`.
- `open-headunit`이 이 쌍을 실제 클라이언트 신원으로 사용한다
  (`SingleKeyKeyManager` + `SslContextFactory`).

### 2.1 의미

- **공식 배포물(DHU)에서 유래한 신원**이므로, "개발/평가" 성격이 명확하다.
- 폰은 DHU를 정상 헤드유닛으로 취급한다 (DHU 기준 성공 로그 있음).
- 개인 테스트에 사용 가능한 가장 정당한 공개 경로다.

### 2.2 한계

- DHU는 Google의 개발 도구이며, 이 인증서를 **제품에 재사용**할 권리는 별도다.
- 테스트 단계 사용은 사용자 지시로 허용되지만, 커밋·배포·상용화는 하지 않는다.
- 인증서 만료(2044)는 문제 없으나, DHU 업데이트로 교체될 수 있다.

---

## 3. 기타 공식/준공식 경로

| 경로 | 내용 | 판정 |
| --- | --- | --- |
| Google AA 앱 (`gearhead`) APK | `ca.crt` + `carservice.crt` + key 운반 | **폰 역할** 신원. 헤드유닛용 아님 |
| DHU (Android Studio) | `Google-Android-Reference` 쌍 | **헤드유닛 역할**. 권장 |
| AASDK `cert/headunit.*` | JVC Kenwood GAL 발급 쌍 | 공개, `-0700` 파서 수정 필요 |
| Cinemo / ART / ECORE / NXP | 상용 SDK/평가 | 이전 조사에서 확인, 개인 접근 제한 |
| AAP 2.0 3PL | OEM/Tier-1 인증 | 개인 불가 |

---

## 4. 판정

| 주장 | 등급 |
| --- | --- |
| AAP 2.0 Certification 2.0이 2026-01부터 의무 | **VERIFIED** |
| 3PL 없이는 신규 양산 불가 | **VERIFIED** |
| 개인용 self-service 신원 발급 없음 | **VERIFIED** |
| DHU가 공식 GAL 발급 헤드유닛 쌍을 운반 | **VERIFIED** (인증서 실체) / **PARTIAL** (DHU 유래 진술) | open-headunit 원문 + 실측 |
| DHU 쌍이 i30 폰에서 통과 | **PARTIAL** (라이브 미시험) |

---

## 5. 결론

- **테스트 단계**: DHU 유래 `Google-Android-Reference` 쌍을 사용한다.
  현재 펌웨어가 수정 없이 로드하며, open-headunit이 필드에서 사용 중이다.
- **양산/배포**: AAP 2.0 3PL 인증이 유일한 공식 경로이며, 개인은 접근할 수 없다.
  따라서 이 프로젝트는 **테스트/연구 범위**를 벗어나지 않는다.
