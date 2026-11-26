# 하드웨어 가속 연구 인계

## 이번 작업

- `npx skills add aicodeking/leanrea -g -a codex -y`로 Codex 사용자 LeanREA 설치. 사용자 경로는 `%USERPROFILE%\.agents\skills\leanrea`다. CLI 명령은 없고 일반 PE 분석 도구를 안내하는 분석 skill이다. Rizin 0.9.1과 기존 PE/ROM evidence를 우선 활용했다.
- 순정 GLES 호출 53개에 대한 기존 HLE 경로는 있었지만 `BitmapGL`이 `Microsoft / GDI Generic / OpenGL 1.1`을 선택하는 것을 직접 확인했다.
- `tools/gd13my_software_gl.py`에 숨겨진 WGL 창 기반 GPU 컨텍스트를 추가했다. 기존 GDI bitmap 경로도 유지한다. `GD13MY_GL_BACKEND=hardware`로 선택하고, 기본값 `software`로 안정 경로를 보존한다. 에뮬레이터 로그와 `map_report`에 실제 renderer를 남긴다.
- `tools/bench_gd13my_gl.py`로 실제 WGL GPU와 GDI renderer를 비교했다. 이 scene에서는 GPU가 총 frame time을 줄이지 않아 기본값으로 승격하지 않았다.
- DSP ABI가 증명되지 않아 AARE decoder는 바꾸지 않았다. 하드웨어/영상 연구 문서 8개를 이 폴더에 정리했다.

## 미완료 / 다음 우선순위

1. 실제 GDdNavi 지도 route 입력을 GPU/GDI로 반복해 `guest_swaps`, frame hash tolerance, map copy time, 전체 boot CPU를 같은 DiskA state에서 비교한다.
2. `LibMMCodec.dll` H.264 create/open/decode/deinit 호출의 IOCTL 상수, 포인터 크기와 구조체를 좁히고 `videodev.dll` dispatcher 및 DSP bridge까지 call chain을 기록한다. 함수 전체 디컴파일 대신 문자열 xref와 각 호출 함수만 분석한다.
3. 공개 ROM의 `videodev.dll`/`dsp_bridge.dll` 및 BSP registry의 메모리/IRQ/펌웨어 항목을 현재 추출 자료에서 다시 대조한다. 보드 SoC SKU, GPU/DSP 클럭은 미확인으로 유지한다.
4. 실기기 기준 측정이 확보되면 CPU/GPU/DSP/DMA/스토리지/USB/LCD를 각각 비교한다. 실기기 데이터 전에는 ±5% 달성을 주장하지 않는다.

## 재현/검증

```powershell
$env:PYTHONPATH = 'tools'
python tools/bench_gd13my_gl.py --frames 10 --warmup 2 --output build/hardware-acceleration/host-gl-benchmark.json
$env:GD13MY_GL_BACKEND = 'hardware'   # WGL PoC 사용
$env:GD13MY_GL_BACKEND = 'software'   # 기존 렌더러
```

다음 검증: Python compile, GL PoC pixel/frame 시험, `python -m unittest discover -s tests`. 기존 실폰 USB 에뮬레이터/뷰어는 이 세션에서도 이미 실행 중이었으므로 종료하지 않는다. 작업 트리 변경은 커밋되지 않았으며 원격 main에 반영하지 않았다.
