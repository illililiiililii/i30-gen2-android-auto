# PROGRESS — OpenCode 조사 (2026-11-24)

상태: **1차 조사 완료 / 문서 10~15 작성 완료 / Genesis 컨테이너 복호화 미완**

---

## 1. 이번에 한 일

| # | 작업 | 결과 |
| --- | --- | --- |
| 1 | 기존 문서 3종(DeepSeek/ChatGPT/Antigravity) 정독 | 교차검증 대상 목록화 |
| 2 | 22개 GitHub 저장소 접근성 확인 | 전부 접근 가능, `headunit-revived` → `open-headunit` 개명 확인 |
| 3 | cert/TLS 관련 프로젝트 소스 확인 | aasdk, open-headunit, pi-auto-headunit, AARE, LIVI, DHU |
| 4 | `pi-auto-headunit` 세 문서 존재 확인 | **존재함** (해시 기록) |
| 5 | 공개 인증서 디코드 | DHU, AASDK, phone leaf, GAL root |
| 6 | DHU metadata 날짜 혼동 재검증 | `notBefore/notAfter: null` 확인 |
| 7 | 에러 07 외부 사례 수집 | Jaycar, WebAA, open-headunit #14/#66/#252, pi-auto |
| 8 | GD13MY 펌웨어 분석 | OMAP3430/3530 BSP, DSP/VideoDev IOCTL 확인 |
| 9 | Genesis 컨테이너 구조 분석 | 고엔트로피 헤더, 기존 RSA 추출 가정 오류 확인 |
| 10 | 문서 10~15 작성 | 완료 |

---

## 2. 확정된 사실

- 에러 07의 현재 원인은 **GAL 체인 미신뢰**(`BR_ERR_X509_NOT_TRUSTED`, alert 48).
- TLS 1.2/`0xC02F`는 정상. wolfSSL 교체 불필요.
- DHU 인증서는 2048-08-01까지 유효. 만료 아님.
- Phone leaf는 2027-02-17 만료. 미래 절벽.
- Phone은 HU의 조직명을 구분하지 않고 **GAL 체인**만 본다(DHU 내부 인증서도 통과).
- `pi-auto-headunit`의 세 정책 문서는 실제로 존재한다.
- GD13MY는 OMAP3430/3530 계열이며 DSP/VideoDev 디코드 경로가 있다.
- Genesis `IBOX.tar`/`rootfs.img`/`update.tar`는 동일 LGE 컨테이너이며 헤더는 암호화되어 있다.

---

## 3. 산출물

```
docs/OpenCode-search/genesis-premium-gen2/
├─ README.md
├─ PROGRESS.md
├─ FINAL_HANDOFF.md
├─ 10_EXISTING_RESEARCH_CROSS_VALIDATION.md
├─ 11_OPEN_SOURCE_IMPLEMENTATION_COMPARISON.md
├─ 12_PUBLIC_CERTIFICATE_COMPARISON.md
├─ 13_ERROR07_EXTERNAL_CASE_ANALYSIS.md
├─ 14_OMAP3530_ACCELERATION_RESEARCH.md
└─ 15_CODEX_IMPLEMENTATION_RECOMMENDATIONS.md
```

증거 파일은 저장소에 커밋하지 않고 `%TEMP%\opencode\aa-research\`에만 보관했다.
(DHU/AASDK 공개 인증서, pi-auto 문서, AARE 문서, 디스어셈블 출력 등)

---

## 4. 검증 상태표

| 항목 | 상태 | 근거 |
| --- | --- | --- |
| DHU 인증서 유효기간 | 확인 | `openssl x509 -text` |
| DHU metadata null 날짜 | 확인 | `dhu21_meta.json` |
| AASDK JVC 인증서 | 확인 | `openssl` + GitHub raw |
| Phone leaf 2027 만료 | 확인 | 실측 JSON + 패키지 인증서 |
| GAL root 2044 | 확인 | 실측 체인 |
| 에러 07 = 체인 미신뢰(현재) | 확인 | BearSSL 로그 |
| 에러 07 ≠ 항상 체인 | 확인 | 외부 사례 5종 |
| pi-auto 세 문서 존재 | 확인 | raw 다운로드 + 해시 |
| GD13MY OMAP3530 계열 | 확인 | BSP PDB 문자열 |
| GD13MY DSP/VideoDev 경로 | 확인 | `LibMMCodec.dll` 문자열 |
| H.264 하드웨어 디코드 가능 여부 | **미확인** | 측정/추적 필요 |
| Genesis AA 리시버 바이너리 | **미확인** | 컨테이너 복호화 실패 |
| Genesis keystore GAL 체인 | **미확인** | 디코드 실패 |
| Genesis i386 ELF | **확인(HU userspace)** | `G:\LIB\*.so`, `G:\BIN\APPNAVI` ELF32 `e_machine=0x03` |
| Antigravity의 OpenSSL/mbedtls 버전 | **미확인** | 근거 없음 |
| 확률 수치 | 폐기 | 근거 없음 |

---

## 5. 막힌 지점

1. **Genesis 컨테이너 복호화**: `IBOX.tar` 헤더가 평문 RSA 블록이 아니다. `DecryptToFile`의 키 유도 경로를 더 리버싱해야 한다.
2. **WinCE 실기 테스트**: 비디오/오디오/USB 측정은 기기 접근이 필요하다.
3. **GAL 체인 신원**: 코드로 해결 불가. provisioning 경로가 없다.

---

## 6. 다음 작업

- `[GPT 분석 필요]` LGE 복호화 의사코드 복원.
- `[Codex 구현 필요]` `TlsDiagnostics`, `IHuIdentityProvider`, phone-role 하네스.
- `[조사]` Google Play Services 25.34.34 이후 정책 변화 모니터링.
- `[조사]` GAL root의 CA 속성/KeyUsage 확인.
- `[실기]` H.264 480p/720p 재생 측정.

---

## 7. 예산/방법 메모

- 저장소 전체 클론/대량 다운로드 없음. 필요한 파일만 raw로 받았다.
- 22개 저장소를 동일 깊이로 분석하지 않았다. cert/TLS 관련 6개만 심층 분석.
- 모든 외부 인용은 URL/파일/해시로 추적 가능하게 남겼다.
