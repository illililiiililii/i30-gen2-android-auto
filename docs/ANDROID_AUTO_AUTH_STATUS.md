# Android Auto 구현 및 인증 상태

11월 25일 교차 검증에서는 공개 인증서의 오프셋 시간 오류와 과거 실폰의 시험 신원 거부를 별개로 확인했다. WinCE 로더의 구성 오류는 TLS 송신 전에 종료된다. 새 진단은 실제 전송한 리프 지문을 UART에 기록한다. 순정 전체 부팅은 가상폰 `AUTH_COMPLETE`, 800×480 영상과 USB 재연결을 통과했다. 새 ARM 빌드의 실폰 시험은 보류 상태다. [인증 해결 인계](Codex-authentication-resolution/FINAL_HANDOFF.md)

2026년 11월 23일 · GD13MY.KOR.SOP.00.061 · Windows CE 6.0 ARM

[11월 24일 XDA·펌웨어 분석과 수신기 재검증](ANDROID_AUTO_REVERSE_ENGINEERING.md)

## 순정 화면 통합 상태

`GDdNavi.exe`는 내비 메뉴에서 `i30nav.dll`의 `I30ToggleProjection`을 같은 프로세스에서 호출한다. 800×480 투사 창은 지도 위에 배치하며 `GetDCEx`의 형제 창 클리핑과 `LibSystem.dll`·`LibVideo.dll`의 후방 표시 상태를 사용한다. 이전 가상 폰 시험에서 순정 메뉴 터치, 영상 확인 응답, 적색 LCD 픽셀 3점을 확인했다. 가상 USB 분리 후 표시가 해제됐고, 재연결한 새 TLS 세션에서 녹색 픽셀 3점을 확인했다. 상대 Z-Order는 두 시험에서 확인했고 별도 포그라운드 확인 플래그는 두 기록 모두 `false`였다. 실차 카메라 합성, 동일 HWND의 OSD, 장시간 스트리밍과 순정 Bluetooth는 벤치 검증이 남았다. [순정 화면 통합](CE_NATIVE_DISPLAY_INTEGRATION.md) · [가상 폰](../build/gd13my-native-oem-screen/stock-menu-full-boot/virtual-phone.json) · [가상 USB 재연결](../build/gd13my-native-oem-screen/virtual-usb-replug/virtual-phone.json)

기존 순정 WinCE 이미지에 실폰을 연결해 AA 1.7과 인증 설정 안내를 확인했다. CE 영상 경로는 BearSSL 0.6과 H.264 Baseline을 사용하며 순정 오디오 포커스를 양보한다. [순정 WinCE 실폰 대기 화면](../build/gd13my-native-oem-screen/phone-wait/live-wait-screen.json) · [CE 포팅 상태](CE_PORTING_STATUS.md)

## 실폰에서 확인한 실패 단계

삼성 폰은 USB AOA로 재열거됐고 Android Auto 1.7 응답을 보냈다. 헤드유닛의 TLS ClientHello 뒤 폰의 ServerHello, Certificate, ServerKeyExchange, CertificateRequest, ServerHelloDone을 관측했다. 이어 PC 진단에서 자체 발급 헤드유닛 인증서를 보내자 폰이 `Trust anchor for certification path not found`를 기록했다. USB 쪽에서는 다음 응답을 기다리다 시간 초과됐다. 폰 로그로 확인된 실패 지점은 **헤드유닛 인증서 체인 검증**이다. 폰이 CertificateVerify를 검증했다는 증거와 상호 Finished, `AUTH_COMPLETE`, 암호화된 서비스 탐색은 이 시도에서 확인되지 않았다. 개발자 서버를 통한 별도 재현에서도 같은 시험 신원으로 연결이 닫히며 화면에 오류 07이 표시됐다. [실폰 초기 TLS 응답](../build/gd13my-native-oem-screen/live-phone-aoa-auth-stage.json) · [USB 송신](../build/gd13my-native-oem-screen/live-phone-usb-trust-root-cause.log) · [폰 검증 오류](../build/gd13my-native-oem-screen/live-phone-usb-trust-android.log) · [개발자 서버 시험](../build/gd13my-native-oem-screen/live-phone-native-identity-fresh.log)

| 관찰 | 실패 위치 |
| --- | --- |
| 최신 Windows 직접 USB 재시험에서 삼성 `04e8:6860`을 열거한 직후 접근 거부 | AOA 전 USB 접근. Windows가 WinUSB 서비스를 정상으로 표시한 뒤 재시도해도 같은 결과였다. [첫 USB 시험](../build/gd13my-aa-error07/pc-live-probe.jsonl) · [재시험](../build/gd13my-aa-error07/pc-live-probe-recheck.jsonl) |
| 이전 CE ARM USB에서 bulk OUT 타임아웃 | 버전 요청 단계. [ARM USB 로그](../build/gd13my-ce-tls-diagnostics/early-startup/phone-arm-usb.jsonl) |
| Windows 수신기에서 의도적으로 신뢰되지 않은 CA 사용 | 수신기가 폰의 서버 인증서를 거부. [PC TLS 로그](../build/gd13my-phase78/boot-projection-untrusted.projection.jsonl) |
| 직접 USB에서 자체 발급 헤드유닛 인증서 사용 | 폰이 헤드유닛의 클라이언트 인증서 체인을 거부. [폰 TLS 로그](../build/gd13my-native-oem-screen/live-phone-usb-trust-android.log) |
| 같은 날 공식 DHU 2.0을 테스트폰에 ADB로 재연결 | Android 15·Android Auto `18.0.664264-release`에서 AA 1.7, TLS 1.2, `ECDHE-RSA-AES128-GCM-SHA256`(`0xC02F`), 인증서 검사 성공과 오디오 스트림을 관측. 이전 공식 DHU 시험에서 USB와 ADB 화면 출력도 확인했다. [최신 DHU 로그](../build/gd13my-aa-error07/dhu-20261123-222431/stderr.log) · [이전 USB 시험](USB_CONNECTION_TEST.md) |

폰이 보낸 공개 체인은 `CarService` leaf와 `Google Automotive Link` 발급자였다. 이 폰에서 관측한 leaf 만료는 2027-02-17 19:01:30 UTC다. AARE의 문서는 다른 앱 관측의 만료일도 기록하므로 실제 재시험에서는 그 세션의 leaf를 기준으로 판정한다. WinCE 시험 게스트는 과거 UTC를 1601년으로 읽었고, 현재 에뮬레이터 이미지에서는 시작 시 호스트 UTC를 동기화한다. 수신기가 폰을 검사할 때는 등록된 공개 CA와 예상 이름 또는 미리 등록한 지문을 쓴다. 폰이 헤드유닛을 검사할 때는 헤드유닛의 별도 클라이언트 체인과 대응 키가 필요하다. [실폰 공개 체인 메타데이터](../build/gd13my-ce-projection/phone-tls-public.json) · [CE 시계와 TLS](CE_PORTING_STATUS.md) · [AARE 인증서 연구](https://github.com/prototux/AARE/blob/main/docs/certificates.md)

## 구현 및 공개 사례 비교

AOA의 51·52·53 제어 전송과 액세서리 재열거 이후 bulk에서 AA 버전을 협상한다. AA 제어 채널 0의 메시지 3이 TLS 레코드를 옮긴다. 헤드유닛이 TLS 클라이언트이고 폰이 서버다. TLS 완료 뒤 헤드유닛이 평문 메시지 4 `AUTH_COMPLETE(0)`를 보내고, 이어 암호화된 서비스 검색과 채널 개설을 처리한다. USB 읽기 경계, AA 프레임 경계와 TLS 레코드 경계는 독립적이다. [Android AOA 명세](https://source.android.com/docs/core/interaction/accessories/aoa) · [OpenAuto 세션 코드](https://github.com/f1xpl/openauto/blob/development/src/autoapp/Service/AndroidAutoEntity.cpp) · [AARE 프로토콜 연구](https://github.com/prototux/AARE/blob/main/docs/certificates.md)

| 프로젝트 | 구현과 확인된 범위 |
| --- | --- |
| f1xpl/aasdk · f1xpl/openauto | `development`의 레거시 C++ 스택. AASDK가 AOA·USB, OpenSSL TLS 1.2의 BIO, 클라이언트 인증서와 키 로딩·일치 검사 및 프레임 분할을 맡고 OpenAuto가 버전·인증 완료·검색을 연결한다. 공개 코드에는 과거 헤드유닛 신원이 포함되어 있다. OpenAuto의 GPLv3 소스 라이선스에서 해당 신원의 발급·사용 권한은 확인되지 않았다. [AASDK TLS](https://github.com/f1xpl/aasdk/blob/development/src/Transport/SSLWrapper.cpp) · [프레임 분할](https://github.com/f1xpl/aasdk/blob/development/src/Messenger/MessageOutStream.cpp) · [OpenAuto](https://github.com/f1xpl/openauto) |
| JanRi3D/OpenAuto | 2026년 갱신된 Android용 Java 수신기. USB AOA/TCP, TLS flight, `AUTH_COMPLETE`와 검색을 구현했다. 프레임 조립기는 채널 간 조각이 섞이는 실폰 패턴도 처리한다. 저자는 ADAYO AC822X에서 USB 영상 투사를, 별도 실폰 시험에서 TLS 1.2와 `0xC02F`를 보고했다. 사용한 신원은 문서상 AASDK의 공개 신원이다. [실폰 시험 기록](https://github.com/JanRi3D/OpenAuto/blob/main/docs/TEST-RESULTS.md) · [세션 코드](https://github.com/JanRi3D/OpenAuto/blob/main/app/src/main/java/me/ri3d/openauto/aa/Session.java) · [프레임 조립](https://github.com/JanRi3D/OpenAuto/blob/main/app/src/main/java/me/ri3d/openauto/aa/FrameAssembler.java) |
| prototux/AARE | GPL-3.0의 폰 측 구현. TLS 서버 역할과 자체 생성 시험 인증서를 제공한다. 자체 데스크톱 시험 수신기 및 일부 수신기와의 호환성을 보고했다. AARE 폰 대역을 수락하는 수신기 사례는 Google Android Auto 앱의 헤드유닛 신뢰 정책을 검증하는 근거와 구분한다. [인증서 및 상호운용 설명](https://github.com/prototux/AARE/blob/main/docs/certificates.md) · [TLS 코드](https://github.com/prototux/AARE/blob/main/aap/src/main/kotlin/net/prototux/aare/aap/Cryptor.kt) |
| aa-proxy/aa-proxy-rs | GPL-2.0의 Rust AOA/네트워크 프록시. AOA 전환과 bulk 입출력·전달을 비교했다. 통과 모드에서는 양단 수신기와 폰이 TLS 신원을 사용하며, 프로젝트는 별도의 TLS 종료 모드도 갖는다. 사용 예는 호환 수신기 또는 DHU가 양단에 있는 구성이다. [프로젝트와 구성](https://github.com/aa-proxy/aa-proxy-rs) · [AOA 코드](https://github.com/aa-proxy/aa-proxy-rs/blob/main/src/aoa.rs) · [전달 코드](https://github.com/aa-proxy/aa-proxy-rs/blob/main/src/proxy.rs) |
| andresurena/android-head-unit-exploration | MIT 라이선스의 XUNZU/ZLINK 사후 분석과 수리 기록. 비교할 독립 Android Auto 수신기나 검증된 TLS 인증 구현은 확인되지 않았다. [프로젝트](https://github.com/andresurena/android-head-unit-exploration) |
| andreknieriem/open-headunit · opencardev 계열 | Open Headunit 사용자가 Android Auto 업데이트 이후에도 USB 연결이 정상이라고 보고했다. 별도의 이슈에는 Pixel 8 Pro의 오류 7이 기록됐다. Open Headunit의 판정은 자체 TLS 정책에 따르며 GD13MY는 기존 CA·이름 검증을 사용한다. opencardev/aasdk는 후속 포크다. 최신 Crankshaft 1.1 알파는 별도 코어를 사용하고, 사용자가 Raspberry Pi 4와 Android 16의 Galaxy Z Fold 6에서 USB 연결을 보고했다. 그 보고에는 헤드유닛 신원의 사용 권한이나 체인 정보가 없다. [Open Headunit USB 동작](https://github.com/andreknieriem/open-headunit/issues/908) · [오류 7 이슈](https://github.com/andreknieriem/open-headunit/issues/14) · [AASDK 포크](https://github.com/opencardev/aasdk) · [Crankshaft USB 연결 보고](https://github.com/opencardev/crankshaft/issues/800) · [Crankshaft 릴리스](https://github.com/opencardev/crankshaft/releases) |

## 변경과 검증

- CE 수신기에 여러 AA 프레임에 걸친 TLS 제어 메시지의 입력 처리를 추가했다. 메시지 ID가 두 조각에 걸쳐도 한 번만 소비하며, 채널·플래그·전체 길이·마지막 위치를 확인한다. 기존 DLL에서 이 입력의 거부를 재현했고, 새 DLL은 상호 TLS와 검색을 완료했다. 전체 길이가 맞지 않는 프레임은 거부한다. 게스트 UART는 ClientHello 송신, 첫 피어 데이터, TLS 성공과 cipher suite, `AUTH_COMPLETE`, 암호화 검색 요청을 각각 기록한다. [CE 구현](../src/ce/ce_aa_tls.c) · [ARM 시험](../build/gd13my-aa-error07/arm-usb-tls.json)
- PC 수신기는 로컬 X.509 검증 오류에 OpenSSL의 코드와 사유를 포함하며 TLS 협상 결과를 버전·cipher로 기록한다. 모의 시험에서 활성 세션 1회, 800×480 영상 5프레임, 터치·오디오·마이크, 정상 종료를 확인했다. [PC TLS 코드](../src/i30_receiver/tls.py) · [PC 모의 시험](../build/gd13my-aa-error07/pc-mock.jsonl)
- ARM 시험은 DER/PEM, RSA 키 일치, 시험 CA·이름·지문, 게스트 UTC, 중간 CA 유무, TLS 버전 불일치, 무응답, 암호화된 서비스·영상과 순정 화면 선점·복귀를 포함한다. 공식 DHU에서 관측한 `0xC02F`로 ARM 상호 TLS와 투사를 통과했다. 시험용 leaf에는 `clientAuth`와 `digitalSignature`를 사용하고 시험 CA에는 CA 제약과 인증서 서명 용도를 넣었다. REA가 새 DLL의 ARM PE32와 `COREDLL.dll` 가져오기를 확인했다. Python 회귀 시험 84개도 통과했다. [ARM 시험 코드](../tools/emulate_ce_usb.py) · [ARM 시험 로그](../build/gd13my-aa-error07/arm-usb-tls-dhu-cipher.json) · [ARM ABI](../build/gd13my-aa-error07/ce/abi.json) · [회귀 시험 로그](../build/gd13my-aa-error07/unittest.log)
- 새 순정 메뉴 이미지에 포함된 USB DLL은 빌드 매니페스트의 SHA-256과 일치하며, TLS 등록 파일은 0개다. 전체 순정 메뉴 재시험은 동의 입력 뒤 초기화 중 230초 제한에 도달해 USB 전송을 시작하지 못했다. [이미지 매니페스트](../build/gd13my-aa-error07/image.json) · [순정 메뉴 재시험](../build/gd13my-aa-error07/stock-menu-virtual-phone/virtual-phone.json)
- 같은 TLS 수정을 적용한 격리 WinCE LCD 시험이 통과했다. 가상 USB에서 AA 버전, 상호 TLS, 암호화 검색, 영상 서비스와 H.264 프레임 확인 응답 1회를 기록했다. 800×480 LCD의 세 표본은 RGB `255,0,0`이었다. 격리 이미지는 시험 창으로 LCD를 사용한다. [WinCE LCD 시험](../build/gd13my-aa-error07/lcd-bench/verify/virtual-phone.json) · [UART 로그](../build/gd13my-aa-error07/lcd-bench/verify/virtual-phone.serial.log)

## 적용 경로

- **A · 기존 구현 활용.** AASDK/OpenAuto의 초기화 순서와 프레이밍을 현재 수신기에 대조했다. 공개 프로젝트에 들어 있는 서드파티 신원은 발급 및 사용 권한을 확인할 자료가 없었다. 기존 CE BearSSL과 PC OpenSSL을 사용한다.
- **B · 평가 SDK.** Google은 앱 시험용 DHU를 제공한다. 이 공개 문서에서 별도로 쓸 수 있는 개인용 헤드유닛 신원 발급 경로는 확인되지 않았다. Cinemo는 Android Auto USB를 포함한 CORE Projection SDK를 안내한다. 기존 WinCE ARM 평가 문의의 발송을 확인했으며 2026-11-23 기준 답변, CE 6.0 지원, 평가용 신원 제공 여부는 미확인이다. P3는 Android Auto Projection 인증 파트너다. [Google DHU](https://developer.android.com/training/cars/testing/dhu) · [Cinemo CORE Projection](https://automotive.cinemo.com/products-and-services/cinemo-core/core-projection/) · [P3 인증 안내](https://p3-group.com/Insights/google-expands-p3s-3pl-accreditation-to-embrace-next-gen-android-autoprojection-aap-technology-certification/)
- **C · 자체 테스트.** 모의 폰과 별도로 생성한 시험 CA와 인증서로 전송·상호 TLS·서비스·영상 경로를 검증한다. 실폰 쪽 신뢰 결정은 실제 폰 로그로 판정한다. [격리 시험 실행기](../tools/verify_gd13my_virtual_phone.py) · [순정 메뉴 통합](CE_NATIVE_DISPLAY_INTEGRATION.md)
- **D · 지원 차량 비교.** 국내 G80 고급형 2세대 `DHBS.P2ALC.KR`의 공식 SW 버전은 `DHPE.KOR.SOP.00.057`이다. 미국형 G80 DIS의 USB 투사와 미국형 Elantra GT (GD)의 Android Auto 업데이트는 공개 자료에서 확인된다. 준비된 로컬 G80 폴더에는 PC용 Navigation Updater만 있다. 비교 대상 차량 이미지가 확보되면 USB·TLS·세션 모듈의 호출 구조와 저장 구조를 검증할 수 있다. [제네시스 국내 SW 목록](https://update.genesis.com/KR/KO/updateNoticeView/software-version) · [미국형 G80 안내](https://owners.genesis.com/genesis/us/mygenesis/manuals/glovebox-manual/2018/G80/8056_2_T1_G80_GettingStartedGuide_R10.pdf) · [현대 미국 GD 서비스 문서](https://static.nhtsa.gov/odi/tsbs/2016/SB-10081532-0699.pdf) · [기존 대조 조사](PHASE7_8_RESULTS.md)

## 실폰 재시험

두 방향의 신뢰 자료를 준비한다. 헤드유닛에는 평가용으로 발급되고 테스트폰이 신뢰하는 클라이언트 인증서 체인과 대응 RSA 키, 수신기가 폰을 검증할 공개 CA와 예상 이름 또는 등록된 SHA-256 지문이 필요하다. WinCE 실험 프로필의 경로는 `\DiskA\Application\NAVI\`이며 기존 `i30-client.pem`(leaf, 중간 CA 순), `i30-client-key.pem`, `i30-ca.pem`, `i30-peer.txt` 또는 `i30-peer-sha256.txt`를 읽는다. 인증 자료가 없는 기본 이미지로는 버전과 인증 설정 안내까지 확인할 수 있다. 실험은 별도 에뮬레이터 이미지에서 실행한다. [CE 설정 경로](../src/ce/ce_aa_tls.c) · [PC TLS 등록 옵션](USB_CONNECTION_TEST.md)

1. 같은 폰과 데이터 케이블로 공식 DHU를 실행해 화면을 확인한다. 종료 후 케이블을 분리해서 폰을 기본 USB 모드로 되돌린다.
2. 에뮬레이터에서 아래 명령으로 새 이미지를 연다. 기본 WinUSB 경로에 접근 가능한 포트를 사용한다. 내비 메뉴에서 **Android Auto**를 누르고 케이블을 다시 연결한다.

   ```powershell
   .\tools\run_gd13my_phase78.ps1 -StockProjectionImage .\build\gd13my-aa-error07\gd13my-aa-error07.img -UsbPort 1-2
   ```

3. Android Auto 버전, 07 화면의 재현 여부와 시각, `build/gd13my-boot`의 해당 UART·USB 로그를 기록한다. 평가 자료를 등록한 시험에서는 TLS 완료, `AUTH_COMPLETE`, 암호화된 검색, 실제 800×480 프레임, 화면 조작과 연결 해제를 순서대로 확인한다. 개인키 파일은 시험 보고에 필요하지 않다.
