# PROGRESS — Android Auto 인증 심층 연구

최종 갱신: 2026-11-25

## 상태

| 항목 | 상태 |
| --- | --- |
| P0-1 실패 지점 확정 | 완료 (VERIFIED) |
| P0-2 인증서 실측 | 완료 (VERIFIED) |
| P0-3 공개 구현 교차 검증 | 완료 (VERIFIED) |
| P0-4 순정 펌웨어 신원 탐색 | 완료 (평문 VERIFIED / 암호문 UNKNOWN) |
| P0-5 정책·외부 사례 | 완료 (현상 VERIFIED / 메커니즘 UNKNOWN) |
| P0-6 공식 경로 | 완료 (부재 VERIFIED / 상용 UNKNOWN) |
| P0-7 코드 리뷰 | 완료 (수정 지점 2개 특정) |
| 12개 산출물 | 완료 |
| 후속 실폰 시험 | 대기 (계획만 수립) |

## 산출물

```
docs/OpenCode-search/authentication-deep-research/
├─ README.md
├─ PROGRESS.md
├─ FINAL_HANDOFF.md
├─ 01_TLS_FAILURE_TRACE.md
├─ 02_HEADUNIT_CERTIFICATE_DEEP_ANALYSIS.md
├─ 03_GAL_TRUST_CHAIN_VERIFICATION.md
├─ 04_OPEN_SOURCE_CROSS_VALIDATION.md
├─ 05_ERROR07_EXTERNAL_CASE_REANALYSIS.md
├─ 06_GOOGLE_POLICY_HYPOTHESIS.md
├─ 07_GENESIS_FIRMWARE_IDENTITY_SEARCH.md
├─ 08_RECEIVER_CODE_REVIEW.md
├─ 09_OFFICIAL_PROVISIONING_ROUTES.md
├─ 10_FEASIBILITY_MATRIX.md
├─ 11_NEXT_TEST_PLAN.md
└─ 12_EVIDENCE_INDEX.md
```

## 이번 연구에서 새로 확정한 것

1. **폰 leaf는 X.509 v3** (기존 "v1" 서술 오류 정정). SKI/AKI 2개 확장만 보유.
2. **GAL root는 v3, `CA:TRUE`, sha1WithRSA, 2044-06-05 만료, 자체 서명.**
3. **DHU 2.1 / AASDK 인증서는 `openssl verify -no_check_time`으로 GAL root에 연결 확인.**
4. **중간 CA 없음** (2장 체인).
5. **HU 인증서의 UTCTime은 `-0700` 오프셋** — DER 비준수이며 OpenSSL 기본 검증이 거부.
   BearSSL과 `ce_aa_tls.c`의 `der_time`도 `Z`만 허용.
6. **순정 Genesis 펌웨어에는 AA/GAL 신원이 없다** — PEM 0건, 매니페스트에 AA 모듈 없음.
7. **2025년 오류 07 파동은 실재하지만**, GD13MY는 같은 날 DHU가 성공하므로 정책 변경만으로 설명되지 않는다.
8. **pi-auto-headunit은 USB와 개발자 터널 모두에서 동일하게 error 7** — 우리 결과의 독립 재현.

## 이번 연구에서 폐기한 것

| 폐기 대상 | 이유 |
| --- | --- |
| "모든 인증서가 X.509 v1" | 폰 leaf·GAL root는 v3 |
| "특정 확장 필드가 필요하다" | DHU 인증서는 확장 0개로 동작 |
| "증거는 alert 48 / `BR_ERR_X509_NOT_TRUSTED`" | 실폰 로그에 존재하지 않음, 방향도 반대 |
| "Genesis 순정 인증서를 추출하면 된다" | 펌웨어에 존재하지 않음 |
| "TLS 구현을 고치면 된다" | DHU와 동일 조건에서 이미 정상 동작 |
| "개발자 모드는 신원 우회다" | pi-auto-headunit + 우리 시험 모두 반증 |

## 남은 미확정 (의도적으로 남김)

| 항목 | 등급 | 다음 방법 |
| --- | --- | --- |
| 클라이언트 flight 후 alert 전송 여부 | PARTIAL | §11 Test A |
| 체인에 루트 포함 시 폰 반응 | UNKNOWN | §11 Test B |
| 암호화된 `rootfs.img` 내부 | UNKNOWN | 범위 밖(후속 과제로 두지 않음) |
| Cinemo CE 6.0 지원·평가 신원 | UNKNOWN | 답변 대기(재문의 금지) |
| Play Services 25.34.34 변경 내용 | UNKNOWN | 비공개 |

## 재현 진입점

- 증거 해시·명령: `12_EVIDENCE_INDEX.md`
- 다음 시험: `11_NEXT_TEST_PLAN.md`
- 질문 9개 답: `FINAL_HANDOFF.md`

## 금지 사항 준수 확인

- [x] `G:\` 원본 수정 없음 (읽기 전용 스캔만)
- [x] GD13MY 제품 코드 수정 없음
- [x] BearSSL 전체 교체 없음
- [x] 실기기 플래싱 없음
- [x] 개인키 추출·사용 없음
- [x] DHU/AASDK/LIVI 신원 위장 없음
- [x] 원본 펌웨어 업로드 없음
- [x] 유료 서비스 이용 없음
- [x] 성공 확률 수치 없음
- [x] Cinemo 재문의 없음
