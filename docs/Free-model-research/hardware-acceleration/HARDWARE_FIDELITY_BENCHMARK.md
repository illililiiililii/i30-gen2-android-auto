# 하드웨어 충실도 및 성능 측정 기준

현재 headless stock map runner는 guest/host wall-clock, CPU time/percent, peak working set, process I/O, guest navigation-ready 시각, LCD capture/blit, renderer ID, guest swaps, video-plane copy 시간을 기록한다. GPTimer IRQ와 MMIO별 read/write 수도 결과에 포함된다. 실제 run JSON은 이미지 실험 경로에 보관한다.

현재 실지도 시험은 software map boot 및 시작 확인/pan 입력만 비교했다. run-to-run host scheduler 변동이 있으므로 두 번의 차이가 약 5%인 항목은 단정하지 않는다. 실제 frame output이 3~5회인 짧은 창을 차량용 연속 FPS로 해석하지 않는다. map zoom/rotation/route/menu, 1/3/5분 sustain, AARE live video, real USB phone, physical device는 검증되지 않았다.

실기기에서 수집할 값: 부팅 및 지도 진입 시간, 연속 화면 frame timestamp, CPU busy/frequency, RAM bandwidth/latency, H.264 input/output frames, USB sustained throughput, storage read latency, DMA transfer completion, LCD VSYNC 간격, touch-to-visible latency. 각 값에 측정 구간/주변 온도/전원/입력 trace를 함께 저장한다. 실측 전 에뮬레이터 시간을 제한해 맞춘 값은 hardware reproduction으로 보지 않는다.

## ±5% 상태

실기기 baseline이 없어 모든 ±5% 항목은 **미검증**이다. CPU guest units/s는 emulator workload throughput 관측값이지 실제 Cortex-A8 cycle rate 비교가 아니다. HLE timer frequency가 같아도 instruction latency, cache, DDR, GPU/DSP, DMA timing 동등성은 보장되지 않는다.
