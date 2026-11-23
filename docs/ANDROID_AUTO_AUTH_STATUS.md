# Android Auto 구현 및 인증 상태

2026-11-23 기준. 대상은 현대 i30 GD13MY 국내형 표준형 2세대 `GD13MY.KOR.SOP.00.061`과 WinCE ARM 에뮬레이터다.

## 확인된 동작

| 경로 | 확인된 결과 | 남은 검증 |
| --- | --- | --- |
| Windows 공식 Desktop Head Unit (DHU) | ADB 터널에서 실폰 TLS 검증 성공과 실제 Android Auto 화면 확인 | WinCE USB 수신기 검증은 별도 |
| 순정 WinCE 에뮬레이터와 가상 폰 | 순정 동의 화면과 내비 메뉴의 Android Auto 터치, 지도 바로 위 창 배치, AOA/버전 교환, 상호 TLS, 영상 채널, 800×480 LCD 시험 프레임과 확인 응답 | 장시간 스트리밍, 터치·오디오·마이크, 순정 표시 중단·복귀, 실제 차량 |
| 순정 WinCE 에뮬레이터와 실폰 | AOA 재열거, Android Auto 1.7 응답, 순정 창 안의 인증 설정 안내 표시. 별도 TLS 진단에서 폰의 인증서 요청과 시험용 체인 수신 확인 | 실폰 TLS 완료와 실폰 영상 서비스 진입 |

`GDdNavi.exe`의 순정 메뉴 입력에서 `i30nav.dll`의 `I30ToggleProjection`을 같은 프로세스에서 호출한다. 800×480 투사 HWND를 지도 바로 위에 배치하고, `GetDCEx`의 형제 창 클리핑 및 순정 표시 상태를 사용한다. 목표 순서는 **시스템 팝업·후방카메라·공조/볼륨 OSD → Android Auto → 지도**다. `LibSystem.dll`과 `LibVideo.dll`의 후방 상태 경로를 연동했고, 실제 카메라의 합성 타이밍과 동일 HWND 내 OSD는 벤치 확인이 남았다. 에뮬레이터 뷰어에 시동 끄기·켜기와 USB 재연결 조작이 있다. 차와의 일치율은 측정하지 않았다. [WinCE 화면 통합](CE_NATIVE_DISPLAY_INTEGRATION.md) · [에뮬레이터](GD13MY_EMULATION.md)

CE ARM 수신기 `i30usb.dll`은 AOA 2.0, Android Auto 버전 교환, BearSSL 0.6 TLS 1.2, 영상 서비스 탐색과 H.264 Baseline 디코딩을 처리한다. 디코더가 제공하는 크롭을 적용해 순정 투사 창의 DC에 그린다. 통합 시험에서 LCD 3점에 적색이 출력됐다. 이어진 가상 USB 시험에서 분리 시 표시가 해제됐고 재연결 시 새 TLS 세션에서 LCD 3점에 녹색이 출력됐다. 두 시험 모두 상대 Z-Order를 확인했다. 별도 포그라운드 확인 플래그는 두 기록에서 모두 `false`다. 두 색상은 시험 영상이며, 장시간 연속 재생을 측정하지 않았다. 현재 CE 영상 프로필은 순정 오디오 포커스를 양보하며, 순정 Bluetooth 음악·통화와의 동시 실차 동작은 미검증이다. [CE 소스](../src/ce/) · [가상 폰 시험 도구](../tools/verify_gd13my_virtual_phone.py)

## 실폰 통신 오류 07

1. 물리 USB에서 실폰이 CE의 버전 질의에 Android Auto 1.7로 응답했다. 호스트 USB 어댑터는 AOA 재열거된 인터페이스를 실제로 열 수 있을 때 게스트에 연결을 알린다. 첫 bulk 출력이 타임아웃된 이전 세션도 있었으므로, 초기 USB 실패와 TLS 실패를 로그에서 구분한다.
2. 별도 물리 USB TLS 시험에서 폰이 TLS 1.2를 시작하고 헤드유닛 인증서를 요청했다. CE가 로드한 자체 발급 시험용 체인을 보낸 뒤 폰의 `CAR.GAL.SECURITY.LITE` 로그에 `Trust anchor for certification path not found`가 기록됐다. 해당 오류 07 시험에서 확인된 실패 지점은 폰의 헤드유닛 인증서 체인 검증이다. 사용자에게 표시되는 오류 번호만으로 다른 세션의 원인을 판별할 수는 없다.
3. CE에는 TLS 1.2, 실제 WinCE UTC 시각을 이용한 유효기간 검사, BearSSL 오류 코드 출력이 구현돼 있다. 에뮬레이터는 호스트 UTC를 전달한다. PEM은 리프부터 중간 인증서 순서로 최대 4장을 읽으며, CE는 폰의 인증서를 CA와 피어 이름 또는 SHA-256 지문으로 검증한다. 중간 인증서가 필요한 가상 상호 TLS 시험도 통과했다. 이번 실폰 실패에서는 날짜를 강제 변경할 근거가 없었다. [TLS 구현](../src/ce/ce_aa_tls.c)
4. Windows에서 보였던 실폰 화면은 Google DHU의 자격 증명과 ADB 개발자 연결로 재현됐다. WinCE 수신기에 사용할 수 있는 헤드유닛 인증 자료의 발급과 사용 권한은 확인되지 않았다. USB 디버깅 허용은 ADB 접근을 허용하며, 실폰의 헤드유닛 신뢰 설정은 별도다. 공급사 문의에 대한 답변 도착 여부는 이번 인계에서 확인하지 않았다. [Google DHU 연결 안내](https://developer.android.com/training/cars/testing/dhu)

## 로컬 검증 기록

아래 파일은 기존 작업 폴더의 `build/gd13my-native-oem-screen/` 기준이다. 로그에는 기기 정보가 포함될 수 있어 로컬에만 보관한다.

| 파일 | 확인할 항목 |
| --- | --- |
| `stock-menu-full-boot/virtual-phone.json` | 순정 메뉴 터치, 표시 상태 발행, Z-Order, 영상 확인 응답 1회, 적색 픽셀 3점 |
| `virtual-usb-replug/virtual-phone.json` | `cable_detached`, `display_released`, `replug_tls`, 두 번째 영상 확인 응답과 녹색 픽셀 3점 |
| `phone-wait/live-wait-screen.usb.log` 및 `.serial.log` | 실폰 버전 응답, 인증 설정 안내로 전환 |
| `cert-chain/usb-current-phone-tls.log` | 폰의 체인 신뢰 루트 오류 |
| `cert-chain/arm-usb-test.json` | ARM TLS 1.2와 중간 인증서 체인 시험 |
| `live-phone-visible.stderr.log` 및 `cert-chain/adb-restarted-dhu.stderr.log` | Windows DHU 기준 연결에서 `Verify returned: ok` |
