# AARE와 순정 DSP 디코딩

AARE는 WinCE 게스트 USB/TLS/AAP 수신 후 게스트 소프트웨어 h264bsd 디코더를 쓴다. CPU/GDI 비용은 에뮬레이션에서 이미 계측됐지만 OMAP 실기 수치는 없다. 순정 `LibMMCodec.dll`의 `VID1:`/`IOCTL_VDEV_*` 경로와 `videodev.dll`/`DSP1:`의 연결은 확인했지만 외부 AARE 스트림이 같은 입력 ABI를 만족한다는 근거가 없다.

따라서 이번 변경은 AARE decoder를 건드리지 않았고 호스트 Media Foundation, DXVA, D3D11 Video decoder를 AARE 수신기처럼 쓰도록 연결하지 않았다. 그런 대체는 게스트의 순정 장치 인터페이스를 우회하게 된다. 실기 DSP ABI가 밝혀지기 전까지 h264bsd는 유지한다.

2026-11-27에는 영상 디코더를 바꾸지 않고 자동 연결/표시 handoff를 지도 프로세스에 연결했다. 자동 모드에서 AAP 미디어 채널이 준비되면 `i30usb.dll`의 기존 h264bsd→BGRA→`StretchDIBits` 경로가 첫 프레임을 숨겨 둔 투사 창에 렌더할 수 있도록 named event를 사용한다. 첫 프레임 출력 완료가 `I30_AA_VIDEO_ACTIVE`로 전달되면 지도 UI가 창을 표시하고, USB 재연결/인증 실패/후방 카메라 우선 상태에서는 자동 창을 숨긴다. 첫 프레임 hidden-window GDI 동작은 새 native-auto 가상폰 회귀에서 확인 중이며, 실폰 지연과 FPS 개선은 아직 미측정이다. 이 구현은 GPU/DSP decode 가속이 아니며 기존 h264bsd fallback이 그대로 사용된다.

진행 가능한 다음 단계:

1. 읽기 전용 정적 분석으로 `VID1:` 세션 open, `DeviceIoControl` 코드/입력/출력 길이, 메모리 query/init/decode/deinit 구조를 복원한다.
2. `videodev.dll`이 호출하는 `DSP1:` 함수와 DSP 서버 적재 파일, 완료 통지·오류/리셋 계약을 찾는다.
3. 실기에서 순정 플레이어로 안전한 baseline clip만 실행해 프로파일, 프레임 크기, 출력 plane과 DSP 동시 점유를 기록한다.
4. ABI가 맞으면 WinCE adapter와 h264bsd fallback을 병행하며 open/init/decode 실패 시 같은 프레임 경계에서 복귀한다.
5. USB 재연결/전원 전환 시 decoder 세션 teardown을 시험하고, 후진/순정 OSD 표시 우선권과 분리 계측한다.

실기기와 WinCE에서 측정한 처리량, 버퍼 소유권과 경쟁 동작이 확보되기 전에는 DSP 디코더를 활성화하지 않는다.
