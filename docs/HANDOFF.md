# 최신 인계 진입점

순정 지도 리소스 및 영상 경로 조사는 [A 기준 계측과 후속 분석 위치](testing/AARE_STOCK_RESOURCE_BASELINE.md)부터 확인한다. h264bsd의 UYVY 메모리 스테이징과 같은 프레임의 BGRA 폴백은 ARM 시험을 통과했다. 기본 CE 바이너리는 기존 P0 복구 이미지와 동일해 물리 USB 대기 뷰어는 현재 이미지로 유지한다. 새 폰용 AARE 1.6.0 APK와 이미지에 일치하는 인증서 세트는 로컬 `build/aare-tools` 및 `build/aare-tools/identity`에 있다.

1. [PROJECT_STATUS](PROJECT_STATUS.md)와 [NEXT_TASKS](NEXT_TASKS.md)를 읽는다.
2. 현재 git status 및 최신 커밋을 확인한다. v8 실폰 시험은 `f004f6f` 소스와 기존 v8 이미지를 사용했다. [실폰 재연결 시험](testing/AARE_PHYSICAL_USB_RECOVERY.md)
3. P0 시험 이미지는 `build/p0-usb-repro/recovery-build/gd13my-aa-autostart-p0.img`다. 별도 DiskA 상태 파일을 사용한다. 재시동 후 기존 AOA 장치의 버전 요청이 타임아웃되면 지도 상태에서 폰 케이블을 물리적으로 다시 연결한다. [실행 명령과 인증 절차](android-auto/aare/FINAL_HANDOFF.md)
4. 성능·DSP·GPU 작업: [가속 인계](hardware/hardware-acceleration/FINAL_HANDOFF.md).
5. 새 환경의 로컬 입력과 과거 재현 명령: [기존 세션 인계](archive/SESSION_HANDOFF.md). 상태 설명은 역사적 기록이다.
6. 후속 기술 조사 및 시험 산출물 (2026-11-27):
   - 작업 A: [순정 DSP 인터페이스 증거](hardware/hardware-acceleration/DSP_INTERFACE_EVIDENCE.md)
   - 작업 B: [AARE 영상 처리 파이프라인 인벤토리](android-auto/aare/VIDEO_PIPELINE_INVENTORY.md)
   - 작업 C: [에뮬레이터 성능 반복 벤치마크](testing/EMULATOR_REPEATED_BENCHMARK.md)
   - 작업 D: [티맵 분할 화면 증거 자료](android-auto/aare/TMAP_DISPLAY_EVIDENCE.md)
   - 작업 E: [AARE 자동 실행 검증 보고서](testing/AARE_AUTOSTART_VALIDATION.md)
   - 작업 F: [AARE H.264 디코더 최적화 결과](android-auto/aare/H264_OPTIMIZATION_RESULTS.md): 내부 함수 프로파일, codegen 비교, opt-in fast-copy. 기본 배포 경로는 그대로 BGRA/ARMv4T이며 NEON과 Cortex-A8은 실험용이다.

원본 로그와 빌드 이미지는 로컬에 있을 수 있다. 원격에서 존재를 가정하지 않는다. 기존 실행 세션을 확인하고 필요한 경우에만 재부팅한다. 완료 후 최신 시험 이미지를 사용자에게 제공할 때 실폰 연결 가능한 상태와 실행 모드를 명시한다.
