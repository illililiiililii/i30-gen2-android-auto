# DeepSeek 조사 문서

GD13MY(현대 i30 GD 2013 순정 내비) Android Auto 이식 관련 조사·판정 문서 모음.

| 문서 | 내용 |
|---|---|
| [i30-gd-aa-error07-research.md](i30-gd-aa-error07-research.md) | 1차 리서치. 오류 07 원인 규명, 참고 프로젝트, 오류 07 해결 후보, WinCE 이식 가능성, 구현 지시서, 저장소 실물 검토(A~G) |
| [i30-gd-aa-phase2-report.md](i30-gd-aa-phase2-report.md) | 2차 보고서. 저장소 실물 검토, 인증서 판정 근거, DHU 2.1 인증서 DER 실측, 적용 절차·로그별 실패 분기, WinCE 6.0/ARM 에뮬레이터 조사 |
| [i30-gd-aa-success-probability.md](i30-gd-aa-success-probability.md) | DHU 신원 적용 시 성공 가능성 평가. 단계별 확률, 잔여 리스크, PC 선행 시험 절차, 확률 갱신 규칙 |

## 요약

- 오류 07은 TLS 계층의 **헤드유닛 인증서 체인 거부**다(프로토콜/암호 문제 아님).
- 폰의 신뢰 앵커는 `O=Google Automotive Link` 루트이며, DHU 2.1 신원이 GAL 체인을 가진 유일한 공개 배포 자료다.
- DHU 인증서 유효기간은 **2048-08-01**(2026-12-31은 폰 측 인증서 숫자).
- 07 소멸 확률 추정 **85~90%**, 화면 투사까지 **55~70%**, 무중단 실사용 **30~50%**.

### 근거 등급
- **[검증]** 파일·로그·문서 원문 직접 확인
- **[부분검증]** 요약·일부 본문만 확인
- **[추정]** 공개 근거 기반 추론

## 추가 문서
| 문서 | 내용 |
|---|---|
| [docs/chatGPT-search](/docs/chatGPT-search) | |
