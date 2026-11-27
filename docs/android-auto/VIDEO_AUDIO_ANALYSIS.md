# 영상·오디오·입력

| 기능 | 확인한 경로 | 남은 검증 |
|---|---|---|
| 화면과 합성 | 800×480 RGB565 로고. `default.hv`의 파일 `0x22402`에 `Displayddi.dll`. XIP `ddi.dll`의 `DisplayInit` RVA `0x38c0`, `HALInit` `0x1116c`. `LibMMCodec.dll`은 `DirectDrawCreate`를 import하고 VA `0x00117d08`, `0x00118e08`이 오버레이 초기화 결과 문자열을 참조한다. ROM에 EGL/GLES가 있다. | 물리 패널 해상도, 프레임버퍼 주소·stride, 쓸 수 있는 표면 및 소유권을 실측한다. |
| H.264 경로 | `LibMMCodec.dll` VA `0x00113680`은 `CreateFileW`를 호출하고 파일 `0x64c98`의 H.264 TS 파서 메시지를 참조한다. VA `0x00115648`에서 `CreateFileW`를 사용하며 파일 `0x65c94`의 `VID1:`을 참조한다. 이 라이브러리와 `GDDTDMB.exe` 모두 `DeviceIoControl` 및 DirectDraw import가 있다. | 현재 확인된 상위 앱 경로는 파일/TS 기반이다. Android Auto의 access unit 또는 Annex B 스트림을 직접 주입할 수 있는 공개 API, 버퍼 계약, 프로파일과 성능은 미확인이다. |
| 디코더와 DSP | ROM 저장 오프셋 `0x11bb867`에서 `videodev.dll`을 복원했다. `VID_IOControl` RVA `0x9cd0`. 디코더 메모리 질의 및 초기화 문자열은 VA `0x1000858c`, `0x100094a4`에서 참조한다. VA `0x1000ac08`은 파일 `0x4510`의 `DSP1:`을 참조하며 `CreateFileW`를 호출한다. `dsp_bridge.dll`에 `DSP_IOControl` RVA `0x255ba4`. TI IVA/DSP에 대한 유력한 제품 펌웨어 경로다. | 실제 클럭·프로파일·레벨·지연과 하드웨어에서 처리되는 범위를 측정한다. `LibMMCodec.dll`의 H.264 미지원 메시지 파일 `0x5f662`는 이번 실행에서 참조를 해석하지 못했다. |
| 카메라 | `LibVideo.dll` VA `0x00103bb4`가 `ShowCameraInput` 및 후방 상태 로그(파일 `0x7480`, `0x78c0`)를 참조하고 `CreateFileW`, `DeviceIoControl`, `PostMessageW`를 호출한다. XIP `camera.dll`의 `CAM_IOControl` RVA `0x2774`. | OEM 표면의 우선 점유와 후진 이벤트에서 화면 준비까지 기준 시간을 측정한다. 프로젝션을 실행하거나 중단해도 카메라 지연과 프레임 유실이 늘지 않아야 한다. |
| 오디오 출력과 믹서 | `default.hv` 파일 `0x2b840`의 `WaveDev`와 `0x2b95e`의 SAF7730 드라이버. XIP의 `WAV_Open` RVA `0x5344`, `WAV_IOControl` `0x5918`, PCM 검사와 Audio Mixer 메시지(ROM `0xc66823`, `0xc6751b`). `LibMMCodec.dll`에 `waveOutOpen/Write/SetVolume`, `LibSound.dll`에 순정 내비 음량 `lSoundGetNaviVolume` RVA `0x123c`. | 다중 스트림 동시 재생, 음악/안내 덕킹, 음소거, 통화와 경고음 우선순위. |
| 마이크 입력 | SAF7730 드라이버의 Audio Input 문자열(ROM `0xc668db`). APP `LibMMCodec.dll`과 `GDDTDMB.exe`에 `waveInOpen/Start` import. 순정 `GDDVoiceHandler.exe`와 ASR 리소스는 존재하며 음성 프로세스가 MICOM 쪽 메시지를 보내는 로그 참조는 VA `0x00011150` 일대에 있다. | 물리 마이크 경로, 지원하는 PCM 포맷, ASR·통화와 동시 사용 및 해제 후 복구. |
| 터치 | `default.hv` 파일 `0x112d2`에 `digen_touch.dll`. ROM 모듈 `TouchPanelEnable` RVA `0x3204`, `TouchPanelSetCalibration` `0x186c`. `uComH_New.exe` VA `0x0002154c`에 좌표 로그 참조(파일 `0x2e8b0`). | CE에서 정상적인 창 포커스·입력 수신 경로 및 보정된 좌표. |
| 버튼/차량 인터페이스 | `uComH_New.exe` 파일 `0x2aaa8`에 `MIM1:`. `default.hv` 파일 `0x2b2b6`, `0x2b58e`에 MIM2/MIM1 항목. XIP `omap2430_micommgr_cdp.dll`의 `MIM_IOControl` RVA `0x3af0`와 read/write export 확인. | 사용자 버튼 매핑 및 물리 전송 계층, CAN 직접 접근 가능성은 미확인이다. 차량 입력은 벤치에서 OEM 상태를 관찰해 확인한다. |

800×480을 계산용으로 적용하면 YUV420 한 면에 576,000 B, RGBA 한 면에 1,536,000 B가 든다. YUV 3장과 RGBA 2장만으로 약 4.58 MiB이며 코덱 상태, 참조 프레임, USB, TLS 및 OEM UI 메모리는 별도다. 기기의 실제 메모리 한도는 [벤치 기준](../archive/PHASE2_IMPLEMENTATION_PLAN.md)으로 검증한다.

순정 `.061`의 `lVideoGetRearViewStatus`는 `LibVideo.dll` VA `0x1013fc`에서 라이브러리 상태 `0x10b110 + 0x18`을 읽는다. `GDdmedia.exe`와 `LibSystem.dll`은 `lVideoSetRearviewStatus`와 `lVideoShowRearView`를 가져온다. `GDdmedia.exe`는 `lVideoSetVideoAuthority`도 사용한다. 투사 감독기가 후진 상태를 받으려면 이 순정 상태를 관리하는 쪽에서 전달해야 한다. 별도 CE 프로세스가 DLL을 자체 로드해 읽은 값이 순정 프로세스의 상태를 공유하는지는 확인되지 않았다.

`LibSystem.dll`의 VA `0x101efc`에서 MICOM 후방 상태 로그를 참조하고 `0x101f20`에서 상태를 객체의 `+0x30`에 기록한다. 값 2일 때 후방 상태 설정과 표시 호출을 연달아 실행한다. 순정 `lSystemGetRearViewState`(VA `0x101290`)는 같은 객체 필드를 반환한다. `LibSystem.dll`과 `LibVideo.dll`의 PE `.data` 섹션에는 공유 속성이 없다. USB 드라이버의 새 DLL 인스턴스에서 getter를 호출해 순정 MICOM 상태를 얻는 방법은 근거가 부족하다. 현 ARM 통합 시험은 화면 소유권 전환 시 그리기를 중단하는 동작을 검증하며, 순정 MICOM 상태 전달은 별도 확인 대상이다.

순정 `LibSound.dll`의 `lSoundGetSoundAuthority`와 `lSoundSetSoundAuthority`는 오디오 권한 분석 지점이다. `lSoundGetBTVolume`의 존재는 Bluetooth 볼륨 경로의 근거이며, 음악 재생 중인지 또는 통화 중인지 나타내는 계약은 별도로 확인해야 한다. 활성 Bluetooth 음악과 통화·우선 경고음이 투사 오디오를 선점하는 정책을 CE 감독기에 추가했다. 여기에서 순정 내비와 투사의 우선순위는 화면 소유권에 적용하며 CE의 스케줄러 우선순위를 사용하지 않는다.

[ROM 인터페이스와 문자열](../research/evidence/phase1-rom.json) · [OEM import/문자열](../research/evidence/phase1-scan.json) · [검증한 함수 참조](../research/evidence/phase1-xrefs.tsv)
