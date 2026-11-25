# GD13MY Windows CE 순정 오디오·후방카메라 통합 조사

- 대상: GD13MY.KOR.SOP.00.061, Windows CE 6.0. 웹 자료 + 공개 소스만 검토, 실물 오디오 계측 **없음**.
- 원칙: **순정 내비 음성, 전화 및 후방카메라 우선권을 보존**. Android/Linux의 AudioFocus를 Windows CE에 그대로 도입하지 않는다.

## 1. Windows CE 오디오에 대한 공식 근거와 함정

**WinCE waveOut은 여러 스트림의 software mixing을 지원하는 구현 경로를 제공**한다. Microsoft WinCE 문서의 `waveOutOpen` 설명에 하드웨어 믹서를 지원하는 드라이버 또는 소프트웨어 믹서로 라우팅한다고 명시되어 있다. 하지만 GD13MY 실제 `WaveDev`/SAF7730 드라이버가 어떤 믹서 모드로 작동하고 여러 프로그램의 독립적인 볼륨을 제공하는지는 **확인되지 않았다**.

- WinCE `waveOutOpen` 및 software mixing: https://learn.microsoft.com/en-us/previous-versions/windows/embedded/aa452455%28v%3Dmsdn.10%29
- WinCE `waveOutSetVolume`, capability probe `WAVECAPS_VOLUME`: https://learn.microsoft.com/en-us/previous-versions/windows/embedded/aa452464%28v%3Dmsdn.10%29
- WinCE `waveInOpen`: https://learn.microsoft.com/en-us/previous-versions/windows/embedded/aa452431%28v%3Dmsdn.10%29
- WinCE `waveOutProc()` / `WOM_DONE`: https://learn.microsoft.com/ko-kr/previous-versions/windows/embedded/aa452458%28v%3Dmsdn.10%29
- Microsoft WinCE 6.0 R3 특정 환경의 여러 스레드 WaveOut 호출이 반환되지 않는 이슈: https://support.microsoft.com/en-us/servicing/os/windows-embedded/2017/01/fix-some-waveform-audio-functions-may-not-be-returned-when-they-are-called-by-multiple-threads-at-th

**중요한 구분:** PC Windows DirectShow `WaveOut Renderer` 문서의 "mixing disabled"를 WinCE 일반 WaveOut에서 믹싱 불가라는 근거로 사용해서는 안 됨. https://learn.microsoft.com/en-us/windows/win32/directshow/audio-renderer--waveout--filter 는 특정 renderer 필터 및 데스크톱용 설명이다. Windows 7+ WASAPI 자동 ducking 문서도 WinCE에 적용되지 않는다.

## 2. 순정 펌웨어의 기존 증거와 함수

| 모듈 | 기존 근거 | 추가 검증 필요 |
|---|---|---|
| `LibSound.dll` | `lSoundGetSoundAuthority` / `lSoundSetSoundAuthority`, `lSoundGetNaviVolume`, `lSoundGetBTVolume` | 권한 반환값·볼륨 스코프 및 누가 소유하는지. OEM DLL 별도 인스턴스에서 공유된 상태인지 미확인 |
| `saf7730wav.dll`, `WaveDev` | ROM wave driver, wave input/output 관련 문자열 | 장치 번호, 지원 rate/channel, 믹싱/동시 캡처·재생 |
| `LibMMCodec.dll` | `waveOutOpen/Write/SetVolume`, `waveInOpen/Start` imports | OEM 미디어가 열어 놓는 장치 ID 및 실제 audio route |
| `GDDVoiceHandler.exe` | 음성/ASR 관련 리소스 | OEM 음성인식과 AA 마이크가 서로 충돌하는지 |
| `LibVideo.dll` + `LibSystem.dll` | 후방 상태 및 video authority (`lVideoGetRearViewStatus`, `lVideoSetVideoAuthority`, `lSystemGetRearViewState`) | 영상 전환/후진과 음성 우선순위 연동. DLL 독립 로드의 상태 공유 여부 미확인 |
| `uComH_New.exe`, MICOM | 버튼/MIM1/MIM2·`MIM_IOControl` 단서 | SWC 버튼 이벤트와 OEM 앱 메시지 매핑, 직접 CAN 패킷 해석 선행 금지 |

GD13MY 분석 근거: https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/VIDEO_AUDIO_ANALYSIS.md , https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/HARDWARE.md

## 3. 현재 코드가 지원하는 것과 지원하지 않는 것

`src/ce/ce_wave.c`는 `pcm_format`, `waveOutOpen`, `waveOutPrepareHeader`, `waveOutWrite`, `waveOutReset`, `waveInOpen`, `waveInPrepareHeader`, `waveInStart`, `waveInAddBuffer`, `waveInReset` 등의 **PCM 입출력 helper**를 이미 구현했다. 이를 새로 만들지 말 것.

반면, `src/ce/ce_aa_tls.c:discover()`는 `I30_NATIVE_VIDEO` 경로에서 영상 채널만 광고하며, `src/ce/ce_aa_projection.c:i30_projection_video()`는 `AUDIO_FOCUS_REQUEST`에 순정 오디오 소유를 유지하는 응답을 보낸다. 현재 코드에 **AA 오디오/마이크 채널과 WaveOut/WaveIn를 연결한 증거는 없다.** 오디오 통합은 '테스트 누락'이 아니라 **별도 설계가 필요한 향후 기능**이다.

소스: https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_wave.c , https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_projection.c , https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_tls.c

## 4. 구현 전 검증 매트릭스

| 시나리오 | 관측 항목 | 안전한 기대 행동 |
|---|---|---|
| OEM 음악만 | WaveOut 장치, 채널, 출력 볼륨·드라이버 로그 | 순정과 동일 |
| OEM 음악 + 순정 안내 | 실제 mixed PCM/볼륨/음성 명료도 | 안내 전달·음악 감소 정책 확인(현재 지원 추정 금지) |
| AA 음악 + OEM 안내(향후 기능) | audio focus request, OEM `SoundAuthority`, 각 소스 PCM amplitude | OEM 안내 가리지 않음; AA 음악만 단계적으로 감소시키기 |
| BT HFP 통화 진입/종료 | WaveIn 열기 실패/독점, `BTVolume`/권한 상태, PCM 복구 | AA 마이크 점유 중단, 통화 우선, 종료 후 장치 복구 |
| 후진/카메라 켜짐 | OEM display owner, 영상 중지 지연, 오디오 안내 | 즉시 OEM 후방 표시, 투사 화면 소유권 양보 |
| 핸들 버튼 | MICOM→OEM 메시지/WM_KEY* 추적 | 기존 차량 버튼 동작 유지, 미매핑 이벤트 폐기 |
| 30–120분 재연결 반복 | wave buffer 상태, thread, handles, Working Set | 음성 끊김 및 buffer 누수 없음 |

### 안전한 구현 원칙

1. 실제 순정 오디오 권한 계약을 알아내기 전 `lSoundSetSoundAuthority`를 무작정 호출하지 않는다. 정상 AV/BT/음성 경로가 끊어질 수 있다.
2. 마이크 동시 캡처 허용 여부와 `waveInOpen` 오류 코드를 확인하기 전 순정 ASR/BT 캡처를 강제로 닫지 않는다.
3. 시스템 전역 `waveOutSetVolume`으로 음악만 duck하려고 하지 않는다. 장치 전체(안내/경고음 포함)가 작아질 수 있다.
4. DirectSound는 존재·드라이버 지원 확인 후 검토, 초기 확인은 이미 지원되는 WaveOut/WaveIn 기반으로 진행한다.
5. 역방향 차량 신호를 직접 추측하지 말고 OEM `LibSystem.dll` 화면 상태/메시지 연결부터 검증한다.

## 5. 외부 비디오/음성 정책 사례와 이식 제한

- Open Headunit `1f23aa48848590e8ad456423ce980df2cbc58015`: Android 플랫폼의 마이크 포맷 광고(16 kHz mono), 캡처 rate 변환, 명시적 응답 및 uplink logging 수정. **원칙만 참고**, Android AudioRecord는 WinCE에 불가. https://github.com/andreknieriem/open-headunit/commit/1f23aa48848590e8ad456423ce980df2cbc58015
- Open Headunit 설정 설명에서 다른 소스와의 audio focus 충돌을 안내하나 Android 오디오 정책이다. https://headunit.andrerinas.com/guides/settings/
- NXP 계열 자동차 오디오 DSP는 별도 navigation beep/voice 삽입 및 mute 회로가 가능하다는 공개 문서가 있다. **이는 SAF7730/GD13MY에 그러한 하드웨어 경로가 있다는 증거가 아니다.** https://www.nxp.com/docs/en/application-note/AN02106.pdf

## 6. 발견 없음 / 미확인

- 공개 소스에서 GD13MY `LibSound.dll` `lSound*Authority`와 호환되는 호출 계약·구체 반환값을 **발견하지 못함**.
- SAF7730 오디오 라우팅의 GD13MY 전용 공개 드라이버 소스, 순정 음악/안내 ducking 정책, 스티어링휠 버튼 구체 MICOM 프로토콜 **미확인**.
- 물리 전화·후방카메라·경고음의 경쟁 상황은 안전한 오프차량 벤치에서만 검사. 차량 탑재 시 기능 손상 위험이 있어 미검증 기능 활성화 금지.
