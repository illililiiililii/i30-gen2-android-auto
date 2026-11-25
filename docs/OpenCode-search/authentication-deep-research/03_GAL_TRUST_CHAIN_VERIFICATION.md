# 03. GAL 신뢰 체인 검증 (P0-2 후속)

작성: 2026-11-25 · 목적: "무엇이 통과를 결정하는가"를 체인 모델로 확정

## 1. 확정된 신뢰 모델

```
[폰 trust store]
  └─ O=Google Automotive Link  (self-signed, CA:TRUE, 2014-06-06 ~ 2044-06-05)
        ├─ (서명) C=US,...,O=CarService            ← 폰 자신의 TLS 서버 인증서
        ├─ (서명) O=Android-Auto-Internal, OU=01    ← Google DHU 2.1
        └─ (서명) C=JP,...,O=JVC Kenwood, OU=01     ← AASDK 공개 신원
```

- **중간 CA 없음** (2단 체인).
- 폰은 헤드유닛 인증서에 대해 **조직명을 구분하지 않는다** (내부 테스트명·OEM명 모두 통과).
- 폰은 **X.509 확장을 요구하지 않는다** (DHU 인증서는 확장 0개, v1).
- 폰은 **DER 비준수 시간 인코딩(`-0700`)도 수락한다** (DHU/AASDK 실사용).
- 반대로 폰은 **자체 CarService 인증서나 루트 자체를 헤드유닛이 보내는 것을 거부**한다(AARE).

⇒ 통과 조건은 사실상 하나다: **헤드유닛 인증서가 GAL root의 서명을 받았고, 그 개인키를 보유할 것.**

## 2. 검증 명령과 결과 (재현 가능)

| 대상 | 명령 | 결과 |
| --- | --- | --- |
| 폰 leaf | `openssl verify -CAfile gal-root.pem phone-leaf.pem` | `OK` |
| DHU 2.1 | `openssl verify -CAfile gal-root.pem dhu21.pem` | `error 13 ... notBefore field` |
| DHU 2.1 | `openssl verify -no_check_time -CAfile gal-root.pem dhu21.pem` | `OK` |
| DHU 2.1 (용도 제한) | `openssl verify -no_check_time -purpose sslclient -CAfile gal-root.pem dhu21.pem` | `OK` |
| AASDK | `openssl verify -no_check_time -CAfile gal-root.pem aasdk-embedded.pem` | `OK` |

추가 확인:
- AKI(leaf) = SKI(root) = `B9:76:AB:EF:F0:33:D0:8B:0A:CC:7E:09:FC:C4:A4:7D:D6:4E:F0:82`
- 서명 알고리즘: leaf/HU = `sha256WithRSA`, root = `sha1WithRSA`
- 공개키: 전부 RSA 2048 / e=65537

## 3. 폰이 실제로 하는 검사 (증거 기반 / 추정 분리)

| 검사 | 판정 | 근거 | 등급 |
| --- | --- | --- | --- |
| 체인 종결(trust anchor) | 함 | `CertPathValidatorException: Trust anchor for certification path not found` | VERIFIED |
| 서명 검증 | 함 | 동일 예외 경로(체인 검증의 일부) | VERIFIED |
| 유효기간 | 함 | AARE: 만료 시 `-24` 상태 코드 존재 | PARTIAL(폰 앱 외부 관측) |
| 조직명(DN) | 안 함 | 내부 테스트명/OEM명 모두 실사용 | VERIFIED |
| EKU/SAN/keyUsage | 안 함(요구하지 않음) | DHU 인증서에 해당 확장 없음 | VERIFIED |
| BasicConstraints(leaf) | 안 함 | DHU에 없음 | VERIFIED |
| DER 시간 형식 엄격성 | 안 함 | `-0700` 인증서 실사용 | VERIFIED |
| 공개키 지문 pinning | 알 수 없음 | 폰 로그에 단서 없음 | UNKNOWN |
| 앱/Play Services 버전별 정책 | 있음(변동) | Jaycar 사례(§06) | VERIFIED(정책 존재) |

## 4. 왜 "검증 코드 개선"으로 해결되지 않는가

체인 검증은 **우리 쪽 코드가 아니라 폰 쪽 코드**가 수행한다.
우리가 바꿀 수 있는 것은 두 가지뿐이다.

1. **보내는 인증서/키** (신원) — GAL 발급이 아니면 무조건 실패.
2. **보내는 방식** (체인 순서, TLS 버전, 프레이밍) — 이미 DHU와 동일 조건에서 정상임을 확인(§01).

즉 이 문제의 해는 **암호학적 신원 확보**이지 구현 개선이 아니다. 이 결론은
pi-auto-headunit(2026-08)이 독립적으로 도달한 결론과 같다(§04).

## 5. "공개 인증서가 있으니 쓸 수 있다"는 오해 정리

| 주장 | 사실 |
| --- | --- |
| 공개 저장소에 인증서+개인키가 있으니 그대로 쓰면 된다 | 개인키가 공개된 신원은 **모두가 같은 신원**이 된다. 제품 신원으로 부적절하고, Google 내부 테스트 신원(`Android-Auto-Internal`) 또는 타사(OEM) 신원의 위장이다. 본 프로젝트 규칙상 금지. |
| DHU 인증서는 Google이 테스트용으로 공개한 것이니 자유롭게 써도 된다 | 공개된 것은 **DHU라는 도구를 실행하기 위한 것**이다. 제3자 제품의 수신기 신원으로 재사용할 권한은 어디에도 명시돼 있지 않다. |
| 체인만 맞으면 폰이 받아준다 | 기술적으로는 맞다. 그러나 "받아준다"와 "사용 권한이 있다"는 별개다. |
| 인증서를 폰에 설치하면 된다 | 폰의 trust store는 시스템 CA이며 사용자/앱이 바꿀 수 없다. 또한 우리가 필요한 것은 **역방향**(폰이 우리를 신뢰)이다. |

## 6. GD13MY 적용 판정

- 수신기(BearSSL)가 폰을 검증하는 방향: **이미 정상**. GAL root 또는 지문 pin으로 통과.
  - `build/gd13my-ce-projection/phone-tls-public.json`의 두 지문을 pin으로 사용 가능.
- 폰이 우리를 검증하는 방향: **GAL 발급 신원 없이는 불가**. 코드로 우회 불가.
- 따라서 §07(신원 확보 경로)이 유일한 미결 항목이다.

## 7. 체인 모델이 바뀔 경우의 리스크

| 리스크 | 징후 | 대비 |
| --- | --- | --- |
| 중간 CA 도입 | 폰이 3장 이상 체인 전송 | 수신기 CA 로더를 다중 인증서로 확장(§08) |
| 루트 교체(2044 만료 전) | 새 루트 지문 | `i30-ca.pem` 교체 가능(이미 파일 기반) |
| 폰 leaf 회전 | 만료일 변경(17.7→2026-12-31, 18.0→2027-02-17) | 만료일 하드코딩 금지, 매 세션 leaf 기준 판정 |
| 정책 강화(Jaycar형) | 갑자기 다수 HU 실패 | 인증서·TLS 모듈을 교체 가능 단위로 유지 |

## 8. 증거 파일

- `build/auth-research/certs/gal-root.pem` (`a611c0db…`)
- `build/auth-research/certs/phone-leaf.pem` (`0e70ee1c…`)
- `build/auth-research/certs/dhu__2.1__certificate.pem` (`9c5a28e2…`)
- `build/auth-research/certs/aasdk-embedded.pem` (`85b5043a…`)
- `build/gd13my-ce-projection/phone-tls-public.json`
- `build/gd13my-native-oem-screen/live-phone-usb-trust-android.log`
