# GD13MY Phase 8 — Android Auto 인증 후속 연구

기준일: 2026-11-25 | 범위: 개인 연구, 비배포 | 상태: 외부 문헌 조사 및 시험 설계

## 1. 신규 발견 및 판단

- Open Headunit(OHU) 3.3.0에서 AA 17.4 USB 연결 및 20분 통화 성공 보고가 2026-09-01에 올라왔다. 인증서 전면 차단 가설에 반하는 프로젝트 수준의 증거다. 단, 실제 송신 리프 지문은 없다. [#387](https://github.com/andreknieriem/open-headunit/issues/387)
- AA 17.4 이후 구형 무선 시작 방식이 제한된다는 OHU README가 있다. USB TLS 인증 정책 변경과 무선 시작 정책을 혼동하면 안 된다. [OHU README](https://github.com/andreknieriem/open-headunit)
- OHU #14에서 관리자가 2026-01-05 SSL 엔진 재작성 시험판을 제공했다. 1월 13일 이슈를 닫았으나 최초 신고자가 성공했다고 확인한 기록은 없다. TLS 엔진 차이도 조사할 가치가 있지만 인증서 문제 해결의 증거는 아니다. [#14 원문](https://github.com/andreknieriem/open-headunit/issues/14)
- 인증서 출처를 묻는 #637(2026-07-02)은 확인된 페이지에서 관리자 답변이 없다. 기존 연구의 DHU 유래 진술은 독립적으로 확인되지 않았다. [#637](https://github.com/andreknieriem/open-headunit/discussions/637)
- OHU 이슈 목록에는 2026-11-12 LineageOS 태블릿 보안 검사 실패도 있다. 본문 접근에 실패했으므로 원인 및 해결 여부는 미확인이다. [#1280](https://github.com/andreknieriem/open-headunit/issues/1280)
- AARE의 인증서 문서는 폰 리프 만료를 2026-12-31로 설명한다. GD13MY 과거 관측은 2027-02-17이다. 두 관측을 동일 인증서로 취급하면 안 된다. 인증서 갱신 가능성은 현 실폰의 공개 체인 재측정으로 확인해야 한다. [AARE 문서](https://github.com/prototux/AARE/blob/main/docs/certificates.md)

## 2. 출처, 역사, 사용 프로젝트 및 권한

Google-Android-Reference의 기존 공개 메타데이터는 2014-07-08부터 2044-07-07까지 유효, RSA 2048, GAL 발급, serial 0x7653이다. 유효기간 시작은 최초 공개 날짜가 아니다. OHU는 Michael Reid의 headunit을 계승한다고 명시한다. 최초 커밋 및 원본 배포물까지의 계보는 이번 조사에서 확정하지 못했다. [OHU](https://github.com/andreknieriem/open-headunit), [원본 프로젝트](https://github.com/mikereidis/headunit), [기존 교차 검증](https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/Codex-authentication-resolution/RESEARCH_VALIDATION.md)

| 프로젝트 | 확인된 관계 | 한계 |
|---|---|---|
| Open Headunit | Google-Android-Reference가 포함된 것으로 공개 토론에 명시 | 릴리스별 실제 송신 리프 미확인 |
| Michael Reid headunit | OHU의 선행 프로젝트 | 동일 인증서 사용 시점 미확인 |
| JanRi3D/OpenAuto | README가 AASDK 계열 인증서를 사용한다고 명시 | Reference와 동일한 신원 아님 |
| Crankshaft/OpenAuto Pro | 실사용 및 버전 호환성 보고 존재 | 개별 세션 인증서 식별 안 됨 |
| pi-auto-headunit | 자체 시험 신원 거절 재현, 승인된 신원 요구 | 신규 발급 경로는 제공하지 않음 |

출처: [JanRi3D](https://github.com/JanRi3D/OpenAuto), [pi-auto-headunit](https://github.com/blakereuben/pi-auto-headunit), [OHU 토론](https://github.com/andreknieriem/open-headunit/discussions/637).

OHU 코드는 AGPL-3.0이다. [LICENSE](https://github.com/andreknieriem/open-headunit/blob/main/LICENSE). 코드 사용권과 제3자 인증 신원 사용 허가는 별개다. 인증 자료의 별도 허가 조건은 확인되지 않았다. 비배포 연구 역시 자동으로 사용 허가를 부여하지 않는다. 본 보고서는 공개 인증서 정보의 비교만 수행하며 미승인 개인키의 획득, 이전, 배포를 요구하지 않는다.

## 3. 실사용 사례 및 정책 변화

| 일자 | 환경/관측 | 증거 수준 | 원본 |
|---|---|---|---|
| 2026-09-01 | OHU 3.3.0, AA 17.4, USB 20분 통화 | 사용자 성공 보고, 리프 미확인 | [#387](https://github.com/andreknieriem/open-headunit/issues/387) |
| 2026-08-29 | AA 업데이트 뒤 무선 실패, USB 정상 | 사용자 보고 | [#908](https://github.com/andreknieriem/open-headunit/issues/908) |
| 2026-10-12/22 | AVIN Android 13, USB 정상 및 수정 알파에서 무선 연결 반복 성공 | 로그 첨부 보고, 로그 본문 미검증 | [#1103](https://github.com/andreknieriem/open-headunit/issues/1103) |
| 2026-07-24 | PX5, Vivo X300 Ultra, H.265에서 검은 화면, H.264에서 표시 정상 | 사용자 보고, TLS 이후 단계 | [#696](https://github.com/andreknieriem/open-headunit/issues/696) |
| 2025-12-30~2026-01-13 | Pixel 8 Pro, OHU 1.2.1/1.3.0 연결 실패, SSL 재작성 제안 | 해결 미확인 | [#14](https://github.com/andreknieriem/open-headunit/issues/14) |
| 2025-08-30 | Belva BMV62W, AA 14.7, S21 계열 실패/S23 성공 | 폰별 차이 보고, 원인 미확인 | [Google 커뮤니티](https://support.google.com/androidauto/thread/369324198/error-code-7?hl=en) |
| 2024-09 이후 | Crankshaft에서 AA 12.7 이후 시작 실패, 12.6 대조 및 이후 부분 개선 보고 | 인증서 폐기 증거 아님 | [Reddit](https://www.reddit.com/r/AndroidAuto/comments/1fibizp/android_auto_not_starting_on_crankshaft_head_unit/) |

Google 공식 FAQ는 오류 7을 보안 통신 수립 실패로 설명하며 구체적 인증서 거부와 동일시하지 않는다. [FAQ](https://support.google.com/androidauto/thread/2467794/faq-what-are-these-cryptic-error-messages-that-i%E2%80%99m-seeing-how-do-i-deal-with-them?hl=en-gb). Reference의 실제 폐기/차단을 증명하는 CRL, 정책 문서 또는 지문이 포함된 실폰 거부 로그는 확보하지 못했다. XDA에서 새로운 판정 가능한 원본 사례도 확보하지 못했다.

## 4. 기술적 비교

아래 파싱 결과는 기존 Codex 실측을 인용한 것이며 이번 연구에서 실행하지 않았다.

| 항목 | Reference | AASDK JVC | DHU 2.1 | 프로젝트 자체 시험 신원 |
|---|---|---|---|---|
| RSA | 2048 | 2048 | 2048 | 시험 설정에 따름 |
| 유효기간 | 2014–2044 | 2014–2045 | 2014–2048 | 생성 설정 |
| 시간 형식 | Z | -0700 | -0700 | Z 시험 |
| BearSSL 0.6 | 0 | 48 | 48 | 기존 가상 시험 통과 |
| OpenSSL 일반 검증 | 통과 | 13 | 13 | 시험 CA에서 통과 |
| 실제 GD13MY 수락 | 미확인 | 미확인 | 미확인 | 과거 PC 진단에서 거부 |

[기존 실측 원본](https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/Codex-authentication-resolution/RESEARCH_VALIDATION.md)

Reference의 DER 헤더상 SHA256withRSA 서명으로 알려져 있으나 이번 조사에서 원본 ASN.1 독립 검사를 수행하지 않았다. 인증서 서명 알고리즘, TLS CertificateVerify 서명 방식, 협상 암호군은 각각 다른 항목이다. 현재 CE는 TLS 1.2 및 RSA 클라이언트 신원, 기존 ARM 시험에서 0xC02F(ECDHE_RSA_WITH_AES_128_GCM_SHA256)를 지원한다. 이 결과는 실제 폰이 같은 cipher를 선택하거나 동일한 클라이언트 인증을 요구함을 입증하지 않는다. CertificateRequest의 certificate_types, supported_signature_algorithms, distinguished_names 원시 목록을 새 실폰 시험에서 확인한다. 빈 CA 목록도 무조건 거절의 의미가 아니다. RFC 5246 §7.4.4, §7.4.8, §7.4.9 참조: https://www.rfc-editor.org/rfc/rfc5246 .

체인은 리프와 필요한 중간 CA를 순서대로 구성하며 신뢰 앵커는 별도로 관리한다. 루트 포함 자체가 거부 원인이라는 가설은 현재 증명되지 않았다. RTC는 폰과 CE 각각의 UTC, 양쪽 인증서 유효기간을 기록한다. 시스템 시계를 검증 통과 목적으로 과거로 조작하지 않는다. 추가 정책(역할 제한, EKU, 폐기, 앱 버전별 정책)은 가능성이지만 미확인이다.

## 5. 기존 연구와 중복되는 항목

자체 서명 거부, BearSSL 시간 오류 48, DER 우선순위, 구성 실패 시 handshake 미실행, TLS 클라이언트/서버 역할, 가상 폰 영상 및 재연결 성공은 이미 알려졌다. 재개발하지 않는다. 기존 84개 Python 테스트와 ARM 회귀는 기존 기록이며 이번 실행 결과가 아니다. [회귀](https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/Codex-authentication-resolution/TLS_REGRESSION_RESULTS.md), [에뮬레이터](https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/Codex-authentication-resolution/EMULATOR_VALIDATION.md).

## 6. Codex 실행 계획 — 승인된 평가 신원 확보 후

### P0: 기준선 확보 (소스 수정 없이)

1. git rev-parse HEAD, git status --short, 빌드 DLL SHA-256을 기록한다. 기존 테스트 결과와 현재 소스 일치 여부를 확인한다.
2. 공식 DHU로 동일 폰/케이블에서 대조 시험한다. 정확한 AA 버전, Android OS, Play services, DHU 버전, UTC를 남긴다. DHU는 원래 도구로 사용한다. [공식 DHU](https://developer.android.com/training/cars/testing/dhu)
3. 승인된 평가 신원을 격리된 시험 이미지에만 등록한다. 기존 지원 경로와 DER 우선 정책을 사용하고 CA, 키 일치, 유효기간, 피어 이름/지문 설정을 확인한다. 승인 범위 및 만료도 기록한다. 개인키는 로그, Git 및 결과 보고서에 포함하지 않는다.
4. 기존 가상폰 회귀를 실행하여 변경 전 기준선을 확보한다. 이어 순정 메뉴 경로에서 실폰을 연결한다. AOA, AAP 버전, TLS 구성, 핸드셰이크, 인증 완료, 서비스 탐색, 영상·분리·재연결을 순차적으로 측정한다. 차량 플래시는 하지 않는다.

### P1: 기존 진단 재사용 및 부족한 관측만 보완

| 파일/함수 | 기존 기능 | 필요할 때만 추가할 항목 |
|---|---|---|
| src/ce/ce_aa_tls.c / configure(), open_credential(), read_credentials() | 로딩 지문, 키 일치, CA/시간 검증 | 구성 실패 단계가 모호하면 구조화된 오류 코드 |
| src/ce/ce_aa_tls.c / handshake() | 실제 송신 리프 지문, 방향별 handshake 번호, CCS, 버전/cipher, alert | CertificateRequest 필드 및 실제 송신 CertificateVerify 서명 알고리즘 관측; 암호화 레코드 내부를 평문으로 오인하지 않음 |
| src/ce/ce_aa_tls.c / discover() | AUTH_COMPLETE, 서비스 탐색 | 응답 유형/상태/시간이 부족한 경우만 보강 |
| src/ce/ce_aa_usb_client.c | 제출/타임아웃/정리 분리 | 기존 USB 진단으로 부족한 경우만 전송 상관 ID |
| tools/verify_gd13my_virtual_phone.py | 순정/재연결 가상 시험 | 필요한 경우 합성 신원으로 signature algorithms 조건 변화 회귀 |

함수와 관측 범위는 기존 교차 검증 문서 기준이며 현재 HEAD에서 재확인한다. TLS 라이브러리 교체나 인증 검증 약화는 기본 작업에 포함하지 않는다. CertificateVerify(type 15) 송신은 상대의 검증 성공과 다르다. Finished(type 20)는 TLS 1.2에서 암호화되어 있기에 수동 캡처의 CCS/레코드만으로 성공을 단정하지 않는다. 기존 엔진 완료 상태와 양방향 암호화 애플리케이션 통신, 필요시 승인된 시험 피어의 엔진 진단을 대응시킨다.

### P2: 실패 분기

| 마지막 성공 단계 | 다음 조치 |
|---|---|
| AOA 이전 | USB 열거/권한/케이블 확인 |
| AAP 버전 이전 | 기존 MUSB/DMA/프레이밍 진단 비교 |
| configure 실패 | 로딩 파일, 시간, 키 일치, 체인 진단(재연결 반복 금지) |
| ClientHello 이후 ServerHello 없음 | USB 응답과 TLS 제안 조건 분리, DHU 대조 |
| CertificateRequest 이후 클라이언트 플라이트 없음 | 요청 알고리즘/키 적합성, 기존 엔진 상태 확인 |
| 클라이언트 플라이트 후 실패 | 로딩/송신 리프 지문 대응, 폰 Conscrypt/alert 확인; 타임아웃만으로 인증 거부 단정 금지 |
| TLS 완료 후 AUTH_COMPLETE 실패 | AAP 상태/프레임 분석 |
| AUTH_COMPLETE 후 서비스 탐색 실패 | 암호화 프레임 및 서비스 응답 분석 |
| 서비스 탐색 후 검은 화면 | H.264 협상, 표면 권한, 프레임 및 GDI 검사 |

ADB 로그 수집 예: `adb logcat -v threadtime > phone-session.log` (ADB 승인 및 개인 정보 제거 필요). UART와 PC 로그에는 세션 ID 및 UTC를 함께 기록한다. USB 캡처가 가능한 환경이라면 기존 USBPcap/Wireshark로 세션을 기록하되 암호화 데이터의 평문 관측을 주장하지 않는다.

완료 기준: 동일 승인 신원으로 로딩/송신 지문 일치, 상호 TLS 엔진 완료, AUTH_COMPLETE 성공, 서비스 탐색 응답, 실제 800×480 표시, USB 분리 시 순정 표시 반환 및 새 세션 성공. 터치 전달은 별도 항목이다.

## 7. 다른 신원 확보 경로

기존 Cinemo/ART/ECORE/NXP 및 3PL 조사를 대체할 새로운 독립 개발자용 공개 발급 프로그램은 확인하지 못했다. pi-auto-headunit도 승인 신원 외부 공급을 요구하며 자체 생성 시 오류 2/7을 보고한다. [프로젝트](https://github.com/blakereuben/pi-auto-headunit). 이는 별도 발급 제도가 아니라 독립적 실패 사례다. AARE는 폰 측 구현으로 원래 요구 사항과 다르다. [AARE](https://github.com/prototux/AARE). 공식 DHU는 앱 시험 도구이지 CE용 신원 제공 프로그램임을 입증하지 않는다. 기존 SDK 문의의 답변을 확인하고 WinCE 6.0/ARM 타깃, 평가 신원 범위, 기존 수신기 연동 권한을 질문한다. 중복 문의를 보내지 않는다.

## 8. 추가 실험 및 미확인 가설

- 동일 폰에서 공식 DHU와 승인 신원 기반 CE를 비교하여 USB/버전/알고리즘/인증 오류를 분리한다.
- 공개 인증서만 이용해 메타데이터와 릴리스 태그별 지문 이력을 비교하고 최초 공개 커밋을 추적한다. 키 파일은 수집하지 않는다. 릴리스의 인증서 동일성이 확인되어도 실제 세션 지문의 직접 증거와 구별한다.
- 현 폰의 공개 서버 체인을 재측정하여 기존 2027-02-17 기록과 AARE 2026-12-31 보고의 차이를 확인한다.
- 합성 CA로 CertificateRequest 알고리즘 불일치, 체인 누락, RTC 경계, 분할 레코드 및 종료 회귀를 검증한다. 기존 테스트가 커버하면 재사용한다.
- AA 최신판 전면 차단, Reference 개별 폐기, 루트 포함 거절, 특정 암호군 필수 및 추가 장치 증명 정책은 모두 미확인이다.

## 9. 연구 한계와 최종 결론

웹 원문, 검색 결과와 앞선 저장소 조사에 근거했다. 로컬 F: 빌드, UART 원본, 첨부 실폰 로그, 실제 릴리스 실행 및 인증서 파서 실험을 이번에 수행하지 않았다. 최초 공개 커밋, 모든 파생 프로젝트의 지문, XDA 독립 성공 사례, 최신 폐기 상태 및 신규 공식 발급 경로는 미확인이다. #637의 DHU 유래 진술은 확인된 공개 토론과 일치하지 않아 보류한다. 최근 OHU USB 성공은 유의미하나 특정 신원 수락의 직접 증거가 아니다. 현재 실질적 다음 단계는 승인 신원 확보와 증거가 연결된 실폰 시험이며, 성공 확률 수치는 제시하지 않는다.
