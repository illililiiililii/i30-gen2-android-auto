# GD13MY 인증 연구 교차 검증

기준은 `main`의 `bf3c347`이다. 착수 시 작업 트리가 깨끗했고 `origin/main`도 같은 커밋이었다. `OpenCode-search/authentication-validation/`은 이 체크아웃에 없었다. 재현에는 공개 인증서의 DER 사본과 합성 시험용 CA만 사용했다.

## 공개 인증서와 파서

| 공개 리프 또는 CA | 원본 ASN.1 유효기간 필드 | BearSSL 0.6 인증서 디코더 | OpenSSL GAL 검증 |
| --- | --- | --- | --- |
| DHU 2.1 | UTCTime `140704000000-0700` / `480801102123-0700` | `48`, `pkey=NULL` | 일반 검증 `13`, 시간만 제외한 검사 통과 |
| AASDK JVC Kenwood | UTCTime `140704000000-0700` / `450429142838-0700` | `48`, `pkey=NULL` | 일반 검증 `13`, 시간만 제외한 검사 통과 |
| Google-Android-Reference | UTCTime `140708224918Z` / `440707224918Z` | `0`, RSA 2048 | 일반 검증 통과 |
| 과거 폰 리프 | UTCTime `140704000000Z` / `270217190130Z` | `0`, RSA 2048 | 일반 검증 통과 |
| GAL Root CA | UTCTime `140606182819Z` / `440605182819Z` | `0`, RSA 2048, CA | 폰이 제시한 체인의 루트와 DER 지문 일치 |

이 공개 샘플에는 GeneralizedTime 필드가 없었다. BearSSL 0.6의 `BR_ERR_X509_BAD_TIME`은 `48`이다. `x509_decoder.t0`에서 `asn1.t0`의 `read-date`를 호출해 `Z`를 검사한 뒤 subject와 SPKI로 이동한다. 따라서 `pkey=NULL`은 시간 오류로 디코더가 중단된 결과다. OpenSSL `x509 -noout -text`는 두 오프셋 샘플에서 RSA 2048 공개키를 해석했다. 프로젝트의 `der_time()`은 별도의 로컬 유효기간 검사다. 기존 `configure()`도 이미 BearSSL에서 키를 얻지 못하면 이 검사에 도달하지 않았다.

OpenSSL 일반 검증은 두 오프셋 인증서의 `notBefore` 형식을 오류 `13`으로 거부했다. `-no_check_time` 결과는 공개 CA로 서명 관계를 확인하는 데만 썼다. 기존 연구의 `dhu21-z.der` 사본은 동일한 CA 검사에서 오류 `7`과 `certificate signature failure`를 반환했다. 헤드유닛에 배포할 인증서의 시간 정책과 DER 서명 대상은 그대로 유지했다. 공개 인증서의 파싱 또는 서명 성공은 프로젝트에 발급된 신원이나 폰의 클라이언트 인증 수락을 입증하지 않는다.

```powershell
$openssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'
$probe = 'build/auth-followup/bearssl-host/cert_probe.exe'
$gal = 'build/auth-research/certs/gal-root.pem'
$public = 'build/auth-followup/dhu21.der'
& $openssl asn1parse -inform DER -in $public | Select-String 'UTCTIME|GENERALIZEDTIME'
& $probe $public
& $openssl verify -CAfile $gal $public
& $openssl verify -no_check_time -CAfile $gal $public
```

나머지 로컬 공개 입력은 `build/auth-followup/aasdk.der`, `open-headunit/gar.der`, `phone-leaf.der`, `gal-root.der`다. 과거 폰이 제시한 GAL 루트의 SHA-256은 `49e52efc13ad2ed09f204c3b10698bd84bb7105f510558aa14b8119a5c4ad17f`다. 이 기록은 폰이 서버로 제시한 체인을 확인한다. 해당 폰이 같은 CA를 클라이언트 인증 정책에서 수락하는지는 이 지문만으로 판정할 수 없다. [원본 증거 색인](../OpenCode-search/authentication-deep-research/12_EVIDENCE_INDEX.md) · [과거 폰의 공개 체인](../../build/gd13my-native-oem-screen/live-phone-aoa-auth-stage.json)

## 오류 07과 과거 실폰 증거

공개 인증서의 원본 시간과 OpenSSL 종료 코드는 시도별 로컬 로그에 남겼다. [공개 DER 전체 실측](../../build/codex-authentication-resolution/public-certificate-check.log)

1. 과거 물리 USB 시험에서 AOA와 AAP 1.7에 도달했다. 초기 TLS 관측에는 폰의 ServerHello, Certificate, ServerKeyExchange, CertificateRequest, ServerHelloDone이 남았다. [초기 TLS 응답](../../build/gd13my-native-oem-screen/live-phone-aoa-auth-stage.json)
2. 별도 PC 진단은 명시적으로 자체 생성 시험 신원을 OpenSSL TLS 컨텍스트에 넣었다. USB로 클라이언트 플라이트 1,230바이트를 보냈다. 대응 Conscrypt 로그는 `verifyCertificateChain`에서 `Trust anchor for certification path not found`를 기록했다. PC의 최종 관측은 USB I/O 시간 초과였다. 원시 TLS 플라이트나 해당 시험 리프 지문을 남긴 자료는 확인하지 못했다. 과거 폰의 fatal alert 번호, 로컬 BearSSL 오류, CertificateVerify 송신 또는 검증은 이 기록으로 확정할 수 없다. [USB 진단 코드](../../build/gd13my-native-oem-screen/test-phone-debug-trust.py) · [USB 로그](../../build/gd13my-native-oem-screen/live-phone-usb-trust-root-cause.log) · [폰 로그](../../build/gd13my-native-oem-screen/live-phone-usb-trust-android.log)
3. 순정 WinCE 실폰 시험은 버전 교환 뒤 로컬 TLS 등록 자료 대기 상태를 기록했다. 이후 별도 ARM USB 재시험은 평문 버전 응답 불일치로 종료됐다. 두 기록 모두 WinCE가 GAL 인증서 디코딩에 실패한 뒤 대체 신원을 송신했다는 가설을 뒷받침하지 않는다. 기준 코드의 `configure()` 실패는 `handshake()` 호출을 건너뛴다. 인증서 탐색에서 지원하던 DER/PEM 확장자 선택과 TLS 신원 대체는 서로 다른 동작이다. [순정 WinCE UART](../../build/gd13my-native-oem-screen/live-phone-stock-menu.serial.log) · [ARM USB 재시험](../../build/gd13my-aa-deep-retest/real-arm-usb.jsonl)
4. 공식 DHU의 과거 성공과 자체 시험 인증서의 거부를 각각 기존 대조 기록으로 유지한다. 신뢰된 개발 신원으로 시험하기 전에는 해당 실폰에서 인증서 이후의 TLS, `AUTH_COMPLETE`, 서비스 탐색, 재연결을 판정할 수 없다. [기존 DHU 기록](../../build/gd13my-native-oem-screen/live-phone-visible.stderr.log)

제네시스 조사 인계서는 GAL 리프를 확정하지 못한 범위의 기록으로 사용했다. 이번에는 인증 실패를 설명할 수 있는 로컬 증거가 충분해 `G:\` 추가 스캔과 펌웨어 대조는 생략했다.

DeepSeek의 연결 성공률 추정과 Antigravity의 인증서 확장 보강 단독 해결 가설에는 대응하는 실폰 수락 결과가 없다. 이번 검증은 과거 시험의 체인 거부를 확인했으며, 신뢰된 신원 이후의 프로토콜 성공률은 미확인으로 둔다. [DeepSeek 요약](../DeepSeek-search/README.md) · [Antigravity 인계](../Antigravity-search/genesis-premium-gen2/FINAL_HANDOFF.md)
