# Phase 3·4 통합 상태

2026-11-21 KST 기준. 기존 소스, 패키지 빌드, 저장된 실폰 로그를 대조했다. 시작 시 이미 있던 30개 테스트를 재실행해 모두 통과했다. 기존 프로젝트 수신기의 실폰 근거는 AOA 2 전환, USB bulk, Android Auto 1.7 버전 응답까지다. Google DHU의 실폰 TLS·화면·터치 결과는 별도의 근거로 남긴다. [기존 실폰 시험](USB_CONNECTION_TEST.md)

## Phase 3 · 수신기 기능과 검증

| 영역 | 구현 및 검증 범위 |
|---|---|
| 버튼과 터치 | 입력 채널이 지원 키를 광고하고 상대가 바인딩한 키만 전송한다. 모의 입력은 HOME, BACK, MENU, NAV, MEDIA, SEEK/TRACK, 재생·일시정지, 음성 키를 모델링한다. 화면 소유권 변경 시 눌린 키와 터치 상태를 해제한다. 볼륨, 매핑 외 버튼과 순정 상태에서 누르기 시작한 버튼은 호스트가 처리한다. 실물 패널 및 스티어링 휠 버튼의 코드·전달 경로는 벤치에서 확인한다. |
| 음악과 안내음 | 48 kHz 스테레오 음악과 16 kHz 모노 안내 PCM을 독립적으로 수신한다. 20 ms 단위 출력, 채널·레이트 변환, 소프트웨어 게인, 안내음 재생 중 음악 25% 게인, 스트림당 큐 최대 120 ms를 적용했다. 모의 세션에서 출력 샘플을 검증했다. Windows WinMM에서는 무음 블록 쓰기, 닫기, 재열기를 확인했다. |
| 마이크 | PC에서 `--mic-in`으로 선택한 장치를 폰의 열기 요청 이후에 획득한다. 입력을 16 kHz 모노 PCM으로 변환하며 20 ms 패킷과 최대 4개 미확인 송신을 사용한다. 대기 중인 오래된 샘플은 버린다. 모의 음성 요청, PCM 내용, 마이크 종료, USB 분리 시 해제를 검증했다. PC 장치 열거와 포맷 질의는 완료했다. 실제 마이크 캡처와 폰의 음성 인식 결과는 미검증이다. |
| PC 화면 | PyAV와 Tk로 800×480 연속 영상, 터치 누름·이동·뗌, 키보드 이벤트를 처리한다. 합성 H.264를 PC 창에 디코딩하고 순정 화면을 모사한 상태로 복귀하는 시험을 통과했다. |

마이크 요청·응답은 기존 aasdk 디스크립터를 사용하며 응답 메시지 ID는 `0x8006`이다. 음성 버튼은 기존 OpenHU 매핑에 맞춰 `KEYCODE_SEARCH`를 사용한다. 최신 Android Auto의 마이크 메시지와 실제 페어링 결과는 별도로 비교해야 한다. [마이크 메시지 ID 근거](https://github.com/mrmees/open-android-auto/blob/main/oaa/av/AVChannelMessageIdsEnum.proto)

## Phase 4 · GD13MY 통합 상태

대상 패키지는 `GD13MY.KOR.SOP.00.061`이다. `uComH_New.exe`의 PE를 다시 확인해 PE32 little-endian 머신 `0x01c2`, Windows CE GUI subsystem `9`, subsystem 버전 `6.0`을 확인했다. ROM의 OMAP3530 BSP, `coredll.dll` export, WaveDev 및 SAF7730 근거를 대조했다. REA로 `uComH_New.exe`와 `LibMMCodec.dll`의 PE import를 재확인했다. 순정 CE의 코드는 경량 ARMV4I API 경계를 대상으로 작성했다. [ROM과 ABI](DEEP_REVERSE_ENGINEERING.md) · [순정 I/O 분석](VIDEO_AUDIO_ANALYSIS.md)

| 영역 | 현재 구현 | 실물 검증 또는 연동이 필요한 부분 |
|---|---|---|
| 실행 및 복구 | `ce_supervisor.c`가 지정한 자식 프로세스를 감시한다. 자식 PID와 현재 시간을 기준으로 연결 후 첫 프레임 준비 및 heartbeat를 확인할 수 있다. 연결 해제, 사용자 선택, 순정 우선 상태, 자원 예산에 따라 화면을 반환하고 종료 이벤트를 보낸다. 응답을 멈춘 프로세스는 1초 후 종료하며 실패는 연결당 2회로 제한한다. | OEM 이벤트, 승인된 실행 경로, 화면 전환과 복구를 담당할 독립 호스트, 작업 프로세스의 ARM TLS·protobuf 코어가 필요하다. |
| 오디오와 마이크 | `ce_wave.c`는 순정 호스트가 자원 사용을 허용했을 때 `waveOut`/`waveIn` PCM을 사용한다. 방향당 고정 버퍼 3개를 사용하며 리셋·반납·닫기를 처리한다. 질의용 probe는 화면 크기·RAM·WaveDev PCM 지원을 디버거에 기록한다. | CE용 빌드와 실제 `WaveDev` 포맷, 라디오·순정 미디어·ASR·통화·경고음과의 독점 및 반환 동작을 확인해야 한다. |
| USB와 영상 | 기존 PC USB AOA, TLS, 프레임, H.264 경로를 유지한다. | CE `USBD`의 대상 USB 클라이언트와 bulk 전송, `VID1:` 디코더 입력, DirectDraw 표면을 연결해야 한다. 확인된 순정 H.264의 파일/TS 경로만으로 Android Auto 스트림 주입을 보장할 수 없다. |
| 차량 기능과 입력 | PC 모의 호스트에서 후방카메라·차량 경고 우선권과 버튼 반환을 시험했다. CE 감독기는 `stock_permits_projection`이 해제되는 즉시 독립 순정 호스트에 화면 반환을 요청한다. | OEM에서 후방카메라, 주차 화면·차량 경고, 라디오·설정, 버튼 이벤트를 공급하고 우선권과 복귀 시간을 직접 실측해야 한다. 차량 통신과 안전 제어 경로의 변경은 없다. |
| 메모리와 CPU | PC PCM/마이크 큐와 H.264 입력 상한을 적용했다. CE 오디오 저장부는 재생 11,520 B와 캡처 1,920 B에 헤더가 추가된다. 감독기는 OEM 호스트가 평가한 `resource_budget_ok`로 동작을 제한한다. | 실제 기기의 피크 메모리, CPU와 480p/30 fps 지속 처리량은 측정되지 않았다. OEM 호스트의 자원 측정과 한도는 실측 후 확정한다. |

현재 PC에는 레거시 ARMV4I 컴파일러와 GD13MY OEM SDK가 확인되지 않았고, USB 열거에 Android Auto 액세서리가 없었다. 네이티브 C 소스는 x64 MSVC에서 `/W4 /WX`를 사용해 확인했다. CE 빌드 레시피의 출력은 `i30-ce-platform.lib`와 진단용 `i30-ce-probe.exe`이며 대상 SDK에서의 컴파일과 실물 검증이 남아 있다. [Microsoft CE 6.0 개발 환경](https://learn.microsoft.com/en-us/archive/msdn-magazine/2006/december/mobilize-explore-the-new-features-in-windows-embedded-ce-6-0) · [TI ARMV4I 빌드 설정](https://software-dl.ti.com/dsps/dsps_public_sw/sdo_sb/targetcontent/rtsc/3_16_01_27/exports/docs/cdoc/microsoft/targets/arm/WinCE-src.html) · [Microsoft CE Wave API](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/aa452455(v=msdn.10))

## 재현

프로젝트 루트에서 기존 Phase 2 가상환경과 protoc를 사용한다. 영상 미리보기와 PC 창은 PyAV가 필요하며 PC 창은 Tk를 사용한다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$protoc = Join-Path $env:LOCALAPPDATA 'i30-phase2-tools/protoc/bin/protoc.exe'
& $py tools/build_phase2.py --protoc $protoc
& $py -m unittest discover -s tests -v
& $py build/i30-receiver.pyz mock --phase3 --scenario unplug --reconnect --tap 300 230
& $py build/i30-receiver.pyz audio-devices
```

테스트 35개가 통과했다. 분리·재연결 모의 시험에서 세션과 USB 링크 2개를 정리했고, 키 보고 8개, 터치 보고 2개, 검증된 마이크 PCM 블록 3개, 오디오 믹싱 블록 3개, 모의 순정 화면 복귀 3회를 관찰했다. 네이티브 테스트는 별도의 실제 자식 프로세스를 실행해 정상 종료, 크래시, 재시작 대기, heartbeat 만료와 강제 종료를 검증한다. 아래 명령은 MSVC x64 Developer PowerShell에서 실행한다.

```powershell
$root = (Get-Location).Path
$out = New-Item -ItemType Directory -Force build/ce-host-test
Push-Location $out.FullName
try {
    cl /nologo /W4 /WX "/I$root/src/ce" "$root/tests/test_ce_host.c" "$root/src/ce/ce_supervisor.c" "$root/src/ce/ce_wave.c" /Fe:i30-ce-host-test.exe winmm.lib
    if ($LASTEXITCODE -ne 0) { throw 'Native test build failed' }
    .\i30-ce-host-test.exe
} finally { Pop-Location }
```

실폰 세션에서는 `connect --device <BUS-PORT> --ca <등록된-CA> --peer-name <등록된-이름>`에 `--display`, `--audio-out <번호>`, `--mic-in <번호>`를 필요에 따라 추가한다. `--volume`은 PC 프로젝션 출력 게인이며 `audio-devices`는 PC 장치 번호를 보여준다. 포트와 인증 설정 절차는 [기존 실폰 시험](USB_CONNECTION_TEST.md)을 따른다.

OEM CE SDK 환경에서는 `tools/build_ce.py --tool-bin <ARMV4I-도구> --sdk-include <SDK-헤더> --sdk-lib <ARMV4I-라이브러리>`를 사용한다. 검증 항목은 PE32 `0x01c2`, subsystem `9`, 버전 `6.0`이다. 실물 적용은 GD13MY 본체·SW 식별, 정상 진단 앱 실행 및 복구, 순정 화면 및 오디오 선점, USB와 H.264 드라이버의 독립 검증에 달려 있다. [기존 벤치 통과 기준](PHASE2_IMPLEMENTATION_PLAN.md)
