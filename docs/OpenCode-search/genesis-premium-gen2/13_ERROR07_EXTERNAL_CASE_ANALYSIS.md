# 13. 에러 07 외부 사례 분석

작성일: 2026-11-24
질문: "같은 에러 07"이 실제로 같은 원인인가? 외부 사례에서 무엇을 배울 수 있는가?
결론 먼저: **아니다.** 에러 07은 최소 5개 원인(A~E)으로 나타난다. 이 프로젝트의 GD13MY 사례는 A(체인 미신뢰)로 확정되지만, 다른 사례를 우리 상황에 그대로 적용하면 오진한다.

---

## 1. 원인 분류

| 코드 | 원인 | 대표 관측 | 판별 테스트 | 사용자가 고칠 수 있나 |
| --- | --- | --- | --- | --- |
| **A** | HU 인증서 체인이 phone trust anchor로 이어지지 않음 | TLS alert 48 `bad certificate`, BearSSL `BR_ERR_X509_NOT_TRUSTED`, 핸드셰이크 중단 | GAL 체인 인증서로 교체하면 즉시 성공 | 아니오(신원 필요) |
| **B** | Google 정책/검증 변경 (phone/Play Services 업데이트) | 어제까지 되던 HU가 갑자기 실패, 동일 시기 다수 보고, 벤더 펌웨어 업데이트로 해결 | 동일 HU를 구버전 phone/Play Services로 테스트, 벤더 공지 확인 | HU 펌웨어 업데이트로만 |
| **C** | 인증서 만료/시계 오류 | `expired` 계열 alert, notAfter 경과 | 인증서 날짜와 기기 시계 확인 | 인증서 갱신/시계 수정 |
| **D** | TLS 스택 호환성 | 핸드셰이크 초반 실패, `handshake_failure`/`decode_error`, 특정 Android 버전에서만 | TLS provider/라이브러리 교체, 버전/cipher 고정 | 앱/펌웨어 업데이트로 가능 |
| **E** | 오진/설정 오류 | "error 7"로 표시되지만 실제로는 USB 권한, 코덱, 앱 버전 문제 | 로그에 TLS alert 자체가 없음, 설정 변경으로 해결 | 예 |

---

## 2. 사례표

| # | 사례 | 시기 | 증상 | 실제 원인 추정 | 근거 |
| --- | --- | --- | --- | --- | --- |
| 1 | Jaycar QM3793 (호주 판매 HU) | 2025-09-24 문서 | "Communication Error 7", "The software does not pass Android security checks" | **B**: Google phone 업데이트로 기존 HU가 거부됨. HU 펌웨어(`ISP_UPDT.BIN`) 업데이트로 해결 | Jaycar 지원 문서 |
| 2 | WebAA (Android Auto 웹 구현) | 2025~2026 | "Latest Google Play Service update breaks WebAA. We are looking for potential workarounds, but options are limited." | **B**: Play Services 변경 | WebAA 배포 페이지 |
| 3 | pi-auto-headunit (Rust, Pi 5) | 2026-08 문서 | 독립 신원으로 error 7. 합성 mTLS 검증기에서는 핸드셰이크 성공 | **A**: 신뢰 앵커 밖 신원 | `receiver-provisioning-options.md` |
| 4 | open-headunit #14 | 2025-12-30 | Android HU 앱 설치 후 error 7, "could not start transport" 반복 | **A/E**: 앱 신원 또는 USB 권한. 커뮤니티는 재삽입/권한을 권했으나 미해결 | GitHub issue #14 |
| 5 | open-headunit #66 | 2026-01-23 | 구버전 Android에서 error 7 | **D**: TLS provider 문제. Conscrypt 도입 후 해결 | PR #66 |
| 6 | open-headunit #252 | 2026-03-18 | error 7로 보고 | **E**: 최신 버전/H.264 설정으로 해결. 사용자가 에러 문구를 오용 | issue #252 |
| 7 | AASDK/OpenAuto 계열 | 2018~ | 대체로 정상 | GAL 체인 공유 신원 사용 | aasdk `cert/headunit.crt` |
| 8 | Google DHU | 현재 | 정상 | GAL 체인 내부 테스트 신원 | 공개 인증서 |
| 9 | **이 프로젝트 GD13MY** | 2026 | error 7, phone이 HU 거부 | **A**: self-signed/사설 CA | `BR_ERR_X509_NOT_TRUSTED`, alert 48 |
| 10 | Google 지원 포럼 25.34.34 스레드 | 2025 | 특정 Play Services 버전 이후 commercial HU에서 error 7 다발 | **B** | 스레드 제목/시기(본문은 JS 렌더링으로 전문 확인 불가) |

---

## 3. 사례별 상세

### 3.1 Jaycar QM3793 — "정책 변경"의 교과서적 사례

원문 요지:

> "A small number of Android phones have recently received updates from Google that may impact the phone's ability to connect ... The affected phones will have a message when connected stating 'Communication Error 7' and 'The software does not pass Android security checks'."

- HU 자체는 바뀌지 않았는데 phone 업데이트 후 실패.
- 해결책은 **phone 설정이 아니라 HU 펌웨어 업데이트**.
- 시사점: Google이 phone 쪽 검증을 강화하면, HU는 새 펌웨어(아마 새 인증서/새 TLS 동작)를 받아야 한다. 이 프로젝트처럼 HU 소프트웨어를 직접 만드는 경우, 이 변경은 **통제 불가능한 외부 리스크**다.

### 3.2 WebAA — "workaround가 제한적"

- Play Services 업데이트로 기존 구현이 깨졌고, 배포자는 "options are limited"라고 명시.
- 시사점: phone 앱을 수정/우회하는 접근은 지속 가능하지 않다. HU 쪽 신원/프로토콜이 정답이다.

### 3.3 pi-auto-headunit — "프로토콜은 되고 신원만 막힌다"

- Pi 5에서 AAP 1.6, USB/AOA 및 Google 개발자 transport로 TLS 데이터 교환까지 성공.
- 독립 신원은 error 7.
- 합성 mutual-TLS 검증기에서는 "when that identity is trusted" 핸드셰이크 완료.
- 시사점: **전송/프레이밍/TLS 구현을 의심할 필요가 없다.** 우리 프로젝트의 진단과 동일하다.

### 3.4 open-headunit #66 — "TLS 스택" 축

- Android 4.4 계열에서 Conscrypt provider로 `SSLContext`를 만들자 error 7이 사라졌다는 보고.
- 이 사례는 인증서가 아니라 **TLS 구현/제공자**가 원인이다.
- 시사점: "error 7 = 체인" 공식은 틀렸다. 다만 이 사례는 HU가 Android일 때의 이야기이고, GD13MY는 BearSSL이므로 직접 해당하지 않는다.

### 3.5 open-headunit #252 — "오진" 축

- 사용자는 error 7이라고 주장했지만, 최신 버전/H.264 설정으로 해결.
- 시사점: 사용자 보고의 에러 문구는 신뢰도가 낮다. 반드시 **로그의 TLS 단계**를 봐야 한다.

### 3.6 AASDK/DHU — "GAL 체인은 통과한다"

- AASDK는 JVC Kenwood leaf를, DHU는 Android-Auto-Internal leaf를 쓴다. 둘 다 GAL 발급이다.
- 시사점: phone은 조직명을 보지 않는다. **체인만 본다.** 따라서 "우리 차 전용 인증서"를 만들 필요는 없고, "GAL 체인"이 필요하다.

---

## 4. 이 프로젝트에 대한 판별 절차

```
phone에 error 7 표시
├─ HU 로그에 TLS alert 48 / BR_ERR_X509_NOT_TRUSTED 있음
│   └─ A. 체인 미신뢰  ← 현재 GD13MY
├─ HU 로그에 TLS handshake 자체가 없음
│   └─ E. USB/AOA/앱 설정 문제
├─ TLS alert 45/46 (expired/unknown)
│   └─ C. 만료/시계
├─ alert 40/47/70 (handshake_failure/illegal_parameter/protocol_version)
│   └─ D. TLS 스택/버전/cipher
└─ 어제까지 동작, 다수 사용자 동시 발생, 벤더 펌웨어로 해결
    └─ B. Google 정책 변경
```

### GD13MY 현재 위치

- A. 체인 미신뢰. TLS 1.2/`0xC02F` 협상은 성공.
- 따라서 B/D/C를 좇는 것은 시간 낭비다.
- 단, **B는 미래 리스크**다. 2025~2026년 사례처럼 Google이 갑자기 요구사항을 바꾸면, GAL 체인 인증서를 확보해도 다시 막힐 수 있다.

---

## 5. "에러 07"이라는 표시의 한계

- Google은 Android Auto 에러 코드표를 공개하지 않는다. `[미검증 가설]`
- phone UI 문구("Car's software didn't pass Android Auto security checks")는 보안 검증 실패를 뜻하지만, 그 내부가 체인인지, 정책인지, TLS 스택인지는 구분하지 않는다.
- 따라서 문서/이슈의 "error 7"만으로 원인을 복사하지 말고, **TLS 단계 로그**를 기준으로 분류해야 한다.

---

## 6. 결론

1. 이 프로젝트의 현재 에러 07은 A(체인)다. 증거는 `BR_ERR_X509_NOT_TRUSTED`와 alert 48.
2. 외부에서 "error 7을 해결했다"는 사례는 대부분 B(정책) 또는 D(TLS 스택)이며, 우리 상황에 그대로 적용되지 않는다.
3. A는 코드로 해결되지 않는다. GAL 체인 신원 확보 또는 Google의 공식 provisioning 경로가 필요하다.
4. B는 미래 리스크다. Jaycar 사례처럼 HU 펌웨어 업데이트가 필요할 수 있으므로, 인증서/ TLS 동작을 **교체 가능한 모듈**로 설계해야 한다.
5. 2027-02-17 phone leaf 만료는 C의 미래 사례이며, 이는 Google이 처리할 영역이다.
