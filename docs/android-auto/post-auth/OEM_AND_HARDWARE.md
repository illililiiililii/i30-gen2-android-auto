# 순정 기능과 차량 벤치 시험

## 순정 오디오·마이크 경로

REA로 `.061` `LibSound.dll`의 `lSoundGetSoundAuthority`, `lSoundSetSoundAuthority`, 내비·Bluetooth 음량 조회와 음소거 제어 export를 확인했다. `LibMMCodec.dll`의 PCM import는 ROM ordinal로 `waveOutOpen` 399, `waveOutWrite` 387, `waveInOpen` 413, `waveInStart` 407임을 확인했다. GNU ARM objdump에서 권한 설정·조회는 각각 VA `0x1015d8`과 `0x101600`을 호출하고, PE의 공유 속성이 없는 `.data` 객체 `0x104060`의 `+8` 슬롯을 사용했다. setter는 `0..34` 값을 받고 다른 값에 `-1`을 반환한다. 이 함수만으로는 프로세스 간 오디오 권한 획득이나 경고음·통화·ASR 전환을 제공한다는 근거가 없다. 기존 `ce_wave.c`에는 포맷 조회 및 소유권이 주어진 경우의 버퍼 준비·종료가 있다. [순정 오디오 분석](../VIDEO_AUDIO_ANALYSIS.md) · [CE Wave 어댑터](../../src/ce/ce_wave.c) · [REA LibSound](../../build/codex-post-auth-integration/libsounds-exports.json) · [REA LibMMCodec](../../build/codex-post-auth-integration/libmmcodec-imports.json) · [권한 함수 ARM 원문](../../build/codex-post-auth-integration/libsound-authority-callees.txt)

기존 Python 호스트 회귀는 모의 PCM 믹싱, 우선권, 마이크 채널과 블록 전달을 검증한다. ARM/WinCE 순정 투사 경로는 영상과 입력 서비스를 광고하고 오디오 포커스 요청에 순정 소스 유지로 응답한다. 현재 에뮬레이터는 McBSP 레지스터를 제공하며 오디오 DSP와 마이크 PCM 백엔드는 구현돼 있지 않다. WinCE의 실제 PCM 재생, 음악 덕킹, 순정 마이크 전달, Bluetooth 통화 충돌은 미검증이다. [호스트 통합 시험](../../tests/test_gd13my_projection.py) · [에뮬레이터 오디오 범위](../EMULATOR_ARCHITECTURE.md) · [WinCE 포커스 처리](../../src/ce/ce_aa_projection.c)

격리 WinCE의 `--lcd-bench --audio-query`에서 순정 `COREDLL`에 `WAVE_FORMAT_QUERY`를 호출했다. 48 kHz 16-bit 스테레오 출력과 16 kHz 16-bit 모노 입력 모두 반환 값 `0`이었다. 포맷 질의 이후 가상 USB의 상호 TLS와 LCD 프레임도 확인했다. 이 시험은 포맷 질의까지이며 PCM 스트림을 열거나 샘플을 재생·채집하지 않는다. [포맷 질의 결과](../../build/codex-post-auth-integration/wave-query/virtual-phone.json) · [순정 API UART](../../build/codex-post-auth-integration/wave-query/virtual-phone.serial.log)

추가 Web-ChatGPT 인계의 `waveOutGetDevCaps`/`waveInGetDevCaps` 제안을 격리 시험에 반영했다. 출력 장치 2개와 입력 장치 1개가 열거됐다. 각 장치 0의 조회 결과는 `0`이며 순정 구조체에 각각 `Audio Output`과 `Audio Input`이 기록됐다. 두 포맷 질의도 모두 반환 값 `0`을 유지했다. 앱별 믹싱과 덕킹을 시험하려면 OEM 장치 소유권을 먼저 확인해야 한다. 실폰 마이크 검증에서는 광고 포맷, WaveIn 포맷, 블록 크기 및 PCM 타임스탬프를 대응시킨다. [순정 Wave 장치·포맷 결과](../../build/codex-post-auth-integration/wave-caps/virtual-phone.json) · [순정 오디오 외부 근거](../chatGPT-search/Web-chatGPT/WINCE_OEM_AUDIO_INTEGRATION.md)

## OEM 표시·물리 버튼·시동

기존 `LibSystem`의 후진 비트와 `LibVideo`의 후방 표시 이벤트가 순정 표시 권한을 제어한다. 투사 창과 USB 렌더러는 같은 이벤트와 순정 지도 바로 위의 Z-order를 확인한다. 투사 입력도 이 표시 권한을 확인하고, 접촉 중 권한이 사라지면 기존 접촉을 종료한다. 가상 MICOM의 SYS `0x95`는 순정 이벤트 처리 경로를 시험할 수 있다. 실제 카메라 입력과 합성 지연은 차량 벤치에서 측정한다. [순정 표시 통합](../CE_NATIVE_DISPLAY_INTEGRATION.md) · [MICOM 에뮬레이터](../../tools/gd13my_mmio.py)

순정 NAVIMENU와 내비 음량 이벤트의 기존 가상 MICOM 경로를 유지했다. 이전·다음 곡, 음소거, 음성·통화·MODE 및 스티어링 휠 버튼의 차종별 입력 계약은 미확인이다. 알 수 없는 키는 AAP에서 광고하지 않는다. HWND 기반 상위 팝업과 OSD 보호는 기존 창 순서와 GDI 클립에 의존한다. 같은 HWND에서 합성하는 공조·볼륨 OSD와 경고창을 포함한 상세 조합은 남아 있다. [OEM 영상 및 버튼 분석](../VIDEO_AUDIO_ANALYSIS.md)

기존 ARM 부팅 패치와 설정 시험은 자동 시작 플래그 유무, 중복 실행 방지, 설정 저장·제거, 취소 경로를 검증한다. 실제 시동·절전·배터리 전환과 기동 시 이미 연결된 폰의 처리 순서, Bluetooth 활성 상태에서의 복귀는 차량 벤치 항목이다. [자동 시작 패치 검증](../../build/codex-post-auth-integration/startup-arm.json) · [기존 자동 시작 시험](../PHASE7_8_RESULTS.md)

## 영상 DSP 가능성

Web-ChatGPT의 TI SDK 조사에서 제시한 장치 경계를 실제 `.061` PE에서 대조했다. REA export 원장에 `videodev.dll`의 `VID_IOControl` VA `0x10009cd0`과 `dsp_bridge.dll`의 `DSP_IOControl` VA `0x10255ba4`가 있다. `videodev.dll`은 `CreateFileW`와 `DeviceIoControl`을 import하고 UTF-16 `DSP1:`을 파일 오프셋 `0x4510`에 포함한다. `LibMMCodec.dll`은 두 API를 import하고 `VID1:`을 `0x65c94`에 포함한다. 기존 역공학의 장치 경로와 일치한다. Android Auto의 Annex B 입력을 받는 OEM IOCTL 계약, DSP 서버의 H.264 프로파일 지원과 자원 중재는 여전히 확인이 필요하다. 하드웨어 가속의 적용 판정은 이 증거를 확보할 때까지 보류한다. [펌웨어 영상 분석](../VIDEO_AUDIO_ANALYSIS.md) · [TI SDK 후속 연구](../chatGPT-search/Web-chatGPT/GD13MY_DSP_ACCELERATION_RESEARCH.md) · [REA 영상 드라이버](../../build/codex-post-auth-integration/videodev.dll.rea.json) · [REA DSP 드라이버](../../build/codex-post-auth-integration/dsp_bridge.dll.rea.json)

GNU ARM objdump로 `videodev.dll`의 `ProcessDecodeRsp: Unsupported H.264 Profile` 참조를 확인했다. VA `0x10009c10`에서 응답 값과 `0x76d`를 비교하고, 일치하면 `0x10009c18`에서 이 문자열을 읽은 뒤 `0x80004001`을 반환한다. 응답 값과 실제 프로파일의 매핑은 남아 있다. [ARM 분기 원본](../../build/codex-post-auth-integration/dsp-profile-disassembly.txt)

## 실폰과 차량 벤치 절차

1. 권한이 확보된 개발 신원, 동일 시험폰, USB 데이터 케이블과 UART·ADB를 준비한다. 먼저 정지된 에뮬레이터 환경에서 AOA, AAP 버전, TLS Finished, `AUTH_COMPLETE`를 각각 확인한다. 화면·입력 시험은 성공한 인증 세션으로 진행한다. [등록과 실폰 시험](../Codex-authentication-resolution/REAL_PHONE_TEST_RESULTS.md)
2. 차량 벤치 전에는 내비 모델·보드·펌웨어 식별자, 승인된 시험 이미지와 원본 복구 매체, 안정적인 전원 및 끊을 수 있는 USB 경로를 확보한다. 실제 펌웨어 적용은 별도 승인을 받은 뒤 진행한다. [복구 및 벤치 조건](../PHASE6_BRICK_RISK_ASSESSMENT.md)
3. 투사를 끈 기준 상태의 후방카메라 준비 지연, 경고·팝업, 스피커, 순정 마이크·Bluetooth, 스티어링 휠 이벤트 및 시동 복귀를 기록한다. 투사를 켠 동일 시나리오에서 우선 표시와 음원·장치 반환 시간을 비교한다. 영상 처리량과 메모리는 해당 OMAP에서 별도로 기록한다.
4. 후방 표시가 가려지거나 순정 경고·통화가 끊기거나 화면이 멈추면 USB를 분리해 투사 세션을 해제한다. 순정 화면과 후방 표시를 확인하고, 계속 이상하면 시험을 중단하고 승인된 복구 절차를 사용한다. 후진과 시동 관련 시나리오는 주행 없이 벤치에서 수행한다.
