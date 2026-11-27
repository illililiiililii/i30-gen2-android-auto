# 현대 i30 GD(2013) 순정 내비게이션(GD13MY) Android Auto 이식
## 오류 07 원인 규명 및 미시도 해결 경로 심층 리서치

작성일: 2026-11-24 · 조사 언어: 한/영/중/러/독 · 대상: Windows Embedded CE 6.0 / ARM(Cortex-A8) 추정 순정 헤드유닛

### 근거 등급 표기
- **[검증]** 소스/원문을 직접 열어 확인
- **[부분검증]** 제목·요약·일부 본문만 확인(전문 미확인)
- **[추정]** 공개 근거 기반 추론, 실측 없음

### 조사 한계 (먼저 밝힘)
1. 대상 프로젝트 저장소 `https://github.com/illililiiililii/i30-gen2-android-auto` 는 **HTTP 404**(비공개 또는 미존재). 내부 코드·이슈·빌드 로그를 볼 수 없어, "오류 07이 발생한다"는 전제만으로 분석했다.
2. `GD13MY` 라는 형번은 공개 웹에서 **차량용 내비 형번으로 검증되지 않았다**(검색 결과는 전자부품 형번만). 이 보고서는 "i30 GD 2013년형 순정 내비 = 현대 표준형 2~3세대 WinCE 계열"이라는 공개 계보 정보로 대체 서술한다. [검증: 나무위키 계보 / 미검증: 형번 자체]
3. WinCE 6.0 실기에서의 TLS·USB 실측은 하지 않았다. 성능 수치는 인용이며 추정임을 표기했다.
4. 접근 불가/부분 확인 자료는 본문에 그대로 표시했다. 짧은 스니펫만 본 자료를 "전문 확인"으로 쓰지 않았다.

---

# A. 핵심 발견 요약

1. **오류 07은 "AA 앱 레벨" 오류가 아니라 TLS 계층 거부다.** 폰 로그는 `E CAR.GAL.SECURITY.LITE: Error in SSL handshake`, `SSLHandshakeException`, `error:100000f0:SSL routines:OPENSSL_internal:UNSUPPORTED_PROTOCOL`로 끝난다. 즉 07은 ①프로토콜/암호 협상 실패 또는 ②헤드유닛 인증서 체인 거부, 두 개의 **독립 게이트** 중 하나에서 발생한다. [검증: XDA 4761332 본문]

2. **AA 핸드셰이크 구조(확정)**: 버전 교환 → 채널0 `ENCAPSULATED_SSL`(type 3) 안에서 **TLS 1.2 상호 인증**. **폰이 TLS 서버, 헤드유닛이 TLS 클라이언트**다. 헤드유닛은 핸드셰이크 후 `AUTH_COMPLETE`(type 4)에 상태코드를 실어 보낸다(0=수락, -3=인증실패, -23=아직 유효하지 않음, -24=만료). [검증: prototux/AARE `docs/certificates.md`]

3. **폰 쪽 신뢰 저장소에는 앵커가 하나뿐이다: `O=Google Automotive Link` 루트.** 헤드유닛 인증서는 이 루트로 체인되어야 하고, 유효기간 검사도 한다. 자기서명·사설 CA·타사 OEM 인증서는 거부된다. **취미 프로젝트가 정당하게 얻을 수 있는 유일한 GAL 발급 인증서는 Android SDK의 DHU(Desktop Head Unit) 인증서**다. [검증: AARE certificates.md / iscle 저장소 `dhu/2.1`]

4. **DHU 2.1 인증서 실물 확인**: `dhu/2.1/certificate.pem` + `private-key.pem` + `metadata.json`. subject `C=US, ST=California, L=Mountain View, O=Android-Auto-Internal, OU=01`, issuer `O=Google Automotive Link`, serial `0111`, kind `desktop-head-unit`, SHA-256 `4eb581dcee2b…`. [검증: iscle/android-auto-certificates metadata.json]

5. **2025년 8~9월 오류 07 대량 발생은 Google Play Services `25.34.34` 업데이트와 시간적으로 일치**한다. 같은 헤드유닛이 "몇 달간 정상 동작 → 갑자기 07"로 바뀌었고, 벨바(Belva)·리무디(Rimoody)·Autolink(ZCD MCU) 등 **서로 다른 저가 안드로이드 헤드유닛**에서 동시다발했다. 제조사 공식 대응은 "펌웨어(BIN) 업데이트"였다. [부분검증: support.google.com thread/371804348, thread/369324198, issuetracker 440779969, Jaycar QM3793 공지]

6. **i30 GD(2013)의 순정 내비에는 애초에 AA 리시버가 없다.** 현대 표준형 내비는 **3세대까지 Windows Embedded Compact(3세대 이전은 부팅 시 Windows CE 6.0 표기)**, **4세대(2013년 K5 후기형~)부터 안드로이드 기반이며 그때부터 CarPlay/AA 지원**이다. i30 GD는 WinCE 계열 적용 차량 목록에 있다. → **07이 관측된다는 것 자체가 "이미 커스텀 AA 리시버(또는 동글앱)가 그 유닛에서 돌고 있다"는 증거**다. [검증: 나무위키 순정 내비게이션/현대자동차그룹]

7. **WinCE 6.0에는 TLS 1.2가 없다.** Windows Embedded Compact 7은 2018년 3월 월간 업데이트로 TLS 1.1/1.2(SCHANNEL)를 추가했지만, **WinCE 6.0용 동등 업데이트는 확인되지 않았다.** 따라서 WinCE 6.0에서 07을 없애려면 TLS 스택을 **직접 이식**해야 한다. [부분검증: MS WEC7 업데이트 문서 / WinCE 6.0 미확인]

8. **wolfSSL은 Windows CE 6.0/7.0을 공식 지원**한다(PR #8709, VS2008 + WinCE SDK, `_WIN32_WCE` 분기, 지원 OS 목록에 WinCE 포함). TLS 1.2/1.3, ECDHE, RSA-2048, PSK 모두 가능. → **WinCE 6.0에서 TLS 게이트를 없앨 수 있는 현실적 유일 라이브러리 후보.** [검증: wolfSSL 저장소/PR]

9. **aasdk의 TLS 구현은 참고용으로 부적합하다**: `getMethod()`가 구 OpenSSL에서 `TLSv1_2_client_method()`, 신 OpenSSL에서 `TLS_client_method()`, 그리고 `SSL_VERIFY_NONE`. 즉 **인증서 검증을 아예 하지 않고**, 협상 결과를 로그로 노출하지 않는다. 프로토콜 framing만 참고하고 TLS 정책은 새로 짜야 한다. [검증: opencardev/aasdk `src/Transport/SSLWrapper.cpp`]

10. **최신 구현은 TLS 계층을 갈아엎었다**: `andreknieriem/headunit-revived`는 aasdk식 C++ SSL 래퍼를 버리고 Kotlin/Conscrypt 기반 `aap/AapSsl*.kt`(핸드셰이크 프레이밍, TLS unwrap 루프, TLS writer, 비디오 회계까지 테스트 존재)로 재작성했고, 릴리스 노트에 **"ssl rewrite"**(v1.5.0-alpha) 및 **"fix the dongle's TLS handshake"**(v3.5.0)가 명시돼 있다. → **AA-over-TLS를 "프레이밍 포함" 구현한 최신 레퍼런스**로 이 저장소가 가장 값어치 있다. [검증: 릴리스 목록/트리]

11. **트랜스포트를 USB에서 떼어내는 우회로가 실증돼 있다**: `blakereuben/pi-auto-headunit`은 **개발자 모드의 head unit server(TCP 5277, ADB forward)** 로 AAP 1.6 버전 교환 + TLS 피어 데이터까지 도달했다(그 다음 07). 즉 **USB AOA 드라이버 없이도 TLS/인증 게이트를 실험할 수 있다**. WinCE 이식에서 가장 먼저 할 일이 이것이다. [검증: `docs/protocol/tls-credential-policy.md`]

12. **"구글 앱을 쓰지 않는" 우회로가 존재하고, 이 경우 인증서 게이트가 사라진다**: `prototux/AARE`는 **폰 측 AA를 대체하는 오픈소스 앱**이다. 헤드유닛 인증서를 GAL로 검증하지 않고, 처음 보는 헤드유닛 인증서는 사용자가 "Trust"로 승인한다. 실사용 50대 중 24대 동작 보고. → **자체서명 헤드유닛 + AARE 조합은 인증서 문제를 원천 제거**한다(대신 구글 앱 생태계 제약). [검증: AARE README / certificates.md]

13. **WinCE에서 AA가 "실제로" 돈 사례는 전부 동글+벤더 앱 경로다.** XDA 2795971: rajsardhara가 WinCE 유닛 + USB 동글 + **Carlinke WinCE 앱**으로 AA/CarPlay 구동, coAlex가 Ford Sync2(WinCE6)에서 **AutoKit** 동작. 반면 Carlinkit은 WinCE용 앱 신규 제작을 거부했고, Android용 동글은 WinCE에서 인식되지 않았다. **자체 구현(순정 유닛 단독 실행) 성공 공개 사례는 아직 없다.** [검증: XDA 2795971 / 미확인: 최신 상태]

14. **인증서 재사용의 경계**: aasdk 기본 탑재 `cert/headunit.crt`(C=JP, O=JVC Kenwood, 2014~2045)와 Carlinkit CPC200-CCPA 펌웨어 내 인증서가 **바이트 단위 동일**하다는 분석이 있다. 이는 **타사 OEM 신원 재사용**이며 해결책으로 제시하지 않는다. 반면 Android SDK가 공개 배포하는 **DHU 인증서는 개발용으로 배포된 자료**이므로 구분해 다룬다. [검증: lvalen91/ocbm 문서 / open-headunit Discussion #637]

15. **시간 제약**: 폰 측 CarService 리프 인증서는 AARE 문서 기준 **2026-12-31 만료**(루트는 2044-06-05)이나, 이 저장소의 실폰 관측값은 **2027-02-17 19:01:30 UTC**로 세션마다 다르다. 구글은 서버 플래그로 교체 가능하므로, 헤드유닛 쪽에서 인증서 유효기간을 하드코딩하거나 오프라인 검증을 하면 조용히 깨진다. **DHU 인증서는 2048-08-01까지 유효**하며 이 숫자와 무관하다(2차 보고서 3-2절 만료일 혼동 정리 참조). [검증: AARE certificates.md / DHU DER `notAfter` / `docs/CE_PORTING_STATUS.md`]

---

# B. 신규 참고 프로젝트

> "신규"는 기존에 흔히 소개되는 openauto/Crankshaft 재소개를 뜻하지 않는다. 아래는 **인증서·TLS·트랜스포트 계층을 실제로 다루는** 저장소 중심이다.

| # | 프로젝트 | URL | OS·언어 | 핵심 기능 | 실제 연결 성공 | 인증서 처리 | WinCE 적용성 | GD13MY 가치 |
|---|---|---|---|---|---|---|---|---|
| 1 | headunit-revived | https://github.com/andreknieriem/headunit-revived | Android, Kotlin | aasdk 없이 AAP 재구현, **TLS 계층 자체 구현** | 성공(안드로이드 헤드유닛 다수) | 자체 `SingleKeyKeyManager`(단일 cert) + trust-all, `SSLContext("TLS")` | 낮음(Android 전용) | **최상**: TLS framing/unwrap 로직의 사실상 유일한 최신 레퍼런스 |
| 2 | AARE | https://github.com/prototux/AARE | Android, Kotlin/Java | **폰 측** AA 대체(구글 앱 불필요) | 50대 중 24대 성공(자체 집계) | 헤드유닛 cert를 GAL로 강제하지 않음, 사용자 Trust 핀닝 | 없음(폰 앱) | **상**: 인증서 게이트 제거 경로, 상태코드/로그 해석 기준 |
| 3 | aa-proxy-rs | https://github.com/aa-proxy/aa-proxy-rs | Linux/임베디드, Rust | 무선 폰 ↔ USB 헤드유닛 프록시(WirelessAndroidAutoDongle 파생) | 성공(RPi 계열) | 헤드유닛 cert 검증 안 함 | 없음(외부 HW) | 중: 프록시로 TLS 종단 분리 아이디어 |
| 4 | WirelessAndroidAutoDongle | https://github.com/nisargjhaveri/WirelessAndroidAutoDongle | Linux, C/C++ | USB 동글 형태 무선 AA 게이트웨이 | 성공 | aasdk 계열 | 없음(외부 HW) | 중: 동글 경로 원형 |
| 5 | LIVI | https://github.com/f-io/LIVI | Linux/macOS/Android, Rust+Slint | CarPlay+AA 풀 헤드유닛, GStreamer 제로카피 | 성공(Linux 임베디드) | 헤드유닛 cert 미검증(오픈소스 계열) | 없음 | 중: 영상/오디오 파이프라인 설계 참고 |
| 6 | pi-auto-headunit | https://github.com/blakereuben/pi-auto-headunit | Linux, C++/Rust 혼합 | "합법적 신원으로 AA 리시버 만들기" 실험/문서 | **실패(07)** — 단 TLS·프레이밍까지 도달 | 정책 문서화: aasdk 신원 재사용 금지 | 낮음 | **상**: 실패 지점·프로비저닝 후보(Cinemo/ART/ECORE/NXP) 정리 |
| 7 | open-android-auto | https://github.com/mrmees/open-android-auto | (프로토콜 정의 중심) | AA 프로토콜/protobuf 정의 | 미확인 | - | 중(정의 참고) | 중: 메시지 스키마 대조 |
| 8 | aasdk | https://github.com/opencardev/aasdk | Linux, C++ | AA 전송/미디어/인증 라이브러리 | 성공(단, 인증서는 타사 것) | `SSL_VERIFY_NONE`, JVC Kenwood cert 내장 | **중**: C++ 구조는 참고, TLS 정책은 버려야 함 | 중: USB/AOA·채널 구조 참고 |
| 9 | openauto | https://github.com/opencardev/openauto | Linux/RPi, C++ | aasdk 기반 헤드유닛 UI | 성공 | aasdk 위임 | 중 | 중: 입력/영상 루프 참고 |
| 10 | open-headunit | https://github.com/andreknieriem/open-headunit | Android, Kotlin | headunit-revived의 전신/배포 채널 | 성공(안드로이드) | Discussion #637: DHU에서 추출한 "official pair" 사용 | 낮음 | 상: 인증서 출처·정책 근거 |
| 11 | android-auto-certificates | https://github.com/iscle/android-auto-certificates | 데이터 저장소 | DHU 및 AA 앱 인증서 아카이브 | - | **DHU 2.1 = GAL 발급, 공개 배포** | - | **최상**: 유일한 합법적 GAL 체인 cert |
| 12 | ocbm | https://github.com/lvalen91/ocbm | 문서/분석 | Carlinkit CPC200-CCPA 바이너리 분석 | - | 인증서가 aasdk 것과 동일함을 SHA-256으로 증명 | - | 상: 상용 동글이 어떻게 통과하는지 구조 파악 |
| 13 | syncextpack | https://github.com/chr0m1ng/syncextpack | WinCE 패키지 | Ford Sync2(WinCE6)용 AutoKit 등 패키징 | 성공(WinCE6) | 벤더 앱 내장 | **최상(WinCE)** | 상: WinCE에서 실제 동작하는 앱/런타임 구성 |
| 14 | AACS | https://github.com/tomasz-grobelny/AACS | 접근 확인(200), 상세 미확인 | AA 관련 구현체 | 미확인 | 미확인 | 미확인 | 하(추가 검증 필요) |
| 15 | AndroidAuto(mretallack) | https://github.com/mretallack/AndroidAuto | 접근 확인(200), 상세 미확인 | AA 관련 자료 | 미확인 | 미확인 | 미확인 | 하(추가 검증 필요) |

### 참고 소스 파일 (직접 열어 확인한 것)
- `headunit-revived/app/src/main/java/com/andrerinas/openheadunit/aap/AapSsl.kt` — TLS 암복호 인터페이스
- 같은 경로 `AapSslContext.kt`, `AapSslNative.kt`, `AapTlsWriter.kt`, `TlsUnwrapLoop.kt`, `TlsApplicationPump.kt`
- 같은 앱 `ssl/SslContextFactory.kt`(`SSLContext.getInstance("TLS")` + trust-all), `ssl/SingleKeyKeyManager.kt`, `ssl/NoCheckTrustManager.kt`, `res/raw/cert`
- 테스트: `app/src/test/.../aap/TlsHandshakeFramingTest.kt`, `TlsUnwrapLoopTest.kt`, `AapSslSessionTest.kt` ← **프레이밍 회귀 테스트를 그대로 이식 가능**
- `aasdk/src/Transport/SSLWrapper.cpp` (`TLSv1_2_client_method()`, `SSL_VERIFY_NONE`)
- `aasdk/src/Messenger/Cryptor.cpp`, `aasdk/cert/headunit.crt`
- `AARE/docs/certificates.md`, `AARE/aap/src/main/proto/aap_protobuf/shared/MessageStatus.proto`
- `pi-auto-headunit/docs/protocol/tls-credential-policy.md`, `receiver-provisioning-options.md`, `livi-adoption.md`
- `ocbm/docs/androidauto/00_ARCHITECTURE.md`

---

# C. 실제 게시글·기술 자료

| # | 제목 | 링크 | 작성일 | 핵심 내용 | 실제 해결 | 소스·첨부 | GD13MY 적용점 |
|---|---|---|---|---|---|---|---|
| 1 | [Guide] Android Auto/CarPlay on WinCE head unit 계열 스레드 | https://xdaforums.com/t/2795971 | 2016~ | WinCE 유닛에서 동글+앱으로 AA 구동, GRL(Google Receiver Library)은 파트너 전용, x13의 Windows OpenAuto 빌드 시도 | 부분 성공(동글 경로) | AutoKit-WINCE.rar 등 첨부 | 유일한 "WinCE에서 AA 화면이 나온" 실증 계열 |
| 2 | Need Firmware for Autolink MP5(ZCD MCU) — Error 7 | https://xdaforums.com/t/need-firmware-for-autolink-mp5-zcd-mcu-android-auto-error-7-came-with-used-car.4761332 | 2025-09-28 | 07 로그 분석(`CAR.GAL.SECURITY.LITE`, `UNSUPPORTED_PROTOCOL`), 해결은 펌웨어뿐 | 미해결(작성자) | 로그 스크린샷 | 07이 TLS 계층임을 확정하는 1차 증거 |
| 3 | Sync2(WinCE6) AutoKit 설치 가이드 | https://xdaforums.com/t/4703992 | 2026경 | AutoKit으로 Sync2에서 AA, 800x480·소프트웨어 디코딩 권장, 오디오 미동작·매우 느림 | 성공(제한적) | syncextpack 저장소 | **WinCE 6.0 + 480p 소프트웨어 디코딩의 현실적 성능 한계** |
| 4 | Error code 7 — Android Auto Community | https://support.google.com/androidauto/thread/369324198 | 2025-08-30 | 갑자기 07, S21 실패/S23 성공 | 미해결 | - | 2025년 파동의 시작점 |
| 5 | Communication Error 7 since Play Services v25.34.34 | https://support.google.com/androidauto/thread/371804348 | 2025-09-08 | **PS 25.34.34 업데이트 직후** 3대 모두 07 | 미해결 | - | 원인을 "구글 측 요구사항 변경"으로 특정 |
| 6 | IssueTracker 440779969 | https://issuetracker.google.com/issues/440779969 | 2025 | PS 업데이트 후 07, 임시방편은 제거/롤백 | 미해결 | - | 동일 (본문 일부만 확인) |
| 7 | Jaycar QM3793 공지 | https://help.jaycar.com.au/hc/en-us/articles/50355885912217 | 2025-09-24 | "일부 폰의 구글 업데이트로 07 발생", **ISP_UPDT.BIN(20MB) 펌웨어 배포** | 해결(제조사 펌웨어) | BIN 다운로드 | **07 해결의 정공법 = 헤드유닛 펌웨어의 TLS/인증 스택 갱신** |
| 8 | open-headunit Discussion #637 | https://github.com/andreknieriem/open-headunit/discussions/637 | - | 인증서 출처 = Android Studio DHU에서 추출한 "official pair", 별도 라이선스 허가 없음 | - | - | DHU 인증서 사용의 사실상 표준 관행 |
| 9 | open-headunit Issue #14 | https://github.com/andreknieriem/open-headunit/issues/14 | 2025-12-30 | 07 재현, 메인테이너 "ssl rewrite" 알파 배포 | 부분 | v1.5.0-alpha | TLS 계층 재작성으로 해결 시도한 사례 |
| 10 | AARE — Certificates and head-unit compatibility | https://github.com/prototux/AARE/blob/main/docs/certificates.md | 2026 | 핸드셰이크 구조, 상태코드, 헤드유닛별 검증 여부 표, 인증서 다운로드 검증 규칙 | - | 문서 | **07 진단표(로그→원인) 그대로 사용 가능** |
| 11 | pi-auto-headunit TLS credential policy | https://github.com/blakereuben/pi-auto-headunit/blob/main/docs/protocol/tls-credential-policy.md | 2026-08 | 자체 생성 신원으로 USB·개발자 터널 모두 07, TLS1.2 compat 모드 | 실패(의도적) | 문서+프로브 | **"자체서명으로는 절대 통과 못한다"는 반증** |
| 12 | ocbm — AndroidAuto 아키텍처 | https://github.com/lvalen91/ocbm/blob/main/docs/androidauto/00_ARCHITECTURE.md | 2026 | AA 전체 세션이 단일 TLS 1.2 안에 들어감, CarLinkit 인증서=aasdk 인증서 | - | 문서 | TLS 종단 지점이 모든 트래픽을 본다는 설계 제약 |
| 13 | wolfSSL Windows CE 지원 PR | https://github.com/wolfSSL/wolfssl/pull/8709 | 2026-01 | VS2008+WinCE SDK 빌드, `_WIN32_WCE` 대응, WinCE 지원 OS 목록 포함 | - | 코드 | **WinCE 6.0 TLS 1.2 확보 수단** |
| 14 | 나무위키 순정 내비게이션/현대자동차그룹 | https://namu.wiki/w/순정%20내비게이션/현대자동차그룹 | 2026-10 갱신 | 3세대까지 WinCE, 4세대부터 안드로이드+AA, 3세대 이전은 명령으로 WinCE 6.0 모드 부팅 | - | - | GD13MY가 왜 AA를 못 하는지, 진입점(CE 모드) 확보 |
| 15 | 현대 i30 PD 카탈로그(2016) | https://www.hyundai.com/contents/repn-car/catalog/i30-price.pdf | 2020 | 8인치 내비 "폰 커넥티비티(AA/CarPlay)" 옵션 | - | PDF | AA 지원은 안드로이드 기반 5세대부터라는 교차 근거 |

---

# D. 오류 07 해결 후보 (실현 가능성 × 근거 수준 순)

> 전제: 07은 두 게이트 중 하나에서 난다. **먼저 어느 게이트인지 로그로 확정**해야 한다(D-0). 아래는 확정 후의 후보 목록이다.

## D-0. 진단 분기 (가장 먼저, 비용 거의 0)
폰 로그/헤드유닛 로그로 3분류:
- **① 핸드셰이크 즉시 실패 + `UNSUPPORTED_PROTOCOL`/`protocol_version` alert** → TLS 버전·암호 스위트 게이트 → D-2, D-3
- **② 핸드셰이크 진행 후 `ALERT bad_certificate`/`unknown_ca`, 또는 07이 0.5초 내 표시** → 인증서 체인 게이트 → D-1
- **③ TLS 완료 후 `AUTH_COMPLETE`가 -3/-24** → 헤드유닛이 폰 인증서를 거부(방향이 반대) → 헤드유닛 검증 로직 문제 → D-5

## D-1. DHU 2.1 인증서(GAL 체인) 적용 — **실현성 높음 / 근거 높음**
- 근거: DHU는 구글이 개발자에게 배포하는 공식 리시버이고, 그 인증서는 GAL 루트로 체인된다. `iscle/android-auto-certificates`의 `dhu/2.1`이 그 사본이며, open-headunit 계열이 실제로 이걸로 동작한다(Discussion #637).
- 조치: 헤드유닛 인증서/키를 DHU 2.1 페어로 교체. 체인(cert + root) 전송, `notBefore/notAfter` 검사 통과 확인.
- 리스크: ①구글이 향후 DHU 신원을 폐기/블랙리스트할 수 있음(공개 근거 없음, 2025년 파동과의 인과 **미확인**). ②"Android-Auto-Internal" subject를 특별 취급할 가능성.
- 판정: **가장 먼저 시도할 것.** 단, D-2(TLS 1.2)가 안 되면 이 인증서도 소용없다.

## D-2. TLS 1.2 + ECDHE 강제 (wolfSSL on WinCE) — **실현성 중 / 근거 높음**
- 근거: WinCE 6.0 SChannel에는 TLS 1.2가 없고(WEC7은 2018-03 업데이트로 추가), wolfSSL은 WinCE 6.0을 공식 지원.
- 조치: SChannel 경로를 버리고 wolfSSL을 정적 링크. `TLSv1_2_client_method`, cipher list를 `ECDHE-RSA-AES128-GCM-SHA256` 등으로 제한, `SSL_VERIFY_NONE`(폰 cert는 검증하지 않음 — 프로토콜상 허용).
- 리스크: ARM Cortex-A8에서 RSA-2048 핸드셰이크 1회 수십 ms~수백 ms(추정), ROM/RAM 추가.
- 판정: **기술적 필수조건.** D-1과 세트.

## D-3. 트랜스포트를 TCP 5277(개발자 head unit server)로 분리 — **실현성 높음 / 근거 높음**
- 근거: pi-auto-headunit이 ADB forward로 AAP 1.6 + TLS 피어 데이터까지 도달.
- 조치: WinCE에서 USB AOA를 건드리지 않고, 폰의 head unit server에 소켓 연결 → 07 여부를 "USB 문제"와 분리해 판정. 이후 USB AOA로 확장.
- 판정: **디버깅 필수 단계.** WinCE에서 USB 호스트 드라이버 작업을 뒤로 미룰 수 있다.

## D-4. 폰 측을 AARE로 교체 (구글 게이트 우회) — **실현성 높음 / 근거 중**
- 근거: AARE는 헤드유닛 cert를 GAL로 강제하지 않고 사용자 Trust로 처리. 자체서명 헤드유닛과 조합 가능.
- 결과: 07이 **원천적으로 발생하지 않음**. 대신 구글 앱(지도/어시스턴트) 생태계 제약, AARE의 앱 세트 사용.
- 판정: "AA를 쓰고 싶다"가 목적이면 가장 빨리 화면이 나오는 경로. "구글 AA를 쓰고 싶다"면 목적 미달.

## D-5. 헤드유닛 측 폰 인증서 검증 제거 — **실현성 높음 / 근거 높음**
- 근거: aasdk가 `SSL_VERIFY_NONE`으로 이미 그렇게 하고, 공장 유닛도 검증 안 하는 사례가 있다(Denso Ten). 상태 -3은 "헤드유닛이 폰을 거부"하는 방향.
- 판정: ③번 분기일 때만. 07(폰이 헤드유닛을 거부)에는 효과 없음.

## D-6. WinCE용 AutoKit/벤더 앱 + 동글 (검증된 유일 경로) — **실현성 높음 / 근거 높음, 단 자체구현 아님**
- 근거: Ford Sync2에서 AutoKit 동작, i30 계열 WinCE 유닛에서 Carlinke WinCE 앱 동작, `chr0m1ng/syncextpack` 유지보수 중.
- 판정: **리스크 최소·성과 최대의 대안.** 단 "순정 내비 자체 실행" 목표에는 미달.

## D-7. 화면 미러링 폴백(EasyConnected 등) — **실현성 매우 높음 / 근거 중**
- 근거: WinCE용 EasyConnected가 다수 유닛에서 동작(제3자 배포). AA 프로토콜을 쓰지 않으므로 07 무관.
- 판정: 목표(AA UI) 미달이지만 "지도+음악을 순정 화면에" 달성.

## D-8. 벤더 프로비저닝(Cinemo CORE Projection, ART SDK, ECORE, NXP) — **실현성 낮음 / 근거 중**
- 근거: pi-auto-headunit 문서가 합법적 후보로 열거. 그러나 개인/취미 대상 셀프서비스 없음.
- 판정: **비현실적.** 참고만.

## D-9. 타사 OEM 인증서 재사용(aasdk JVC, Carlinkit 추출 등) — **기술적 가능 / 정책상 배제**
- 근거: ocbm이 인증서 동일성을 증명. 그러나 타사 신원 도용이며, 폐기·차단 시 무효.
- 판정: **해결책으로 제시하지 않는다.**

---

# E. Windows CE 직접 이식 가능성

## E-1. 계층별 판정

| 계층 | 필요한 것 | WinCE 6.0 현실 | 난이도 | 근거/비고 |
|---|---|---|---|---|
| 실행 환경 | 임의 코드 실행 | SD/업데이트 경로 또는 CE 모드 부팅(3세대 이전) | 중 | 나무위키: 특정 커맨드로 WinCE 6.0 모드 부팅 |
| USB 전송 | USB 호스트 + AOA(accessory) 협상 | WinCE USB 호스트 드라이버에 AOA 없음 → 직접 구현 또는 우회 | **최상** | aasdk는 libusb 의존 |
| 대체 전송 | TCP 5277 / Wi-Fi | winsock으로 즉시 가능 | 하 | pi-auto-headunit 실증 |
| TLS | TLS 1.2, ECDHE, RSA-2048 | SChannel 불가 → wolfSSL | 중 | wolfSSL WinCE 공식 지원 |
| 프로토콜 | AAP protobuf, 채널/프레임 | nanopb 또는 protobuf-lite C++ 포팅 | 중 | AARE의 .proto, aasdk 메시지 |
| 영상 | H.264 디코딩(720p 이하), YUV→RGB | HW 디코더 API 비공개, SW 디코딩은 느림 | **상** | Sync2 사례: 800x480 SW 디코딩 "매우 느림" |
| 오디오 | 48kHz PCM, 지연 최소화 | waveOut 가능 | 중 | 버퍼/지연 튜닝 필요 |
| 입력 | 터치/키 → AA input report | 터치 드라이버 후킹 | 중 | 유닛별 상이 |
| UI | AA 화면 표시 | DirectDraw/GDI 오버레이 | 중 | 기존 내비 UI와 전환 문제 |
| 성능 | Cortex-A8 1GHz급(추정) | 480p/30fps 목표면 빠듯 | 상 | 실측 필요 |

## E-2. 결론
- **"가능하다"**: TLS·프로토콜·오디오·영상 모두 WinCE 6.0에서 구현 가능한 부품이 존재한다(wolfSSL, nanopb, FFmpeg, waveOut/DirectDraw).
- **"어렵다"**: ① USB AOA 호스트 스택, ② H.264 디코딩 성능, ③ 인증서 게이트(구글 정책). 이 셋이 동시에 병목이다.
- **"아직 아무도 못 했다"**: WinCE 6.0 순정 유닛에서 **자체 구현으로 구글 AA 인증을 통과한 공개 사례는 없다.** 있는 것은 동글+벤더 앱(Ford Sync2/AutoKit)과 폰 측 대체 앱(AARE)뿐이다.

## E-3. 권장 아키텍처 (이식 시)
```
[폰: Google AA 앱]  --TLS1.2(mTLS, DHU cert)-->  [WinCE: AA 리시버]
        (A) USB AOA  ← 최난, 후순위
        (B) TCP 5277 ← 먼저 여기로 검증
        (C) Wi-Fi    ← 최종 목표(무선 AA)
```
- 1단계: TCP로 AAP 버전교환 + TLS1.2 + AUTH_COMPLETE까지 (화면 없이 로그만)
- 2단계: 서비스 디스커버리 + 비디오 채널 수신(더미 표시)
- 3단계: H.264 디코딩 + 표시
- 4단계: 오디오/입력/센서
- 5단계: USB AOA 전환

---

# F. Codex 전달용 구현 지시서

## F-1. 분석 기준 저장소 (읽기 전용, 우선순위)
1. `andreknieriem/headunit-revived` — **TLS/프레이밍 1차 레퍼런스**
   - `app/src/main/java/com/andrerinas/openheadunit/aap/AapSsl.kt`, `AapSslContext.kt`, `AapSslNative.kt`, `AapTlsWriter.kt`, `TlsUnwrapLoop.kt`, `TlsApplicationPump.kt`
   - `.../ssl/SslContextFactory.kt`, `SingleKeyKeyManager.kt`, `NoCheckTrustManager.kt`, `res/raw/cert`
   - 테스트: `app/src/test/.../aap/TlsHandshakeFramingTest.kt`, `TlsUnwrapLoopTest.kt`, `AapSslSessionTest.kt`, `TlsVideoAccountingTest.kt`
2. `prototux/AARE` — 상태코드/진단표/프로토콜 정의: `docs/certificates.md`, `aap/src/main/proto/aap_protobuf/**`
3. `opencardev/aasdk` — 채널/메시지 구조: `src/Transport/SSLWrapper.cpp`(정책은 무시), `src/Messenger/Cryptor.cpp`, `src/Channel/**`, `cert/headunit.crt`(참고만)
4. `blakereuben/pi-auto-headunit` — `docs/protocol/tls-credential-policy.md`, `receiver-provisioning-options.md`
5. `lvalen91/ocbm` — `docs/androidauto/00_ARCHITECTURE.md`
6. `chr0m1ng/syncextpack` — WinCE 실동작 앱 구성/런타임 확인

## F-2. 확인할 소스 파일·함수 (구현 전 체크리스트)
- [ ] `SSLWrapper::getMethod()` — 협상 프로토콜 결정 지점
- [ ] `SSLWrapper::createContext()` / `useCertificate()` / `usePrivateKey()` — cert 체인 전송 여부
- [ ] `Cryptor` 계열 — cert/key 로딩 방식(파일 vs 내장)
- [ ] AAP 채널0 메시지 타입 3(`ENCAPSULATED_SSL`)/4(`AUTH_COMPLETE`) 처리부
- [ ] `MessageStatus.proto` — 0/-3/-23/-24 매핑
- [ ] TLS 레코드 ↔ AAP 프레임 경계 처리(부분 TLS 레코드가 AAP 프레임을 걸치는 경우) — **여기가 실제로 가장 많이 깨지는 지점**
- [ ] 서비스 디스커버리 요청/응답 스키마(비디오 1, 오디오 2/3, 입력, 센서)

## F-3. 비교 구현 (A/B)
| 항목 | A: aasdk/openauto | B: headunit-revived |
|---|---|---|
| TLS 메서드 | `TLSv1_2_client_method()` / `TLS_client_method()` | `SSLContext("TLS")` (플랫폼 최신) |
| cert 검증 | `SSL_VERIFY_NONE` | trust-all TrustManager |
| 프레이밍 | BIO 쌍 + 수동 루프 | `TlsUnwrapLoop`/`TlsApplicationPump` + 테스트 |
| 인증서 | JVC Kenwood(타사) | DHU 페어 |
→ **B를 기준으로 삼고, A는 채널/메시지 구조만 참조한다.**

## F-4. 수정/신규 모듈 (WinCE 프로젝트 구조 제안)
```
/aa
  /transport
    tcp_transport.cpp        (1단계, winsock)
    aoap_transport.cpp       (5단계, USB 호스트)
  /tls
    wolfssl_ctx.cpp          TLS1.2, ECDHE, cert chain 주입
    tls_record_reader.cpp    레코드 경계 처리(부분 레코드 버퍼링)
  /aap
    version_negotiator.cpp
    auth_complete.cpp        status 매핑 + 로그
    service_discovery.cpp
    channel_router.cpp
  /media
    h264_decoder_ffmpeg.cpp  (또는 HW 디코더 래퍼)
    video_surface_gdi.cpp
    audio_out_wave.cpp
  /input
    input_report.cpp
  /diag
    handshake_trace.cpp      ★ TLS alert/protocol/cipher/cert subject/issuer 기록
```

## F-5. 필요 도구
- 빌드: Visual Studio 2008 + Windows CE 6.0 SDK(플랫폼 SDK는 유닛 벤더 것), 또는 VS2019+WinCE 툴체인 대안
- 라이브러리: wolfSSL(WinCE), nanopb 또는 protobuf-lite, FFmpeg(ARM 최적화) 또는 유닛 HW 디코더 SDK
- 분석: OpenSSL CLI(cert 체인/만료 확인), Wireshark(USB pcap은 USBPcap+VM 필요), `openssl s_client -connect ... -tls1_2`로 서버측 재현
- 폰: adb, Android Auto 개발자 모드(head unit server), `adb logcat | grep -iE 'GAL|SSL|handshake'`
- 검증: DHU(Android Studio) — **정상 동작 기준선 확보용**

## F-6. 테스트 방법
1. **기준선**: PC에서 DHU ↔ 폰 연결 성공 확인(정상 로그 확보). 실패하면 폰/케이블 문제.
2. **서버 재현**: `openssl s_server -tls1_2 -Verify 0 -cert dhu.pem -key dhu.key` 로 WinCE 클라이언트의 ClientHello를 캡처 → **protocol/cipher/extension 목록을 눈으로 확인**.
3. **역방향**: WinCE 클라이언트가 TLS1.2로 붙는지 `s_server`로 확인(폰 없이).
4. **AAP 단위**: 버전교환 패킷 hex를 AARE/headunit-revived 테스트 벡터와 바이트 비교.
5. **프레이밍 회귀**: TLS 레코드가 1바이트씩 쪼개져 도착하는 케이스, AAP 프레임이 두 TLS 레코드에 걸치는 케이스 — `TlsUnwrapLoopTest` 시나리오를 그대로 이식.
6. **통합**: TCP 5277 경로로 실제 폰 연결, `handshake_trace`로 ①/②/③ 분기 판정.
7. **성능**: 480p/720p H.264 30fps 디코딩 fps, 오디오 지연(ms), 터치→화면 반영 지연 측정.

## F-7. 우선순위
- **P0**: ① DIN/폰 로그로 게이트 확정(D-0), ② TCP 5277 전송 + TLS1.2(wolfSSL) + AUTH_COMPLETE까지
- **P1**: DHU 2.1 인증서 적용 → 실제 폰 연결로 07 소멸 여부 확인
- **P2**: 서비스 디스커버리 + 비디오 채널 수신 + 더미 렌더
- **P3**: H.264 디코딩/표시, 오디오, 입력
- **P4**: USB AOA 호스트 스택, 무선 AA
- **병행(리스크 헤지)**: syncextpack/AutoKit으로 "일단 화면이 나오는" 상태 확보

## F-8. 중단/전환 조건 (미리 정해둘 것)
- P1에서 DHU 인증서로도 07이 지속되고 로그가 `bad_certificate`/`unknown_ca`가 아니라면 → 인증서가 아니라 **정책/버전** 문제 → D-2·D-3 재점검
- P0에서 `UNSUPPORTED_PROTOCOL`이 계속되면 → wolfSSL 빌드/암호 스위트 문제 → `s_server` 비교로 회귀
- 480p SW 디코딩이 15fps 미만이면 → "순정 유닛 단독 실행" 목표를 접고 동글 경로(D-6)로 전환

## F-9. 하지 말 것
- aasdk/Carlinkit의 OEM 인증서·키를 복사해 쓰지 않는다(타사 신원).
- 인증서 유효기간/폰 cert 만료(2026-12-31)를 하드코딩하지 않는다.
- `SSL_VERIFY_NONE`을 "해결"로 착각하지 않는다 — 07은 **폰이 헤드유닛을 검증**하는 방향이다.

---

# G. 저장소 실물 검토 (2026-11-24, public 전환 후)

> 이 절은 2차 보고서 `i30-gd-aa-phase2-report.md`로 확장되었다. 인증서 판정 근거 4개, DHU 인증서 DER 실측, 적용 체크리스트, 로그별 실패 분기, WinCE 에뮬레이터 조사가 포함되어 있으며 **충돌 시 2차 보고서가 우선**한다.

대상: https://github.com/illililiiililii/i30-gen2-android-auto (main, 151 blobs)

## G-1. 판정
**오류 07의 원인은 인증서 체인이다. TLS 버전/암호 스위트 문제가 아니다.**
- 근거 1: 저장소 자체 로그 — 자체 발급 헤드유닛 인증서 전송 시 폰이 `Trust anchor for certification path not found` 기록. 이는 Android TrustManager의 앵커 부재 오류이며 TLS 협상 실패가 아니다.
- 근거 2: 동일 폰에서 공식 DHU 2.0 연결 시 AA 1.7 / TLS 1.2 / `0xC02F` / 인증서 검사 성공 / 오디오 스트림 관측.
- 근거 3: CE BearSSL 수신기가 시험 CA로 상호 TLS·`AUTH_COMPLETE`·암호화 검색까지 통과(에뮬레이터).

## G-2. 본 보고서 D절 제안의 적용 여부
| 제안 | 판정 | 이유 |
|---|---|---|
| D-1 DHU 인증서 적용 | **적용(유일한 잔여 조치)** | 폰 신뢰 앵커가 GAL 루트뿐 |
| D-2 wolfSSL TLS1.2 | **불필요** | BearSSL 0.6으로 TLS1.2 + 0xC02F 이미 동작 |
| D-3 TCP 5277 분리 | **이미 완료** | 개발자 서버 시험에서 동일 07 재현 |
| D-5 폰 인증서 검증 | **이미 정상** | CA + 이름/지문 핀 구현됨 |
| D-4 AARE / D-6 동글 | 폴백 | 구글 앱 경로 실패 시 |

## G-3. DHU 2.1 인증서 실측(직접 DER 디코드)
- RSA-2048, 서명 `sha256WithRSAEncryption`(1.2.840.113549.1.1.11)
- **X.509 v1, 확장 없음** → EKU/keyUsage/basicConstraints 부재. `clientAuth` 요구 없음, 클라이언트 인증서로 그대로 사용 가능
- subject `C=US/ST=California/L=Mountain View/O=Android-Auto-Internal/OU=01`, issuer `O=Google Automotive Link`
- 유효기간 2014-07-04 ~ **2048-08-01**, serial `0111`

## G-4. 저장소 코드에 맞춘 적용 지점
`src/ce/ce_aa_tls.c` 기준, 경로 `\DiskA\Application\NAVI\`:
- `i30-client.pem` ← DHU `certificate.pem` (**leaf 단독**, 중간 CA 삽입 금지)
- `i30-client-key.pem` ← DHU `private-key.pem` (PKCS#8 `PRIVATE KEY`, 191행에서 허용 → 변환 불필요)
- `i30-ca.pem` ← GAL 루트(폰 체인에서 확보)
- `i30-peer.txt` 또는 `i30-peer-sha256.txt` ← 폰 `O=CarService` 핀
- 이미지 매니페스트(`image.json`)의 SHA-256 갱신 필요

## G-5. 잔여 리스크
- DHU 신원은 **개발자 테스트용 배포물**이며 제품 프로비저닝이 아니다. 개인 차량 검증 범위로 한정.
- v1·무확장 인증서이므로 향후 Android가 v1 클라이언트 인증서나 EKU 부재를 거부하면 조용히 깨진다.
- 실패 시 판별: `BR_ERR_X509_NOT_TRUSTED` 유지 → 폰이 DHU 신원 자체를 거부(정책) → 구글 앱 경로 종료, AARE/동글로 전환.
