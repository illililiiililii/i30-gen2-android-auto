# 순정 WinCE 에뮬레이터 성능

OpenCode의 헤드리스 벤치와 `build/opencode-bench/baseline/bench-20261126-124533-282456.json`을 인계받았다. 기준 실행은 첫 LCD 127.84초, 내비 준비 705.50초, CPU 665.00초, 최대 작업 집합 451.6MB를 기록했다.

고정 4,096명령 단위 실행은 첫 LCD까지 89.63초였으며, 94.06초에 게스트 오류로 멈췄다. 대기 중인 터치가 F2를 막지 않는지 보는 기존 테스트도 실패했다. 명령어 한도를 지정한 Unicorn 호출에는 내부 명령어 훅이 설치된다. 묶음 사이의 CPU 모드만 검사하면 그사이 실행한 예외 복귀 지점과 문맥을 놓칠 수 있다. [Unicorn FAQ](https://github.com/unicorn-engine/unicorn/blob/2.1.4/docs/FAQ.md)

짧은 기준 프로파일은 3,500만 명령에서 Python 블록 콜백 약 746만 회를 기록했다. 블록 콜백과 Python 래퍼의 자체 시간은 6.19초로, 계측된 에뮬레이션 11.76초의 약 53%였다. 이전 기준 부팅에서 HSMMC1 읽기는 약 1,296만 회였다.

블록 시계의 카운터와 콜백 조건만 C로 옮겼다. 동일한 Unicorn 블록 크기에서 시간을 계산한다. Python은 기존 타이머와 I/O 기한에 도달한 블록, 예외 복귀 후보를 처리한다. C와 Python 경로를 번갈아 두 번씩 측정한 3,500만 명령 구간의 평균은 각각 1.88초와 5.75초였다. 종료 PC `0xc010b4ac`, 게스트 타이머 17,920틱, 타이머 IRQ 9회와 예외 95회가 모두 일치했다. 두 경로에서 Python 테스트 87개를 통과했다.

| 전체 헤드리스 부팅 | OpenCode 기준 | C 블록 시계 |
| --- | ---: | ---: |
| 첫 LCD | 127.84초 | 24.15초 |
| 내비 준비 | 705.50초 | 144.33초 |
| 프로세스 CPU | 665.00초 | 125.42초 |
| 최대 작업 집합 | 451.6MB | 453.9MB |
| 읽은 데이터 | 490.6MB | 489.8MB |

C 실행은 내비 준비 이벤트 뒤 정상 종료했다. 전체 부팅 비교는 OpenCode가 남긴 기준 실행을 사용했다. 두 실행 사이의 호스트 부하와 DiskA 상태 차이가 전체 부팅 수치에 영향을 줄 수 있다. 동일 커널의 고정 명령 구간은 같은 프로세스에서 순서를 교차해 비교했다. 새 원본 보고서는 `E:/i30-gd13my-images/opencode-resume-perf/native-full/`에 있다.

## 빌드와 비교

Visual Studio x64 Developer PowerShell에서 저장소 루트로 이동하고 다음을 실행한다.

```powershell
$output = (Resolve-Path build).Path
cl.exe /nologo /LD /O2 /W4 /WX /MT `
    "/Fo$output/gd13my-block-clock.obj" "/Fe$output/gd13my-block-clock.dll" `
    tools/gd13my_block_clock.c /link "/IMPLIB:$output/gd13my-block-clock.lib"
```

`build/gd13my-block-clock.dll`을 만들면 순정 뷰어와 헤드리스 실행에서 사용한다. 다른 저장장치에 둔 DLL은 `GD13MY_CLOCK_DLL`에 경로를 지정한다. 비교 실행에 `GD13MY_CLOCK_DLL=off`를 사용하면 Python 블록 시계를 쓴다. 각 실행의 JSON에서 `timer.block_clock`으로 사용 경로를 확인한다.

`tools/bench_gd13my.py --help`는 순정 커널·디스크, DiskA 앱 볼륨과 내비 프로그램을 받는 헤드리스 벤치를 설명한다. 요약 JSON과 원본 게스트 보고서는 별도 파일에 저장한다. `--state`를 지정하면 SQLite 백업 API로 시험 전용 DiskA 상태를 만든다. 벤치에 USB가 연결되지 않으며 내비 준비까지 걸린 시간을 기록한다.

## 전체 에뮬레이터 처리량

동일한 AARE `-O2` 시험 이미지를 새 DiskA 상태로 부팅했다. 기준과 후보의 게스트 타이머·USB 설정은 같았다. 현재 기준은 내비 준비 176.903초이며 목표 2.5배는 약 71초다.

| 순정 헤드리스 실행 | 첫 LCD | 내비 준비 | 프로세스 CPU |
| --- | ---: | ---: | ---: |
| 이전 C 블록 시계 | 19.236초 | 176.903초 | 144.86초 |
| 네이티브 eMMC FIFO·IRQ 경로 캐시·ARM 주소 재사용 | 12.964초 | 142.022초 | 113.44초 |
| IRQ 레지스터 조회와 장치 폴링까지 개선 | 10.477초 | 115.449초 | 111.23초 |

부팅 중 eMMC의 4바이트 데이터 레지스터를 약 1,261만 번 읽었다. 섹터 내부에서는 C가 게스트에 같은 바이트를 반환한다. 마지막 워드, BRR·TC 처리와 DMA는 기존 장치 모델을 이용한다. 실제 ARM 명령으로 2섹터를 읽는 회귀에서 256워드, BRR, TC 및 바이트 통계를 확인했다. DLL에 새 MMIO 함수가 없는 경우 Python 모델을 사용한다.

계측 실행에서는 IRQ 경로를 약 240만 번 확인했고, ARM 예외 처리에서 페이지 테이블 주소를 약 53만 번 평가했다. 마스크와 ILR이 갱신될 때 IRQ 경로를 다시 계산하고, 한 ARM 예외의 동일 주소 변환을 재사용한다. 마지막 행에는 GPTIMER·GPIO·SPI·DMA의 반복 레지스터 조회와 호스트 장치 폴링 개선이 포함된다. 내비 준비는 약 1.53배 빨라졌다. 2.5배를 달성하려면 이 기준에서 71초 안팎이 필요하다.

게스트 기본 블록 표본에서 순정 `nk.exe`의 64비트 정수 나눗셈, `kernel.dll`의 반복 루프와 `k.ceddk.dll`의 대기 루프를 확인했다. 이 코드들의 정확한 실행 시간도 측정해야 한다. 기본 블록 표본은 CPU 시간 비율과 다를 수 있다. 순수 Python 경로는 88개 시험을 통과했고 DLL이 필요한 1개 시험을 건너뛰었다. native 경로는 89개 시험을 통과했다. 원본과 별도 진단 DLL은 `E:/i30-gd13my-images/opencode-resume-perf/whole-2.5x/`에 있다.

## WinCE 영상 처리

이미 표시 중인 영상의 지연도 별도로 계측했다. `tools/emulate_ce_usb.py --continuous-seconds 1 --continuous-fps 15 --motion-pattern --profile-video`에서 동일 800×480 입력 15장을 사용했다. H.264 라이브러리만 `-O2`로 변경했고 두 실행에서 15장 모두 응답과 표시를 확인했다.

| ARM 시험 | 기존 `-Os` | H.264 `-O2` |
| --- | ---: | ---: |
| 프레임당 디코딩 평균 | 157.12ms | 133.81ms |
| 프레임당 BGRA 변환 평균 | 51.56ms | 23.50ms |
| 전체 ARM 시험 벽시계 | 4.365초 | 3.117초 |

이 수치는 에뮬레이션된 ARM 실행이다. 실제 순정 GDI와 실폰 USB를 포함한 영상 속도는 따로 측정해야 한다. 원본은 로컬 `E:/i30-gd13my-images/opencode-resume-perf/touch/`의 `current-arm-video-profile.json`, `decoder-o2-profile.json`이다.

## 순정 지도 표시 경로

`GuestGL.egl`은 순정 앱의 `eglSwapBuffers`가 완료돼도 호스트에서 LCD 비디오 평면으로 2초에 한 번만 복사했다. 이제 실제 복사 비용에 따라 최대 30Hz까지 전달한다. 별도 지도 미리보기 PNG에는 기존 2초 간격을 적용한다. `LcdDisplay.copy_map_to_video`는 RGB565 바이트를 일괄 변환하고 한 줄의 패딩이 없으면 Unicorn에 한 번에 쓴다. LCD 캡처는 RGB565 채널 변환과 한 색으로 채워진 키 행의 합성을 묶어서 처리한다. Tk에 화면이 여러 장 대기하면 가장 최근 프레임을 표시한다.

기존 펌웨어 추적에서 순정 `srvkm.dll`의 SGX 초기화 대기와 `GDdNavi.exe`의 GLES 호출을 확인했다. 현재 에뮬레이터의 지도는 53개 GLES 호출을 Windows 소프트웨어 OpenGL로 전달해 그린다. 이번 개선은 그 출력과 DISPC 합성 사이에 적용했다. 실차의 GPU 사용률과 DSP 영상 디코딩 처리량은 측정되지 않았다. [순정 그래픽 초기화와 지도 렌더링](../GD13MY_EMULATION.md)

800×480 프레임 합성 시험에서 같은 입력을 7번씩 사용했다. RGB888 지도 복사 중앙값은 93.64ms에서 6.38ms로, LCD PNG는 일반 화면 147.37ms에서 39.42ms, 전체 컬러 키 화면 165.43ms에서 45.97ms, 혼합 키 화면 135.01ms에서 79.98ms로 줄었다. 비교하는 각 출력의 해시가 일치했다. 65,536개 RGB565 값의 RGB 확장도 이전 LUT와 일치했다. 이 수치는 호스트 디스플레이 경로의 합성 입력 시험이다.

헤드리스 후보에서 순정 앱이 완료한 5개의 스왑을 모두 LCD 비디오 평면에 기록했다. OpenGL 읽기와 LCD 비디오 평면 쓰기는 합계 47.4ms였다. 내비 준비 후 15초 동안 서로 다른 LCD 프레임 2장이 관찰됐다. 경로를 시작하지 않은 상태에서의 결과다. 사용자가 보고한 모의 주행 지연에서 게스트 렌더링과 LCD 전달이 각각 차지하는 시간은 동일 경로를 재생해 측정해야 한다.

E: 지도 이미지와 같은 DiskA 앱 이미지로 한 번씩 순차 부팅했다. 기준과 후보에서 내비 준비는 173.95초와 159.65초, 첫 LCD는 12.04초와 13.87초, 프로세스 CPU는 115.69초와 152.45초였다. 기존 실폰용 뷰어가 두 실행 중 계속 동작했고 두 실행의 CPU 사용률도 달랐다. 전체 처리량이 2.5배 좋아졌다는 증거는 없다. 비교 원본은 로컬 `E:/i30-gd13my-images/map-perf/`의 `paired-baseline`, `paired-candidate`에 있다. 기존 115.45초 기록과의 비교에는 같은 미디어 경로에서 반복 실행이 필요하다.

기존 가상환경에서 전체 회귀 90개를 통과했다. 네이티브 클록을 비활성화하면 89개를 통과했고 네이티브 eMMC 전용 시험 1개를 건너뛰었다. RGB565 패딩과 행 순서를 확인하는 회귀를 추가했다. Windows에서는 삼성 USB 장치가 보였고 ADB 목록은 비어 있었다. 실행 중인 실폰용 뷰어를 유지했다. 변경 후 실폰 인증·영상·터치는 다시 검증해야 한다.

`tools/bench_gd13my.py`의 `stock_map`은 게스트 스왑 수, 비디오 평면 복사 수와 소요 시간을 기록한다. `lcd_after_ready`는 준비 후 바뀐 LCD 화면 수와 화면 간격을 기록한다. `--route-input`에 `[준비 후 초, x, y, 눌림 여부]` 배열을 전달하고 같은 DiskA를 `--state`로 복제하면 터치를 재생할 수 있다. 출발지·목적지·모의 주행을 확인한 입력 목록은 아직 필요하다.

DiskA를 복제한 시험에서 `[[1.0,400,430,true],[1.35,400,430,false]]`로 시작 경고의 동의를 눌렀다. 입력 2개가 전송됐고 최종 LCD에 양재 지도가 표시됐다. 이 시험의 준비 시간은 126.22초였고, 준비 이후 변경된 LCD 프레임은 3장이다. 원본은 `E:/i30-gd13my-images/map-perf/route-input-smoke/`에 있다. 별도의 WinCE ARM 시험에서는 모의 피어와 상호 TLS 및 순정 터치 전달을 확인했다. 800×480 영상 15장은 모두 응답과 표시를 마쳤으며 벽시계는 3.064초였다. 원본은 같은 상위 폴더의 `arm-video-regression.json`이다.

```powershell
Set-Location F:/i30-gen2-android-auto
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py tools/bench_gd13my.py `
    --image firmware/extracted/GD13MY/BSP/0002dfc7_kernel `
    --disk E:/i30-gd13my-images/gd13my-media-v2.img `
    --app-volume E:/i30-gd13my-images/opencode-resume-perf/touch/gd13my-aare-settings-o2.img `
    --software-gl-app firmware/extracted/GD13MY/APP/00d12869_GDdNavi.exe `
    --output-dir E:/i30-gd13my-images/map-perf/repeat `
    --stop-after-ready 15 --ready-timeout 300 --save-output
```

F:와 E:는 같은 USB 디스크의 파티션이다. 기존 이미지에서 각각 32MiB를 읽은 한 차례 시험은 17.71 및 18.00MiB/s였다. 호스트 캐시와 파일 배치에 영향을 받을 수 있다. E:를 출력에 사용했고 기존 이미지를 옮기지 않았다.
