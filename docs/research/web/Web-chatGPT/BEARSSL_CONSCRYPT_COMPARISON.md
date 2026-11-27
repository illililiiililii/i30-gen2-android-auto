# GD13MY BearSSL vs Open Headunit 3.3.0 Conscrypt 기술 비교

- 범위: 인증서 출처·오류 07 반복 제외. 공개 소스 및 라이브러리 기술 자료 정적 비교만 수행.
- 비교 대상 고정: `open-headunit` **v.3.3.0**, commit `97a88ba3932b78de08e698b56a680c3e01364460`.
- GD13MY 소스: https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_tls.c
- OHU 고정본: https://github.com/andreknieriem/open-headunit/blob/v.3.3.0/app/src/main/java/com/andrerinas/openheadunit/aap/AapSslContext.kt

## 1. 구현 비교

| 항목 | GD13MY: BearSSL 0.6 | Open Headunit 3.3.0: JSSE/Conscrypt | 실제 추가 검증 포인트 |
|---|---|---|---|
| 역할 | `br_ssl_client_context` 클라이언트 | `SSLEngine.useClientMode=true` | 동일: 폰=서버. 역할 구현 중복 불필요 |
| TLS | `br_ssl_engine_set_versions(BR_TLS12, BR_TLS12)`로 TLS 1.2 고정 | `ConscryptInitializer.getProviderName()` 우선, `SSLContext.getInstance("TLS", provider)` 또는 기본 제공자. 프로토콜 고정 호출 확인되지 않음 | **실제 세션 버전/제공자** 계측. OHU가 항상 TLS 1.2만 광고한다고 단정 불가 |
| ClientHello | BearSSL full profile, `br_ssl_client_reset()`, 호스트/핀 구성 | JSSE 제공자 자동 구성. `createSSLEngine("android-auto",5277)`, `beginHandshake()` | 패킷에 제시한 cipher suites, signature_algorithms, supported_groups, SNI(유무) 기록 비교. 헤더 추측 금지 |
| 암호군 | BearSSL full-profile 기본 목록, TLS 1.2 범위. 협상값을 `engine->session.cipher_suite`로 로그 | Conscrypt/OpenSSL 계열 제공자 설정에 따른 목록, handshake 완료 후 engine session | GD13MY 이미 협상 suite 출력하므로 **기존 로그 사용**; 필요시 ClientHello만 별도 캡처 |
| client cert | `br_ssl_client_set_single_rsa()`와 유효성/키 일치 확인 | `SingleKeyKeyManager`가 X.509 + RSA PKCS#8을 KeyStore/KeyManager에 공급 | CertificateRequest `certificate_types` 및 `signature_algorithms`에 부합하는 신원 선택 여부. BearSSL 현재 RSA 한정 |
| 서버 인증서 | `br_x509_minimal_context` 신뢰 앵커 + 선택적 SHA256 pin + guest UTC 확인 | OHU 소스 `NoCheckTrustManager`가 server chain 검증을 건너뜀 | 보안 정책 차이. **GD13MY 검증 제거/우회 권장 금지** |
| TLS record split | `receive_record()`/`read_exact()`와 BearSSL sendrec/recvrec | `readAapMessage()`가 6B AAP 프레임을 정확히 읽고, `SSLEngine.unwrap()`이 `BUFFER_UNDERFLOW`면 추가 누적 | TLS record/AAP fragment **경계 다름**. 1 byte 분할, TLS 제어 전용 record, 누적 길이 제한 fixture |
| handshake state | `BR_SSL_SENDREC/RECVREC/SENDAPP/CLOSED`, 최대 256 step | `NEED_WRAP/NEED_UNWRAP/NEED_TASK/FINISHED/NOT_HANDSHAKING`, 15s deadline | 의미적 상태 비교. GD13MY는 횟수 제한은 있으나 OHU형 wall-clock 시간 제한 동일성 미확인 |
| 완료 판단 | `BR_SSL_SENDAPP` + 오류 없음 + 미소진 프레임 없음 | SSLEngine `FINISHED`/`NOT_HANDSHAKING`, 실제 handshake success | 둘 다 암호화 엔진 성공 판단 사용. Finished 암호학적 검증은 엔진이 함. 단순 trace의 CCS 확인을 성공으로 오인 금지 |
| AUTH_COMPLETE | `discover()`가 handshake 반환 이후 `AuthResponse(status=0)` 원시 AAP 프레임 전송 | OHU `AapTransport.handshake()`가 성공 후 Status OK 메시지 전송 | **TLS 완료 전 status 전송 금지**. 현 구현은 동일 순서로 보이나 실제 phone trace 필요 |

### 공식 라이브러리 자료
- BearSSL SSL API: https://bearssl.org/apidoc/bearssl__ssl_8h.html
- BearSSL 클라이언트 인증 및 체인: https://www.bearssl.org/x509.html
- BearSSL 버전/암호군: https://bearssl.org/support.html
- Conscrypt CAPABILITIES: https://github.com/google/conscrypt/blob/master/CAPABILITIES.md
- Conscrypt 프로젝트: https://github.com/google/conscrypt (BoringSSL 기반 TLS 제공자)
- OHU `SingleKeyKeyManager`: https://github.com/andreknieriem/open-headunit/blob/v.3.3.0/app/src/main/java/com/andrerinas/openheadunit/ssl/SingleKeyKeyManager.kt
- OHU `NoCheckTrustManager`: https://github.com/andreknieriem/open-headunit/blob/v.3.3.0/app/src/main/java/com/andrerinas/openheadunit/ssl/NoCheckTrustManager.kt
- OHU `AapTransport`: https://github.com/andreknieriem/open-headunit/blob/v.3.3.0/app/src/main/java/com/andrerinas/openheadunit/aap/AapTransport.kt

## 2. OHU에서 검증된 구체적인 경계 사례

1. `67bcae278418d75528b882567877f0e6ed4aa2ba`는 USB/TCP reader에서 버전 응답의 분할·병합, 뒤따르는 TLS 메시지 보존 및 malformed response 검사에 대한 수정이다. https://github.com/andreknieriem/open-headunit/commit/67bcae278418d75528b882567877f0e6ed4aa2ba
2. `ae83901e36ebad1765049202efcf001262566bde`는 TLS control-only 메시지로 plaintext가 비어도 AAP fragment의 LAST 의미가 없어지지 않게 하는 수정이다. https://github.com/andreknieriem/open-headunit/commit/ae83901e36ebad1765049202efcf001262566bde
3. `cfbd2cbb57bfac75d59b4894ddb7852b8d542fde`는 JSSE `NEED_TASK`만 진행된 unwrap도 정상 handshake progress로 인정하고 무진행 반복을 제한한다. https://github.com/andreknieriem/open-headunit/commit/cfbd2cbb57bfac75d59b4894ddb7852b8d542fde
4. `fbe128d0ceaf195a325751962546107c3bcba678`는 재접속 시 동글이 전달한 이전 세션의 encrypted envelope가 버전 교환에 섞이는 경우를 별도 처리한다. https://github.com/andreknieriem/open-headunit/commit/fbe128d0ceaf195a325751962546107c3bcba678
5. `06d7d33c9db10dff76d1ac669085dd42a0f569d2`는 nonzero 버전 status의 해석을 조정한다. 원인 재현 없는 GD13MY 선제 완화는 금지. https://github.com/andreknieriem/open-headunit/commit/06d7d33c9db10dff76d1ac669085dd42a0f569d2

## 3. GD13MY 함수별 검증 범위 (개발 전)

- `configure()` (대략 572–670): TLS1.2/RSA, 실제 호스트 이름·핀·시계·서버 인증 정책은 **이미 구현**. 단, `CertificateRequest`에서 서버가 허용하는 서명 알고리즘과 `CertificateVerify`를 위한 선택 결과를 실제 로그로 검증해야 함.
- `trace_records()`, `trace_handshake()` (대략 396–480): ClientHello, certificate, ChangeCipherSpec 로그 기능 **존재**. Finished 본문은 암호화되어 trace로 직접 식별되지 않음. `BR_SSL_SENDAPP` 진입과 인증된 암호화 데이터 송수신이 성공 기준.
- `receive_record()`/`secure_read_fragment()`/`secure_read()` (대략 673–888): AAP/TLS 경계, FIRST 총길이, 재조립 기능 **존재**. 특히 `secure_read_fragment()`에 **`if (!decoded) return -1`**가 있으므로 *유효한 TLS 제어 전용 레코드에 AAP 평문이 없을 때* false failure인지 회귀 fixture로 분리해야 함. 다만 실제 입력에서 이 상황이 발생했는지는 미확인.
- `handshake()` (984–1029): 완료 때 cipher suite 로깅 존재; 256-step 제한으로 무응답 벽시계 시간 상한이 확정되지 않음. 기존 USB read timeout 등과 함께 실제 시간 기준 관찰.
- `discover()` (909–953): AUTH_COMPLETE 후 Service Discovery 요청/응답. 전송 순서 이미 구현. 응답 시 영상-only 광고이므로 다른 채널 동작을 기대하지 않음.

## 4. 권고 실험 (실폰 인증이 해결되면)

| 우선순위 | 인풋 | 성공 기준 | 실패 시 판단 |
|---|---|---|---|
| P0 | ClientHello/ServerHello + Suite + 버전 | 합의가 TLS1.2 + 양측이 지원하는 suite | handshake 원인과 인증 문제 구분 |
| P0 | `CertificateRequest` 및 승인된 시험용 클라이언트 신원 | 사용된 RSA client cert/CertificateVerify 수용 후 application data | 신원/서명 알고리즘 불일치 여부 |
| P1 | split/coalesced AAP/TLS fixture, 0 plaintext control-only record | byte 누락 없이 framing 상태 유지 | `secure_read_fragment` 경계 및 empty LAST 분기 조사 |
| P1 | interrupted read/close/reconnect | 새로운 세션 수립 및 초기화된 기록 상태, 누수 없음 | 세션 간 정적 데이터/USB pipe 상태 오염 검증 |
| P2 | 실제 기록과 OHU provider 차이 | 차이가 재현 장애와 상관될 때만 원인 추적 | **라이브러리 교체는 보류** |

**미확인:** 실제 GD13MY/폰의 cipher suite·extensions 덤프, CertificateRequest 서명 알고리즘 전체, TLS Finished transcript, Conscrypt 제공자 런타임 정보. 따라서 호환성 성공을 단정할 수 없다.
