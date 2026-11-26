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

## WinCE 영상 처리

이미 표시 중인 영상의 지연도 별도로 계측했다. `tools/emulate_ce_usb.py --continuous-seconds 1 --continuous-fps 15 --motion-pattern --profile-video`에서 동일 800×480 입력 15장을 사용했다. H.264 라이브러리만 `-O2`로 변경했고 두 실행에서 15장 모두 응답과 표시를 확인했다.

| ARM 시험 | 기존 `-Os` | H.264 `-O2` |
| --- | ---: | ---: |
| 프레임당 디코딩 평균 | 157.12ms | 133.81ms |
| 프레임당 BGRA 변환 평균 | 51.56ms | 23.50ms |
| 전체 ARM 시험 벽시계 | 4.365초 | 3.117초 |

이 수치는 에뮬레이션된 ARM 실행이다. 실제 순정 GDI와 실폰 USB를 포함한 영상 속도는 따로 측정해야 한다. 원본은 로컬 `E:/i30-gd13my-images/opencode-resume-perf/touch/`의 `current-arm-video-profile.json`, `decoder-o2-profile.json`이다.
