# GPU readback 및 화면 복사

기존 실제 GDdNavi GPU/GDI A/B에서는 동일한 5개 video-plane copy 중 GDI 경로 0.0298s, WGL GPU 경로 0.2495s였다(합계 약 8.4배 차이). GPU raster 구간만 빨라도 CPU가 `glReadPixels` 결과를 기다리고 RGB/LCD 데이터를 복사해야 하므로 전체 경로가 느려질 수 있다. GPU utilization counter는 유효한 표본을 내지 않았다. GPU를 기본 renderer로 승격하지 않았다.

`tools/gd13my_display.py`의 `LcdDisplay.capture()`는 `read_ram()`으로 guest memory를 detached `bytearray` snapshot으로 받는다. 기존에 이 snapshot을 즉시 `bytes()`로 변환해 800×480 source plane, 조건에 따라 video backdrop까지 추가 복사했다. 변환을 제거해 snapshot 자체를 보존하고 결과 형식 및 `scanout` 비교를 유지했다. RAM buffer는 다음 read 전에 이미 분리돼 있으므로 guest memory alias를 저장하지 않는다.

실제 software renderer 지도 부팅 후 LCD capture는 2,066 polls에서 capture 누계 3.48s(약 1.68ms/poll), 준비 후 579 polls/5 LCD changed frames였다. 동일 workload 전후의 안정된 반복 쌍은 확보되지 않아 전체 FPS나 벽시계 시간 개선으로 환산하지 않았다. 메모리 복사 감소는 구현 사실이며, 지각 가능한 개선은 아직 입증되지 않았다.

PBO/비동기 readback은 현재 렌더러의 동기식 CPU framebuffer 계약을 유지하면서 LCD와 guest memory를 함께 바꾸지 않고서는 유익한지 확인하기 어렵다. 화면 일부 변경 전송, RGB565 직접 출력, texture compositor도 dirty-region 및 readback 소유권 근거가 없다. 측정 없이 추가하지 않았다. 다음 비교는 capture poll 내부의 layout scan, color-key search, RGB565 conversion, Tk blit 시간을 분리해 동일 입력에서 실행해야 한다.

재현 스크립트 및 scene 범위는 [실지도 벤치마크](REAL_MAP_BENCHMARK.md), 고정 장면 수치는 [성능 결과](PERFORMANCE_RESULTS.md)를 참조한다.
