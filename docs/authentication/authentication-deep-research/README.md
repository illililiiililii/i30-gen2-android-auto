# Android Auto 인증 심층 연구 (GD13MY)

작성: 2026-11-25 · 범위: 헤드유닛 인증서 · TLS 상호 인증 · GAL 신뢰 체인 · 신원 프로비저닝
제외: DSP, 영상 디코딩, 오디오, UI, 에뮬레이터 최적화

## 목적

GD13MY(Hyundai i30 GD 2013, Windows CE 6.0, ARM Cortex-A8, BearSSL 0.6)에서
**순정 Google Android Auto**를 폰 측 앱·루트·외부 수신기·동글 없이 실행하려 할 때
발생하는 오류 07의 정확한 원인과, 가능한 경로를 증거 기반으로 확정한다.

## 핵심 결론 (한 줄)

> 오류 07은 **폰이 헤드유닛의 클라이언트 인증서 체인을 검증하는 단계**에서 발생하며,
> 원인은 **GAL(Google Automotive Link) root로 이어지지 않는 신원**이다.
> 코드·TLS 구현·전송에는 문제가 없다. 해결은 **신원 확보**이며, 공개된 공식 경로는 없다.

## 문서 목록

| # | 문서 | 내용 |
| --- | --- | --- |
| 01 | [TLS 실패 지점 추적](01_TLS_FAILURE_TRACE.md) | 실폰 로그로 단계 확정, 기존 "alert 48" 서술 정정 |
| 02 | [헤드유닛 인증서 심층 분석](02_HEADUNIT_CERTIFICATE_DEEP_ANALYSIS.md) | DHU/AASDK/폰/루트 4종 실측, v1·확장 가설 반증 |
| 03 | [GAL 신뢰 체인 검증](03_GAL_TRUST_CHAIN_VERIFICATION.md) | 체인 모델, 폰이 보는 것/안 보는 것 |
| 04 | [공개 구현 교차 검증](04_OPEN_SOURCE_CROSS_VALIDATION.md) | pi-auto-headunit 등 독립 재현 |
| 05 | [외부 오류 07 재분석](05_ERROR07_EXTERNAL_CASE_REANALYSIS.md) | A~E 원인 분류, Jaycar/WebAA |
| 06 | [Google 정책 가설 검증](06_GOOGLE_POLICY_HYPOTHESIS.md) | 2025 파동, AAP 2.0, 반증 논리 |
| 07 | [순정 펌웨어 신원 탐색](07_GENESIS_FIRMWARE_IDENTITY_SEARCH.md) | `G:\` 전수 스캔 결과 |
| 08 | [수신기 코드 리뷰](08_RECEIVER_CODE_REVIEW.md) | `ce_aa_tls.c` 수정 지점 2개 |
| 09 | [공식 프로비저닝 경로](09_OFFICIAL_PROVISIONING_ROUTES.md) | Google/3PL/상용 SDK |
| 10 | [실현 경로 매트릭스](10_FEASIBILITY_MATRIX.md) | 의사결정 트리 |
| 11 | [다음 시험 계획](11_NEXT_TEST_PLAN.md) | 쿼터 리셋 후 1시간 시험 |
| 12 | [증거 색인](12_EVIDENCE_INDEX.md) | SHA-256, 재현 명령, 판정 원장 |

## 읽는 순서

- **처음 읽는 사람**: 이 문서 → 01 → 03 → `FINAL_HANDOFF.md`
- **코드 작업자**: 08 → 11
- **의사결정자**: 09 → 10 → `FINAL_HANDOFF.md`
- **검증자**: 12 (모든 수치와 해시)

## 후속 연구 (2026-11-25)

이 보고서의 결론 일부는 후속 세션에서 정정되었다. 특히:

- 실폰 실패의 직접 원인은 **GAL 발급 헤드유닛 인증서가 `-0700` UTCTime 때문에
  BearSSL에서 로드되지 않아 자체 서명 신원으로 시험된 것**이다.
- **`Google-Android-Reference`** (GAL 발급, `Z` 시간) 쌍이 공개되어 있으며
  현재 코드로 로드된다.

→ [`../authentication-followup/`](../authentication-followup/)

## 원칙

- 모든 주장에 `VERIFIED` / `PARTIAL` / `HYPOTHESIS` / `UNKNOWN` / `FAILED` 등급을 붙였다.
- 로그에 없는 것은 추정으로 채우지 않았다.
- 개인키·비공개 자격증명은 열람·복사·사용하지 않았다.
- DHU/AASDK/LIVI의 공유 신원은 **기술적으로 가능하나 정책상 금지**로 명시했다.
- `G:\` 원본과 GD13MY 제품 코드는 수정하지 않았다.
