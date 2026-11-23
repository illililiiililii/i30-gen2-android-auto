# Android Auto 수신기 CE 포팅

## GD13MY 시험 이미지

### 순정 CE 안의 TLS 인증

`gd13my-aa-ce-tls.img`에는 CE ARM USB 클라이언트와 BearSSL 0.6이 들어 있다. 순정 메뉴와 부팅 설정이 시작하는 같은 USB 드라이버가 AOA와 버전 교환을 마치면 그 파이프에서 Android Auto 제어 프레임으로 TLS 1.2를 교환한다. WinCE의 `CeGenRandom`과 시스템 시각을 사용한다. 시험 프로필의 CA, 피어 이름과 RSA 클라이언트 인증서·키로 양방향 인증을 검증하고, 신뢰 설정이 없으면 버전 교환 뒤 파이프를 정리한다. 이미지에는 인증 자료가 들어 있지 않다. [ARM 실행과 인증 검증](../build/gd13my-ce-tls/arm-usb-tls.log) · [BearSSL API](https://www.bearssl.org/api1.html)

후속 `gd13my-aa-ce-session.img`는 인증 뒤 `AUTH_COMPLETE`, 암호화된 서비스 탐색과 종료 응답까지 구현한다. 이 빌드는 GD13MY 식별 정보로 응답하며 미디어 채널은 등록하지 않는다. ARM 시험에서 시험 피어와 상호 인증, 서비스 탐색 및 정상 종료를 확인했다. 실폰용 인증 자료, 지속 영상 채널, H.264 출력·터치 및 순정 후진·오디오 선점 연결이 필요하다. 표준 실행기는 이 이미지를 별도 설정 프로필에서 사용한다. [ARM 세션 로그](../build/gd13my-ce-session/arm-usb-tls.log) · [이미지 감사](../build/gd13my-ce-session/image.json)

순정 내비 메뉴의 Android Auto 영역에서는 터치 누름과 떼기를 모두 순정 메뉴 전환 처리 전에 가로챈다. 영역을 누르는 동안 순정 경로정보 전환을 막고, 떼면 `i30aa.exe -i30run`을 시작한다. 영역 밖과 다른 화면은 순정 입력 처리로 진행한다. [ARM 터치 시험](../build/gd13my-ce-session/arm-menu.log)

### WinCE H.264 출력 시험

`src/ce/ce_aa_video.c`는 Baseline H.264 Annex B 프레임을 ARM에서 디코딩하고, 호출자가 소유한 WinCE 장치 컨텍스트에 최대 800×480 BGRA 그림을 그린다. ARM 시험은 생성한 800×480 H.264 프레임을 실제 ARM 디코더에 넣어 `StretchDIBits` 인수와 디코딩된 색상을 대조했다. 시험에는 WinCE API 대역을 썼다. 실폰 영상 서비스와 순정 화면 권한 연결은 남아 있다. [ARM 영상 시험](../build/gd13my-ce-video/arm-video.log) · [h264bsd 소스](https://github.com/oneam/h264bsd/tree/42bcb5d753ad86d84903354bf3c68423c28adb7b) · [Windows CE 출력 API](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms940374%28v%3Dmsdn.10%29)

`tools/build_ce_minimal.py --h264-source <h264bsd 경로> --compiler <ARM 컴파일러>`는 별도 진단 실행 파일 `build/gd13my-ce-video/i30video.exe`를 빌드한다. 이 실행 파일은 로컬 시험 스트림을 읽으며 기본 펌웨어 이미지에는 포함하지 않는다.

후속 `gd13my-aa-ce-projection.img`에는 WinCE USB 드라이버에 영상 채널을 연결했다. ARM 시험에서 등록된 시험 TLS 피어가 전송한 암호화·분할 H.264 메시지를 재조립하고 800×480 그림을 WinCE GDI 대역에 보냈다. 포그라운드 소유권을 바꾼 시험에서는 두 번째 영상 그리기 없이 연결을 정리했다. 영상 채널은 순정 화면 관리자가 `I30.GD13MY.VideoSurface.1` 전면 창을 제공한 경우에만 광고한다. 실제 순정 후진·경고와 이 창을 연결하는 작업 및 실폰 수신기 인증 자료는 남아 있다. 현재 USB 연결은 기존 Attach 경로의 8초 한도를 사용한다. 장시간 사용에는 USB 통지 및 작업 스레드 수명 관리가 필요하다. [ARM 통합 시험](../build/gd13my-ce-projection/arm-projection.log) · [실폰에서 관찰한 버전 응답](../build/gd13my-ce-projection/phone-version.jsonl)

표준 에뮬레이터 실행기는 WinCE의 USB 요청 뒤 호환 폰이 한 대일 때 포트를 자동 선택한다. 여러 대라면 `-UsbPort 1-2`처럼 지정한 포트만 열고, `-UsbPort ''`는 물리 USB 전달을 비활성화한다.

별도의 로컬 벤치 사본에서 순정 WinCE가 영상 진단 프로그램을 시작했다. 110초에 GDI 출력 성공 로그와 LCD 그래픽 평면의 세 위치에서 RGB565 `f800`(빨강)을 함께 읽었다. 입력은 생성한 H.264 시험 영상이었다. 110초는 진단 프로그램의 첫 프레임까지이며 순정 지도 부팅 시간과는 별개다. [게스트 LCD 읽기](../build/gd13my-ce-projection/guest-lcd-proof.json) · [게스트 UART](../build/gd13my-ce-projection/guest-lcd.serial.log)

시험용 등록에는 게스트 `\DiskA\Application\NAVI`에 신뢰 CA `i30-ca`, 헤드유닛 인증서 `i30-client`, 헤드유닛 RSA 키 `i30-client-key`가 필요하다. 각 파일은 DER 또는 PEM을 지원하며, 같은 이름의 DER 파일이 있으면 먼저 사용한다. `i30-client.pem`에는 헤드유닛 인증서부터 발급 중간 인증서 순서로 최대 네 장을 담을 수 있다. 이 경우 `i30-client.der`이 없는 시험 이미지에서 사용한다. DER 인증서, CA와 키는 파일당 한 개씩 읽는다. PEM 키는 암호화하지 않은 PKCS#1 또는 PKCS#8 RSA를 지원한다. 순정 펌웨어와 배포 시험 이미지에는 이 인증 자료가 포함되지 않는다. ARM USB 시험은 OpenSSL로 생성한 임시 자료를 사용한다.

폰의 신원은 `i30-peer.txt`의 호스트명이나 `i30-peer-sha256.txt`의 SHA-256 지문으로 설정한다. 둘 중 하나를 설정하며 두 방식 모두 CA 검증을 거친다. ARM 시험에서 올바른 체인·지문을 통과시키고 지문 불일치 및 신뢰되지 않은 CA를 각각 거부했다. 연결된 삼성 폰은 2027년 2월 17일 UTC까지 유효한 `CarService` 인증서와 TLS 1.2 `CertificateRequest`를 보냈다. [ARM 지문 시험](../build/gd13my-ce-tls-diagnostics/early-startup/arm-projection.log) · [실폰 인증 요청 로그](../build/gd13my-ce-projection/phone-tls-public.json)

기존 순정 CE 게스트가 읽은 부팅 시각은 1601년 1월 1일 UTC였다. 별도 게스트 시험에서 `SetSystemTime`을 호출해 정상 UTC를 읽어 오는 것을 확인했다. 표준 실행기의 시험 이미지는 시스템 관리자 시작 때 호스트의 현재 UTC를 읽어 CE 시계를 설정한다. 에뮬레이터 전원 재시작마다 UTC를 새로 읽고, 동적 값은 이미지와 저장 상태의 식별자에 기록하지 않는다. [기존 게스트 UTC](../build/gd13my-ce-tls-diagnostics/guest-clock-before.json) · [SetSystemTime 시험](../build/gd13my-ce-tls-diagnostics/guest-clock-set-probe.json) · [새 이미지 부팅](../build/gd13my-ce-tls-diagnostics/early-startup/guest-boot.json)

새 이미지의 재부팅에서 UTC 적용과 순정 시스템 관리자 시작을 함께 확인했다. 같은 빌드의 연결된 실폰 ARM USB 재시험은 버전 요청을 보내는 단계에서 시간 초과됐다. [재부팅 로그](../build/gd13my-ce-tls-diagnostics/early-startup/guest-reboot.json) · [실폰 USB 재시험](../build/gd13my-ce-tls-diagnostics/early-startup/phone-arm-usb.jsonl)

CE 드라이버는 BearSSL TLS 1.2를 사용한다. UART에서 게스트 UTC, 헤드유닛 인증서 유효기간과 RSA 키 일치 여부, 폰 인증서 체인·신원 검증 오류, 폰이 보낸 TLS 경고 및 USB 무응답을 구분한다. Google 문서에서 통신 오류 7은 보안 통신 수립 실패를 뜻하며, 오류 코드만으로 어느 단계에서 실패했는지는 확인할 수 없다. [ARM 정상·실패 시험](../build/gd13my-ce-tls-diagnostics/early-startup/arm-projection.log) · [Google Android Auto 오류 안내](https://support.google.com/androidauto/thread/2467794/faq-what-are-these-cryptic-error-messages-that-i%E2%80%99m-seeing-how-do-i-deal-with-them?hl=en)

`gd13my-aa-ce-video-short-read.img`는 USB 버전 교환과 TLS의 시간 한도를 유지하면서, 영상 채널을 협상하면 별도의 20초 영상 시험 시간을 시작한다. Android Auto 제어 및 영상의 USB 벌크 입력에는 단축 패킷을 허용한다. ARM 시험에서는 기존 8초 한도를 지난 뒤 첫 프레임을 표시했고, 포그라운드가 순정 화면으로 바뀔 때 프레임을 그리지 않고 상대에게 영상권 반환을 알렸다. 동일한 투사 창이 다시 포그라운드를 얻으면 새 TLS 연결 없이 다음 프레임을 표시했다. 영상 전용 세션은 폰의 오디오 포커스 요청을 거절하며 영상 연결은 계속한다. 순정 후방카메라 이벤트가 실제 투사 창을 제어하는 연동, 순정 Bluetooth 실측과 USB Attach 밖의 지속 세션은 남아 있다. 순정 `usbd.dll`은 분리 통지 전에 파이프를 닫으므로 지속 세션의 작업 스레드에는 이 종료 순서에 맞는 소유권이 필요하다. [ARM 영상·오디오 시험](../build/gd13my-ce-video-focus/arm-short-read.log) · [Microsoft USB 분리 통지](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms902162%28v%3Dmsdn.10%29)

별도의 전체 WinCE 게스트 시험은 시험용 전면 창과 가상 USB 상대를 사용했다. 최신 이미지의 USB 버전 응답과 TLS 첫 응답의 512, 512, 280바이트 수신을 확인했다. 그다음 단계에서 순정 MUSB 드라이버가 0바이트 DMA 수신을 기록했고, 다음 TLS USB 출력이 중단됐다. 단축 입력 허용을 추가한 뒤에도 전체 게스트의 상호 인증과 LCD 출력을 확인하지 못했다. [전체 게스트 전송 기록](../build/gd13my-ce-video-focus/guest-video-test-qa3.json) · [순정 MUSB UART 로그](../build/gd13my-ce-video-focus/guest-video-test-qa3.serial.log)

가상 폰 재현 시험은 `tools/run_gd13my_virtual_phone.ps1`로 실행한다. 에뮬레이터의 MUSB에 AOA 장치를 연결하고, 작업용 DiskA 사본에서 WinCE 창과 USB 드라이버를 실행한다. TLS 시험 인증서는 실행마다 새로 만들고 임시 사본과 함께 정리한다. 부팅에는 4.5MHz 가상 CPU 설정을 사용하고 USB 시작 때 게스트 시각을 이어 받은 채 64MHz로 전환한다. 시험은 USB 버전, TLS 상호 인증, 영상 서비스·프레임 응답과 LCD의 세 픽셀을 각각 기록한다. MUSB는 RX FIFO에 실제로 들어온 0바이트 패킷의 DMA를 메모리 접근 없이 완료한다. [시험 실행기](../tools/run_gd13my_virtual_phone.ps1) · [TI MUSB 컨트롤러 설명](https://www.ti.com/lit/ug/sprufw6b/sprufw6b.pdf)

가상 폰 시험에서 WinCE USB 드라이버가 Android Auto 1.7 버전 응답을 받아 TLS 1.2 상호 인증과 암호화된 서비스 탐색까지 완료했다. 시험 창이 순정 WinCE의 포그라운드 권한을 얻지 못해 드라이버가 영상 서비스를 제공하지 않았으며, LCD에 영상 프레임은 기록되지 않았다. [가상 폰 시험 결과](../build/gd13my-virtual-phone/foreground/virtual-phone.json) · [WinCE UART](../build/gd13my-virtual-phone/foreground/virtual-phone.serial.log)

`tools/run_gd13my_virtual_phone.ps1 -LcdBench`는 격리 이미지에서 시험용 LCD 사용권을 WinCE 수신기에 부여한다. 순정 CE 커널과 USB 호스트 드라이버를 부팅한 상태에서 가상 폰의 TLS 1.2, 영상 서비스 협상, 암호화된 H.264 전송, ARM 디코딩 및 GDI 그리기를 연결해 확인했다. 영상 응답 한 건과 LCD 800×480 평면의 세 지점에서 RGB `255,0,0`이 기록됐다. [LCD 검증 JSON](../build/gd13my-virtual-lcd/standalone/virtual-phone.json) · [WinCE 출력 로그](../build/gd13my-virtual-lcd/standalone/virtual-phone.serial.log)

`tools/run_gd13my_phase78.ps1 -OwnedWindowCandidate`는 순정 내비 메뉴가 터치를 받은 HWND를 새 실행기에 넘기는 시험 이미지다. 실행기는 인증용 CA가 있고 전달한 창이 여전히 전면에 있을 때만 그 창 소유의 Android Auto 대화상자를 연다. USB 대기는 작업 스레드에서 처리하며, 투사 창을 잃으면 영상 그리기를 중단한다. ARM 시험은 메뉴 터치가 HWND를 전달하고 포커스가 다른 창으로 바뀐 경우 대화상자를 열지 않는 것을 확인했다. [메뉴 ARM 시험](../build/gd13my-ce-owned-window/arm-menu-owner.json) · [소유권 ARM 시험](../build/gd13my-ce-owned-window/arm-owner.log)

Windows에서 실제 화면을 표시했던 실행은 Google DHU였으며, 성공 로그는 BoringSSL과 TLS 1.2 인증을 기록한다. 공개 DHU 문서의 지원 환경은 Windows, macOS, Linux다. WinCE로 넘길 수 있는 별도 인증 자료의 개인용 공개 발급 절차는 확인하지 못했다. 공개 제조사 연동 자료에서 Android Auto Projection 인증은 승인된 OEM과 시험기관을 대상으로 한다. [Windows 성공 로그](../research/evidence/phase2-dhu-display-20261120-230704.stderr.log) · [Google DHU 문서](https://developer.android.com/training/cars/testing/dhu) · [OEM 인증기관 안내](https://p3-group.com/Insights/google-expands-p3s-3pl-accreditation-to-embrace-next-gen-android-autoprojection-aap-technology-certification/)

케이블 재연결 후 실폰에서 Android Auto 1.7 응답을 받아 이전에 관측한 폰 인증서 체인 지문과 대조했다. 진단 도구로 임시 자체 서명 헤드유닛 인증서를 USB에 전송했지만 폰의 응답을 기다리다 시간이 초과됐다. 명시적인 인증 거부 응답은 관측되지 않았다. [재연결 시험](../build/gd13my-ce-peer-pin/phone-self-issued-cable.json)

`tools/build_ce_usb.py`의 `--bearssl-source`에는 공식 `bearssl-0.6.tar.gz`를 푼 경로를 지정한다. 사용한 다운로드의 SHA-256은 `6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14`이다. [빌드 결과 및 라이선스](../build/gd13my-ce-tls/ce)

Phase 7·8 시험판의 순정 CE 게스트에서 새 삼성 폰을 AOA 모드로 전환했고, 순정 Android Auto 설정 창에서 재시험해 실폰 1.7 버전 응답을 받았다. 화면에서 저장한 자동 연결 옵션은 콜드 부팅 뒤 복원됐다. 에뮬레이터의 Windows 수신기가 같은 USB 연결을 이어받아 TLS, H.264, 입력과 오디오를 처리하는 경로를 추가했다. 차량 본체의 CE 인증·영상 처리는 후속 포팅 단계다. [시험 기록과 사용 방법](PHASE7_8_RESULTS.md)

현재 `.061` 후보는 순정 내비 메뉴의 Android Auto 항목과 수동 동의 뒤 자동 연결 경로를 포함한다. 새 ARM 이미지의 정적 검증을 마쳤다. 기본 실행기는 Windows 수신기로 USB를 인계하지 않는다. 위 실폰 버전 응답과 아래 실행 추적은 이전 이미지의 기록이다. [현재 이미지와 범위](PHASE7_8_RESULTS.md)

### 순정 USB 호스트 연결

`내비설정 → 기타 → Android Auto` 실행 경로의 새 `i30aa.exe`는 확인을 받은 뒤 `i30usb.dll`을 35초간 CE USB 호스트에 시험 등록한다. 대상은 시험한 삼성 폰의 `04e8:6860` 모드와 AOA 데이터 PID `18d1:2d00/2d01`이다. 이번에 쓴 등록 키만 해제하며, 기존 등록 키와 충돌하면 설치를 중단한다. [USB ABI와 등록 근거](USB_ANALYSIS.md) · [APP 구성](FIRMWARE_PACKAGING.md)

재배치된 ARM DLL에 ROM 규약과 일치하는 USB API를 모의해 AOA 전환, 재열거 후 버전 협상, 저장장치 제외, 전송 시간초과, 파이프 열기 실패를 확인했다. 메뉴 실행 파일도 ARM으로 실행해 등록 중 오류와 기존 키 충돌 시 정상 롤백을 확인했다. [ARM 시험 로그](../build/gd13my-aa-lab/ce-usb-test-v3.json)

순정 WinCE 게스트에서는 진단용 `CreateProcessW`로 같은 실행 파일을 시작했다. 시험 확인 응답만 진단에서 입력했고, 실제 CE API가 등록 키 4개를 만들고 DLL 경로 3개를 쓴 뒤 35초 대기 종료 `0x102`를 반환했다. 키 4개 삭제도 모두 성공했다. [네이티브 ARM 호출 기록](../build/gd13my-boot/gd13my-window-20261122-033220-861723.usb-ce-native.log)

`--usb-port` 시험 포트는 OMAP MUSB의 호스트 역할, 연결 인터럽트 92, 제어 및 bulk 전송을 모델링한다. WinUSB로 바꾼 실폰 `04e8:6860`에서 순정 CE가 장치 디스크립터 18바이트, 구성 디스크립터 113바이트를 읽고 주소 `1`과 구성 `1`을 설정했다. CE의 USB 로더가 `i30usb.dll`을 읽고 실제 ARM `USBDeviceAttach` 함수를 호출했다. v5는 이 함수의 `OpenEventW(SYNCHRONIZE, ...)`가 실패해 AOA 요청 전에 돌아왔다. v6은 CE의 `CreateEventW`로 이미 생성된 이름 있는 이벤트를 연다. 차량에서는 별도 설치와 복구 검증이 필요하다. [실폰 열거 로그](../build/gd13my-boot/gd13my-window-20261122-141322-094832.usb-host.log) · [순정 USB 로더 로그](../build/gd13my-boot/gd13my-window-20261122-141322-094832.usb-loader.log) · [ARM 호출 추적](../build/gd13my-boot/gd13my-window-20261122-141322-094832.usb-attach-arm.log) · [v6 ARM 시험](../build/gd13my-aa-lab/ce-usb-test-v6.json)

v6의 ARM DLL을 실행한 순정 WinCE 게스트가 실폰에 AOA 요청 `51`, `52`, `53`을 보내 `AOA 2` 응답과 `18d1:2d00` 재열거를 확인했다. 재열거 직후 순정 USB 경로가 `EXT_USB_Off`와 `Vbus OFF`를 기록해 그 세션에서는 버전 교환까지 진행하지 못했다. [게스트 USB 로그](../build/gd13my-boot/gd13my-window-20261122-141322-094832.usb-host.log) · [순정 UART 로그](../build/gd13my-boot/gd13my-window-20261122-141322-094832.serial.log)

액세서리 모드인 실폰을 별도 콜드 부팅에서 연결했을 때 순정 호스트가 첫 AA 요청을 위해 DMA 주소 `0x81787000`, 길이 `10`, 제어 `0x61b`를 기록했다. 모델에 USB DMA mode 0의 단일 패킷 RAM 전송과 IRQ 93을 추가했다. [순정 DMA 요청 추적](../build/gd13my-aa-lab/v6-native-aoa-boot.transport.log) · [Mentor DMA 레지스터](https://github.com/torvalds/linux/blob/v6.12/drivers/usb/musb/musbhsdma.c)

같은 v6 ARM DLL의 별도 실행에서 실제 포트 `1-2`를 통해 요청 `00030006000100010006`에 대한 Android Auto **1.7** 응답 `000300080002000100070000`을 받았다. 동일한 실폰을 Google DHU에 연결해 TLS 1.2 인증서 검증 및 실제 800×480 화면을 확인했다. DHU는 이후 ping 시간초과를 기록했다. WinCE용 DLL은 버전 확인 뒤 USB 파이프를 닫으므로 WinCE 화면 투사에는 인증, 서비스 세션 및 영상 출력 경로가 필요하다. [실폰 버전 패킷](../build/gd13my-aa-lab/arm-v6-phone-version-packets.jsonl) · [DHU 실폰 화면](../build/gd13my-aa-lab/dhu-v6-phone.png)

~~~powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$usb = 'build/ce-aa-usb-v3'
$patch = 'build/gd13my-aa-lab/patched-nav'
& $py tools/build_ce_usb.py $usb --compiler $cc
& $py tools/emulate_ce_usb.py $usb
& $py tools/build_gd13my_app_archive.py $patch "$usb/i30aa.exe" build/gd13my-aa-lab/app-archive-usb-v3 --usb-client "$usb/i30usb.dll"
~~~

### 순정 HMI 메뉴 연결

`gd13my-aa-native-menu.img`를 콜드 부팅해 순정 내비 홈, `내비설정 → 기타` 및 새 `Android Auto` 항목을 확인했다. 부팅 시험에서 가상 MICOM 기동 이벤트를 한 번 보조했다. 실제 터치 `(723,181)`에서 수정한 순정 `GDdNavi.exe`가 `CreateProcessW`를 호출했고, `\DiskA\Application\NAVI\i30aa.exe`의 ARM 진입점과 실행 명령이 일치했다. [게스트 메뉴 캡처](../build/gd13my-aa-lab/gd13my-native-android-auto-menu.png) · [ARM 실행 추적](../build/gd13my-boot/gd13my-window-20261122-022543-030164.native-menu.log)

WinCE 기본 대화상자가 에뮬레이터 화면 오른쪽에서 잘려 두 대화상자를 진단 중 `SetWindowPos`로 화면 안에 옮겼다. 실제 `OK` 터치 후 CE에서 모의 Android Auto 1.7 진단이 통과했다. 순정 설정 메뉴와 실행 파일 연결은 이미지에 들어 있다. WinCE의 실폰 USB 전송·인증·투사와 물리 차량 설치·복구 검증은 남아 있다. [실제 게스트 결과](../build/gd13my-aa-lab/gd13my-native-android-auto-result.png) · [UART 진단 로그](../build/gd13my-boot/gd13my-window-20261122-022543-030164.serial.log) · [APP 구성](FIRMWARE_PACKAGING.md)

### 물리 USB에서 ARM 드라이버 시험

`tools/probe_gd13my_phone.py`는 선택한 PC USB 포트에서 펌웨어에 포함된 `i30usb.dll`의 ARM 코드를 실행한다. WinCE USB 함수표의 제어 및 bulk I/O를 Windows libusb에 연결한다. .061에서 지원하는 삼성 기본 모드와 AOA 데이터 모드만 선택하며, 같은 포트에서 재열거한 기기를 확인한다. 이 진단은 WinCE 부팅 에뮬레이터와 별도의 ARM 실행이다. 순정 게스트의 USB 호스트를 시험하려면 [에뮬레이터 v6 실행 절차](GD13MY_EMULATION.md#시작-설정이-포함된-v6-시험판)를 따른다.

~~~powershell
Set-Location 'F:\i30-gen2-android-auto'
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv\Scripts\python.exe'
& $py tools\probe_gd13my_phone.py --list
& $py tools\probe_gd13my_phone.py --device 1-2
~~~

현재 PC에서 포트 `1-2`의 삼성 폰 `04e8:6860`은 열거됐다. 기본 삼성 USB 드라이버 구성에서는 첫 USB 접근이 `Entity not found`로 끝나 실폰에 대해 ARM 드라이버의 AOA 협상은 시작되지 않았다. 모의 USB 전송에서는 같은 ARM 드라이버가 AOA 모드 전환, `0x82/0x02` bulk 버전 교환, 타임아웃 시 리소스 반환을 통과했다. 성공 결과는 Android Auto의 평문 버전 단계까지를 뜻한다. [실폰 로그](../build/gd13my-aa-lab/arm-live-phone-probe.jsonl) · [모의 USB 시험](../build/gd13my-aa-lab/arm-live-probe-fixture.log)

### 이전 독립 시험 앱

2026-11-22에 `gd13my-aa-settings.img`를 만들어 `i30-aa-settings.exe`를 추가했다. 새 이미지에서 순정 CE 로더가 `CreateProcessW` 성공을 반환했고, FAT32에서 추출한 실행 파일의 ARM 진입점 `0x111d8`과 실행 중 실제 명령을 대조했다. ARM 명령어 시험에서는 모의 `coredll`로 확인·취소·파일 오류를 각각 검증했다. [실행 추적](../build/gd13my-boot/gd13my-window-20261122-012905-074959.direct-launch.log) · [이미지 검증](../build/gd13my-aa-lab/settings-image-audit.json)

- 에뮬레이터의 `내비 메뉴 (F2)`가 가상 MICOM을 통해 `60 02 1E 01`을 보내도록 했다. 순정 `OnHardKey_NAVIMENU`가 실행됐고 실제 터치로 `내비설정 → 기타`에 진입했다. HMC/KOR의 정상 지역 값 `0x00`에서는 순정 `HandleHK_SetUp`이 `E0 02 35 01`을 전달하지 않는다. WinCE 버튼 생성은 성공했으나 순정 HMI 화면에 표시되지 않았다. `i30-aa-settings.exe`는 독립 시험 앱이며 순정 HMI 항목 등록과 터치 연결은 남아 있다. [순정 설정 PNG](../build/gd13my-aa-lab/gd13my-stock-settings-other.png) · [순정 UART 로그](../build/gd13my-boot/gd13my-window-20261122-011900-365940.serial.log) · [버튼 실험](../build/gd13my-boot/gd13my-window-20261122-011900-365940.setup-button.log)
- 연결된 삼성 폰에서 PC 수신기로 Android Open Accessory 2 연결, 액세서리 재열거, USB bulk 및 Android Auto 1.7 버전 응답을 확인했다. WinCE에서 실폰에 연결하는 USB 전송과 인증·화면 투사는 미검증이다. [실폰 시험](../build/gd13my-aa-lab/phone-20261122.jsonl)
- 새 이미지의 순정 파일 119개, MBR, 지도·설정 영역을 원본 가상 매체와 비교했다. `DiskA`에 독립 실행 파일 두 개를 추가했다. 이 검증은 에뮬레이터용 가상 매체에 적용되며 차량 업데이트 로더와 전원 손실 시 복구는 미검증이다. 회귀 테스트 65개가 통과했다. [이미지 비교](../build/gd13my-aa-lab/settings-image-audit.json) · [회귀 테스트](../build/gd13my-aa-lab/settings-regression.log)

순정 GD13MY 가상 매체를 복사한 뒤 `\DiskA\Application\AndroidAuto\i30-ce-probe.exe`에 ARM WinCE 6.0 진단 앱을 추가했다. 맵과 설정 파티션을 포함한 4,094,689,280바이트 시험 이미지를 생성하고, FAT32에서 실행 파일을 다시 읽어 SHA-256 `17fcc03b4b03b41aa2c1d3ce3f98bbb8f27d593caf1d3382057660a2f05f5b97`과 대조했다. [이미지 검증 기록](../build/gd13my-aa-lab/verified-image.json)

- 같은 ARM 실행 파일을 APP 전용 시험 이미지에서 순정 CE 로더로 실행했다. `CreateProcessW`가 1을 반환했고, 순정 UART에 `i30 CE bench probe passed`가 남았다. 실제 CE에서 파일 API, 힙, 스레드 API를 실행하고 모의 전송 계층으로 Android Auto 1.7 응답을 확인했다. [CE 실행 기록](../build/gd13my-boot/gd13my-window-20261121-214029-363694.serial.log) · [ARM 호출 추적](../build/gd13my-boot/gd13my-window-20261121-214029-363694.direct-launch.log)
- PC 수신기에서 모의 Android Auto 피어와 TLS, H.264 영상 5프레임, 터치, 오디오 믹싱, 마이크, 연결 해제 및 재접속을 확인했다. WinCE의 실폰 USB 전송과 TLS·영상 경로는 미구현이다. [영상 및 입력 시험](../build/gd13my-boot/aa-host-phase3.log) · [분리 및 재접속 시험](../build/gd13my-boot/aa-host-reconnect.log)

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$base = Join-Path $env:LOCALAPPDATA 'i30-gd13my/gd13my-media-v2.img'
$image = Join-Path $env:LOCALAPPDATA 'i30-gd13my/gd13my-aa-lab.img'
& $py tools/build_ce_minimal.py --compiler $cc
& tools/venv/gd13my-disk/Scripts/python.exe tools/build_gd13my_aa_lab.py $base build/ce-minimal/i30-ce-probe.exe $image
& $py tools/build_ce_minimal.py --compiler $cc --settings
$settingsImage = Join-Path $env:LOCALAPPDATA 'i30-gd13my/gd13my-aa-settings.img'
& tools/venv/gd13my-disk/Scripts/python.exe tools/build_gd13my_aa_lab.py $base build/ce-minimal/i30-ce-probe.exe $settingsImage --settings build/ce-aa-settings/i30-aa-settings.exe
```

기존 PC 수신기와 모의 폰은 Phase 5 검증에도 그대로 사용한다. CE 쪽에서는 사용 범위가 작은 전송 헤더와 버전 협상을 먼저 C로 포팅했다.

| 영역 | 산출물 및 검증 | 다음 의존성 |
|---|---|---|
| ARM 프레임과 버전 협상 | `aa_wire.c`를 `libi30_aa_wire.a`로 크로스 컴파일했다. 길이·플래그·확장 헤더를 판별하고, 크기가 제한된 읽기·쓰기 콜백에서 AA 1.6 요청과 1.x 응답을 처리한다. 진단 앱에서 응답을 1바이트 단위로 받아 1.7을 확인했다. | 물리 USB 수신기 및 일반 메시지 재조립과 연결해야 한다. 진단 앱 버전 응답은 한 프레임으로 제한한다. |
| CE 사용자 모드 | `ce_minimal_probe.c`로 파일·디버그 로그·메모리·스레드·대기를 검증하는 ARM32 PE를 만들었다. ARM 명령어 시험에 순정 export를 바탕으로 만든 모의 API를 사용했다. | 대상 CE 로더와 실제 `coredll` 호출 규약 확인이 필요하다. |
| 인증·서비스 탐색 | PC의 `ssl.MemoryBIO`, protobuf 디스크립터, TLS 신뢰·인증 설정은 유지된다. | 경량 ARM TLS 구현과 protobuf 파서 연결, 등록된 테스트 인증 자료, 정상 및 거부 경로 실폰 검증이 필요하다. |
| USB | `i30usb.dll`은 순정 CE USB 클라이언트 ABI로 삼성 폰의 AOA 전환과 bulk 버전 교환을 시도한다. 재배치된 ARM DLL을 모의 USB 전송으로 검증했다. | 실물 모드 전환, 콜백 호출, 지속 전송과 분리·재연결을 검증한다. |
| 영상·오디오·입력 | PC PyAV/WinMM/Tk와 기존 CE WaveDev·감독기 소스가 있다. 이전 어댑터는 Windows 데스크톱 네이티브 시험을 통과했다. | CE `VID1:`의 Android Auto 접근 단위 수락, DirectDraw 표면, OEM WaveDev·마이크 동시 사용, 카메라 선점과 물리 버튼 매핑이 남아 있다. |

`libi30_aa_wire.a`는 GNU ARM ELF 오브젝트를 담은 정적 아카이브다. `build_ce_minimal.py`에서 진단 PE에 링크하며, Microsoft 도구용 `.lib` 산출물과의 상호 사용은 확인되지 않았다. 기존 Phase 4 `ce_wave.c`와 `ce_supervisor.c`의 OEM SDK 빌드는 별도다. [Phase 3·4 현황](PHASE3_PHASE4_STATUS.md) · [순정 I/O 자료](VIDEO_AUDIO_ANALYSIS.md)
