# OpenCode 조사 — Genesis Premium Gen2 / GD13MY

작성일: 2026-11-24
이 디렉터리는 기존 DeepSeek/ChatGPT/Antigravity 조사를 1차 자료로 교차검증한 결과를 담는다. 문서 번호는 Antigravity의 01~08 + `EVIDENCE_VERIFICATION.md` 뒤를 이어 10부터 시작한다.

## 읽는 순서

1. `FINAL_HANDOFF.md` — 결론/다음 작업/리스크
2. `10_EXISTING_RESEARCH_CROSS_VALIDATION.md` — 기존 주장의 등급 재분류
3. `12_PUBLIC_CERTIFICATE_COMPARISON.md` — 인증서 실측 비교
4. `13_ERROR07_EXTERNAL_CASE_ANALYSIS.md` — 에러 07 5분류
5. `11_OPEN_SOURCE_IMPLEMENTATION_COMPARISON.md` — OSS 소스 비교
6. `14_OMAP3530_ACCELERATION_RESEARCH.md` — GD13MY 영상 가속
7. `15_CODEX_IMPLEMENTATION_RECOMMENDATIONS.md` — 구현 티켓

## 문서 목록

| 문서 | 내용 |
| --- | --- |
| `10_EXISTING_RESEARCH_CROSS_VALIDATION.md` | DeepSeek/ChatGPT/Antigravity 주장의 확인/기각/미확인 분류 |
| `11_OPEN_SOURCE_IMPLEMENTATION_COMPARISON.md` | aasdk, open-headunit, pi-auto, AARE, LIVI, DHU의 TLS/인증서 처리 |
| `12_PUBLIC_CERTIFICATE_COMPARISON.md` | DHU/AASDK/phone/GAL 인증서 메타데이터와 신뢰 체인 |
| `13_ERROR07_EXTERNAL_CASE_ANALYSIS.md` | A~E 원인 분류, Jaycar/WebAA/GitHub 사례 |
| `14_OMAP3530_ACCELERATION_RESEARCH.md` | GD13MY OMAP BSP, DSP/VideoDev 증거, 디코드 옵션 |
| `15_CODEX_IMPLEMENTATION_RECOMMENDATIONS.md` | P0~P3 티켓, 수용 기준, 테스트 매트릭스 |
| `PROGRESS.md` | 작업/검증 상태/막힌 지점 |
| `FINAL_HANDOFF.md` | 최종 요약과 인수인계 |

## 증거 등급

- `[확인됨]` — 공개 1차 자료 또는 실측으로 재현 가능
- `[미검증 가설]` — 근거 부족
- `[외부 신규 검증]` — 이번 조사에서 새로 확보한 외부 증거
- `[제네시스 펌웨어 직접 증거]` — G80/DHPE 펌웨어에서 직접 확인
- `[GD13MY 적용 가능]` — i30 WinCE/ARM에 적용 가능
- `[GPT 분석 필요]` — 추가 모델/프로토콜 분석 필요
- `[Codex 구현 필요]` — 코드/테스트 작업 필요

## 주의

- 공개 인증서는 식별/테스트 벡터로만 사용했다. 개인키는 사용하지 않았고 저장소에 커밋하지 않았다.
- `G:` 펌웨어는 읽기 전용으로만 다뤘다.
- `pi-auto-headunit`의 세 정책 문서는 실제로 존재하며, 11번 문서에 해시와 원문 근거를 남겼다.
