# Phase 8 — Open Headunit 릴리스 분석

기준일: 2026-11-25. 공개 GitHub API의 태그, 커밋, 파일 Blob 및 이슈 본문/댓글을 개별 조회했다. APK 실행, 실폰 연결, 로컬 GD13MY 재시험은 수행하지 않았다.

## 1. 릴리스별 공개 인증서

모든 아래 행에서 `app/src/main/res/raw/cert`의 Git Blob SHA-1은 `30a775b7683e4732eb246cb2dd3addb113ca39b5`로 동일하다. Git Blob SHA-1은 X.509 DER SHA-256과 다른 값이다. 각 ref를 별도로 조회했으며 main의 내용을 소급 적용하지 않았다.

| 태그/시점 | 정확한 커밋 | 인증서 변경 |
|---|---|---|
| 최초 확인 파일 이력, 2025-12-03 | 42fcd3895781d1ea95e29e25ed361b79917584e6 | 기준 |
| v1.2.1 | 0600b36d28611278b763d907200c772b457bb4eb | 없음 |
| v1.3.0 | 110350aff2d426fb0518e9c81b8790d2fbde9155 | 없음 |
| 2026-01-05 재작성 전 main | 21f6c68d389e46892d5fbdd36ca186592bc553ed | 없음 |
| v.1.5.0-alpha | 8494f992582e9ee5dc9b77945a79098626707d35 | 없음 |
| v.1.5.0 | d59d9e98ea1dc92219909ecd80804c0f796f9523 | 없음 |
| v.3.2.6 | e7a3b3ad5deac6d727e8ea8b0318ec4a6e5ac6e1 | 없음 |
| v.3.3.0 | 97a88ba3932b78de08e698b56a680c3e01364460 | 없음 |
| v.3.5.0-beta4 | 0cbff00432d13c164799fe2d20e79444be2c0983 | 없음 |
| v.4.0.0 | 5511654d0d01ec72db34f94befbcebcab3f8af23 | 없음 |
| v.4.1.0-beta1 | 216e016295ad561e621b55ac369816ee95b03e3e | 없음 |

공통 공개 인증서 속성(기존 GD13MY 분석의 DER 메타데이터와 이번 동일 Blob 조회를 연결): Subject C=US, ST=CA, L=Mountain View, O=Google-Android-Reference; Issuer C=US, ST=California, L=Mountain View, O=Google Automotive Link; serial 0x7653; RSA 2048; sha256WithRSAEncryption; 2014-07-08 22:49:18 UTC ~ 2044-07-07 22:49:18 UTC; DER SHA-256 E323CC6DD52D1F2A280360A0E92EFA04AB3664DD68FAB3DD187F03D663FEED6D. 이번 조사에서 DER SHA-256을 독립 실행하여 재계산하지는 않았다.

파일 경로 이력 API는 2025-12-03 커밋 한 건을 반환했다. 이는 해당 경로에서 확인된 최초 이력이며 원래 인증서의 최초 공개를 증명하지 않는다. 최신 API 릴리스는 4.1.0-beta1(2026-11-18), 이름상 최신 안정판은 4.0.0(2026-11-10)이다. API prerelease 플래그가 beta에도 false인 점에 주의한다.

원본 URL:
- https://api.github.com/repos/andreknieriem/open-headunit/commits?path=app/src/main/res/raw/cert&per_page=100
- https://github.com/andreknieriem/open-headunit/releases
- https://github.com/andreknieriem/open-headunit/blob/v1.2.1/app/src/main/res/raw/cert
- https://github.com/andreknieriem/open-headunit/blob/v.1.5.0-alpha/app/src/main/res/raw/cert
- https://github.com/andreknieriem/open-headunit/blob/v.3.3.0/app/src/main/res/raw/cert
- https://github.com/andreknieriem/open-headunit/blob/v.4.0.0/app/src/main/res/raw/cert
- https://github.com/andreknieriem/open-headunit/blob/v.4.1.0-beta1/app/src/main/res/raw/cert
- https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/Codex-authentication-resolution/RESEARCH_VALIDATION.md

정확한 커밋 링크는 https://github.com/andreknieriem/open-headunit/commit/ 뒤에 표의 전체 SHA를 붙이면 된다.

## 2. 실사용 사례

| 사례 | 폰/Android | AA | OHU | 결과 | 증거 |
|---|---|---|---|---|---|
| #387 2026-09-01 | S21 Ultra(최초 신고 기준), OS 미확인 | 17.4 | 3.3.0 | USB, 20분 통화 성공 및 H.265 동작 | 동일 리소스 및 소스 로딩 경로: 간접 |
| #908 2026-08-29 | Galaxy 계열 언급, 정확한 모델/OS 미확인 | 업데이트 직후 정확한 빌드 미확인, 17.4 논의 | 당시 정확한 버전 미확인 | USB 정상, 무선 실패 | 릴리스 특정 불가 |
| #1103 2026-10-12 | 폰 미확인; AVIN HU Android 13 | 미확인 | 3.5.0-beta4, 0cbff00432d1(신고 환경) | 여러 버전 USB 정상, Native 무선 실패 | beta4 리소스 동일, USB 시험 버전 미특정 |
| #1103 2026-10-22 | 동일 신고 환경 | 미확인 | PR #1106 시험 alpha | BT 수동 재연결 후 무선 성공 | APK/세션 인증서 미확인 |
| #14 2025-12-30 | Pixel 8 Pro, 업데이트 완료, OS 미확인 | 미확인 | 1.2.1 | USB 오류 07 | 리소스 동일, native 송신 신원 미확인 |
| #14 2026-01-04 | 동일 신고자 | 미확인 | 1.3.0 | USB 실패 지속 | 리소스 동일, native 송신 신원 미확인 |

#14의 Xiaomi 13T 추가 신고도 존재한다. 관리자는 1월 5일 SSL 재작성 alpha를 제시했으나 원 신고자의 성공 확인 없이 1월 13일 종료했다. #908에서 3.2.4/3.2.6은 별도 동글 인식 실패 테스트에 등장한다. 이를 직접 USB 폰 성공 버전으로 연결하면 안 된다. #1103은 OEM Bluetooth 서비스 접근 개선과 무선 성공의 연관성을 보여주지만 인증서 변경 근거는 아니다.

- https://github.com/andreknieriem/open-headunit/issues/387#issuecomment-5499478056
- https://github.com/andreknieriem/open-headunit/issues/908
- https://github.com/andreknieriem/open-headunit/issues/908#issuecomment-5463637725
- https://github.com/andreknieriem/open-headunit/issues/1103
- https://github.com/andreknieriem/open-headunit/issues/1103#issuecomment-6335227998
- https://github.com/andreknieriem/open-headunit/pull/1106
- https://github.com/andreknieriem/open-headunit/issues/14
- https://github.com/andreknieriem/open-headunit/issues/14#issuecomment-3711887602
- https://github.com/andreknieriem/open-headunit/issues/14#issuecomment-3743917401

판정: 3.3.0 소스에서 해당 공개 인증서를 읽는 경로까지 확인했으므로 기존보다 강한 간접 증거다. 하지만 배포 APK와 실제 송신 인증서 지문이 없으므로 직접 증거가 아니다. 오류 07의 해결 원인이 인증서 변경이었다는 가설은 확인된 리소스 이력으로 지지되지 않는다. 초기 native 경로의 실제 인증서가 같았는지는 별도 확인 사항이다.

## 3. SSL 엔진 재작성

핵심 커밋:
- https://github.com/andreknieriem/open-headunit/commit/564c74a4151481d32955dec6ce00b14bd2d0e3f4 (엔진 선택 변경 및 상태 관리)
- https://github.com/andreknieriem/open-headunit/commit/d9be7e3329f836fdc940be4bcb7aa54498c39b72 (JNI/OpenSSL 정리)
- https://github.com/andreknieriem/open-headunit/commit/8494f992582e9ee5dc9b77945a79098626707d35 (alpha 태그)

| 항목 | 재작성 전 21f6c68 | alpha 8494f99 | 3.3.0 97a88ba |
|---|---|---|---|
| 엔진 | AapSslNative; crypto_1_1/ssl_1_1/hu_jni | AapSslContext, Java SSLEngine | SSLEngine, Conscrypt 우선 기본 provider 대체 |
| TLS 버전 설정 | native 내부 미확인 | SSLContext TLSv1.2 | SSLContext TLS, 실제 협상 버전 미확인 |
| ClientHello/암호군 | 캡처 없음 | provider 기본 동작, 실제 목록 미확인 | provider/device 의존, 실제 목록 미확인 |
| 체인 | native 신원 미확인 | SingleKeyKeyManager의 단일 리프 | 동일 소스 구조 |
| 상태 | 고정 2회 송수신 | NEED_WRAP/UNWRAP/TASK, 최대 20회 | performHandshake, 15초 deadline |
| 레코드 | 한 번 recvBlocking 후 6바이트 제외 | 반복 unwrap, underflow 보존 미확인 | AAP 헤더/페이로드 읽기 및 pendingTlsData 누적 |
| CertificateRequest | native 내부 미확인 | provider KeyManager | provider KeyManager |
| AUTH_COMPLETE | 고정 루프 후 statusOk | 엔진 상태 종료 및 reset 후 statusOk | performHandshake 성공 및 reset 후 statusOk |

3.3.0의 SSLEngine 생성은 일정한 캐시 키를 사용한다. 재개 가능성을 염두에 둔 구현이며 실제 세션 재개 성공은 미확인이다. 3.3.0의 구체적인 TLS 협상 버전 및 암호군을 Java SSLContext 이름으로 단정하지 않는다. 로컬 상대 인증 정책이 GD13MY와 다르지만 상대방 검증 약화는 폰이 헤드유닛을 수락하는 문제를 해결하지 않으므로 변경 대상으로 삼지 않는다.

원본 코드:
- https://github.com/andreknieriem/open-headunit/blob/21f6c68d389e46892d5fbdd36ca186592bc553ed/app/src/main/java/com/andrerinas/headunitrevived/aap/AapTransport.kt
- https://github.com/andreknieriem/open-headunit/blob/v.1.5.0-alpha/app/src/main/java/com/andrerinas/headunitrevived/aap/AapSslContext.kt
- https://github.com/andreknieriem/open-headunit/blob/v.1.5.0-alpha/app/src/main/java/com/andrerinas/headunitrevived/aap/AapTransport.kt
- https://github.com/andreknieriem/open-headunit/blob/v.3.3.0/app/src/main/java/com/andrerinas/openheadunit/aap/AapSslContext.kt
- https://github.com/andreknieriem/open-headunit/blob/v.3.3.0/app/src/main/java/com/andrerinas/openheadunit/aap/AapTransport.kt
- https://github.com/andreknieriem/open-headunit/blob/v.3.3.0/app/src/main/java/com/andrerinas/openheadunit/ssl/SingleKeyKeyManager.kt

## 4. GD13MY와 비교 및 Codex 후속 작업

GD13MY 기존 코드의 `src/ce/ce_aa_tls.c`는 BearSSL 상태 기반 진행, TLS 1.2, AAP 및 TLS 분할 처리, 인증 후 discover 경로를 구현한다. 따라서 이 기능을 재작성할 근거가 없다. 다음 검증은 프로젝트가 사용할 권한이 있는 평가 신원 또는 합성 시험 신원으로 수행한다.

1. 공개 인증서 메타데이터 증거를 보존하고 DER SHA-256을 독립 재계산한다. 개인키는 수집하거나 복제하지 않는다. 배포 APK가 확보되면 공개 인증서 리소스만 소스와 비교한다.
2. `ce_aa_tls.c`의 `handshake()` 기존 로그와 합성 피어 시험을 재사용한다. USB 단축 읽기, 여러 TLS 레코드의 한 AAP 메시지 포함, AAP 메시지 사이로 분리된 TLS 레코드, 무응답 및 실패 후 정리를 검증한다. 기존 회귀로 충족되면 중복 추가하지 않는다.
3. 공식 DHU 및 승인된 평가 신원의 실폰 시험에서 TLS 버전, 협상 결과와 실패 단계를 기록한다. 공개 인증서 리소스와 실제 송신 지문은 혼동하지 않는다. 승인된 신원의 송신 지문과 Android 로그를 대응시킨다.
4. AUTH_COMPLETE가 엔진의 실제 애플리케이션 데이터 가능 상태 이후에만 송신되는 기존 조건을 회귀 확인한다. 이미 구현된 Service Discovery, 영상 및 재연결을 재사용한다.
5. 동일한 승인된 신원으로 USB와 가상 피어를 비교하고, 실패 원인이 레코드 처리인지 인증 정책인지 분리한다. TLS 라이브러리 교체는 동일 조건에서 재현된 엔진 결함이 입증되기 전에는 보류한다.

원본: https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_tls.c

## 5. 미확인 사항 및 한계

- 최초 파일 이력 이전의 원래 공개 시점 및 출처.
- 초기 JNI 경로의 실제 송신 인증서와 실제 TLS 설정.
- 1.5.0-alpha 이후 #14 최초 신고자의 성공 여부.
- 모든 중간 태그를 전수 조회하지 않았으며 파일 경로 이력과 선정 ref를 검증했다.
- 4.0.0/4.1.0-beta1의 TLS 코드 전수 비교는 수행하지 않았다.
- 배포 APK 원본, 첨부 로그 파일 실제 내용, 실폰 TLS 캡처는 확보하지 않았다.
- 실제 ClientHello 확장, 암호군 순서, CertificateRequest, CertificateVerify 및 Finished의 세션 관측은 미수행이다.
- 인증서 리소스 동일성은 사용 권한 또는 폰의 수락을 보장하지 않는다.

결론: 동일 공개 인증서가 오류 신고 버전, SSL 재작성 alpha, AA 17.4 USB 성공 보고 버전과 최근 안정판에 모두 포함된다. 실제 송신 신원과 최초 오류 원인은 확정할 수 없다. 현재 근거는 BearSSL 교체보다 승인 신원으로 수행하는 단계별 검증 및 기존 상태/분할 처리 회귀 확인을 지지한다.
