# 호스트 OpenGL 가속 브리지

## 구현

`tools/gd13my_software_gl.py`의 기존 GDI bitmap OpenGL 컨텍스트는 Microsoft `GDI Generic` 소프트웨어 renderer를 사용했다. 이번 PoC는 숨겨진 Win32 window/DC에서 WGL 컨텍스트를 만들고, renderer/vendor/version을 질의한다. 순정 `GDdNavi.exe`의 기존 GLES import thunk가 동일 OpenGL 호출을 유지한다. 완성된 RGB 프레임만 기존 `glReadPixels` 경로로 회수해 게스트 DISPC VID1 메모리에 복사한다. UI 창을 보여 주거나 AARE USB/TLS/AAP를 호스트에서 실행하지 않는다.

실행 설정은 `GD13MY_GL_BACKEND=software|hardware|auto`다. 기본값은 `software`다. `hardware`는 GPU renderer가 식별되지 않으면 실패하며, `software`는 기존 DIB 렌더러를 강제한다. `auto`는 가능한 경우 GPU 컨텍스트를 택한다. 시험 예:

```powershell
$env:GD13MY_GL_BACKEND = 'hardware'
& $py tools/view_gd13my.py --software-gl-app firmware/extracted/GD13MY/APP/00d12869_GDdNavi.exe ...
```

비교 도구:

```powershell
$env:PYTHONPATH = 'tools'
python tools/bench_gd13my_gl.py --frames 10 --warmup 2 --output build/hardware-acceleration/gl.json
```

도구는 800×480 화면의 고정 2,000 삼각형 장면에 대해 렌더+finish와 RGB readback 시간을 따로 기록하고, 프레임 안정성·백엔드 간 픽셀 차이를 비교한다. 실행 기록은 [PERFORMANCE_RESULTS.md](PERFORMANCE_RESULTS.md) 및 git 무시 대상인 `build/hardware-acceleration/host-gl-benchmark.json`에 있다.

## Fidelity 및 경계

이것은 OpenGL API 수준의 HLE이며 SGX command processor, GPU 레지스터, DMA, MMU, IRQ, 리셋과 버퍼 소유권 모델은 아니다. 게스트 CPU가 GLES 함수를 호출하고 가상 장치 wrapper가 호스트 GL을 실행한다. `glReadPixels` readback 및 RGB888→RGB565 메모리 복사는 동기·CPU 복사 비용을 남긴다. 측정된 WGL 결과가 현시점 기본 renderer를 바꾸지 않을 만큼 이득이 없어서 기본 실행은 소프트웨어 경로를 보존한다.

현재 머신의 실측 renderer는 Intel UHD Graphics, OpenGL 4.6 (driver 30.0.101.2079). 다른 PC에서는 driver에 따라 자동 경로가 달라질 수 있다. `hardware` 결과를 실제 지도 탐색 시나리오로 확인하기 전에는 사용자의 기본 실행 설정으로 삼지 않는다.
