# 12. 공개 인증서 비교 (공개 자료만 사용)

작성일: 2026-11-24
범위: 공개 저장소/공개 배포물에 포함된 인증서의 **메타데이터와 공개키**만 비교한다. 개인키는 사용하지 않으며, 이 저장소에 커밋하지 않는다. 아래 지문은 식별용이다.

---

## 1. 비교표

| 항목 | DHU 2.1 / latest | AASDK 공개 HU 인증서 | Phone leaf (CarService) | GAL root |
| --- | --- | --- | --- | --- |
| 파일 출처 | Google DHU 배포물 | `opencardev/aasdk` `cert/headunit.crt` | phone 실측 캡처 + Android Auto 패키지 | phone 체인 2번째 |
| X.509 버전 | v1 | v1 | v1 | (확인 범위 밖) |
| Subject | `C=US, ST=California, L=Mountain View, O=Android-Auto-Internal, OU=01` | `C=JP, ST=Tokyo, L=Hachioji, O=JVC Kenwood, OU=01` | `C=US, ST=California, L=Mountain View, O=CarService` | `O=Google Automotive Link` (self-signed) |
| Issuer | `O=Google Automotive Link` | `O=Google Automotive Link` | `O=Google Automotive Link` | 자기 자신 |
| Serial | `0x0111` | `0x1B` | (캡처에서 미기록) | (미기록) |
| 유효 시작 | 2014-07-04 07:00:00Z | 2014-07-04 07:00:00Z | 2014-07-04 00:00:00Z | 2014-06-06 18:28:19Z |
| 유효 종료 | **2048-08-01 17:21:23Z** | **2045-04-29 21:28:38Z** | **2027-02-17 19:01:30Z** | **2044-06-05 18:28:19Z** |
| 공개키 | RSA 2048 | RSA 2048 | RSA (캡처) | RSA (캡처) |
| 서명 알고리즘 | sha256WithRSA | sha256WithRSA | sha256WithRSA | (미확인) |
| SHA-256 지문 | `4e:b5:81:dc:ee:2b:84:36:9c:a8:70:66:ab:6e:aa:73:a4:78:3a:ef:5c:7b:6e:dc:68:41:e0:66:cf:fa:7e:7c` | `1c:0e:0e:f9:e6:72:dd:1a:63:ab:4d:61:af:aa:89:96:a5:7c:a7:aa:96:6d:19:22:b9:7d:8f:93:85:ea:3c:35` | `46:d9:07:a7:48:2d:0a:bd:5d:0c:a2:6c:0f:14:78:48:08:cc:0e:61:49:45:a2:f3:92:1c:53:09:97:54:d2:7c` | `49:e5:2e:fc:13:ad:2e:d0:9f:20:4c:3b:10:69:8b:d8:4b:b7:10:5f:51:05:58:aa:14:b8:11:9a:5c:4a:d1:7f` |
| 개인키 공개 여부 | **공개** | **공개** | 비공개(phone 내부) | 비공개 |
| phone이 수락 | 예 | 예(다수 OSS 보고) | (서버 자신) | (신뢰 앵커) |

주의: 위 "예"는 기술적 관측이며, 해당 신원을 제품에 사용할 권리가 있다는 뜻이 아니다.

---

## 2. 구조적 관찰

### 2.1 공통점

- 모든 HU/phone 인증서의 issuer가 `O=Google Automotive Link`다. 즉 **GAL가 발급 CA 역할**을 한다.
- CN이 없고, `OU=01` 또는 `O=CarService` 같은 단순 DN을 쓴다.
- X.509 v1이라 **SAN, EKU, basicConstraints가 없다.** 그런데도 phone은 수락한다. phone의 검증기는 "GAL 체인 + 유효기간 + 서명" 정도만 본다고 추론할 수 있다.
- 키는 RSA 2048, 서명은 SHA-256.

### 2.2 차이점

- DHU는 `Android-Auto-Internal`(내부 테스트), AASDK는 `JVC Kenwood`(OEM 파트너), phone은 `CarService`(phone 앱)다.
- 즉 phone은 **조직명을 구분하지 않는다.** `Android-Auto-Internal`도 통과한다.
- 만료 시점이 제각각이며, HU 쪽(2045/2048)은 phone leaf(2027)보다 오래 살아남는다.

### 2.3 신뢰 체인

```
phone 검증:
  HU leaf (Android-Auto-Internal / JVC Kenwood / ...)
      └─ issuer: Google Automotive Link (root, self-signed, 2044)
  → phone의 trust store에 GAL root 존재
  → 통과

HU가 phone을 검증하는 경우:
  CarService leaf
      └─ issuer: Google Automotive Link (root)
```

**핵심:** phone의 trust anchor는 사실상 `O=Google Automotive Link` 하나다. 자체 서명, 사설 CA, 제3자 OEM CA는 전부 거부된다. 이것이 이 프로젝트의 에러 07과 일치한다.

---

## 3. 왜 만료가 원인이 아닌가

- DHU 인증서: 2048년 만료. 2026년 현재 유효.
- AASDK 인증서: 2045년 만료. 유효.
- phone leaf: 2027-02-17 만료. 2026년 현재 유효.
- 따라서 2026년의 에러 07을 만료로 설명할 수 없다.
- 유일한 미래 절벽은 **phone leaf 2027-02-17**이며, 이는 Google이 phone 앱 업데이트로 처리할 영역이다.

---

## 4. DHU metadata 혼동의 정확한 원인

DHU 2.1 `metadata.json`:

```json
{
  "version": "2.1",
  "certificates": [
    {
      "kind": "desktop-head-unit",
      "sha256": "4eb581dcee2b84369ca87066ab6eaa73a4783aef5c7b6edc6841e066cffa7e7c",
      "subject": "C=US\nST=California\nL=Mountain View\nO=Android-Auto-Internal\nOU=01",
      "issuer": "C=US\nST=California\nL=Mountain View\nO=Google Automotive Link",
      "serialNumber": "0111",
      "notBefore": null,
      "notAfter": null
    }
  ]
}
```

- `notBefore`/`notAfter`가 null이라 metadata만 보고는 만료를 계산할 수 없다.
- 실제 인증서를 디코드하면 2048-08-01까지 유효하다.
- `dhu/2.1/cert.pem`과 `dhu/latest/cert.pem`은 동일 파일이다(둘 다 SHA-256 `9c5a28e2…`, 인증서 지문 `4eb581dc…`).

---

## 5. 이 프로젝트가 공개 인증서로 할 수 있는 것 / 없는 것

### 할 수 있는 것

1. **검증기 동작 확인**: DHU 인증서를 "신뢰되는 예시"로 넣어, 우리 HU/phone 시뮬레이터가 GAL 체인을 제대로 검증하는지 단위 테스트.
2. **에러 분류**: 체인 미신뢰(`X509_NOT_TRUSTED`)와 서명 불일치, 만료, 알 수 없는 CA를 구분하는 테스트 벡터 생성.
3. **메타데이터 비교**: 실제 차량/공개 HU가 어떤 DN·시리얼·만료를 쓰는지 문서화.
4. **SAT/사설 CA 시나리오**: 자체 서명 인증서가 거부되는 것을 재현.

### 할 수 없는 것

1. DHU/AASDK/LIVI의 **개인키를 사용해 HU 신원을 위조**하는 것.
2. 공개 인증서를 제품에 포함해 "GAL 발급"으로 보이게 하는 것.
3. 인증서만으로 phone의 trust store를 바꾸는 것(phone은 사용자 통제 밖).

### 저장소 위생

- 공개 인증서의 PEM/DER은 테스트 벡터로만 쓰고, 개인키는 절대 커밋하지 않는다.
- 이미 저장소에 개인키가 들어간 OSS의 파일을 복사하지 않는다.
- 테스트 벡터는 `test/fixtures/certs/`에 두더라도 "공개 테스트 신원, 제품 사용 금지" 주석을 단다.

---

## 6. 검증 명령 (재현용)

```powershell
$openssl = 'C:\Program Files\Git\usr\bin\openssl.exe'
& $openssl x509 -in dhu21_cert.pem -noout -text
& $openssl x509 -in dhu21_cert.pem -noout -serial -subject -issuer -dates -fingerprint -sha256
& $openssl x509 -in aasdk_headunit.crt -noout -serial -subject -issuer -dates -fingerprint -sha256
```

전체 `-text`에서 확인할 점:

- `Version: 1 (0x0)` → 확장 없음.
- `Signature Algorithm: sha256WithRSAEncryption`.
- `Public-Key: (2048 bit)`.
- `X509v3 extensions` 섹션이 없음.

---

## 7. GD13MY에 주는 결론

`[GD13MY 적용 가능]`

- BearSSL의 `br_x509_minimal` 설정에 **GAL root를 trust anchor로 넣는 것은 phone 검증용**이며, phone이 우리를 검증하는 것과는 무관하다.
- 우리 HU 인증서는 반드시 GAL 체인이어야 한다. 자체 CA/self-signed는 100% 거부된다.
- 따라서 구현 단계에서 할 일은 "인증서 검증 코드 개선"이 아니라 **"GAL 체인 신원 확보 경로"**다. 이는 코드로 해결되지 않는다.
- 2027-02-17 phone leaf 만료 전에, 장기적으로는 Google의 정책 변화(Jaycar 사례처럼 HU 펌웨어 업데이트를 요구하는 변경)를 모니터링해야 한다.

---

## 8. 남은 확인

- `[GPT 분석 필요]` GAL root의 X.509 버전/CA 플래그/KeyUsage. 현재는 phone 체인에서 관측한 DN과 지문만 있다.
- `[GPT 분석 필요]` phone이 HU 인증서에서 실제로 검사하는 필드(체인, 기간, 서명, DN). DHU 내부 인증서가 통과하는 사실로 보아 DN/EKU 검사는 없거나 느슨하다.
- `[Codex 구현 필요]` 인증서 고정 테스트 벡터와 "신뢰/거부" 기대값을 담은 자동 테스트.
