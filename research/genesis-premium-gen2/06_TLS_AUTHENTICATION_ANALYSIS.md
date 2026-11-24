# 06_TLS_AUTHENTICATION_ANALYSIS.md: Android Auto TLS 및 인증 구조 정밀 분석

## 1. TLS 프로토콜 스택 및 역할 정의

Android Auto는 차량 헤드유닛과 스마트폰 간의 모든 제어 및 미디어 스트림을 TLS 1.2 암호화 터널 위에서 운용한다.

| 항목 | 제네시스 순정 구현 | GD13MY 기존 구현 (`src/ce/ce_aa_tls.c`) |
|---|---|---|
| **TLS 라이브러리** | OpenSSL 1.0.x / mbedtls 2.x | **BearSSL 0.6** |
| **헤드유닛 역할** | **TLS Client (클라이언트)** | **TLS Client (클라이언트)** |
| **스마트폰 역할** | **TLS Server (서버)** | **TLS Server (서버)** |
| **프로토콜 버전** | **TLS 1.2** (TLS 1.3 미지원 / 핸드셰이크 강제) | **TLS 1.2** |
| **주 협상 암호 스위트** | `TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256` (`0xC02F`) | `0xC02F` (`BR_TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256`) |
| **상호 인증 (mTLS)** | 필수 (폰이 `CertificateRequest` 전송) | 필수 구현 중 |
| **핸드셰이크 완료 신호** | TLS `Finished` 후 AAP `AUTH_COMPLETE` 전송 | 동일 |

---

## 2. 인증서 신뢰 체인 (Trust Chain) 및 오류 07 메커니즘 규명

### 2.1 폰과 헤드유닛의 공개 인증서 체인 구조

```
[스마트폰 인증서 체인 (Phone -> Headunit)]
  Root: Google Automotive Link Root CA
    └── Intermediate: Google Automotive Link Intermediate CA
          └── Leaf: CN=CarService (유효기간: ~2027년, Android OS 내부 발급)
               * 헤드유닛 수신기는 Google CA 공개키로 검증

[헤드유닛 인증서 체인 (Headunit -> Phone)]
  Root: Google Automotive Link Headunit Root CA (또는 Google 신뢰 OEM Root)
    └── Intermediate: Hyundai / LGE OEM Sub-CA
          └── Leaf: Headunit Client Certificate (기기/제조사 Leaf)
               * 폰(Android Auto App)의 X509TrustManager가 체인 검증
```

### 2.2 오류 07의 정확한 기술적 원인 (VERIFIED)
- **오류 증상**: 실물 폰 연결 시 `Trust anchor for certification path not found` 로그 출력 후 폰 화면에 "오류 07" 팝업 표시.
- **원인 분석**:
  1. 프로토콜 버전(AA 1.7), AOA 연결, TLS 1.2 암호 스위트(`0xC02F`) 협상까지는 완벽히 통과한다.
  2. 스마트폰이 `CertificateRequest`를 보내면 헤드유닛이 자신의 클라이언트 인증서 체인을 회신해야 한다.
  3. GD13MY의 자체 발급(Self-signed) 인증서는 Android OS 및 Google Android Auto APK 내부의 `TrustAnchor` 저장소에 루트 CA가 등록되어 있지 않다.
  4. Android의 `TrustManagerImpl.checkTrustedRecursive()` 함수가 PKIX 경로 구축에 실패하여 예외를 발생시키고 즉시 TLS 연결을 종료(Close Notify)한다.
  5. 따라서 오류 07은 **"TLS 스택 오류"나 "통신 패킷 오류"가 아니라 Google의 엄격한 X.509 PKIX 인증 체인 서명 검증 실패**이다 (`VERIFIED`).

---

## 3. 제네시스 순정 인증 자료 공급 구조

1. **키스토어 배포 메커니즘**:
   - `AppUpgrade` 바이너리 내부의 `:decrypt/genesis.keystore` 리소스 확인.
   - 업데이트 과정에서 `/common_data/upgrade/decrypt/genesis.keystore`로 전개.
   - 키스토어 내에 현대/제네시스 OEM 전용으로 Google Automotive Link 상위 인증기관에서 공인 서명된 인증서 체인과 기기 개인키가 탑재된다.
2. **비밀값 및 개인키 보안 경계**:
   - 순정 시스템에서는 개인키와 보안 자격 증명이 eMMC 보안 파티션 또는 전용 키스토어로 캡슐화되어 비인가 외부 접근이 차단된다.
   - 본 연구에서는 윤리 및 안전 원칙에 따라 비공개 개인키를 추출하거나 복제하지 않았으며, 공개 인증 구조와 체인 요구 조건만을 규명하였다.

---

## 4. GD13MY BearSSL 구현을 위한 기술적 권고사항

1. **DHU / 가상 스마트폰 환경**:
   - 공식 Google DHU(Desktop Head Unit) 2.0 또는 에뮬레이터 환경에서는 자체 인증서 테스트 옵션이 허용되므로, 현재 GD13MY의 BearSSL 0.6 및 자체 발급 인증서로도 정상적인 세션 완결 및 영상/오디오 스트리밍이 가능하다.
2. **실물 Google Android Auto 폰 연결을 위한 검증 경로**:
   - 별도 외부 기기/동글이나 루팅 없이 순정 Google Android Auto를 구동하려면, 폰의 Android Auto 앱이 신뢰하는 헤드유닛 인증서 체인 형식(Subject, Issuer, KeyUsage: `digitalSignature`, `keyEncipherment`, ExtendedKeyUsage: `clientAuth`)과 완벽히 부합하는 체인 공급 인터페이스가 필요하다.
   - BearSSL 0.6 자체는 메모리 30KB 미만으로 OMAP3530(WinCE 6.0)에서 `0xC02F` GCM 및 X.509 클라이언트 인증 체인을 온전히 처리할 수 있는 충분한 암호 성능을 갖추고 있음이 확인되었다.
