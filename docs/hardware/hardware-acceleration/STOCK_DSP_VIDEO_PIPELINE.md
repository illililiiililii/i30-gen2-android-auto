# 순정 DSP 영상 파이프라인

## 바이너리 근거

- APP `002c98d9_LibMMCodec.dll`의 `phase1-xrefs.tsv`에서 H.264 TS parser 문자열은 `FUN_00113680` (`0x00113680`), `VID1:` 문자열은 `FUN_00115648` (`0x00115648`), `appInit: Cannot open VideoDev` 문자열은 `FUN_001028c0` (`0x001028c0`)에서 참조된다. 이 DLL의 COREDLL import table은 `CreateFileW` ordinal 168 및 `DeviceIoControl` ordinal 179를 포함하고, DDRAW import에는 `DirectDrawCreate`가 있다.
- `LibMMCodec.dll`의 `.rdata`에는 `IOCTL_VDEV_VID_DECINIT`, `IOCTL_VDEV_VID_DECODE`, `IOCTL_VDEV_VID_DEC_DEINIT` 및 `IOCTL_VDEV_IMG_QUERYINFO` 등이 있다. 현재 자료는 동일 모듈 내 장치/API 사용과 문자열/xref를 보이며, `FUN_00115648`에서 그 IOCTL 중 하나를 실제 호출하는 전체 함수 흐름까지는 아직 증명하지 않는다. 따라서 정적 근거상 후보 파이프라인이다.
- ROM `videodev.dll`의 `VID_IOControl` export는 VA `0x10009cd0`. H.264 메모리 query 문자열은 `FUN_1000858c` (`0x1000858c`), init 문자열은 `FUN_100094a4` (`0x100094a4`)에서 참조되고, `DSP1:` 문자열은 `FUN_1000ac08` (`0x1000ac08`)에서 참조된다. `dsp_bridge.dll`은 `DSP_IOControl` export VA `0x10255ba4`를 갖는다. 기존 REA 결과와 바이너리 인벤토리는 `build/codex-post-auth-integration/videodev.dll.rea.json`, `dsp_bridge.dll.rea.json`에 기록돼 있다.
- `videodev.dll`의 H.264 프로파일 거부 분기에서 응답 `0x76d`와 문자열 `Unsupported H.264 Profile`을 확인했다. 실제 H.264 profile_idc로 매핑되는지는 확인되지 않았다.

## 결론

`VID1:`/`DSP1:`와 IOCTL 호출 경로가 존재하는 것은 확인됐다. 이 사실은 GD13MY가 AARE Annex B access unit을 DSP 디코더로 받을 수 있다는 뜻이 아니다. 이 펌웨어에서 DSP H.264 성공, profile/level 범위, DMA 공유 버퍼, 완료 IRQ 또는 동시에 동작하는 내비/DMB와의 점유 정책은 검증되지 않았다. IOCTL 구조를 모르는 상태에서 AARE 바이트를 직접 전달하는 실험은 하지 않았다.

현재 AARE 경로는 WinCE 내 `h264bsdDecode()` 후 BGRA 변환과 GDI 표시다. 실기 디코딩·GDI 시간은 실측하지 않았다. TI OMAP3530 DVSDK의 Baseline 디코더 자료는 가능성 참고이며 OEM 구현의 증거가 아니다. 상세 선행 자료: [DSP 조사](../../chatGPT-search/Web-ChatGPT/GD13MY_DSP_ACCELERATION_RESEARCH.md), [펌웨어 영상 분석](../../VIDEO_AUDIO_ANALYSIS.md), [호스트-게스트 AARE 차이](AARE_HARDWARE_DECODING.md).

현재까지 IOCTL 상수와 구조체 ABI의 검증된 값은 없다. 각 미확인 ABI 항목과 후속 정적 분석 경계는 [DSP IOCTL ABI 상태](DSP_IOCTL_ABI.md)에 분리 기록했다. 이번 성능 작업에서는 DSP 경로를 추측 구현하지 않았다.
