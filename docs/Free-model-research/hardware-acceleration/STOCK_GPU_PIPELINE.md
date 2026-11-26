# 순정 지도 GPU 파이프라인

## 확인한 경로

1. `.061` `ddi.dll` 초기화가 DSS/DISPC에 설정을 기록한다. 순정 앱 시작 추적은 `DisplayInit`, `DrvEnableDriver`와 DSS 레지스터 쓰기를 확인했다.
2. 순정 `GDdNavi.exe`는 EGL/GLES 엔트리를 사용한다. 현재 에뮬레이터는 실행 파일의 53개 GLES import thunk를 가로채고 GLES 상태·정점/텍스처 배열을 Win32 OpenGL로 전달한다.
3. 지도 프레임은 호스트 OpenGL에서 렌더링된 뒤 `glReadPixels`로 RGB888을 회수하고, DISPC VID1 RGB565 버퍼에 복사한다. 순정 GFX 평면의 컬러 키 합성은 `LcdDisplay.capture_rgb()`에서 재현한다.
4. 순정 `srvkm.dll`은 SGX 초기화 대기 루프에서 관측됐다. 이 경로 및 SGX530 ID는 GPU 드라이버의 존재·초기화 근거지만, 실차 앱이 모든 지도를 SGX에서 그렸다는 성능 계측은 아니다.

## 에뮬레이터 범위

게스트의 GLES API 요청은 순정 앱에서 발생하므로 지도 코드를 대체 렌더러로 바꾼 것은 아니다. 다만 GPU 명령 버퍼, SGX 레지스터 시퀀스, SGX IRQ/DMA, 메모리 소유권은 가상화하지 않는다. 호스트 OpenGL 렌더링은 GLES API 수준의 HLE다. DSS RGB565 scanout은 별도 CPU 경로다.

기존 지도와 프레임 성능 측정, swap copy 최적화는 [에뮬레이터 성능 기록](../../Codex-AARE-integration/EMULATOR_PERFORMANCE.md)에 있다. 이번 추가 WGL 브리지와 성능 비교는 [호스트 가속 브리지](HOST_ACCELERATION_BRIDGE.md) 및 [측정 결과](PERFORMANCE_RESULTS.md)를 참고한다.
