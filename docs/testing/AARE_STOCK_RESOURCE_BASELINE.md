# 순정 지도 리소스 및 영상 출력 조사 — 2026-11-27

기준은 `726f6409`의 WinCE 게스트 코드와 기존 USB 복구 이미지 `build/p0-usb-repro/recovery-build/gd13my-aa-autostart-p0.img`다. 기존 AOA, AAP, TLS, 소프트웨어 디코더를 그대로 사용했다. 변경은 가상폰 시험기와 근거 문서에 들어갔다.

## 프로세스와 순정 자원

| 방식 | 판단 |
|---|---|
| A. 지도 위에 투사 창 배치 | 현재 방식이다. 자동 실행에서는 첫 정상 영상 전까지 지도가 보이고 USB 분리 후 투사 창이 숨겨진다. 투사 중에도 순정 지도 프로세스는 살아 있다. |
| B. 지도 연산·렌더링 일시 중단 | 순정의 협력적 중지/재개 진입점과 영향 범위를 확인하지 못했다. 지도 PE의 `PauseSetDest` xref `0x1124c0`는 경로 목적지 검사 로그다. 순정 `CMapFlyer::UpdateMapFlyer`의 `CheckMapDirState` 분기(`0x90bd0`)는 내부 플래그를 검사하고 호출 후 지운다. `OnTimer`의 `0x93588`은 주변 등록 지점 점프 타이머다. 두 곳 모두 외부에서 지도 렌더러 전체를 일시 중지하고 안전하게 재개할 계약을 제공한다는 근거가 없다. 이 증거로 렌더링 중단을 선택할 수 없다. |
| C. 정상 종료·재시작 | `GDdNavi.exe` 내부의 `i30nav.dll`이 투사 창을 소유하고 USB 대기 작업 스레드를 띄운다. 지도 프로세스 종료는 해당 창과 작업 스레드도 없앤다. 정상 종료·재실행 계약, 독립 복구 감독기와 안전 복귀를 확보할 때까지 이 방식을 시험하지 않는다. |

`gd13my_aa_menu.S`의 순정 메뉴 훅은 `i30nav.dll`을 로드하고 수동 및 자동 진입점을 호출한다. `ce_aa_native_display.cpp`의 `refresh()`는 지도 HWND의 존재와 상대 Z-order를 검증하며 카메라 표시권이 바뀌면 숨기고 터치를 취소한다. USB 트래픽은 `i30usb.dll!USBDeviceAttach`로 진입한다. `i30aa.exe`의 빌드 대상은 설정 UI다. 기존 감독기 코드는 P0 이미지에서 독립적인 지도 복구 수단으로 연결되어 있지 않다. [빌드 및 엔트리](../../tools/build_ce_usb.py) · [메뉴 훅](../../src/ce/gd13my_aa_menu.S) · [투사 창](../../src/ce/ce_aa_native_display.cpp)

후방 관련 순정 상태는 MICOM 경로의 `LibSystem.dll`과 `LibVideo.dll`이 게시한다. 투사 창과 USB 표시가 같은 허가 상태를 소비한다. 라디오, Bluetooth, GPS 수신·경로·타이머 스레드의 종료 의존성은 아직 확인하지 못했다. `[DrFish] navResetGpsHwClbk`가 투사 후에도 UART에 나타났다. 이 로그는 가상 RTC 읽기 실패에 이은 GPS 재설정 경로의 활동을 보여준다. 실제 GPS 위치 갱신 및 경로 계산은 별도 계측이 필요하다. [순정 표시 통합](../android-auto/CE_NATIVE_DISPLAY_INTEGRATION.md)

## A 기준 측정

가상폰 시험기는 순정 지도 준비, 첫 프레임, 전송 종료, USB 표시권 반환, 순정 메뉴 응답 시점에 누적 게스트 `eglSwapBuffers` 호출 수와 에뮬레이터 지도 플레인 복사 수를 기록한다. 게스트 타이머와 호스트 벽시계는 별도로 기록한다. 기존 프레임 ACK와 LCD 픽셀 검증은 그대로 사용한다. 이 지표로 프로세스 CPU 점유율, 게스트 힙·핸들 잔존량 또는 모든 프레임의 LCD 표시를 산출할 수 없다.

| 12프레임 가상폰 시험 구간 | 호스트 경과 | 게스트 지도 swap 증가 | 에뮬레이터 플레인 복사 증가 |
|---|---:|---:|---:|
| 지도 준비 → 투사 첫 프레임 | 13.60초 | 3회 (2 → 5) | 3회 |
| 투사 첫 프레임 → 전송 종료 | 30.15초 | 0회 (5 → 5) | 0회 |
| 전송 종료 → 순정 메뉴 응답 | 1.84초 | 0회 (5 → 5) | 0회 |

- 800×480 Baseline H.264, 가상폰 설정 30 FPS, 부팅 4.5 MHz/USB 12 MHz 조건에서 AAP 버전 협상과 상호 TLS를 통과했고 12개 중 12개를 ACK했다. 프레임 송신부터 ACK까지 호스트 중앙값은 2.42초였다. 전체 표시 FPS와 디코딩·색변환의 개별 소요 시간은 이 시험에서 측정하지 않았다. 동시에 실행한 대화형 뷰어의 영향이 섞인 호스트 시간이다.
- 투사 후 GPS 재설정 로그는 계속됐다. 위 12프레임 구간의 swap·복사 증가는 0회였고, 3회 반복 시험에서는 각 세션 첫 프레임부터 전송 종료까지 각각 1회·6회·4회씩 증가했다. 후진 신호는 첫 세션에서만 주입했다. 현재 방식에서도 지도 렌더링 작업이 일어날 수 있다. B/C에는 시험 가능한 안전 경로가 없어 성능 차이를 산출하지 않았다.
- 3회 반복 가상 USB 시험에서 첫 프레임, 총 ACK 38/38(30+4+4), 세 번의 표시권 반환, 가상 후진 선점 및 터치 억제와 재개를 관측했다. 세 번 분리한 뒤 이전 시험기는 자동 실행 이미지에서 수동 닫기 완료를 기다리다 종료했다. 별도 12프레임 시험에서 마지막 ACK 후 USB 분리를 시작하고 1.84초 뒤 순정 내비 메뉴 ACK를 받았다. 이 메뉴 확인은 데스크톱 벽시계 기준이며 이전 지도 경로의 복원이나 지도 프로세스 재시작을 시험한 결과가 아니다.
- 두 가상폰 시험에서 터치에 따른 영상 변화를 확인했다. 일부 롱프레스와 드래그가 복수 접촉으로 보고돼 엄격한 전체 제스처 검증은 두 시험에서 실패했다. 자동 시작 이미지에서는 USB가 빠지면 투사 창이 이미 숨겨지므로, 검증기가 수동 닫기 버튼 대신 순정 메뉴 이벤트로 응답을 확인하게 수정했다. 수동·자동 복귀 분기와 중복 종료 방지 동작은 별도의 상태 전이 시험을 통과했다.
- ARM/API fixture는 비정상 종료 5가지 지점의 정리, 재연결, 표시 복귀 및 순정 터치 11개 경로를 통과했다. fixture 할당 추적에서 세션 종료 뒤 잔존 할당은 0이었다. 게스트 프로세스 CPU·힙·핸들 수치와 장시간 누수는 미계측이다. 대화형 뷰어의 Windows 프로세스는 USB 대기 중 한 시점에 working set 483.5 MiB, private 488.8 MiB였으며 이 값에는 Unicorn과 호스트 렌더러가 포함된다.
- Python 전체 회귀는 98개 중 97개 통과, 네이티브 GPTimer DLL 환경 조건으로 1개 건너뜀이다. 새 폰은 AARE와 등록된 P12 설정이 필요해 이번 세션의 실폰 투사와 분리·재연결이 남아 있다. 기존 USB 복구 이미지는 순정 지도 및 물리 USB 대기 상태로 유지했다.

산출물은 `virtual/virtual-phone.json`, `virtual/virtual-phone.progress.jsonl`, `virtual-auto-restore/virtual-phone.json`, `arm.json`, `unittest-final.log`다. 12프레임 복귀 시험은 아래 명령에서 `--stream-frames 12 --fps 30 --restore-map --usb-clock-mhz 12 --seconds 450`을 사용했다.

## 순정 영상 출력

원본 .061 `003248a0_LibVideo.dll`에서 `lVideoShowOverlay`(`0x1011d0`)는 순정 비디오 상태 객체 `0x10b110`과 표시 인자를 내부 `0x103b48`로 전달한다. `0x1032f0`부터 오버레이 지원 조건을 검사한다. `0x103354–0x103390`에서 `0x10b0e4`의 32바이트 픽셀 포맷을 복사한다. 여기에는 flags `0x4`와 FourCC `UYVY`가 들어 있다. 이 순정 호출은 기본 폭 720, 높이 576 및 backbuffer 요청값 2를 채운 뒤 `0x1033b0`에서 오버레이를 생성한다. `LibMMCodec.dll`의 `0x17e390`에도 같은 포맷 구조가 있다. 순정 쇼/숨김 분기(`0x10352c`, `0x1035bc`), Lock 실패(`0x103ce4`), 크기 변경(`0x103898`, `0x1038c4`), 해제 시 숨김(`0x102b34`)을 가리키는 로그 참조가 있다.

이 근거에서 검토할 첫 포맷은 **UYVY 4:2:2**다. h264bsd의 planar YUV420을 사용하려면 최소한 UYVY 패킹과 chroma 행 확장이 필요하다. YUV420 직접 제출, YUY2, 오버레이 RGB565, 800×480의 실제 surface capability는 미확인이다. 출력 후보를 연결하려면 Lock 시 반환 pitch, 크롭과 스케일링, Flip과 Unlock의 완료·버퍼 수명, 카메라와 표면 점유 전환을 먼저 확인해야 한다. 테스트 환경에 물리 오버레이 동작을 검증할 모델이 없어 백엔드를 추가하지 않았다. 후속 정적 확인은 `LibVideo`의 `0x102e44` Lock 래퍼와 `0x1033d4` 이후의 backbuffer 및 `0x102b00` 해제 경로에서 시작한다.

### 후속 UYVY 스테이징 시험

순정 `LibVideo`의 Lock(`0x102e44`)은 108바이트 surface descriptor와 vtable `+0x4c`를, Unlock(`0x102e9c`)은 `+0x68`을 사용한다. 생성 이후 `0x1033d4–0x103424`에서 연결된 표면을 열거하고, `0x102ddc`와 `0x10352c` 근처에서 오버레이 갱신을 호출한다. `0x102b54–0x102bf8`의 해제 경로는 오버레이를 숨기고 overlay, primary 및 DirectDraw 참조를 차례로 반환한다. `lVideoShowOverlay` 내부는 순정 객체 상태를 기록하고 자체 창에 메시지 `0xb002`를 전달한다(`0x103b54–0x103b74`). 별도 프로세스가 이 호출을 사용해 순정 오버레이를 소유할 수 있는지와 후방카메라와의 표면 인계는 미확인이다.

`--uyvy-staging`으로 별도 CE 시험 실행 파일을 빌드한다. 실제 h264bsd I420 출력에서 crop과 destination pitch를 반영해 UYVY를 메모리에 한 번에 기록한다. 픽셀 형식은 `U Y0 V Y1`이며, 4:2:0의 Cb/Cr 행은 대응하는 두 Y 행에 사용한다. 동기 콜백이 출력에 실패하면 같은 디코딩 결과를 BGRA DIB로 전달한다. CE USB 수신기의 기본 빌드는 이 시험 경로를 포함하지 않는다. 패딩을 제외한 800×480의 UYVY 프레임은 768,000바이트이고 BGRA는 1,536,000바이트다. 이는 형식별 데이터 크기이며, 실제 표면 복사량과 성능은 측정 전이다.

ARM fixture에서 800×480, crop된 798×478, 행 및 끝 패딩 보존, 출력 버퍼 할당 실패 후 같은 프레임의 32bpp GDI 폴백과 할당 해제를 검증했다. 화면 출력을 공유하는 하드웨어 백엔드는 표면 크기·pitch·동기화 및 카메라 권한 인계를 확인한 뒤 연결한다. 기본 CE PE 세 개를 다시 빌드해 기존 P0 실행 이미지에 사용한 산출물과 SHA-256이 모두 일치함을 확인했다. 새 기본 빌드에서 ARM USB/TLS/투사·카메라 선점·재연결 fixture와 순정 터치 11개 경로, Python 테스트 97개(환경 조건으로 1개 건너뜀)를 통과했다. [변환 코드](../../src/ce/ce_aa_uyvy.h) · [ARM 검증](../../tools/verify_ce_uyvy_staging.py)

```powershell
& $py tools/build_ce_minimal.py --compiler $cc --h264-source build/ce-video-dependency/h264bsd --uyvy-staging
& $py tools/verify_ce_uyvy_staging.py build/gd13my-ce-uyvy-staging/i30video.exe
```

### HAL과 ARM 성능 대조

- .061 ROM의 `DDRAW.dll`는 `DirectDrawCreate` ordinal 1을 제공한다. `ddi.dll!HALInit` RVA `0x1116c`의 콜백 초기화는 VA `0xc090f338`을 호출하고, `0xc090f410`에서 HAL 정보에 RVA `0x3e91c` 주소를 채운다. 이 목록의 세 항목은 순서대로 YUY2, YUYV, UYVY다. 별도 내부 표의 I420/YV12는 이 HAL 목록에 들어 있지 않다. 이 목록과 순정 720×576 생성 경로로부터 800×480의 표면 수용을 확정할 수 없다. [DirectDraw HAL 정보](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms897605%28v%3Dmsdn.10%29)
- `LibVideo!0x102d40`의 다음 화면 처리 함수는 `0x102d60`에서 표면 콜백을 실행하고, 실패 분기에서 primary와 overlay를 복원한 뒤 `UpdateOverlay`를 다시 시도한다. `0x102e44`의 Lock 및 `0x102e9c`의 Unlock, 순정 후방카메라 표시 이벤트와의 독립적인 오버레이 반환 순서까지 함께 검증해야 한다. 기존 RGB565 DISPC 캡처는 UYVY 표면의 실제 색 변환과 Flip 완료를 재현할 수 없다. 수신기에서 해당 하드웨어 경로를 활성화하지 않았다. [Windows CE 표면 상태와 Flip](https://learn.microsoft.com/hr-hr/previous-versions/windows/embedded/ms936859%28v%3Dmsdn.10%29)

동일한 800×480 Baseline H.264 프레임을 같은 ARM Unicorn 조건에서 세 가지 모드로 교차 실행했다. 각 모드 5회 중앙값이며 호스트 벽시계다. `StretchDIBits`는 인자·픽셀이 확인되는 시험 대역으로 실제 LCD 화면 전송 비용은 포함하지 않는다.

| ARM fixture | 변환/패킹 | 전체 video push | 할당 횟수 / 피크 요청 바이트 |
|---|---:|---:|---:|
| 기본 BGRA | 263.62 ms | 504.58 ms | 14 / 5,122,662 |
| UYVY 메모리 | 55.19 ms | 292.90 ms | 14 / 4,370,022 |
| UYVY 버퍼 거부 → BGRA | 거부 0.03 ms, BGRA 287.95 ms | 543.69 ms | 14 / 5,122,662 |

14회는 입력·디코더·출력 초기화와 1프레임을 합친 할당이다. 모든 반복에서 종료 시 잔존 할당은 0이다. UYVY의 쓰기량은 프레임당 768,000바이트, BGRA의 쓰기량은 1,536,000바이트다. 스테이징의 피치 패딩 15,360바이트는 쓰지 않았다. 실제 오버레이 전송·복사량, 표시 FPS, 누락률 및 ACK 간격의 개선은 미검증이다. 이 벤치는 USB ACK를 발생시키지 않는다. UYVY 버퍼 거부의 직접 측정 비용과 실행 간 전체 시간 편차는 따로 표기했다. 기존 수신기의 USB/TLS·재연결·카메라 선점·순정 터치 ARM fixture도 통과했다. 전체 Python 회귀는 97개 통과, GPTimer 환경 조건 1개 건너뜀이다.

```powershell
& $py tools/build_ce_minimal.py --compiler $cc --h264-source build/ce-video-dependency/h264bsd
& $py tools/build_ce_minimal.py --compiler $cc --h264-source build/ce-video-dependency/h264bsd --uyvy-staging
& $py tools/verify_ce_uyvy_staging.py build/gd13my-ce-uyvy-staging/i30video.exe `
    --compare-bgra build/gd13my-ce-video/i30video.exe
```

## DSP 디코딩

실제 내장 이미지와 지원 판정은 [DSP 펌웨어 판별](../hardware/hardware-acceleration/GD13MY_DSP_PAYLOAD.md)에 있다.

상위 순정 재생은 내부 스트림 값 9, 6, 17에서 H.264/H.263 미지원 분기로 간다. 하위 `videodev.dll`에는 타입 6에 대응하는 별도 H.264 디코더 메모리 query/init 분기가 존재한다. DECINIT/DECODE 호출 크기와 출력 상태는 정적으로 대조했다. 펌웨어에서의 실제 디코딩 성공, 데이터·DMA 계약, SPS/PPS/IDR 재동기화와 폴백을 검증해야 하므로 기존 h264bsd/BGRA/GDI가 계속 사용된다. [DSP 호출과 분기](../hardware/hardware-acceleration/DSP_IOCTL_ABI.md)

## 재현

```powershell
$py = "$env:LOCALAPPDATA/i30-phase2-venv/Scripts/python.exe"
$cc = "$env:LOCALAPPDATA/i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe"
$ssl = "$env:ProgramFiles/Git/usr/bin/openssl.exe"
$disk = "$env:LOCALAPPDATA/i30-gd13my/codex-auth-map-cache/gd13my-media-v2.img"
$env:PYTHONPATH = Join-Path (Get-Location) 'tools/venv/gd13my-disk/Lib/site-packages'
$b = 'build/p0-usb-repro/recovery-build'
$nav = 'firmware/extracted/GD13MY/APP/00d12869_GDdNavi.exe'
& $py tools/verify_gd13my_virtual_phone.py --image "$b/gd13my-aa-autostart-p0.img" `
    --manifest "$b/image.json" --disk $disk --compiler $cc --openssl $ssl `
    --output build/stock-resource-baseline/virtual-repro --native-menu $nav `
    --stream-frames 30 --fps 30 --cycles 3 --camera --restore-map --usb-clock-mhz 12 --seconds 950
```

가상폰 인증 자료는 시험용 이미지 사본에만 들어간다. 물리 USB용 뷰어는 같은 P0 이미지, 별도 DiskA 상태 파일, USB auto, 게스트 4.5 MHz/USB 12 MHz 설정으로 실행한다. 원본 로그 및 디스어셈블리는 로컬 `build/stock-resource-baseline`에 있다.
