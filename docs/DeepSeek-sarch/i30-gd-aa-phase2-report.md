# i30 GD13MY Android Auto — 저장소 실물 검토 · 인증서 판정 · WinCE 에뮬레이터 보고서

2차 보고서 · 작성일 2026-11-24 · 대상 저장소 `illililiiililii/i30-gen2-android-auto` (main, 151 blobs)

이 문서는 1차 보고서(`i30-gd-aa-error07-research.md`, A~F)를 **실물 저장소 확인 결과로 갱신**한 것이다. 1차 보고서의 D절 제안 중 상당 부분은 이 저장소에서는 이미 구현되어 있거나 불필요하다. 충돌하는 부분은 이 문서가 우선한다.

### 근거 등급
- **[검증]** 파일·로그·문서 원문을 직접 열어 확인
- **[부분검증]** 요약·일부 본문·검색 스니펫만 확인(전문 미확인)
- **[추정]** 공개 근거 기반 추론, 실측 없음

### 이 문서의 결론 3줄
1. **오류 07의 원인은 헤드유닛 인증서 체인이다.** TLS 버전·암호 스위트·전송 계층 문제가 아니다.
2. **저장소에 남은 조치는 하나 — 폰이 신뢰하는 GAL 체인을 가진 헤드유닛 신원으로 교체하는 것.** wolfSSL 이식은 불필요하다(BearSSL 0.6으로 이미 TLS 1.2/`0xC02F` 동작).
3. **WinCE 6.0 + ARMv6을 정확히 겨냥한 턴키 에뮬레이터는 없지만, 이 저장소는 이미 자체 에뮬레이터로 순정 커널을 메뉴까지 부팅시켰다.** 남은 병목은 에뮬레이터가 아니라 인증서다.

---

# 1. 판정: 오류 07은 인증서 게이트다

## 1-1. 근거 4개 (모두 저장소 내부 자료)

| # | 근거 | 원문 위치 | 무엇을 증명하는가 |
|---|---|---|---|
| 1 | 실폰 로그: 헤드유닛 TLS ClientHello → 폰의 ServerHello/Certificate/ServerKeyExchange/CertificateRequest/ServerHelloDone 관측 → 자체 발급 HU 인증서 전송 → 폰이 **`Trust anchor for certification path not found`** 기록 → USB 응답 대기 중 시간 초과 | `docs/ANDROID_AUTO_AUTH_STATUS.md` | TLS 협상은 성립 단계까지 갔고, **인증서 검증 단계에서 폰이 끊었다**. `UNSUPPORTED_PROTOCOL`이 아니다. |
| 2 | 같은 폰 + 같은 케이블 + 공식 DHU 2.0 → **AA 1.7 / TLS 1.2 / `ECDHE-RSA-AES128-GCM-SHA256`(0xC02F) / 인증서 검증 성공 / 800×480 영상**, 반복 10회 전부 통과 | `docs/USB_CONNECTION_TEST.md`, `docs/ANDROID_AUTO_AUTH_STATUS.md` | 폰·케이블·프로토콜·암호 스위트는 **정상 기준선**이 존재한다. 즉 이 세 요소는 용의선상에서 제외된다. |
| 3 | CE ARM 수신기가 **시험 CA + 시험 피어**로 상호 TLS → `AUTH_COMPLETE` → 암호화 서비스 탐색 → 정상 종료까지 통과 | `docs/CE_PORTING_STATUS.md`, `src/ce/ce_aa_tls.c` | 구현 결함이 아니다. 같은 코드가 신뢰 관계만 맞으면 끝까지 간다. |
| 4 | 개발자 서버(TCP 5277) 경로에서도 **같은 시험 신원으로 연결이 닫히고 화면에 오류 07** 표시 | `docs/ANDROID_AUTO_AUTH_STATUS.md` | USB/AOA 계층을 우회해도 07이 재현된다 → 원인은 전송 계층이 아니라 **신원**이다. |

**결론: 4개 근거가 서로 다른 계층(USB / TCP / CE 코드 / 폰 로그)에서 같은 지점을 가리킨다.**

## 1-2. 반증 검토 — 다른 가설은 왜 아닌가

| 가설 | 반증 근거 | 판정 |
|---|---|---|
| TLS 1.2 미지원 (1차 보고서의 `UNSUPPORTED_PROTOCOL` 프레임) | 이 저장소는 그 오류를 관측한 적이 없다. BearSSL 0.6으로 TLS 1.2, `0xC02F`까지 협상됨 | **기각** |
| 암호 스위트 불일치 | DHU와 동일 스위트(`0xC02F`)를 CE 수신기가 사용 | **기각** |
| USB AOA 구현 결함 | 실폰에서 AOA 2 전환·재열거·bulk 개방·AA 1.7 버전 응답까지 확인 | **기각**(버전 단계까지) |
| CE 게스트 시계 오류로 인증서 만료 판정 | 초기 게스트가 1601년을 읽은 것은 사실이나, 이후 `SetSystemTime`으로 호스트 UTC 동기화 완료 | **해결됨**(단, 회귀 주의) |
| 폰 인증서 검증(역방향) 실패 | `i30-ca.pem` + `i30-peer.txt`/`i30-peer-sha256.txt`로 CA·이름·지문 핀 구현, ARM 시험에서 정상/거부 경로 모두 확인 | **기각** |
| 2025년 Play Services `25.34.34` 회귀 | 해당 이슈는 기존에 정상 동작하던 완제품 헤드유닛이 갑자기 07이 된 사례. 이 프로젝트는 **처음부터 07**이며, 같은 폰에서 DHU는 통과 | **무관**(단, 향후 정책 변동 리스크로 별도 관리) |

## 1-3. 남은 미지수
- 폰이 **GAL 루트로 체인되지 않은 신원**을 거부한다는 것은 확인됐다.
- 확인되지 않은 것: **GAL 체인을 가진 신원을 폰이 실제로 수락하는지.** 저장소는 이 시도를 아직 하지 않았다.
- 따라서 다음 시도는 "또 하나의 실험"이 아니라 **마지막 게이트를 여는 단일 시험**이다.

---

# 2. 저장소 실물 구조

## 2-1. 규모
- `main` 트리 151 blob, 문서 30여 개, `src/ce`(ARM/C), `src/i30_receiver`(PC/Python), `tools/`(에뮬레이터·이미지 빌더), `build/`(증거 로그) 구조.
- 문서가 코드보다 많다. 즉 **이 프로젝트의 자산은 코드보다 "무엇이 어디까지 됐는지에 대한 증거"**다. 이 보고서도 그 증거를 기준으로 판정했다.

## 2-2. 핵심 문서 지도

| 문서 | 역할 | 이 보고서에서 쓴 정보 |
|---|---|---|
| `docs/ANDROID_AUTO_AUTH_STATUS.md` | 실폰 인증 실패 단계, DHU 대조 | `Trust anchor ... not found`, DHU 10회 성공, 07 재현 |
| `docs/CE_PORTING_STATUS.md` | CE ARM 구현 상태·시험 항목 | BearSSL 0.6, AUTH_COMPLETE, 파일 규약, UTC, 오류 구분 |
| `docs/EMULATOR_ARCHITECTURE.md` | 자체 에뮬레이터 구조 | Unicorn Cortex-A8, 256MiB RAM, MUSB, DISPC, DiskA |
| `docs/GD13MY_EMULATION.md` | 순정 커널 메모리 맵·부팅 실험 | OEM 테이블, `0x8000aadc`, F2/터치/MICOM 조작 |
| `docs/CE_EMULATION_FEASIBILITY.md` | 에뮬레이터 후보 비교 | Device Emulator/QEMU/CERF/Unicorn 실측 결과 |
| `docs/PHASE7_8_RESULTS.md` | 최신 시험판 실행법 | `run_gd13my_phase78.ps1`, USB 포트 지정, 실폰 버전 응답 |
| `docs/USB_CONNECTION_TEST.md` | USB 단계별 판정 기준 | DHU 반복 10회, WinUSB 바인딩 이슈 |
| `docs/FIRMWARE_PACKAGING.md` | APP 이미지 패키징 | `DiskA` 119파일, 해시·매니페스트 |
| `docs/CE_NATIVE_DISPLAY_INTEGRATION.md` | 순정 화면 통합 | `GetDCEx` 형제 창 클리핑, 800×480 투사 창 |

## 2-3. 코드 자산

| 경로 | 실체 | 상태 |
|---|---|---|
| `src/ce/ce_aa_tls.c` | CE용 AAP+TLS 수신기 (BearSSL 0.6) | 32,938 B. 상호 TLS, 피어 핀, `AUTH_COMPLETE`, 서비스 탐색, 오류 매핑 구현 |
| `src/ce/ce_aa_video.c` | ARM H.264 Baseline 디코더 + GDI 출력 | 800×480 BGRA, `StretchDIBits` 검증 |
| `src/ce` (USB) | 순정 `usbd.dll` 위 AOA 클라이언트 | AOA 1.7 버전 응답까지 실폰 확인 |
| `src/i30_receiver` | PC 기준 구현(Python) | TLS·서비스·H.264·오디오·입력·재접속 시험 통과 |
| `tools/emulate_gd13my.py` | 자체 에뮬레이터 | 순정 CE 커널 → 순정 내비 메뉴까지 |
| `tools/run_gd13my_virtual_phone.ps1` | 가상 폰 시험 | TLS 상호 인증 + H.264 + LCD 3픽셀 검증 |

## 2-4. 이미 검증된 것 / 미검증 (혼동 방지)

**검증됨**
- AOA 2 전환, 재열거, bulk 개방, **AA 1.7 버전 응답** (실폰)
- 순정 CE 커널 부팅 → 순정 내비 메뉴 → 설정 화면 (에뮬레이터)
- CE ARM에서 **시험 CA로** 상호 TLS · `AUTH_COMPLETE` · 암호화 서비스 탐색 · 종료
- CE ARM에서 암호화 H.264 수신 → 디코딩 → GDI 표시(LCD 3점 확인)
- 폰 인증서 검증: 올바른 체인 통과, 지문 불일치·미신뢰 CA 거부

**미검증**
- **실폰이 수락하는 헤드유닛 신원** (이 문서의 핵심)
- 실폰 구간에서의 CE TLS 완주 (현재는 인증서에서 끊김)
- 지속 세션(8초 Attach 한도 밖), 후진·경고 선점 실차 연동
- 순정 Bluetooth/오디오 포커스 실측

---

# 3. 인증서 계층 분석

## 3-1. AAP/TLS 구조 (확정)

```
[폰]  ── USB(AOA) 또는 TCP 5277 ──  [헤드유닛]
  │                                      │
  ├─ 채널0 메시지3 = ENCAPSULATED_SSL ──▶│   ← TLS 레코드를 그대로 운반
  │                                      │
  │  TLS 1.2 상호 인증 (폰=서버, HU=클라이언트)
  │◀────────── ClientHello ──────────────┤
  ├─────────── ServerHello ─────────────▶│
  ├──── Certificate(CarService leaf) ───▶│
  ├──── CertificateRequest ─────────────▶│   ← HU에 클라이언트 인증서 요구
  │◀──── Certificate(HU 신원) ───────────┤   ★ 여기서 폰이 검증
  │◀──── ClientKeyExchange .. Finished ──┤
  │                                      │
  │◀──── AUTH_COMPLETE(status) ──────────┤   ← 평문, 0=수락 / -3 / -23 / -24
  │◀──── 암호화된 서비스 탐색 ────────────┤
```

핵심 두 가지:
- **검증 방향**: 07은 "폰이 헤드유닛을 검증"하는 방향에서 발생한다. 헤드유닛이 폰을 검증하는 설정(`SSL_VERIFY_NONE`, trust-all)을 아무리 느슨하게 해도 07은 사라지지 않는다.
- **앵커 단일성**: 폰의 신뢰 저장소에는 `O=Google Automotive Link` 루트가 들어 있고, 헤드유닛 인증서는 여기로 체인되어야 한다. 자체서명·사설 CA·타사 OEM 인증서는 거부된다.

## 3-2. DHU 2.1 인증서 실측

`iscle/android-auto-certificates`의 `dhu/2.1/certificate.pem`을 DER로 직접 디코드한 결과:

| 항목 | 값 | 의미 |
|---|---|---|
| 서명 알고리즘 | `sha256WithRSAEncryption` (1.2.840.113549.1.1.11) | BearSSL/RSA-2048 경로와 호환 |
| 버전 | **X.509 v1, 확장 없음** | EKU(`clientAuth`)·keyUsage·basicConstraints 부재 → 클라이언트 인증서로 그대로 사용 가능 |
| serial | `0111` | iscle `metadata.json`의 serial과 일치 |
| 유효기간 | 2014-07-04 00:00:00 -0700 ~ **2048-08-01 10:21:23 -0700** | 폰 cert(2027년경)보다 훨씬 길다 |
| 공개키 | RSA-2048 | `br_ssl_client_set_single_rsa` 계열과 정합 |
| subject | `C=US, ST=California, L=Mountain View, O=Android-Auto-Internal, OU=01` | [부분검증] metadata/AARE 문서 기준 |
| issuer | `O=Google Automotive Link` | GAL 루트로 체인됨 |
| kind | `desktop-head-unit` | 공식 DHU 배포물 |

**왜 이 인증서가 후보인가**: 취미 개발자가 정당하게 손에 넣을 수 있는 **GAL 발급 체인**은 사실상 이것뿐이다. Android SDK에 포함된 DHU가 스스로를 증명하는 데 쓰는 신원이며, 공개 배포물이다.

**왜 이것이 "해결책"은 아닌가**: 이 신원은 **Google이 개발자 테스트용으로 배포한 것**이고, 사용자에게 "당신의 헤드유닛 신원으로 써도 된다"고 허여한 것이 아니다. 제품·배포·판매 경로에 쓰면 안 되고, Android SDK 라이선스 범위도 별도 확인 대상이다. 저장소 자체 문서도 "개인용 공개 발급 절차는 확인하지 못했다"고 더 보수적으로 적고 있다. 즉 **개인 차량 1대 검증용 실험**으로 한정해야 한다.

## 3-3. 자체서명이 실패한 정확한 이유

폰 로그의 문자열은 `Trust anchor for certification path not found`다. 이는 Android `TrustManager`/`X509TrustManager` 계열에서 **체인을 만들 앵커를 찾지 못했을 때** 나오는 메시지다.

- 서명 검증 실패(`Signature does not match`)도 아니고
- 이름 불일치(`No subject alternative names`)도 아니고
- 만료(`Certificate expired`)도 아니고
- **"앵커 없음"** 이다. 즉 폰은 자체서명 인증서를 "검증 불가"로 판정한 게 아니라, **애초에 신뢰 목록에 없는 루트에서 시작하는 체인**이라 경로 탐색 자체를 실패시켰다.

이 구분이 중요한 이유: 앵커 문제는 **신원 교체만으로 해결**되지만, 서명·이름·만료 문제였다면 키 교체·SAN 추가·시계 수정이 각각 필요하다. 로그가 앵커 문제라고 말하고 있으므로 조치도 하나로 좁혀진다.

---

# 4. 적용 절차 — 저장소 코드 기준

## 4-1. 파일 배치

게스트 경로 `\DiskA\Application\NAVI\`:

| 파일 | 내용 | 주의 |
|---|---|---|
| `i30-client.pem` (또는 `.der`) | DHU `certificate.pem` **leaf 단독** | 중간 CA를 여기 끼우면 체인 순서가 깨진다. 최대 4장까지 허용되지만 **1장이 정답** |
| `i30-client-key.pem` | DHU `private-key.pem` | PKCS#8 `PRIVATE KEY` 그대로 허용(코드가 `RSA PRIVATE KEY`도 함께 인식). 변환 불필요 |
| `i30-ca.pem` (또는 `.der`) | GAL 루트 공개 인증서 | 저장소 문서상 폰 체인에서 이미 확보 |
| `i30-peer.txt` **또는** `i30-peer-sha256.txt` | 폰 `O=CarService` 예상 이름 또는 SHA-256 지문 | 둘 중 하나만. 두 방식 모두 CA 검증을 거친다 |

로더 동작(코드 확인):
- 같은 이름의 `.der`가 있으면 `.pem`보다 먼저 읽는다 → **기존 시험용 `.der`가 남아 있으면 교체가 무시된다.** 반드시 함께 지우거나 갱신할 것.
- `i30-client.pem`의 체인 최대 4장(`CLIENT_CHAIN_MAX 4`).
- 인증 자료는 배포 이미지에 포함되지 않는다(런타임 주입 방식).

## 4-2. 시계

- 과거 게스트가 부팅 시각을 **1601-01-01 UTC**로 읽은 이력이 있다. 이 상태에서는 DHU 인증서(2014~)도 만료로 판정될 수 있다.
- 현재 표준 실행기는 시스템 관리자 시작 시 **호스트 UTC를 `SetSystemTime`으로 주입**하고, 전원 재시작마다 다시 읽는다.
- 주의: 에뮬레이터 스냅샷/저장 상태를 오래 보관하면 게스트 시계가 뒤처질 수 있다. **시험 전 게스트 UTC를 로그로 1회 확인**하는 습관이 필요하다.

## 4-3. 이미지 매니페스트

- APP 이미지 빌더는 파일 SHA-256을 `image.json`에 기록하고 실행 시 대조한다.
- 인증 파일을 넣거나 바꾸면 **매니페스트 재생성**이 필요하다. 안 하면 무결성 검사에서 걸려 실행 전에 멈춘다.

## 4-4. A/B 시험 절차 (5단계)

| 단계 | 조작 | 통과 기준 | 실패 시 의미 |
|---|---|---|---|
| 1 | 인증 파일 없이 부팅 | "신뢰 설정 없음 → 버전 교환 뒤 파이프 정리" 로그 | 기준선 확보 실패 → 빌드 문제 |
| 2 | DHU 신원 + GAL 루트 주입, 폰 없이 PC `s_server` 상대 | TLS 1.2, `0xC02F`, ClientHello에 client cert 포함 | BearSSL 설정/체인 순서 문제 |
| 3 | 실폰 USB 연결 | `AUTH_COMPLETE` 로그 출력 | 07 지속 → 4단계 판정 |
| 4 | 실폰 + `i30-peer-sha256.txt` 핀 | 폰 인증서 지문 일치 로그 | 지문 불일치 → 폰 cert 교체 시점 확인 |
| 5 | 암호화 서비스 탐색 | `encrypted service discovery request received` | 채널/프레이밍 문제 |

## 4-5. 로그 문자열 → 원인 → 조치

`ce_aa_tls.c`의 `handshake_error()`가 남기는 문자열을 그대로 판정표로 쓴다.

| 로그 | 코드 | 원인 | 조치 |
|---|---|---|---|
| `phone rejected the head unit certificate chain (unknown CA)` | TLS alert **48** | 폰이 HU 신원 거부 | DHU 신원 교체가 실제로 적용됐는지, `.der` 잔재·매니페스트 확인 |
| `phone certificate chain has no trusted anchor` | `BR_ERR_X509_NOT_TRUSTED` | HU가 폰을 못 믿음 | `i30-ca.pem` 내용 확인(루트인지, 중간 CA인지) |
| `phone certificate fingerprint does not match` | `BR_ERR_X509_NOT_TRUSTED` + `pinned.rejected` | 지문 핀 불일치 | 폰 교체/업데이트 여부 확인 후 지문 갱신 |
| `phone certificate rejected at guest UTC` | `BR_ERR_X509_EXPIRED` / `TIME_UNKNOWN` | 게스트 시계 | 호스트 UTC 동기화 확인 |
| `phone certificate hostname does not match` | `BR_ERR_X509_BAD_SERVER_NAME` | `i30-peer.txt` 이름 오타 | `O=CarService` 실제 값으로 수정 |
| `TLS cipher suite rejected` | `BR_ERR_BAD_CIPHER_SUITE` | BearSSL suite 미설정 | `br_ssl_client_init_full` suite 목록 확인 |
| `TLS protocol version rejected` | `BR_ERR_UNSUPPORTED_VERSION` | 버전 협상 | 폰 AA 버전/서버 정책 확인 |
| `USB write interrupted` / 무응답 | - | MUSB 0바이트 DMA, 8초 한도 | 단축 패킷 허용 이미지, Attach 수명 관리 |

---

# 5. 실패 시 분기 (미리 정해둘 것)

| 관측 | 해석 | 다음 행동 |
|---|---|---|
| `unknown CA`가 **사라지고** `AUTH_COMPLETE` 도달 | 인증서 게이트 통과 | P2(서비스/영상)로 진행 |
| `unknown CA` **지속** (DHU 신원인데도) | 폰이 DHU 신원 자체를 정책으로 차단 | 구글 AA 앱 경로 종료 → AARE(폰 앱 대체) 또는 동글 경로 |
| TLS는 끝나는데 `AUTH_COMPLETE` -3 | HU가 폰 cert를 거부(방향 반대) | `i30-ca`/핀 점검 |
| TLS 완료 후 즉시 끊김 | 세션 수명/Attach 8초 한도 | 지속 세션 스레드 소유권 재설계 |
| 인증은 되는데 영상 없음 | 서비스 광고/포그라운드 권한 | `I30.GD13MY.VideoSurface.1` 권한 확인 |

**중요**: 07이 사라지지 않더라도 그 자체가 정보가 된다. "DHU 신원도 거부"라면 이는 개인 구현으로 뚫을 수 없는 **정책 경계**이며, 그때는 AARE/동글로 목표를 전환하는 것이 합리적이다.

---

# 6. WinCE 6.0 / ARM 에뮬레이터 조사

## 6-1. 먼저 정정할 전제

- **Cortex-A8은 ARMv6이 아니라 ARMv7-A다.** ARMv6은 ARM1136/ARM1176(i.MX31, OMAP2420, BCM2835/RPi1) 계열이다. GD13MY가 Cortex-A8 계열이라면 "ARMv6 에뮬레이터"를 찾는 것 자체가 목표를 좁게 잡은 것이다.
- **CE6 애플리케이션은 보통 ARMV4I로 컴파일된다.** 즉 "앱 로직 검증"에는 ARMv6/ARMv7 정확도가 거의 필요 없다. 이 사실이 선택지를 크게 넓힌다.
- 실제 병목은 명령어 집합이 아니라 **보드 모델**(메모리 맵, DISPC, MUSB, MICOM, HSMMC)이다. 이 저장소가 자체 에뮬레이터를 만든 이유도 그것이다.

## 6-2. 후보 비교

| 에뮬레이터 | 에뮬레이트 대상 | CE6 | ARMv6 정확도 | 준비물 | 난이도 | 판정 |
|---|---|---|---|---|---|---|
| **자체 에뮬레이터(이 저장소)** | GD13MY 보드(OMAP 계열) | **O (순정 커널 부팅)** | 해당 없음(보드 정확) | 저장소 + 순정 BIN | - | **실사용 1순위.** 이미 메뉴까지 감 |
| **MS Device Emulator 3.0 + PB6 `DeviceEmulator` BSP** | 가상 보드, **ARMv4I 명령어 수준** | **O (공식)** | ✗ | VS2005+PB6, CE6 ISO | 하 | CE6 앱 바이너리 그대로 실행. 공식 경로 |
| **CERF (`gweslab/cerf`)** | WinCE 범용 + 보드 프로필 | **O (커널 인식 확인)** | O (JIT: ARMv4~v7-A/Thumb-2/VFP/NEON) | 릴리스 바이너리 | 중 | **보조 1순위.** `omap_3530_evm`으로 진입까지 확인됨 |
| **QEMU + `Milek7/wince-qemu`** | vexpress-a15 (**ARMv7-A**) | ✗ (CE7) | ✗ | 릴리스 이미지 + 스크립트 | 하 | 검증된 최신 경로. AAP/TLS 검증엔 충분 |
| **QEMU + CE6 `TI SDP2420` BSP** | OMAP2420 (**ARM1136 = ARMv6**) | O (BSP 내장) | **O** | PB6 + QEMU ≤9.1 `n800` | **상** | 이론상 유일한 "정확한 ARMv6" 경로, BSP 포팅 필수 |
| **`Teulis/zunehd-emu`** | Tegra APX 2600(ARM11) + Zune HD 펌웨어 | **O (재고 펌웨어 부팅)** | O | QEMU 오버레이 + NK.bin | 상 | "CE6 ARMv6이 에뮬레이터에서 돈다"는 존재 증명 |
| **Unicorn (PE 단위)** | CPU만 | ✗(API 모의) | - | Python | 하 | 진단 PE 단위 시험에 이미 사용 중 |
| ARM Fast Models / Simics / Imperas | 상용 가상 플랫폼 | O | O | 고가·NDA·BSP 필요 | 상 | 개인 프로젝트 비현실 |

## 6-3. CE6 공식 BSP에 ARM11 계열이 있었다

- CE6 문서의 BSP 장은 `Device Emulator`, `Intel PXA27x(MainstoneIII)`, `TI OMAP5912 Aruba`, `TI SDP2420`, `VoIP PXA270` 등을 다룬다. [부분검증: *Windows Embedded CE 6.0 Fundamentals* Ch.5]
- `SDP2420` = OMAP2420 = **ARM1136(ARMv6)**. 즉 "CE6 + ARMv6" 조합은 개념적으로 존재했고, QEMU `n800`이 그 SoC를 모델링한다. [부분검증]
- 단, PB6 설치 목록에서 실제 BSP 항목명을 눈으로 확인한 것은 아니다. **PB6 ISO가 없으면 이 경로는 성립하지 않는다.**

## 6-4. QEMU `n800`/`n810` 제거

- QEMU 문서 `removed-features`에 `n800`, `n810`, `mainstone`, `verdex` 등이 **9.2에서 제거**로 명시. 9.0에서 deprecated → 9.2 제거. [검증: qemu.org/docs/master/about/removed-features.html]
- 따라서 OMAP2420 경로를 쓰려면 **QEMU ≤ 9.1**을 고정해야 한다. 최신 QEMU만 설치된 환경에서는 재현 불가.

## 6-5. `Milek7/wince-qemu` (CE7, vexpress-a15)

- CE7 BSP + 릴리스 이미지 + 실행 커맨드까지 공개. 256MB RAM, PL011/PL111/PL050/PL041, virtio-tablet/blk. [검증: README]
- `NK.bin`을 flat 이미지로 변환해 `0x80000000`에 로드하고 PC를 엔트리로 설정하는 방식.
- CE7이지만 **AAP/TLS/프레이밍 로직 검증**에는 충분하다. 성능·USB 검증용은 아니다.

## 6-6. CERF — 이 저장소가 실제로 쓴 도구

- JIT가 **ARMv4~ARMv7-A, Thumb/Thumb-2, VFP, NEON** + MIPS I/III/IV/MIPS16 지원, "WinCE 에뮬레이터용"으로 개발. [검증: libCerfEngine README]
- 이 저장소는 CERF 8.1.3.669 + `omap_3530_evm` 보드로 GD13MY 커널 복사본을 로드:
  - CE 6.0 및 진입 가상주소 `0x8400aadc` 인식, 커널 초기 코드 실행
  - 게스트 PC `0x8400b0b0`에서 **미매핑 `0x8ff00000` 접근으로 중단**
  - SHA-256은 실행 후에도 불변 [검증: `docs/CE_EMULATION_FEASIBILITY.md`]
- 즉 **CERF는 "부팅 시작까지"는 되고, "GD13MY 전용 메모리 맵"이 없으면 그 다음에서 멈춘다.** 이 지점을 넘긴 것이 저장소 자체 에뮬레이터다.
- 라이선스: 베타 배포 + 비상업 조건으로 알려져 있다. [부분검증] 상업적 사용 전 cerf.cx 약관 확인 필요.

## 6-7. 자체 에뮬레이터가 이긴 이유

`docs/EMULATOR_ARCHITECTURE.md` 기준:
- 순정 `BSP.spd.000`의 CE BIN 레코드 체크섬 검증 → 물리 `0x8000aadc`에서 Unicorn Cortex-A8 실행
- OEM 테이블의 `0x84000000 → 0x80000000` 매핑으로 256 MiB RAM 제공
- DISPC(GFX/VID1 RGB565 800×480), MUSB(IRQ 92/93, DMA mode 0), McSPI 터치, MICOM CDP, HSMMC, GPTIMER, INTC, I2C 모델
- `DiskA` FAT32 119파일, MBR LBA 131070, 세션 오버레이 + 선택적 스냅샷

**교훈**: 범용 에뮬레이터를 찾는 것보다, **보드 모델을 이미 가진 저장소를 쓰는 것**이 압도적으로 빠르다. 새 에뮬레이터 도입은 이 저장소 기준으로 후퇴다.

## 6-8. 에뮬레이터로 되는 것 / 안 되는 것

| 검증 대상 | 가능? | 근거 |
|---|---|---|
| AAP 버전 교환·TLS·프레이밍·`AUTH_COMPLETE` | **가능** | 가상 폰 시험에서 완료 |
| DHU 인증서 체인/상태코드 처리 | **가능** | 시험 CA로 완료, 실폰만 남음 |
| 폰 인증서 핀(이름/지문) | **가능** | ARM 정상·거부 시험 완료 |
| H.264 디코딩·GDI 표시 | **가능(기능)** | LCD 3픽셀 검증 |
| H.264 **성능/지연** | **불가** | TCG/Unicorn 수치는 실기와 무관 |
| USB AOA 실폰 전 구간 | **부분** | 버전 응답까지 확인, TLS 구간은 Windows 수신기가 이어받음 |
| GD13MY 고유 드라이버(튜너·DSP·전원) | **불가** | 모델 없음 |

## 6-9. 권장 순서

1. **저장소 자체 에뮬레이터**로 DHU 신원 주입 → A/B 시험(4-4절). 인증서 판정은 여기서 끝난다.
2. 가상 폰 시험(`run_gd13my_virtual_phone.ps1`)으로 TLS 이후 경로 회귀 확인.
3. 실기(차량 or 동일 유닛 중고/벤치)에서 USB·전원·화면 확인.
4. 새 에뮬레이터가 필요하면 **CERF `omap_3530_evm`** 로 교차 검증(부팅 초기만).
5. Device Emulator/PB6 경로는 **"CE6 앱 바이너리 단위 시험"** 용도로만. GD13MY 부팅 재현용이 아니다.

---

# 7. 리스크와 금지 사항

## 7-1. 기술 리스크
- **v1·무확장 인증서 의존**: DHU cert는 X.509 v1이고 EKU가 없다. 지금은 통과하지만, Android가 클라이언트 인증서에 EKU를 요구하거나 v1을 거부하면 **조용히 깨진다.**
- **폰 cert 만료**: AARE 문서의 일반값은 2026-12-31, 이 저장소가 관측한 세션 leaf는 2027-02-17 UTC. 날짜를 하드코딩하면 안 되고, **매 세션 leaf 기준**으로 판정해야 한다.
- **정책 변동**: 2025년 Play Services 업데이트로 완제품이 대량 07이 된 사례가 있다. 구글 앱 경로는 언제든 닫힐 수 있다.
- **USB 수명**: 순정 `usbd.dll`은 분리 통지 전에 파이프를 닫는다. 지속 세션에는 별도 스레드 소유권 설계가 필요하고, 현재 Attach 경로는 8초 한도다.
- **MUSB 0바이트 DMA**: 전체 게스트 시험에서 0바이트 DMA 수신 후 다음 TLS 출력이 중단된 이력. 회귀 시험 항목으로 유지.

## 7-2. 하지 말 것
- **aasdk/Carlinkit의 OEM 인증서·개인키를 복사해 쓰지 않는다.** 타사 신원 재사용이며, 기술적 성공과 별개로 정당성 문제가 생긴다.
- **DHU 신원을 제품·배포물에 넣지 않는다.** 개인 검증 범위 한정.
- **인증서 만료일을 코드에 하드코딩하지 않는다.**
- **`SSL_VERIFY_NONE`/trust-all을 07 해결로 착각하지 않는다.** 07은 반대 방향이다.
- 공개 저장소에 개인키를 커밋하지 않는다(현재 `.gitignore` 방향 유지).

---

# 8. 다음 작업 (완료 판정 기준 포함)

| 순위 | 작업 | 완료 판정 |
|---|---|---|
| **P0** | DHU 2.1 leaf + 키 + GAL 루트를 `\DiskA\Application\NAVI\`에 주입, `.der` 잔재 제거, 매니페스트 재생성 | 게스트 UART에 인증 파일 로드 성공, 시계 정상 |
| **P0** | PC `s_server` 상대로 TLS 1.2 + client cert 전송 확인 | `0xC02F`, Certificate 송신 확인 |
| **P1** | 실폰 USB 시험 | `AUTH_COMPLETE sent` 로그, 07 미표시 |
| **P1** | `unknown CA` 지속 시 정책 차단 여부 판정 | 로그 근거로 AARE/동글 전환 결정 |
| **P2** | 서비스 탐색 + 영상 채널 광고 + 더미 렌더 | 폰이 영상 채널 수락 |
| **P3** | 실폰 H.264 표시·터치·오디오 | 800×480 프레임 + 탭 반응 |
| **P4** | 지속 세션/후진·경고 선점/Bluetooth | 실차 또는 벤치 30분 무중단 |

---

# 9. 근거 링크 일람

| 주장 | 근거 | 등급 |
|---|---|---|
| 07 = TLS 계층 거부, 폰 서버 / HU 클라이언트 | https://github.com/prototux/AARE/blob/main/docs/certificates.md | 검증 |
| 폰 신뢰 앵커 = GAL 루트 단일 | 위 동일 | 검증 |
| DHU 2.1 인증서 공개 배포 | https://github.com/iscle/android-auto-certificates | 검증 |
| 저장소 실폰 실패 지점·DHU 10회 성공 | `docs/ANDROID_AUTO_AUTH_STATUS.md`, `docs/USB_CONNECTION_TEST.md` | 검증 |
| CE BearSSL 구현·파일 규약·오류 매핑 | `src/ce/ce_aa_tls.c`, `docs/CE_PORTING_STATUS.md` | 검증 |
| 자체 에뮬레이터 구조·부팅 | `docs/EMULATOR_ARCHITECTURE.md`, `docs/GD13MY_EMULATION.md` | 검증 |
| CERF `omap_3530_evm` 진입 후 중단 | `docs/CE_EMULATION_FEASIBILITY.md` | 검증 |
| CERF JIT ARM 범위 | https://github.com/gweslab/libCerfEngine | 검증 |
| QEMU `n800`/`n810` 9.2 제거 | https://www.qemu.org/docs/master/about/removed-features.html | 검증 |
| CE7 vexpress-a15 BSP | https://github.com/Milek7/wince-qemu | 검증 |
| CE6 BSP 목록(DeviceEmulator/SDP2420 등) | *Windows Embedded CE 6.0 Fundamentals* Ch.5 | 부분검증 |
| Device Emulator = ARMv4I | CodeConcept "Porting BSP to WinCE 6.0", SO(ctacke) | 부분검증 |
| Zune HD(WinCE6/ARM11) 에뮬 부팅 | https://github.com/Teulis/zunehd-emu | 검증 |
| 2025년 Play Services 07 대량 발생 | support.google thread/371804348, issuetracker 440779969 | 부분검증 |
| WinCE AA 실증은 동글+벤더앱 | XDA 2795971, 4761332 | 검증 |

---

# 10. 1차 보고서와의 차이 (변경 이력)

| 1차 제안 | 2차 판정 | 이유 |
|---|---|---|
| D-1 DHU 인증서 적용 | **유지 (유일한 잔여 조치)** | 근거 4개가 동일 지점 지시 |
| D-2 wolfSSL TLS 1.2 이식 | **폐기** | BearSSL 0.6으로 TLS 1.2 + `0xC02F` 이미 동작 |
| D-3 TCP 5277로 분리 | **완료됨** | 개발자 서버 경로에서도 07 재현 → 오히려 원인 확정에 기여 |
| D-5 폰 인증서 검증 구현 | **완료됨** | CA + 이름/지문 핀 + `PinnedChain` 구현·시험 완료 |
| D-4 AARE / D-6 동글 | **폴백 유지** | DHU 신원도 거부될 경우의 유일한 탈출구 |
| "ARMv6 에뮬레이터 필요" | **불필요** | Cortex-A8=ARMv7-A, CE6 앱=ARMV4I, 자체 보드 에뮬레이터 존재 |
| "WinCE 6.0에 TLS 1.2 없음 → 이식 필수" | **부분 정정** | OS 기본 스택에는 없지만 BearSSL 포팅으로 이미 해결 |

---

*이 문서는 저장소 `main` 트리의 문서·코드·로그를 직접 열어 확인한 내용과, 공개 자료 조사를 근거 등급과 함께 정리한 것이다. 저장소에 없는 파일·로그·수치는 만들어 넣지 않았고, 확인하지 못한 항목은 `[부분검증]`/`[추정]`으로 표시했다.*
