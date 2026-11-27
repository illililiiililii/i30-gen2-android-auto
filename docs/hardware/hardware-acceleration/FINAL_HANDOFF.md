# 하드웨어 가속 연구 인계

## 이번 작업

- 실제 stock GDdNavi 지도 boot와 동일한 DiskA state/input으로 software WGL 비교를 2회씩 실행했다. 로그/재현 명령 및 제한 사항은 [실지도 벤치마크](REAL_MAP_BENCHMARK.md), 요약 통계는 [성능 결과](PERFORMANCE_RESULTS.md)에 있다.
- 기존 DLL을 쓰는 GPTimer baseline과 C native GPTimer read를 비교하는 선택 경로를 추가했다. native 카운터는 기존 32.768 kHz Python 기준 모델과 8개 clock 지점에서 일치시켰다. 전체 실행 guest clock throughput 중앙값은 약 7.7% 높았지만 지도 구간 처리량은 +1% 미만이며 표본 변동이 커 실질적인 지도 체감 개선으로 확정하지 않았다. 기본 DLL과 timer 모델은 변경하지 않았다.
- `LcdDisplay.capture()`에서 Unicorn이 반환한 detached `bytearray`를 `bytes()`로 다시 복사하던 동작을 제거했다. 실제 지도 전체 실행 개선은 오차/환경 변동과 분리해 입증하지 못했다. 기존 LCD RGB565 변환과 snapshot 보존은 유지했다.
- WGL 실제 지도 GPU 경로는 readback/copy가 GDI보다 느렸다. software renderer 기본값을 보존했다. AARE decoder는 h264bsd로 유지했고 DSP ABI는 아직 확인되지 않았다.
- `python -m unittest discover -s tests -q`: 93개 통과, 1개 skip (2026-11-27, 1ec0bb2 기준). 자동 실행 변경 이후 다시 실행했다.
- AARE 설정에 USB 연결 자동 실행/부팅 연결 대기 두 항목을 분리했다. 성공한 AOA 버전 응답 뒤 USB listener를 종료해 중복 점유를 피하고, bounded helper가 WM_MOUSEMOVE를 게시해 순정 입력 훅에서 자동 receiver를 시작한다. 같은 프로세스의 표시된 800×480 map window를 제한적으로 탐색한다. 정상 video-active 신호 후 화면을 전환한다.
- `tools/emulate_ce_usb.py`에서 두 설정의 독립 저장/해제, auto USB success handoff, WM_MOUSEMOVE/paint/timer hook, 기존 touch route를 ARM/API double로 실행했다. `tools/emulate_gd13my_startup.py`에서 boot-only/USB-only/두 옵션 동시 설정의 시작 소유권을 검증했다.
- v8 앱 볼륨은 `build/gd13my-aa-autostart-v8/gd13my-aa-autostart.img`, SHA-256은 `image.json`에 기록했다. 가상폰 native-auto 실행에서 순정 지도 ACK 이후 자동 receiver 시작, AOA, TLS 1.2 mutual authentication, 서비스 탐색 및 첫 영상 표시 로그를 확인했다. 이 가상 복제본만 두 자동 옵션을 켰고 AARE 시험 인증서를 포함한다. 분리/재연결 픽셀 검증과 물리 스마트폰은 미검증이다. 원본 펌웨어와 기존 실행 창은 수정하지 않았다.

## 확인되지 않은 범위와 다음 우선순위

1. 지도 stationary, mock drive, pan, zoom, rotate, route, menu transition, 1/3/5 minute sustain을 동일 조건으로 benchmark한다. 이번 touch set은 startup accept + map pan only; route guidance와 physical vehicle input은 미측정이다.
2. `LibMMCodec.dll` 및 `VID1:`/`DSP1:` IOCTL 인자 구조와 버퍼 계약은 정적 자료만으로 입증되지 않았다. 추가 분석은 [DSP IOCTL 상태](DSP_IOCTL_ABI.md)에 적는다.
3. AARE USB/TLS/AAP 수신·h264bsd/GDI 경로를 보존한다. DSP ABI가 확인되기 전에는 실순정 decoder 호출을 추가하지 않는다. 자동 첫 프레임 실행 로그는 `build/gd13my-aa-autostart-v8/native-auto-replug/`에 있다. 분리 후 색상 검증은 미완료다.
4. 실기기 기준 측정이 확보되면 CPU/GPU/DSP/DMA/스토리지/USB/LCD를 비교한다. ±5% 목표는 실측 근거가 없어 미검증이다.
5. 실제 펌웨어 빌드 전 별도 브릭 안전 검토가 필요하다. [브릭 예방 메모](BRICK_PREVENTION_NOTES.md)를 확인한다.

## 재현/검증

```powershell
$env:PYTHONPATH = 'tools'
python tools/bench_gd13my_gl.py --frames 10 --warmup 2 --output build/hardware-acceleration/host-gl-benchmark.json
$env:GD13MY_GL_BACKEND = 'hardware'   # WGL PoC 사용
$env:GD13MY_GL_BACKEND = 'software'   # 기존 렌더러
```

실지도 벤치 명령은 [REAL_MAP_BENCHMARK.md](REAL_MAP_BENCHMARK.md)에, GPU readback 결과는 [GPU_READBACK_OPTIMIZATION.md](GPU_READBACK_OPTIMIZATION.md)에 있다. WGL 성능을 기본값으로 올리지 않았고 ±5% 실기기 재현 목표는 미검증이다. 실폰 USB 승인/최초 수신기 지문 Trust는 사용자 동작이 필요하며 실제 스마트폰에서 자동 첫 프레임/분리/재연결은 별도 검증 대상이다. 호스트 가속은 끌 수 있으며 순정 펌웨어/BSP/실차 저장장치에는 어떤 기록도 하지 않았다.
