# 하드웨어 가속 연구 인계

## 이번 작업

- 실제 stock GDdNavi 지도 boot와 동일한 DiskA state/input으로 software WGL 비교를 2회씩 실행했다. 로그/재현 명령 및 제한 사항은 [실지도 벤치마크](REAL_MAP_BENCHMARK.md), 요약 통계는 [성능 결과](PERFORMANCE_RESULTS.md)에 있다.
- 기존 DLL을 쓰는 GPTimer baseline과 C native GPTimer read를 비교하는 선택 경로를 추가했다. native 카운터는 기존 32.768 kHz Python 기준 모델과 8개 clock 지점에서 일치시켰다. 전체 실행 guest clock throughput 중앙값은 약 7.7% 높았지만 지도 구간 처리량은 +1% 미만이며 표본 변동이 커 실질적인 지도 체감 개선으로 확정하지 않았다. 기본 DLL과 timer 모델은 변경하지 않았다.
- `LcdDisplay.capture()`에서 Unicorn이 반환한 detached `bytearray`를 `bytes()`로 다시 복사하던 동작을 제거했다. 실제 지도 전체 실행 개선은 오차/환경 변동과 분리해 입증하지 못했다. 기존 LCD RGB565 변환과 snapshot 보존은 유지했다.
- WGL 실제 지도 GPU 경로는 readback/copy가 GDI보다 느렸다. software renderer 기본값을 보존했다. AARE decoder는 h264bsd로 유지했고 DSP ABI는 아직 확인되지 않았다.
- `python -m unittest discover -s tests -v`: 92개 통과 (2026-11-27, 새 C timer DLL 사용). viewer USB-clock 회귀도 수정 후 통과.

## 확인되지 않은 범위와 다음 우선순위

1. 지도 stationary, mock drive, pan, zoom, rotate, route, menu transition, 1/3/5 minute sustain을 동일 조건으로 benchmark한다. 이번 touch set은 startup accept + map pan only; route guidance와 physical vehicle input은 미측정이다.
2. `LibMMCodec.dll` 및 `VID1:`/`DSP1:` IOCTL 인자 구조와 버퍼 계약은 정적 자료만으로 입증되지 않았다. 추가 분석은 [DSP IOCTL 상태](DSP_IOCTL_ABI.md)에 적는다.
3. AARE USB/TLS/AAP 수신·h264bsd/GDI 경로를 보존한다. DSP ABI가 확인되기 전에는 실순정 decoder 호출을 추가하지 않는다.
4. 실기기 기준 측정이 확보되면 CPU/GPU/DSP/DMA/스토리지/USB/LCD를 비교한다. ±5% 목표는 실측 근거가 없어 미검증이다.
5. 실제 펌웨어 빌드 전 별도 브릭 안전 검토가 필요하다. [브릭 예방 메모](BRICK_PREVENTION_NOTES.md)를 확인한다.

## 재현/검증

```powershell
$env:PYTHONPATH = 'tools'
python tools/bench_gd13my_gl.py --frames 10 --warmup 2 --output build/hardware-acceleration/host-gl-benchmark.json
$env:GD13MY_GL_BACKEND = 'hardware'   # WGL PoC 사용
$env:GD13MY_GL_BACKEND = 'software'   # 기존 렌더러
```

실지도 벤치 명령은 [REAL_MAP_BENCHMARK.md](REAL_MAP_BENCHMARK.md)에, GPU readback 결과는 [GPU_READBACK_OPTIMIZATION.md](GPU_READBACK_OPTIMIZATION.md)에 있다. USB 스마트폰 실물, AARE 실시간 수신, 차량 실기기는 이번 세션에서 검증하지 않았다. 호스트 가속은 끌 수 있으며 순정 펌웨어/BSP/실차 저장장치에는 어떤 기록도 하지 않았다.
