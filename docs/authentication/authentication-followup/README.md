# Android Auto 인증 후속 연구 (GD13MY)

작성: 2026-11-25 · 선행: [`../authentication-deep-research/`](../authentication-deep-research/)
범위: 헤드유닛 인증서 · TLS 상호 인증 · GAL 신뢰 체인 · 신원 확보 경로
제외: 영상, DSP, 오디오, UI

---

## 핵심 결론

> **실패 원인은 GAL root 불신이 아니라, GAL 발급 헤드유닛 인증서가 `-0700` UTCTime
> 때문에 BearSSL에서 로드되지 않아 라이브 시험이 자체 서명 신원으로 진행된 것이다.**
>
> **`Google-Android-Reference` (GAL 발급, `Z` 시간, 키 일치) 쌍이 공개되어 있고,
> 현재 펌웨어 코드를 수정하지 않고 로드된다.** 테스트 단계의 실행 가능한 신원 경로다.

---

## 문서

| # | 문서 | 내용 |
| --- | --- | --- |
| 01 | [펌웨어 인증서 스캔](01_FIRMWARE_CERTIFICATE_SCAN.md) | `G:\` 308 파일 / 15.24 GB, PEM 0, OID 1(오탐) |
| 02 | [컨테이너 구조](02_CONTAINER_STRUCTURE.md) | boot/rootfs 동일 magic, IBOX 키스트림 재사용 |
| 03 | [시간 인코딩 근본 원인](03_TIME_ENCODING_ROOT_CAUSE.md) | **핵심** — `err=48`, `pkey=NULL`, `error 13` |
| 04 | [외부 사례·신원](04_EXTERNAL_CASES_AND_IDENTITIES.md) | **핵심** — behead EV6 성공, dexter, `Google-Android-Reference` |
| 05 | [공식 경로](05_OFFICIAL_ROUTES.md) | AAP 2.0 Certification 2.0, 3PL, DHU |
| 06 | [대체 펌웨어](06_ALTERNATIVE_FIRMWARE.md) | Sony XAV-AX100, Kenwood DNX |
| — | [PROGRESS](PROGRESS.md) | 세션 기록 |
| — | [FINAL_HANDOFF](FINAL_HANDOFF.md) | 후보·실패 원인·후속 작업 |

---

## 읽는 순서

- **빠르게**: 이 문서 → `FINAL_HANDOFF.md` → 03 → 04
- **코드 작업자**: 03 (파서 수정안) → 04 (신원)
- **검증자**: 01 → 02 → 03 → `scripts/`

---

## 실행 가능한 경로 (요약)

1. `build/auth-followup/open-headunit/cert` + `privkey`를 `i30-client.pem` /
   `i30-client-key.pem`으로 배포 (leaf first).
2. `build/auth-research/certs/gal-root.pem`을 `i30-ca.pem`으로 배포.
3. 폰 연결 후 `AuthComplete` status 0 확인.
4. 실패 시 `der_time()`/SPKI 파서 수정 후 JVC 인증서로 재시험 (03 문서).

키는 **테스트 단계에서만** 사용하고 커밋·배포하지 않는다.

---

## 원칙

- 모든 주장에 `VERIFIED` / `PARTIAL` / `HYPOTHESIS` / `UNKNOWN` / `FAILED` 등급.
- 로그에 없는 것은 추정으로 채우지 않았다.
- `G:\` 원본과 GD13MY 제품 코드는 수정하지 않았다.
- 개인키는 테스트 단계에서만 사용하며, 저장소·제품에 포함하지 않는다.
