# 하드웨어 가속 성능 결과

측정 날짜: 2026-11-26 KST. 장비: Intel Core i5-1235U, Intel UHD Graphics, WGL OpenGL 4.6 driver 30.0.101.2079. 테스트 scene: 800×480, 삼각형 2,000개, RGB888 frame readback 1,152,000 bytes, warmup 2회와 표본 10회. Python `perf_counter`, draw 구간은 `glFinish()` 포함.

| 경로 | 렌더+완료 중앙값 / p95 | readback 중앙값 / p95 | 합계 중앙값 / p95 |
|---|---:|---:|---:|
| GDI Generic software | 0.948 / 1.517 ms | 1.666 / 2.800 ms | 2.774 / 3.709 ms |
| Intel UHD WGL | 0.841 / 1.156 ms | 3.740 / 5.172 ms | 4.661 / 6.068 ms |

GPU raster 구간 중앙값은 약 11% 낮았지만 CPU readback이 길어 총 프레임 중앙값은 약 68% 높았다. 초기 GPU readback은 context 생성 후 첫 동기화에서 335ms를 기록했다. 초기화/캐시 warmup 비용과 steady-state를 구분한다. 고정 장면의 두 경로는 각각 10/10 프레임이 동일하게 반복됐다. 같은 픽셀 해시는 아니었다. RGB 채널의 768,000/1,152,000 바이트가 달랐고 최대 채널 차이는 1/255였다. 작은 차이지만 비트 단위 화면 동등성은 입증하지 못했다.

이 결과는 단순 geometry scene의 host API benchmark이며 지도 전체, guest Unicorn 비용, 텍스처 upload, DISPC RGB565 변환/복사, Tk 표시를 포함하지 않는다. AARE H.264, USB, WinCE guest FPS도 측정하지 않는다. 따라서 WGL 옵션은 넣었으나 기본 renderer는 변경하지 않았다. ±5% 실기기 목표의 검증 근거는 아직 없다.

재현:

```powershell
$env:PYTHONPATH = 'tools'
python tools/bench_gd13my_gl.py --frames 10 --warmup 2 --output build/hardware-acceleration/host-gl-benchmark.json
```

실행 JSON은 build/ 아래에 남겨 저장소에 커밋하지 않는다. 이전 O2 h264bsd 및 sustained navigation 기준은 [에뮬레이터 성능 기준](../../Codex-AARE-integration/EMULATOR_PERFORMANCE.md)에 있다.
