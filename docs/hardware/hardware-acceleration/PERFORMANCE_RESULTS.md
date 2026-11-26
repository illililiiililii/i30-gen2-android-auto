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

## GDdNavi 실지도 및 계측 변경 (2026-11-27 KST)

같은 GD13MY kernel/media/App volume, 복사한 DiskA SQLite 시작 상태, `map-pan-input.json` 5개 터치 이벤트로 stock map viewer를 headless 실행했다. 지도 준비까지 포함한 실제 GDdNavi 작업이다. 재현 스크립트와 경로는 [실지도 벤치마크](REAL_MAP_BENCHMARK.md)에 기록했다.

| 경로 | 2회 전체 guest clock 단위/s 중앙값 | 지도 준비 후 guest s/wall s 중앙값 | 지도 준비 이후 LCD 변경 프레임 | CPU% 중앙값 | Peak WS 중앙값 |
|---|---:|---:|---:|---:|---:|
| 기존 Python GPTimer MMIO | 23.58M | 3.702 | 3 | 92.9% | 461.7 MiB |
| native C GPTimer read | 25.39M | 3.737* | 3 | 92.5% | 465.3 MiB |

`*` 지도 구간 지표의 두 표본은 4.365와 3.109로 분산이 커 유의한 개선으로 판정하지 않는다. 전체 guest clock 처리량의 표본 중앙값은 약 +7.7%지만 각 조건 2회뿐이고 CPU 부하가 90%대이며 호스트 scheduler 변동이 나타났다. 지도 준비 후 화면 변경 프레임은 양쪽 모두 대개 3회였고 이 입력은 회전/확대/경로 안내 장면이 아니다. 따라서 체감 지도 FPS 향상은 확인되지 않았고 이 기능을 기본 DLL에 포함하거나 성능 성공으로 선언하지 않는다. C read path는 ABI가 맞는 새 DLL에만 노출되는 선택 기능이다.

다른 반복 측정에서 `LcdDisplay.capture()` 입력이 이미 detached `bytearray`임을 확인하고 매 LCD poll마다 `bytes()`로 중복 복사하던 그래픽 plane과 video backdrop 변환을 제거했다. 기존 bitmap/LCD 결과 형식과 게스트 RAM snapshot 소유권은 바뀌지 않는다. 동등한 화면 결과 및 회귀는 확인했으나, 실지도 전체 런 median에서 독립된 유의 성능 이득은 입증되지 않았다. 초당 LCD poll 성능 및 캡처 구간 지표는 [GPU/readback 기록](GPU_READBACK_OPTIMIZATION.md)을 참조한다.

기존 실제 map GPU/GDI 결과는 WGL GPU가 0.2495s/5 copy 대 GDI 0.0298s/5 copy로 약 8.4배 오래 걸렸고, CPU/working set도 증가했다. 실제 scene에선 GPU를 기본값으로 올리지 않았다.

## AARE 자동 시작 변경 (2026-11-27 KST)

이번 변경은 지도/영상의 실행 경로와 자동 전환을 연결한 기능 변경이다. USB 자동 실행은 AOA 버전 응답 후 임시 USB 등록을 정리하고 지도 프로세스의 표준 입력 훅을 깨워 native receiver를 시작한다. 부팅 대기 helper는 500ms마다 제한적으로 WM_MOUSEMOVE를 게시하며 지도 창이 준비되면 종료한다. 자동 시작 함수는 같은 NAVI 프로세스의 표시된 800×480 map window를 탐색한다. 투사 창은 첫 영상이 준비될 때까지 숨겨 두고, 정상 frame 출력 후 화면을 전환한다. v8 가상폰 실행에서 지도 ACK, 자동 receiver, TLS 1.2, 서비스 탐색 및 `i30 CE projection frame presented.`를 확인했다. 분리/재연결의 색상 출력 감지는 검증을 완료하지 못했다. 이 변경의 FPS 또는 실제 스마트폰 지연 개선은 측정되지 않았다.

설정 메뉴는 `USB 연결 시 AARE 자동 실행`과 `부팅 후 AARE 연결 대기`를 독립된 `i30auto.opt`/`i30boot.opt` 파일로 저장한다. 둘 다 켜지면 uComH의 USB 서비스와 지도 프로세스의 USB receiver가 중복 등록되지 않도록 uComH 시작을 건너뛴다. 정상 `i30usb.dll`/TLS/h264bsd 경로와 수동 투사 메뉴는 유지된다. 이 기능을 GPU/DSP 가속이나 실기 성능 향상으로 해석하지 않는다.

자동 시작 이미지와 헤드리스 시험은 `build/gd13my-aa-autostart-v8/`에 생성한다. AARE TLS 신원은 실폰용 이미지에만 보관하고 가상폰 시험은 일회성 임시 인증서를 사용한다. 순정 실기, USB 권한 대화상자, 실제 Android AARE 화면 전환, 분리/재연결 및 장시간 지도 안정성은 실폰/실기 측정이 필요하다. 기존 map 실측 값(+0.9% median, 표본 변동 큼)은 이번 변경에서도 개선으로 재분류하지 않는다.
