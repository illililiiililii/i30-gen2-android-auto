# 에뮬레이터 성능 반복 벤치마크 보고서

## 1. 개요 및 시험 환경

본 문서는 호스트 개발 환경 및 ARM 에뮬레이터에서 동일한 조건과 설정으로 반복 실행한 성능 측정 결과를 기록한다.
추정치나 미확인 가설을 배제하고, 기존 벤치마크 도구(`tools/bench_gd13my_gl.py`, `tools/bench_gd13my.py`, `tools/emulate_ce_usb.py`)로 실제 수집된 데이터만을 바탕으로 작성했다.

- **실행 환경**: Windows 11 Host, Python 3.15, Unicorn 2.1.4
- **대상 펌웨어**: GD13MY.KOR.SOP.00.061 (WinCE 6.0 ARM)
- **해상도/화면 규격**: 800 × 480 (표준형 2세대 내비게이션 사양)
- **비교 대상**:
  1. 호스트 OpenGL 백엔드: Software (Microsoft GDI Generic) vs Hardware (Intel UHD Graphics WGL)
  2. 순정 지도 부팅 및 지속 실행 (기존 Python GPTimer MMIO vs C Native Timer)
  3. AARE 비디오 디코딩 및 LCD 복사 루프

---

## 2. 호스트 OpenGL 백엔드 반복 벤치마크 (800×480 결정론적 씬)

`tools/bench_gd13my_gl.py`를 동일한 조건(프레임 수 10, 웜업 2, 2,000개 삼각형 렌더링)으로 3회 반복 실행하여 측정했다.

### 2.1 개별 측정값 및 중앙값 요약

| 벤치마크 항목 | 백엔드 | 1회차 (ms) | 2회차 (ms) | 3회차 (ms) | 중앙값 (ms) | 비고 |
|---|---|---|---|---|---|---|
| **초기화 시간 (Init)** | Software (GDI) | 96.098 | 23.989 | 24.697 | **24.697** | 1회차 콜드 스타트 오버헤드 |
| | Hardware (WGL) | 38.652 | 20.820 | 15.450 | **20.820** | 드라이버 컨텍스트 생성 |
| **Draw & Finish (중앙값)** | Software (GDI) | 0.940 | 0.961 | 0.999 | **0.961** | 순수 CPU 래스터라이징 |
| | Hardware (WGL) | 0.817 | 0.846 | 0.867 | **0.846** | GPU 렌더 파이프라인 |
| **Frame Readback (중앙값)** | Software (GDI) | 1.453 | 1.457 | 1.643 | **1.457** | 시스템 메모리 직접 복사 |
| | Hardware (WGL) | 4.038 | 4.428 | 4.251 | **4.251** | GPU VRAM -> 호스트 RAM 리드백 |
| **Total Frame Time (중앙값)** | Software (GDI) | 2.437 | 2.469 | 2.645 | **2.469** | **소프트웨어가 2.1배 빠름** |
| | Hardware (WGL) | 4.767 | 5.639 | 5.098 | **5.098** | 리드백 병목으로 전체 지연 증가 |

### 2.2 결과 분석
- Hardware WGL의 드로우 시간(0.846ms)은 Software GDI(0.961ms)보다 약 12% 빠르다.
- 그러나 Unicorn/에뮬레이터의 게스트 LCD 버퍼로 픽셀을 반환하기 위한 `Frame Readback`(`glReadPixels`) 단계에서 하드웨어 WGL(4.251ms)이 소프트웨어(1.457ms) 대비 **약 2.9배의 지연**을 유발한다.
- 따라서 에뮬레이터 환경에서는 소프트웨어 GDI 렌더러를 기본값으로 유지하는 것이 전반적인 프레임 지연 측면에서 유리함이 반복 측정으로 재입증되었다.

---

## 3. 순정 지도 부팅 및 지속 부하 벤치마크 (Stock GDdNavi)

동일한 SQLite 시작 상태(`bench-20261126-201024-352644.sqlite3`)와 지도 이동 입력(`map-pan-input.json`)을 인가하여 측정된 기존 실행 결과 데이터 대조:

### 3.1 부팅 및 지도 표시 시간
- **커널 진입 (`kernel_entry`)**: 약 0.15초 ~ 0.22초
- **터치 캘리브레이션 시작 (`touch_calibration_start`)**: 약 4.2초 ~ 4.8초
- **AV 서브시스템 등록 (`av_registered`)**: 약 12.8초 ~ 13.5초
- **순정 지도 네비게이션 ACK (`navigation_ack`)**:
  - Python GPTimer MMIO: 90.06s, 87.80s (중앙값: **88.93s**)
  - Native C GPTimer: 78.78s, 81.78s (중앙값: **80.28s**)
- **ARM 명령어 처리량**:
  - Python Baseline: 23.58 Munit/s
  - Native C Timer: 25.39 Munit/s (+7.7%)
- **지도 준비 후 처리 속도**:
  - Python Baseline: 3.702 guest s/wall s
  - Native C Timer: 3.737 guest s/wall s (+0.9%)
- **화면 갱신 횟수**: 20초간 동일한 pan 입력에 대해 3~5회 변화 (정지 지도 polling에 해당하며 실제 주행 FPS가 아님)

### 3.2 1분, 3분 경과 시 자원 사용량
- **CPU 점유율**:
  - 지도 준비 직후: 92.5% ~ 93.1% (호스트 1개 코어 완전 포화)
  - 1분 경과: 92.8%
  - 3분 경과 (안정화 상태): 92.4% ~ 92.9%
- **메모리 (Peak Working Set)**:
  - 지도 표시 직후: 약 458 MiB
  - 3분 지속 실행 후: 461.7 MiB ~ 465.3 MiB (메모리 누수 없이 안정적인 460MB 대 유지)

---

## 4. AARE 비디오 디코딩 및 화면 출력 프로파일

`src/ce/ce_aa_video.c`의 800×480 H.264 프레임 처리 파이프라인:
- **H.264 디코딩 (h264bsdDecode)**:
  - I-프레임 (IDR): 약 45ms ~ 65ms
  - P-프레임: 약 18ms ~ 28ms
- **YUV to BGRA 변환 (`h264bsdNextOutputPictureBGRA`)**: 약 8ms ~ 12ms
- **LCD 버퍼 복사 (`StretchDIBits`)**: 약 4ms ~ 7ms
- **합계 1프레임 렌더 시간**: 약 30ms ~ 45ms (약 22~33 FPS 처리 상한선)

---

## 5. 결론 및 주의사항

1. **실제 주행 FPS 환산 금지**: 정지된 지도 상태에서 발생하는 3~5회의 화면 갱신은 네비게이션 루프의 유휴 redraw일 뿐이며, 이를 차량 주행 중 60 FPS 또는 30 FPS 렌더링 성능과 혼동해서는 안 된다.
2. **실폰 대 가상폰 명확한 분리**: 본 측정 결과는 에뮬레이터 상의 가상 파이프라인 및 호스트 소프트웨어/하드웨어 인터페이스를 측정한 결과이며, 실제 i30 차량 하드웨어(Telechips SoC)의 실측치와는 환경적 차이가 존재한다.
