# 06. Google 정책·Play Services 변경 가설 검증

작성: 2026-11-25 · 질문: "2025~2026년 Google 정책 변경이 GD13MY 오류 07의 원인인가?"

## 0. 결론

| 질문 | 답 | 등급 |
| --- | --- | --- |
| 폰/Play Services 업데이트로 기존 HU가 거부된 사례가 있는가 | **있다** (2025-08~09 다수) | VERIFIED(공지·스레드 존재) |
| 그 사례들이 원인을 공개했는가 | **아니다.** "Google update"만 언급 | VERIFIED(부재) |
| GD13MY 오류 07이 그 정책 변경 때문인가 | **아니다(주 원인).** 우리 신원은 정책 변경 이전에도 통과한 적이 없다 | VERIFIED |
| 정책 변경이 향후 리스크인가 | **그렇다.** AAP 2.0 인증 세대 교체 진행 중 | VERIFIED(보도자료) / HYPOTHESIS(영향) |

즉 **정책은 원인이 아니라 배경**이다. 원인은 A(체인 미신뢰)다.

---

## 1. 2025년 파동의 사실관계

기존 조사(`docs/DeepSeek-search/i30-gd-aa-error07-research.md`)에 정리된 출처:

| # | 출처 | 날짜 | 내용 |
| --- | --- | --- | --- |
| 1 | `https://support.google.com/androidauto/thread/369324198` | 2025-08-30 | 갑자기 07, Galaxy S21 실패 / S23 성공 |
| 2 | `https://support.google.com/androidauto/thread/371804348` | 2025-09-08 | **Play Services `25.34.34` 업데이트 직후 3대 모두 07** |
| 3 | `https://issuetracker.google.com/issues/440779969` | 2025 | PS 업데이트 후 07, 임시방편은 제거/롤백 |
| 4 | `https://help.jaycar.com.au/hc/en-us/articles/50355885912217` | 2025-09-24 | Jaycar QM3793: "Google phone update" → `ISP_UPDT.BIN`(20MB) HU 펌웨어로 해결 |
| 5 | WebAA 배포 페이지 | 2025~2026 | "Latest Google Play Service update breaks WebAA … options are limited" |

패턴: **같은 HU가 어제까지 동작 → 폰 업데이트 후 07 → HU 펌웨어 업데이트로 복구.**

이 패턴이 성립하려면:
1. 폰이 HU에 요구하는 조건이 바뀌었고,
2. HU 펌웨어가 그 조건을 만족하도록 바뀌었다.

조건의 정체는 **공개되지 않았다.** 후보:
- 새 인증서/새 프로비저닝
- TLS 파라미터(버전·cipher·extension)
- 버전 협상/서비스 디스커버리 스키마
- 폰 앱의 알려진 HU 목록·지문 허용목록

등급: VERIFIED(현상) / UNKNOWN(메커니즘)

---

## 2. 우리 프로젝트에는 왜 이 가설이 적용되지 않는가

핵심 반증: **우리 신원은 "정상 동작하던 시절"이 없다.**

| 시점 | 신원 | 실폰 결과 | 근거 |
| --- | --- | --- | --- |
| 2026-11 (현재) | 자체 생성/실험 신원 | `Trust anchor … not found` | `live-phone-usb-trust-android.log` |
| 2026-11 (개발자 터널) | 동일 | `phone closed before completing mutual TLS` | `live-phone-native-identity-fresh.log` |
| 2026-11 (공식 DHU) | GAL 발급 | **정상** (`Verify returned: ok`) | `dhu-20261123-222431/stderr.log` |

→ 같은 폰, 같은 날(2026-11-23), 같은 AA 버전에서 **DHU만 성공**한다.
→ 폰의 정책이 "모든 HU 거부"로 바뀐 것이 아니다.
→ 우리 체인만 거부된다 = A.

만약 B(정책)가 주 원인이라면 DHU도 실패해야 한다. **DHU는 성공했다.**
이 단일 대조가 B 가설을 주 원인에서 배제한다. 등급 VERIFIED.

---

## 3. 그럼에도 B를 무시할 수 없는 이유

B는 **미래 리스크**로 남는다.

1. **AAP 2.0 세대 교체** (2026-10-06)
   - P3 보도자료: Google이 P3를 "AAP 2.0" 3PL 인증 파트너로 인증.
   - "newest generation of AAP standards and protocols" — 프로토콜·인증 요건이 세대 교체 중.
   - 출처: `https://p3-group.com/Insights/google-expands-p3s-3pl-accreditation-to-embrace-next-gen-android-autoprojection-aap-technology-certification/`
2. **AA 앱 버전별 leaf 회전**
   - 17.7 → 2026-12-31, 18.0 → 2027-02-17 (AARE 문서 vs 우리 캡처)
   - 폰 앱이 자체 신원을 교체한다는 것은 **검증 규칙도 함께 바뀔 수 있음**을 뜻한다.
3. **Jaycar형 사후 무효화**
   - 어떤 방식으로든 신원을 확보하더라도, 폰 업데이트 한 번에 무효화될 수 있다.

⇒ 따라서 "신원 확보"는 **일회성 이벤트가 아니라 유지보수 관계**여야 한다.
이 관점은 §09(공식 경로)의 전제가 된다.

---

## 4. 확인할 수 없었던 것

| 항목 | 상태 | 이유 |
| --- | --- | --- |
| `25.34.34`의 정확한 변경 내용 | UNKNOWN | Play Services는 비공개. apk 디핑은 정책 범위 밖 |
| Jaycar `ISP_UPDT.BIN` 내부 변경 | UNKNOWN | 배포 파일 미확보, 2차 배포 금지 |
| 폰의 HU 허용목록 존재 여부 | UNKNOWN | 시스템 파티션 분석 필요, 본 연구 범위 밖 |
| Google의 공식 입장 문서 | 없음 | 오류 07 코드 정의표 비공개 |

이 항목들을 "추정으로 채우지 않는다."

---

## 5. 판정

1. 2025년 오류 07 파동은 **실재**하며, 폰 업데이트가 방아쇠였다. (VERIFIED)
2. 그러나 그 파동의 메커니즘은 공개되지 않았다. (UNKNOWN)
3. GD13MY의 오류 07은 **같은 날 DHU가 성공**하므로 정책 변경만으로 설명되지 않는다. (VERIFIED 반증)
4. 정책은 **향후 유지보수 리스크**로 문서화하고, 해결책 설계에는 반영하되 원인 분석에서는 분리한다.
