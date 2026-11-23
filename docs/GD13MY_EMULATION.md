# GD13MY 순정 커널 메모리 맵과 부팅 실험

Phase 7·8 시험판과 현재 실행 스크립트는 [검증 결과 및 실행 방법](PHASE7_8_RESULTS.md)에 있다. 아래 명령은 당시의 시험 이미지를 재현하는 경로다.

## 내비 홈과 Android Auto USB 시험 창 열기

Windows PowerShell에서 실행한다.

~~~powershell
Set-Location 'F:\i30-gen2-android-auto'
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv\Scripts\python.exe'
$disk = 'build\gd13my-aa-lab\gd13my-aa-usb-full-v3.img'
$navi = 'firmware\extracted\GD13MY\APP\00d12869_GDdNavi.exe'
& $py tools\view_gd13my.py --disk $disk --micom-display navi --assist-navi-start --software-gl-app $navi --guest-clock-mhz 8 --seconds 7200
~~~

1. 아래 상태 줄에 표시되는 게스트 시간과 터치 수신 횟수로 진행 상태를 확인한다. 첫 화면이 나오기 전에는 검은 화면이 표시된다.
2. 흰색 터치 보정 화면에서는 십자가 한가운데를 잠깐 누른 뒤 뗀다. 십자가가 옮겨 가면 반복하고, 다섯 번째 터치 뒤의 확인 화면도 한 번 누른다.
3. `동의함`이 회색이면 로딩을 기다린다. 버튼이 파란색으로 활성화되면 누른다. 화면 전환과 지도 로딩에는 PC 성능에 따라 수 분이 걸릴 수 있다. `--assist-navi-start`는 가상 MICOM의 기동 이벤트를 한 번 보조한다. [내비 시작 로그](../build/gd13my-boot/gd13my-window-20261122-114202-827299.mode.log) · [로딩 중 화면](../build/gd13my-aa-lab/gd13my-usb-v3-consent-loading.png)
4. 지도 홈에서 메인 에뮬레이터 창 아래의 `내비 메뉴 (F2)`를 누른다. `내비설정 → 기타 → Android Auto`에서 USB 연결을 시험할 수 있다. PC에 연결한 폰을 시험하려면 아래 실행 예제에서 `--usb-port`를 지정한다.

F2 상태 줄에 요청 접수, 가상 MICOM 전송, 순정 내비 처리 여부가 표시된다. 내비가 로딩 중이면 요청을 보관했다가 로딩 뒤 전송한다. LCD 화면 하나를 기본으로 표시한다. 지도만 따로 보고 싶을 때 `--show-map-preview`를 추가한다. `--guest-clock-mhz 8`은 게스트 타이머의 진행 비율이며, 프레임 캡처의 변경 감지와 적응형 주기도 계속 적용된다.

최신 게스트 화면 PNG와 UART 로그는 `build/gd13my-boot/gd13my-window-*`에 저장된다. 창을 닫으면 실행이 종료된다. 게스트의 쓰기는 세션 메모리 오버레이에 기록되므로 재실행하면 터치 보정 등이 다시 필요할 수 있다. [이전 순정 홈 캡처](../build/gd13my-boot/gd13my-stock-navigation-home.png) · [Android Auto 메뉴 캡처](../build/gd13my-aa-lab/gd13my-native-android-auto-menu.png)

최신 USB 이미지 콜드 부팅에서는 순정 지도가 별도 창에 렌더링되고 F2가 순정 내비 메뉴에 전달됐다. 이 실행의 메인 LCD 창에는 동의 화면이 남았다. [지도 캡처](../build/gd13my-aa-lab/gd13my-usb-v3-stock-map.png) · [게스트 UART 로그](../build/gd13my-boot/gd13my-window-20261122-114202-827299.serial.log)

### 시작 설정이 포함된 v6 시험판

순정 지도 이미지와 새 APP 전용 이미지를 함께 열 수 있다. 지도와 순정 이미지 파일은 읽기 전용으로 열린다.

~~~powershell
Set-Location 'F:\i30-gen2-android-auto'
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv\Scripts\python.exe'
$disk = Join-Path $env:LOCALAPPDATA 'i30-gd13my\gd13my-media-v2.img'
$app = Join-Path $env:LOCALAPPDATA 'i30-gd13my\gd13my-aa-startup-v6.img'
$navi = 'firmware\extracted\GD13MY\APP\00d12869_GDdNavi.exe'
& $py tools\probe_gd13my_phone.py --list
& $py tools\view_gd13my.py --disk $disk --app-volume $app --micom-display navi --assist-navi-start --assist-touch-calibration --software-gl-app $navi --guest-clock-mhz 8 --usb-port 1-2 --seconds 7200
~~~

`내비설정 → 기타 → Android Auto`를 열면 `시작 안내 다음부터 보지 않기`와 `부팅 시 Android Auto 연결 시도` 체크박스가 나온다. `저장`은 두 설정을 기록한다. `USB 연결 시험`은 결과를 같은 창에 표시한다. 현재 에뮬레이터의 쓰기는 세션 메모리에 남는다.

`--usb-port`에는 목록에 나온 폰의 물리 포트를 넣는다. 위 예제의 `1-2`에는 삼성 폰이 연결돼 있으며 Windows의 `04e8:6860` 드라이버는 WinUSB다. WinCE 호스트가 시험용 드라이버를 등록하면 에뮬레이터가 가상 케이블을 다시 연결한다. 창의 `USB 다시 연결` 버튼으로도 재연결할 수 있다. `.usb-host.log`에 장치 열거와 USB 시험 결과가 남는다. 현재 펌웨어의 USB 시험은 Android Auto 버전 응답까지 검사한다. 인증과 영상 투사는 아직 구현되지 않았다.

메인 창에서 `F3`은 현위치, `F4`는 목적지를 보낸다. `F7`·`F8` 또는 버튼 줄의 마우스 휠은 순정 내비에 마이컴 볼륨 값을 전달한다. 순정 차량 오디오 출력과 라디오 튜너는 별도 검증이 필요하다.

## 현재 진행 상황 요약

**2026-11-22 KST · 순정 내비 홈과 설정 화면을 실제 게스트에서 확인했다.** 홈까지 진입하는 검증에서는 가상 MICOM의 기동 이벤트를 진단용으로 한 번 전달했다. 화면 캡처는 RGB565 평면의 바이트가 그대로일 때 PNG를 재사용하고, 바뀌었을 때는 색 변환표를 사용한다. 발행 주기는 캡처 비용에 따라 조정된다. 800×480 GFX·VID1 합성 벤치에서 바뀐 프레임이 186ms에서 96ms로, 같은 프레임이 170ms에서 0.4ms로 줄었다. 두 구현의 PNG는 바이트 단위로 일치했다. [캡처 벤치](../build/gd13my-aa-lab/display-performance.json) · [순정 내비 홈](../build/gd13my-boot/gd13my-stock-navigation-home.png)

| 항목 | 현재 상태 |
|---|---|
| 커널 부팅 | 순정 ROM의 OEM 테이블을 읽어 256 MiB RAM 배치를 재현했다. 이전 평가보드의 RAM 초기화 오류를 넘겼고, Windows CE 자체 페이지 처리와 시스템 모듈 실행을 확인했다. |
| 가상 저장장치 | 순정 APP 파일 119개를 읽기 전용 eMMC 이미지에 배치했다. 게스트에서 MBR, FAT32 부트 섹터, FAT와 루트 디렉터리 읽기까지 확인했다. [부팅 로그](../build/gd13my-boot/ui-disk-irq.json) |
| 주변장치 | 가상 타이머와 I2C 인터럽트가 게스트에 전달됐다. MICOM 송수신 스레드 시작과 GPS·RTC 초기화 메시지를 확인했다. 외부 I2C 장치 응답은 아직 구현되지 않았다. |
| 순정 시작 | Device Manager와 `AVNSysInit.exe`가 각각 `SignalStarted(20)` 및 `SignalStarted(25)`를 호출했다. 이어 순정 `GwesMain`, `DisplayInit`, `DrvEnableDriver`를 확인했다. [콜드 부팅 추적](../build/gd13my-boot/phase6-enum-1.json) |
| 순정 UI | 순정 `Touch_Calib.exe`가 그린 터치 보정 화면을 게스트 DISPC의 800×480 RGB565 프레임버퍼에서 추출했다. [순정 PNG](../build/gd13my-boot/gd13my-stock.png) · [콜드 부팅 로그](../build/gd13my-boot/gd13my-stock.json) |
| 검증 | 기존 46개를 포함한 57개 시험이 통과했다. 추출 BIN, 배포 BSP·APP, 가상 디스크 SHA-256은 작업 전후 일치했다. [시험 로그](../build/gd13my-boot/phase6-tests.log) · [무결성 확인](../build/gd13my-boot/phase6-integrity.json) |

2026-11-21 KST. `BSP.spd.000`에서 이전 단계에 추출한 GD13MY CE BIN을 Unicorn 2.1.4의 Cortex-A8에서 실행했다. BIN 레코드의 체크섬과 적재 주소를 검증하고 물리 진입점 `0x8000aadc`부터 실행했다. 원본 SHA-256은 `272b17f49f8c3dd9854755b25a7e6f0173bffb9b53798126c1ecb3f025f7c91e`다.

## 순정 커널의 주소 변환

가상 `0x8400ab70`의 두 ARM 명령어가 페이지 테이블 초기화 함수에 OEM 주소 테이블 포인터를 넘긴다. 테이블은 가상 `0x8400ab7c`, BIN 오프셋 `0x8bcb`에서 시작한다. 크기 단위는 MiB다. 아래 범위는 펌웨어가 선언하는 매핑이며, 실물 RAM 칩 용량이나 MMIO 구간 전체의 실장 여부는 측정 대상에 포함되지 않았다.

| 가상 시작 | 물리 시작 | 크기 (MiB) |
|---|---|---:|
| `0x84000000` | `0x80000000` | 256 |
| `0x94000000` | `0x20000000` | 16 |
| `0x95000000` | `0x18000000` | 16 |
| `0x96000000` | `0x28000000` | 16 |
| `0x97000000` | `0x15000000` | 16 |
| `0x98000000` | `0x48000000` | 16 |
| `0x99000000` | `0x49000000` | 1 |
| `0x9a000000` | `0x68000000` | 16 |
| `0x9b000000` | `0x6c000000` | 16 |
| `0x9c000000` | `0x6d000000` | 16 |
| `0x9d000000` | `0x6e000000` | 16 |
| `0x9e000000` | `0x40200000` | 1 |
| `0x9f000000` | `0x5c000000` | 16 |

순정 커널은 물리 `0x81500000`에 ARM 페이지 테이블을 만들고 가상 `0x8400ae60`으로 진입했다. 가상 `0x93f00000`과 캐시를 사용하지 않는 별칭 `0xb3f00000`은 모두 물리 `0x8ff00000`에 대응했다. ROMHDR이 명시하는 초기 RAM은 가상 `0x85500000`부터 `0x86800000` 직전까지다. 이후 CE는 가상 `0x88800000`부터 `0x0b400000`바이트(180 MiB)를 확장 RAM으로 보고했다.

## 대조 실행과 부팅 진행

| 설정 | 관찰 |
|---|---|
| EVM RAM 배치 | `0x80000000`과 `0xa0000000`에 128 MiB씩 배치하면 기존 CERF와 같은 PC `0x8400b0b0`에서 물리 `0x8ff00000` 쓰기가 실패한다. [실행 로그](../build/gd13my-boot/evm.json) |
| GD13MY RAM과 UART | 미리 `0xa5`로 채운 `0x8ff00000`의 1 MiB 전체가 순정 초기화 함수 반환 시점 `0x84017ef0`에 0이었다. 순정 CE가 UART로 커널 빌드 메시지를 출력했다. [실행 로그](../build/gd13my-boot/uart-only.json) |
| 부팅 MMIO와 CE 예외 | ARM 벡터를 거쳐 순정 CE 예외 처리기가 VA `0xc0042000`의 L2 항목을 `0x00000010`에서 `0x8fbe101e`로 바꿨다. `filesys.dll`의 쓰기 접근에서는 같은 물리 페이지의 권한이 갱신됐다. `0xf100add0`에서 발생한 프리페치 중단도 순정 벡터 `0xffff000c`로 전달했다. [실행 로그](../build/gd13my-boot/empty-mmc.json) |
| 가상 타이머와 빈 MMC | `k.ceddk.dll`의 지연 보정 루프를 통과했다. `pm.dll`과 후속 `filesys.dll` 코드의 실행을 CE ROM의 원본 코드 섹션과 대조했다. 2,000만 명령 한도에서 `filesys.dll`의 PC `0xc01158e8`, 3,000만 명령 한도에서 `kernel.dll`의 PC `0x8405346c`를 기록했다. [2,000만 명령 로그](../build/gd13my-boot/virtual-timer.json) · [3,000만 명령 로그](../build/gd13my-boot/virtual-timer-30m.json) |

## 재현

프로젝트 루트에서 기존 Phase 2 Python 환경과 추출된 GD13MY BIN을 사용한다. 한 실행의 호스트 시간은 6초로 제한한다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py tools/emulate_gd13my.py --layout evm --periphery uart
& $py tools/emulate_gd13my.py --periphery uart
& $py tools/emulate_gd13my.py --guest-exceptions --empty-mmc --instructions 20000000
& $py tools/emulate_gd13my.py --guest-exceptions --empty-mmc --virtual-timer --instructions 30000000
& $py -m unittest discover -s tests -p test_gd13my_boot.py -v
```

UART, INTC·I2C 리셋, GPIO, 클록·전원 레지스터, GPTIMER1, 32 kHz 동기 카운터, 미디어 없는 HSMMC 초기화에 필요한 동작을 모델링했다. SRAM은 `0x40208000–0x4020ffff`의 32 KiB를 제공한다. 가상 타이머는 번역 블록의 4바이트 단위 6,400만 개를 가상 1초로 환산해 32,768 Hz GPTIMER1 카운터를 진행하는 실험값이다. 실물 CPU 주파수, 실제 경과 시간 및 스케줄러 틱과의 일치는 확인하지 않았다. [TI OMAP35x TRM](https://www.ti.com/lit/ug/spruf98y/spruf98y.pdf) · [ARMv7 아키텍처 매뉴얼](https://documentation-service.arm.com/static/5f8daeb7f86e16515cdb8c4e)

이 절의 초기 부팅 시험은 커널 초기화, CE 자체 페이지 처리, 저장장치 컨트롤러 접근, ROM 내 시스템 모듈의 초기 코드 실행을 다룬다. 가상 eMMC와 타이머·I2C IRQ를 추가한 이후의 결과는 아래 순정 UI 도달 시험에 기록했다.

## 순정 UI 도달 시험

실행 한도를 늘리자 순정 MICOM 관리자가 OMAP UART1 `0x4806a000`에 접근했다. 수신 장치가 연결되지 않은 UART1을 모델링한 뒤 순정 `MIM_RcvThread`와 `MIM_TransThread` 시작 메시지를 받았다. 9,000만 명령 한도에서는 ROM의 `gwes.dll`, `ddi.dll`, `AutoStartUp.exe` 진입점 실행이 관측되지 않았다. 보고서의 `ui_entries`는 ROM 목차의 진입 주소와 현재 MMU가 가리키는 원본 코드의 물리 주소가 모두 일치할 때만 기록한다. [부팅 추적](../build/gd13my-boot/ui-uart1.json) · [TI OMAP3 장치 주소](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/blame/arch/arm/boot/dts/omap3.dtsi?h=ti-linux-4.14.y-next&id=b915c81ff372341b8d67593f00d64c98bdc6b32d)

```powershell
& $py tools/emulate_gd13my.py --guest-exceptions --empty-mmc --virtual-timer --instructions 90000000 --seconds 15
```

### 가상 eMMC와 화면 캡처

APP 헤더의 디렉터리와 파일 수를 검증하고 `uComH_New.exe`를 포함한 119개 파일을 원래 경로에 배치했다. 생성된 이미지는 하나의 FAT32 파티션을 가진 실험용 디스크다. 7-Zip으로 파티션과 파일을 검사했다. 순정 `moviDisk.dll`이 논리 섹터 0을 요청받아 실제 HSMMC1의 물리 LBA `131070`에 CMD17을 발행했다. `--disk-start-lba 131070`으로 그 위치에 이미지의 MBR을 배치한 후, 게스트가 MBR, FAT32 부트 섹터 `133118`, FAT `133150`과 루트 디렉터리 `141280`을 읽는 것을 확인했다. 이미지는 읽기 전용이다. 실물 매체의 나머지 영역과 `DiskA2`·`DiskA3`는 복원 범위에 포함되지 않았다. [게스트 실행 로그](../build/gd13my-boot/ui-disk-offset.json) · [순정 앱 시작 경로](DEEP_REVERSE_ENGINEERING.md) · [TI HSMMC 레지스터](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/tree/drivers/mmc/host/omap_hsmmc.c?h=ti-linux-4.4.y-next&id=af93382dbdbf247a72358b0e98c17a59aa9c28d1)

`--timer-irq`는 GPTIMER1 비교 이벤트와 I2C 완료 신호를 INTC로 전달한다. 타이머 IRQ를 추가하자 CE가 저장장치 드라이버를 시작했다. 현재 I2C 요청은 주변기기가 없어 NACK으로 끝난다. 순정 CE의 기본 레지스트리에서 `Depend25=20`, `Depend30=25`, `Depend100=30`을 확인했다. 앞선 실행은 GPS와 RTC의 초기화 메시지까지 관측했고, `AVNSysInit.exe`와 `gwes.dll` 진입 및 DSS 접근은 기록되지 않았다. `--frame`은 게스트가 LCD와 선형 RGB565 그래픽 평면을 활성화하면 게스트 RAM에서 PNG를 저장한다. 색과 행 패딩은 테스트 패턴으로 검증했으며 게스트 화면 PNG는 생성되지 않았다. SDMA는 레지스터 접근만, HSMMC는 PIO만 지원한다. [최신 부팅 로그](../build/gd13my-boot/ui-disk-irq.json) · [TI 타이머 레지스터](https://git.ti.com/cgit/sitara-epos/sitara-epos-kernel/tree/arch/arm/plat-omap/dmtimer.c?h=int_epos_linux_02.02.x&id=ce2df9ca41997f38cdfb9bee0db08763487222ae) · [TI DISPC 레지스터](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/tree/drivers/gpu/drm/omapdrm/dss/dispc.h?h=ti-linux-5.10.y-next-20220818&id=41ab5a111c97546157e942980b45998b535389e1)

```powershell
& $py -m venv tools/venv/gd13my-disk
$diskPy = 'tools/venv/gd13my-disk/Scripts/python.exe'
& $diskPy -m pip install pyfatfs==1.1.0 'setuptools<82'
& $diskPy tools/build_gd13my_diska.py build/gd13my-boot/diska.img
& $py tools/emulate_gd13my.py --guest-exceptions --disk build/gd13my-boot/diska.img --disk-start-lba 131070 --virtual-timer --timer-irq --instructions 240000000 --seconds 55 --frame build/gd13my-boot/oem-screen.png
```

### 순정 시작 순서 확인

복원한 순정 하이브의 연결된 키·값 레코드에서 다음 시작 순서를 확인했다. Depend 값은 little-endian 16비트 Launch 번호다. [하이브 레코드](../build/gd13my-boot/phase6-hive-evidence.json) · [Microsoft CE 6.0 시작/의존성 설명](https://download.microsoft.com/download/8/a/6/8a66a2e1-f2e1-4113-8877-514d6f668fe3/Chapter%203%20-%20Performing%20System%20Programming.pdf)

| Launch | 순정 모듈 | Depend |
|---|---|---|
| 20 | `device.dll` | 값 없음 |
| 25 | `AVNSysInit.exe` | 20 |
| 30 | `gwes.dll` | 25 |
| 60 | `servicesStart.exe` | 20 |
| 100 | `AutoStartUp.exe` | 30 |

`device.dll`의 `DevMainEntry`가 VA `0xc0251060`, ROM PA `0x80286060`에서 실제 실행됐다. Ghidra와 ROM import를 대조해 `0xc025201c`의 IAT가 `devmgr.dll!StartDeviceManager`(`0xc0262334`)를 가리키는 것을 확인했다. `devmgr.dll`의 `0xc0262570`은 `r0`에 20을 넣고 `0xc0262574`에서 `SignalStarted` import thunk를 호출한다. 초기 실행에서는 `RTC_Init`, `GPS_Init`, `DBG_Init`에 진입했으며, 커널의 `SignalStarted(0)` 호출 주소는 `0x8403f148`이었다. [Device Manager 디컴파일](../build/gd13my-boot/phase6-ghidra-device.log) · [실행 추적](../build/gd13my-boot/phase6-pll.json)

`AVNSysInit.exe`는 ROM에 있으며 엔트리 VA는 `0x11c74`다. 정적 분석에서 `\DISKA3\System\calib.bak`과 `calib.cgf`의 보정 파일을 확인했다. 경로가 없으면 50ms 간격으로 최대 20회 재시도한다. `0x1157c`에서 `HKLM\Init`의 자신의 Launch 번호를 찾고 `0x116c4`에서 `SignalStarted` 호출로 이어진다. 순정 `moviDisk` 파티션 이름은 `Part00=DiskA`, `Part01=DiskA3`, `Part02=DiskA2`다. [AVNSysInit 디컴파일](../build/gd13my-boot/phase6-ghidra-avn.log) · [하이브 레코드](../build/gd13my-boot/phase6-hive-evidence.json)

### 부팅 정체와 주변장치 변경

장시간 순정 BIN 실행에서 확인한 중단 지점은 아래와 같다. 주소는 게스트 PC와 OMAP 물리 주소다.

| 게스트 PC | 물리 접근 | 코드 변경과 재실행 결과 |
|---|---|---|
| `0xd1e48958` | `0x48094010` 읽기 | Mailbox soft reset과 RESETDONE을 모델링했다. [최초 중단](../build/gd13my-boot/phase6-experiment.json) |
| `0xd1e4745c` | `0x48004024` 읽기 | 순정 `dsp_bridge.dll` RVA `0x25745c`는 IVA2 DPLL 잠금 비트를 검사한다. 게스트가 lock·bypass 모드를 쓰면 상태 비트에 반영했다. [정체 재현](../build/gd13my-boot/phase6-mailbox.json) |
| `0xc00a1ee4` | `0x5c7f8000` 쓰기 | DSP 드라이버가 초기화하는 IVA2 L2 및 L1 RAM 범위를 TI 메모리 맵대로 매핑했다. [DPLL 통과 실행](../build/gd13my-boot/phase6-pll.json) |
| `0xd1e4850c` | `0x5d000010` 읽기 | IVA2 MMU의 soft reset과 RESETDONE을 모델링했다. 게스트가 DSP 시작을 세 차례 재시도하고 타임아웃 분기 후 다음 장치를 로드했다. [IVA2 RAM 실행](../build/gd13my-boot/phase6-iva2.json) · [DSP 타임아웃 로그](../build/gd13my-boot/phase6-iva2-mmu.json) |
| `0xc0892a90` | `0x480ab060` 읽기 | `musbotg.dll`이 읽는 DEVCTL과 OMAP MUSB 리셋 레지스터를 모델링했다. 케이블 감지 상태는 VBUS가 없는 B-device다. [MUSB 접근](../build/gd13my-boot/phase6-iva2-mmu.json) |
| `0xc08a23e0` | `0x20000018` 쓰기 | `ISP1582Function.dll`의 2바이트 간격 레지스터 접근에 맞춰 soft reset, 읽기 전용 ID 및 VBUS 상태를 구현했다. [ISP1582 접근](../build/gd13my-boot/phase6-musb.json) |
| `0xc0893b2c` | `0x480ab102–0x480ab103` 읽기 | 게스트가 빈 MUSB EP0의 `FLUSHFIFO` 완료를 기다렸다. 빈 FIFO에서 레지스터 명령을 처리하고 비트를 내리도록 구현했다. [정체 재현](../build/gd13my-boot/phase6-live-1.json) |
| `0xd38c52d8` | `0x48098068` 쓰기 | McSPI1 채널 3 구성이었다. 분리된 SPI 장치의 PIO 송수신 상태를 구현하고 오류 명령에서 재개했다. [McSPI 접근](../build/gd13my-boot/phase6-flush-1.json) · [Linux McSPI 레지스터](https://github.com/torvalds/linux/blob/v6.12/drivers/spi/spi-omap2-mcspi.c) |
| `0xa401878c` | 순정 OAL `WFI` | 캐시 별칭의 WFI로 Unicorn 실행이 반환됐다. 모델링된 IRQ 또는 GPTIMER1 비교 시점에 게스트가 계속 실행되도록 연결했다. [WFI에서 반환된 실행](../build/gd13my-boot/phase6-flush-2.json) |
| `0xa40187d0` | `0x48004a4c` 읽기 | WFI 이후 OAL은 L3 인터페이스 클록 활성 비트를 기다렸다. 에뮬레이터에서 계속 동작하는 L3·L4의 클록 상태를 `CM_CLKSTST_CORE`에 반영했다. [Wake 이후 정체](../build/gd13my-boot/phase6-wake-1.json) |
| `0xf100afac` | CE 프리페치 트랩 | `AVNSysInit.exe`의 `RegEnumValueW` 호출에서 반복 예외 보호가 동작했다. `coredll.dll` 반환 주소 `0x4002e840` 및 트랩 직전 코드를 확인했다. ARM 인자까지 비교해 서로 다른 레지스트리 열거 호출을 구분했다. [트랩 로그](../build/gd13my-boot/phase6-core-1.json) |
| `0xc0772ab0` | `0x50000014` 읽기 | `srvkm.dll`의 SGX530 리비전 읽기를 확인했다. TI OMAP35x BSP가 명시하는 1.2.1을 읽기 전용으로 노출했다. GPU 명령은 실행하지 않는다. [SGX 접근](../build/gd13my-boot/phase6-enum-1.json) · [TI CE BSP 릴리스 노트](https://software-dl.ti.com/sdoemb/sdoemb_public_sw/wince_sdk/latest/exports/BSP_WINCE_ARM_A8_02_00_00_Release_Notes.pdf) |
| `0xc0996344` | `k.fpcrt.dll` ARM opcode `0xee000a10` | VFP 레지스터 이동 명령에서 발생한 예외를 조사했다. CPACR 또는 FPEXC가 접근을 막으면 순정 Undefined Instruction 벡터에 전달한다. [VFP 중단 로그](../build/gd13my-boot/phase6-enum-2.json) · [ARM Cortex-A8 기술 참조](https://documentation-service.arm.com/static/5e8e186488295d1e18d35b06) |

McSPI 매핑 후 같은 게스트 상태에서 재개한 진단에서는 `devmgr.dll`의 `0xc0262310` 복귀 주소에 해당하는 순정 `SignalStarted(20)` 호출이 관측됐다. 이어 `filesys.dll`이 `CreateProcessW("AVNSysInit.exe")`를 호출했고, 실제 명령 실행을 VA `0x00011c74`, ROM PA `0x80d62c74`에서 검증했다. `AVNSysInit.exe`가 `\DISKA3\System\calib.bak`과 `calib.cgf`를 열고 보정 경로를 재시도하는 것까지 확인했다. [실행 추적](../build/gd13my-boot/phase6-flush-2.json)

이후 콜드 부팅에서 보정 파일 경로 없음(오류 3) 처리와 `SignalStarted(25)`을 확인했다. `gwes.dll`의 진입점은 VA `0xc01ef5e8`, ROM PA `0x8024b5e8`였다. SGX 레지스터를 매핑하고 같은 게스트에서 재개하자 DISPC 그래픽 평면이 활성화됐다. 게스트 물리 `0x84000000`, stride 3,200바이트의 RGB565 내용을 추출했다. [콜드 부팅](../build/gd13my-boot/phase6-enum-1.json) · [재개 로그](../build/gd13my-boot/phase6-enum-2.json) · [단색 게스트 PNG](../build/gd13my-boot/phase6-enum-2.png)

VFP 접근 예외를 넣은 콜드 실행에서 `CPACR=0`, `FPEXC=0`인 게스트를 순정 벡터 `0xffff0004`로 전달했다. 순정 GWES의 `SignalStarted(30)` 호출자 복귀 주소 `0xc015bebc`와 이어진 `CreateProcessW("AutoStartUp.exe")`를 관측했다. CE 콜백이 같은 인자로 반복될 때 실제 게스트의 복귀 주소·모드·스택을 추적해 반복 예외 보호의 오판을 줄였다. 전체 예외 수를 `exception_count`에 기록하고 최신 4,096건의 원시 내용을 보존한다. [VFP 및 GWES 실행](../build/gd13my-boot/phase6-vfp-1.json)

IVA2 MMU 모델은 ARM이 읽고 쓰는 레지스터 수준이며 C64x+ 명령은 실행하지 않는다. USB 모델은 분리된 케이블의 초기화 상태를 제공한다. 레지스트리 Launch·Depend 값과 드라이버 반환값은 순정 코드에 맡겼다. [TI OMAP35x TRM](https://www.ti.com/lit/ug/spruf98y/spruf98y.pdf) · [Linux MUSB 레지스터](https://github.com/torvalds/linux/blob/v6.12/drivers/usb/musb/musb_regs.h) · [NXP ISP1582 데이터시트](https://www.mouser.com/catalog/specsheets/ISP1582_6.pdf)

Unicorn 2.1.4는 CPU 컨텍스트와 프로세스 내부 RAM 스냅샷을 지원한다. 프로세스를 넘어 동일 상태에서 재개하려면 Python 장치 모델의 IRQ, 타이머, 디스크 및 UART 상태도 저장해야 한다.

### 도구 호환성

2026-11-21 KST에 GitHub 저장소의 접근 가능 여부, 아카이브 상태, 마지막 push 및 설명을 확인했다. 아래 항목은 모두 접근 가능했고 활성 아카이브 플래그가 꺼져 있었다.

| 도구 | 조사 결과와 적용 |
|---|---|
| REA, REA Skill, REI Skills | 로컬 REA MCP의 PE 분석으로 `moviDisk.dll`과 `dsp_bridge.dll`의 ARM PE32 import를 확인했다. Windows 공급자의 raw ARM 지원 범위 때문에 코드 분석에는 로컬 Ghidra를 사용했다. REA Skill과 REI Skills는 분석 흐름과 스킬 인덱스를 제공한다. [REA](https://github.com/morluto/rea) · [REA Skill](https://github.com/smartworldarafath/REA_Skill) · [REI Skills](https://github.com/rootcastleco/rei-skills) · [PE 분석 근거](../build/gd13my-boot/phase6-rea-dsp-bridge.json) |
| Ghidra, Ghidra MCP | 기존 Ghidra 12.2 headless에서 ROM 코드 섹션을 원래 ARM VA에 배치하고 `device.dll`, `devmgr.dll`, `AVNSysInit.exe`, `dsp_bridge.dll`을 분석했다. 별도 Ghidra MCP에는 GUI·headless 연결 기능이 있으나 이 세션에는 기존 REA MCP만 연결돼 있었다. [Ghidra](https://github.com/NationalSecurityAgency/ghidra) · [Ghidra MCP](https://github.com/bethington/ghidra-mcp) · [DSP 디컴파일](../build/gd13my-boot/phase6-ghidra-dsp.log) |
| unblob, binwalk, firmware-workshop | 범용 추출기와 에뮬레이션 실습 자료다. 기존 파서가 APP과 CE BIN을 검증·추출하므로 이를 계속 사용했다. [unblob](https://github.com/onekey-sec/unblob) · [binwalk](https://github.com/ReFirmLabs/binwalk) · [firmware-workshop](https://github.com/onekey-sec/firmware-workshop) |
| Unicorn, QEMU, Qiling, CERF | Unicorn 2.1.4의 Cortex-A8 MMU, MMIO 및 코드 훅을 재사용했다. QEMU는 보드 단위 모델 비교에, Qiling은 개별 바이너리 계측에 참고할 수 있다. CERF의 OMAP3530 EVM 모델과 기존 실행 로그는 GD13MY OEM 메모리 차이를 확인하는 대조군이다. [Unicorn](https://github.com/unicorn-engine/unicorn) · [QEMU ARM](https://www.qemu.org/docs/master/system/target-arm.html) · [Qiling](https://docs.qiling.io/en/latest/) · [CERF](https://github.com/gweslab/cerf) |
| hvtool, extract-wince-rom, YAC6xSim | hvtool의 참조 레이아웃을 사용해 CE 하이브의 연결 레코드를 해석했다. extract-wince-rom은 e32/o32에서 PE를 재구성하는 후속 도구 후보다. YAC6xSim은 공개 C64x 시뮬레이터지만 C64x+ 확장과 OMAP IVA2 통합은 확인되지 않았다. [hvtool](https://github.com/nlitsme/hvtool) · [extract-wince-rom](https://github.com/gweslab/extract-wince-rom) · [YAC6xSim](https://github.com/DragonL/YAC6xSim) · [TI DSP 명령어 참조](https://www.ti.com/lit/ug/spru732j/spru732j.pdf) |
| 개발 효율화 | RTK 1.2.1 Windows OSS 바이너리의 릴리스 SHA-256을 확인하고 심볼 검색과 테스트 요약에 사용했다. Serena와 Code Review Graph는 로컬 명령 및 연결 MCP에서 확인되지 않아 현재 범위는 `rg` 심볼 검색으로 조사했다. Ponytail과 Caveman의 구현 및 보고 지침을 적용했다. [RTK](https://github.com/rtk-ai/rtk/releases/tag/v1.2.1) · [Serena](https://github.com/oraios/serena) · [Code Review Graph](https://github.com/tirth8205/code-review-graph) · [Ponytail](https://github.com/SuperCodeAgents/ponytail-skill) · [Caveman](https://github.com/JuliusBrussee/caveman) |

CE 6.0의 커널 공간 Device Manager와 `udevice.exe` 분리를 기준으로 실행 결과를 해석했다. CE 5.0과 Compact 7의 자료는 API와 하드웨어 모델을 조사하는 데 참고했으며 GD13MY 모듈의 주소와 의존성은 이 ROM에서 확인했다. TI TRM의 PRCM, 메모리 맵, IPC mailbox, IVA2 MMU 및 DSS 설명과 Linux OMAP3 디바이스 트리 및 DISPC 구현을 대조했다. [Microsoft CE 6.0 커널 구조](https://learn.microsoft.com/en-us/archive/msdn-magazine/2006/december/mobilize-explore-the-new-features-in-windows-embedded-ce-6-0) · [TI OMAP35x TRM](https://www.ti.com/lit/ug/spruf98y/spruf98y.pdf) · [Linux OMAP3 디바이스 트리](https://github.com/torvalds/linux/blob/v6.12/arch/arm/boot/dts/ti/omap/omap3.dtsi) · [Linux DISPC](https://github.com/torvalds/linux/blob/v6.12/drivers/gpu/drm/omapdrm/dss/dispc.c)

### 장시간 콜드 부팅 재현

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$boot = 'build/gd13my-boot'
$run = Join-Path $boot ('gd13my-stock-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
& $py tools/emulate_gd13my.py --guest-exceptions --disk "$boot/diska.img" --disk-start-lba 131070 --virtual-timer --timer-irq --instructions 2000000000 --seconds 300 --boot-trace --frame "$run.png" > "$run.json"
```

`boot_trace.milestones`에는 출처를 ROM 물리 페이지와 대조한 실행 지점을 남긴다. `ui_entries`는 실제 게스트가 실행한 모듈 진입점, `stop_context`와 `last_mmio`는 마지막 CPU 상태와 MMIO 접근을 보여 준다.

### 콜드 부팅 결과

- `device.dll`, `AVNSysInit.exe`, `gwes.dll`이 각각 순정 시작 신호 20, 25, 30을 호출했다. `ddi.dll`이 DSS 레지스터를 77회 썼고, `AutoStartUp.exe`와 `Touch_Calib.exe`의 진입을 각각 `0x00012160`, `0x00011968`에서 확인했다. `AutoStartUp.exe`의 `0x00011eec`로 복귀하는 순정 `CreateProcessW`가 `\DiskA\Application\UComH_New.EXE`를 요청했다. [장시간 실행 로그](../build/gd13my-boot/gd13my-stock.json)
- LCD가 물리 `0x84000000`에서 읽은 RGB565 화면을 저장했다. 800×480, stride 3,200바이트이며 실제 화면에 터치 보정 안내와 중앙 십자 표시가 있다. PNG SHA-256은 `67ab583fb186452ffa652ca4096c168f7cf879445723558435822252a8683728`이다. [PNG](../build/gd13my-boot/gd13my-stock.png)
- 실행은 호스트 시간 한도에 도달해 `kernel.dll+0xb79c`(VA `0x8402779c`)에서 반환됐다. 이 실행은 미처리 메모리 오류나 미처리 명령 오류 없이 시간 한도까지 진행됐다. 캡처 시 화면은 보정 입력을 기다리고 있었고 내비게이션 메인 화면과 `UComH_New.EXE` 명령 실행은 미확인이다. 순정 게스트는 `OpenPartition` 오류 2를 두 차례 보고했다. 현재 디스크에는 `DiskA` 한 파티션만 있다. [실행 로그](../build/gd13my-boot/gd13my-stock.json)
- 다음 단계는 정상 터치 경로에 원시 좌표를 공급하고 보정 뒤의 앱 실행을 검증하는 것이다. `ddi.dll`의 정상 모드는 `0x01010098` HAL 요청에 IRQ 246과 65를 각각 넘긴다. `digen_touch.dll`의 `0xc0841368`는 이벤트 데이터를 읽어 좌표와 접촉 플래그로 해석한다. 터치 입력과 추가 파티션의 읽기·쓰기 동작을 확인한 뒤 `UComH_New.EXE` 진입을 추적한다. [Microsoft IRQ와 SYSINTR 매핑 참조](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms904468%28v%3Dmsdn.10%29)

### 터치 보정과 내비게이션 시작 추적

- 마우스 입력을 GPIO118과 McSPI1 CS3에 연결했다. 순정 드라이버가 IRQ 32와 65를 통해 원시 접촉 데이터를 읽었고, 보정점 다섯 개를 수집한 뒤 순정 `TouchPanelSetCalibration(5, …)`을 호출했다. 게스트가 그린 보정 확인 화면을 저장했다. [게스트 PNG](../build/gd13my-boot/gd13my-calibration-confirm.png) · [보정 로그](../build/gd13my-boot/gd13my-window-20261121-153854-559840.calib.log)
- APP 119개와 MAP 914개를 가상 디스크에 기록했다. WinCE 파일 API로 확인한 마운트 순서는 `DiskA`, `DiskA2`, `DiskA3`다. 초기 이미지에서는 레지스트리의 `Part01`과 `Part02` 문자열을 따라 지도와 설정을 반대로 배치해 `\DiskA2\Map`이 열리지 않았다. 빌더의 파티션 순서를 수정하고 새 이미지에서 순정 `SAFPlayer`가 지도 음성 아카이브를 찾고 재생 스레드를 시작하는 것을 확인했다. 창 실행의 섹터 쓰기는 메모리에 보관된다. [수정 이미지 부팅 로그](../build/gd13my-boot/gd13my-window-20261121-201231-338653.serial.log) · [TI OMAP3 MMC 및 DMA](https://github.com/torvalds/linux/blob/v6.12/arch/arm/boot/dts/ti/omap/omap3.dtsi)
- 순정 `UComH_New.exe` 진입 VA `0x00038cd8`에서 파일의 ARM 코드를 확인했다. 가상 MICOM이 UART1에서 XOR 검사를 통과한 기동 프레임에 응답했고, 순정 시스템 관리자가 `CStateStandBy`에 진입했다. 가상 응답은 순정 ARM 코드의 상태 전이를 확인하기 위해 사용했다. [실행 지점](../build/gd13my-boot/gd13my-window-20261121-153854-559840.app.log) · [순정 UART 로그](../build/gd13my-boot/gd13my-window-20261121-155213-546057.serial.log)
- 순정 `ddi.dll`의 `GET_HW_KEY` 처리 중 PC `0xc08e4e04`에서 OMAP35x 공개 ROM의 물리주소 `0x400140bc`를 읽는다. 공개 ROM 이미지가 없을 때 에뮬레이터는 동기 외부 데이터 어보트(DFSR `0x8`)를 전달하고, 순정 CE 예외 처리 경로가 후속 초기화를 진행한다. `--omap-public-rom`을 지정하면 제공받은 32 KiB 이미지를 읽기 전용으로 매핑한다. [수정 이미지 부팅 로그](../build/gd13my-boot/gd13my-window-20261121-201231-338653.serial.log) · [TI OMAP35x TRM 메모리 맵](https://www.ti.com/lit/ug/spruf98y/spruf98y.pdf)
- `FPCRT.dll`의 `0x40ca6344`에서 WinCE가 Undefined Instruction 벡터를 처리한 뒤 FPEXC.EN을 설정하고 같은 명령을 다시 실행하는 것을 관측했다. FPEXC.EN과 번역 블록의 진행 여부, 또는 같은 스택과 복귀 주소로 다음 명령에 도착했는지를 확인해 이미 처리된 VFP 예외를 반복 횟수에서 제거한다. OMAP 동기 타이머의 `0x48320010` 읽기도 GPTIMER1과 같은 32,768 Hz 가상 시계에 연결했다. [VFP 추적](../build/gd13my-boot/gd13my-window-20261121-201231-338653.user-vfp.log) · [TI 32 kHz 카운터](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel/commit/?id=1fe97c8f6a1de67a5f56e029a818903d5bed8017)
- 게스트 `CreateProcessW`로 순정 `GDdNavi.exe`를 진단 실행했다. 수정된 지도 볼륨으로 `InitNavi_Step1()`을 통과했고, `InitMap()`이 CMD18 `0x12220032`와 MMCHS_BLK `0x1ff80200`을 요청했다. 이전 구현의 2,048섹터 제한에서 DTO가 발생했다. 블록 수를 16비트 레지스터 범위로 처리하도록 고치고 8,184섹터 읽기를 회귀 검증했다. [순정 내비게이션 로그](../build/gd13my-boot/gd13my-window-20261121-201231-338653.serial.log) · [MMC 추적](../build/gd13my-boot/gd13my-window-20261121-201231-338653.mmc-progress.log)
- 수정한 에뮬레이터를 다시 부팅해 실제 지도 읽기 CMD18의 정상 R1 응답 `0x00000900`과 후속 읽기를 확인했다. 다음 대기 지점은 순정 `srvkm.dll`의 그래픽 초기화였다. PC `0xc0776954`에서 VA `0xd42b0010`의 bit 0이 0을 기다렸으며 값은 1로 유지됐다. 호출자는 시간 초과 뒤 `0x22`를 반환했으며 같은 초기화를 반복했다. [실제 다중 블록 읽기](../build/gd13my-boot/gd13my-window-20261121-203429-019821.large-read.log) · [GPU 대기 추적](../build/gd13my-boot/gd13my-window-20261121-203429-019821.sgx-recovery.log) · [PowerVR SGX530 레지스터 정의](https://android.googlesource.com/kernel/omap.git/+/android-omap-tuna-3.0-jb-mr2/drivers/gpu/pvr/sgx530defs.h)

가상 디스크가 준비된 PC에서는 Windows 창을 다음 명령으로 열 수 있다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$disk = Join-Path $env:LOCALAPPDATA 'i30-gd13my/gd13my-media-v2.img'
& $py tools/view_gd13my.py --disk $disk
```

가상 디스크를 다시 만들 때는 `tools/build_gd13my_diska.py --with-map`에 새 이미지 경로를 전달한다. 이 빌드에는 `pyfatfs`와 `pkg_resources`가 포함된 setuptools가 필요하다.

### 순정 내비게이션 홈

- 내비 모드를 최초 MICOM 표시 모드로 선택한 부팅에서 순정 시스템 관리자가 `GDdNavi.exe`를 시작하고 `PATH_Navi`로 등록했다. 순정 `BUTTON_PUSH_AGREE_ON`, `NAVI mode`, `MAIN mode ACK from APP`을 관측했다. 가상 MICOM이 아직 생성하지 못하는 앱 상태 통지는 진단 실행에서 한 번 전달했다. [부팅과 동의 기록](../build/gd13my-boot/gd13my-window-20261121-211518-350165.serial.log) · [진단 이벤트](../build/gd13my-boot/gd13my-window-20261121-211518-350165.mode.log)
- SGX530 대신 순정 내비 자체의 OpenGL ES 호출 53개를 Windows 소프트웨어 렌더러로 전달했다. 지도 픽셀을 게스트 VID1 `0x84000640`에 기록하고, GFX `0x84000000`의 RGB565 투명색 `0xf818`에서 VID1을 합성했다. 하단 버튼과 상태 표시가 포함된 800×480 홈 화면을 캡처했다. [순정 내비 홈](../build/gd13my-boot/gd13my-stock-navigation-home.png) · [DISPC 합성](../build/gd13my-boot/gd13my-window-20261121-211518-350165.lcd-composite.log) · [TI DISPC 레지스터](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/tree/drivers/gpu/drm/omapdrm/dss/dispc.c?h=ti-linux-5.10.y-next&id=41ab5a111c97546157e942980b45998b535389e1)
- 동의 뒤 TPEG 초기화가 물리주소 `0x4809a010`을 읽다가 중단됐다. 기존 SPI 모델을 McSPI2에 배치하고 IRQ 66을 연결한 뒤 순정 드라이버의 SPI2 설정 성공을 확인했다. [SPI2 재개 로그](../build/gd13my-boot/gd13my-window-20261121-211518-350165.spi2.log) · [TI OMAP3 장치 주소](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/blame/arch/arm/boot/dts/omap3.dtsi?h=ti-linux-4.14.y-next&id=b915c81ff372341b8d67593f00d64c98bdc6b32d)

Windows 소프트웨어 렌더링은 `--software-gl-app`에 추출한 순정 `GDdNavi.exe`를 전달해 사용한다. PVRTC·ETC1 텍스처에는 `texture2ddecoder==1.0.6`이 필요하다. [텍스처 디코더 배포본](https://pypi.org/project/texture2ddecoder/1.0.6/)

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$disk = Join-Path $env:LOCALAPPDATA 'i30-gd13my/gd13my-media-v2.img'
$navi = 'firmware/extracted/GD13MY/APP/00d12869_GDdNavi.exe'
& $py tools/view_gd13my.py --disk $disk --micom-display navi --software-gl-app $navi --seconds 1800
```
