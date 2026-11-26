# 실제 GDdNavi 지도 성능 비교

측정일: 2026-11-26/27 KST. 실제 stock WinCE kernel, GDdNavi.exe, GD13MY media image와 DiskA app volume으로 `tools/bench_gd13my.py`를 실행했다. 각 실행은 같은 SQLite 시작 상태를 read-only backup으로 복사했고 동일한 입력(시작 확인 tap, 지도 pan)을 사용했다. 화면 renderer는 두 조건 모두 GDI Generic software였다. 비교 변수는 GPTimer MMIO read 처리 방식뿐이었다.

## 재현 명령

```powershell
$py = "$env:LOCALAPPDATA\i30-phase2-venv\Scripts\python.exe"
$env:GD13MY_CLOCK_DLL = (Resolve-Path build\gd13my-block-clock.dll).Path # baseline
# native C 경로 비교 시: build\gd13my-block-clock-fasttimer.dll
& $py tools\bench_gd13my.py `
  --image firmware\extracted\GD13MY\BSP\0002dfc7_kernel `
  --disk E:\i30-gd13my-images\gd13my-media-v2.img `
  --app-volume E:\i30-gd13my-images\opencode-resume-perf\touch\gd13my-aare-settings-o2.img `
  --software-gl-app firmware\extracted\GD13MY\APP\00d12869_GDdNavi.exe `
  --state E:\i30-gd13my-images\map-perf\route-input-smoke\bench-20261126-201024-352644.sqlite3 `
  --route-input E:\i30-gd13my-images\map-perf\wgl-stock-map-ab-20261126\map-pan-input.json `
  --micom-display navi --seconds 180 --stop-after-ready 20 `
  --output-dir E:\i30-gd13my-images\map-perf\native-gptimer-fixed-ab-20261127\baseline --save-output
```

실행 JSON 및 guest JSON은 `E:\i30-gd13my-images\map-perf\native-gptimer-fixed-ab-20261127\` 아래에 보존했다. 동일 이미지와 입력을 써도 host scheduler 부하 및 boot stage 도착 시간이 변하므로 표본 2회만으로 작은 차이를 확정하지 않는다.

## 결과

| 경로 | 전체 guest clock Munit/s (2회) | 지도 준비 wall s (2회) | 준비 후 guest s/wall s (2회) | LCD 변경 프레임 (2회) |
|---|---|---|---|---|
| 기존 Python GPTimer MMIO | 23.27, 23.89 | 90.06, 87.80 | 3.697, 3.707 | 3, 3 |
| Native C GPTimer read | 26.57, 24.21 | 78.78, 81.78 | 4.365, 3.109 | 5, 3 |

전체 throughput 표본 중앙값은 23.58→25.39 Munit/s(+7.7%)이다. 지도 구간 처리량 중앙값은 3.702→3.737 guest s/wall s(+0.9%)다. 화면 변화 프레임은 모두 3~5회뿐이고 20초의 이동 입력이다. CPU 사용률 중앙값은 약 92.9%→92.5%, peak working set 중앙값은 461.7→465.3 MiB다. 따라서 whole-run throughput 증가는 관찰됐지만 지도 FPS의 실질적 개선은 확인되지 않았다. 반복 표본이 늘고 낮은 변동으로 재현되기 전까지 native timer를 성능 성공으로 간주하지 않는다.

시험 범위는 정지 지도 boot 이후 pan뿐이다. route guidance, 확대/축소, 회전, 메뉴/지도 전환, mock drive 경로, 1/3/5분 장시간 성능은 미측정이다. 정지 화면 polling을 차량 FPS로 환산하지 않는다. 실기기 비교와 GPU utilization은 미측정이다.

## GPU 대 software 실제 지도 결과

별도 동일 조건 25초 실행에서 software GDI의 5 VID1 plane copy 합계는 0.0298s, WGL GPU는 0.2495s였다. GPU는 readback 및 copy 비용이 전체 경로를 느리게 했으므로 hardware backend를 기본값으로 바꾸지 않는다. `guest_swaps_after_ready`는 양쪽 3회였고 이것만으로 FPS 차이를 주장하지 않는다. 상세는 [GPU readback 최적화](GPU_READBACK_OPTIMIZATION.md).
