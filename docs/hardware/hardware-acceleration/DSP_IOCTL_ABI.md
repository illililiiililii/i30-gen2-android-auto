# VID1/DSP1 IOCTL ABI 상태

## 확인한 호출 증거

- `LibMMCodec.dll`에는 `VID1:`, `IOCTL_VDEV_VID_DECINIT`, `IOCTL_VDEV_VID_DECODE`, `IOCTL_VDEV_VID_DEC_DEINIT`, `IOCTL_VDEV_IMG_QUERYINFO` 문자열이 있다. 해당 모듈은 `CreateFileW`, `DeviceIoControl`, `DirectDrawCreate`를 import한다.
- ROM `videodev.dll`은 `VID_IOControl` export와 `DSP1:` 문자열을 가진다. `dsp_bridge.dll`에는 `DSP_IOControl` export가 있다.
- 기존 연구 xref는 `docs/Free-model-research/hardware-acceleration/STOCK_DSP_VIDEO_PIPELINE.md`에 있다.

## 미확인 계약

바이너리 문자열/xref만으로 실제 `DeviceIoControl` 연결과 호출 인자, IOCTL 숫자, 입력·출력 구조체 크기/오프셋, 포인터 깊이, handle 수명, 출력 buffer owner를 증명하지 못했다. H.264 bitstream framing, SPS/PPS 설정, completion event/IRQ, DMA 주소 의미, DSP firmware load 경로, 실패 status, init/deinit sequence도 미확인이다. 따라서 순정 드라이버 호출이나 AARE host decoder bridge는 구현하지 않았다.

실기기 없는 동안 추가 정적 분석은 각 DLL의 dispatcher와 DeviceIoControl 호출자 하나씩을 따라가며 해당 call site의 상수/길이/버퍼 준비를 확인한다. 함수명이나 문자열로 ABI 지원을 추정하지 않는다. 실제 ioctl 재현·WinCE 진단기는 구조체와 반환 계약이 충분히 입증된 뒤 작성한다.
