# Codex 후속 검증 작업 — 신규 외부 증거 기반, 중복 구현 금지

**최신 확인 기준:** 2026-11-25. 프로젝트 `main` 공개 코드 정적 검토 및 외부 기술 문서 연구. 이 문서는 **실행 결과가 아닌 작업 지시서**이다. 우선순위는 기능 착수의 검증 가치이며 실제 성공 가능성 점수가 아니다.

대상: https://github.com/illililiiililii/i30-gen2-android-auto

## 0. 작업 공통 규칙

- 시작 전 `main` 최신 버전과 기존 실험·회귀 테스트 목록 확인. 이미 존재하는 코드를 다시 만들지 않는다.
- 이 문서의 P0/P1/P2는 **검증·기록 우선순위**, 대규모 리팩터링 지시가 아니다.
- 필드 데이터는 `확인된 실제 관측`, `정적 추론`, `미검증 가설`로 분리하고 log path와 실패 재현 조건 저장.
- 필요한 도구(Serena/Code Review Graph, RTK, Ponytail, Caveman)는 설치·지원 여부 확인 후 사용 가능한 것만 활용. 강제 설치·대체 출력 포맷 요구 없음.
- 실제 기기와 자동차 기능 안전이 확인되기 전 펌웨어 플래시 및 OEM 드라이버 변경 금지. 조사 단계에서는 리포지토리 기존 소스 **수정 금지**.

## P0 — 인증 성공 직후 실제 문제를 구분하는 계측

### P0-1. Service Discovery 후 채널 광고 현실 검증

**근거:** `ce_aa_tls.c:discover()`는 native-video 경로의 video channel 하나만 광고하며, audio/mic/touch를 광고하지 않음.

- 현재 `docs/PROTOCOL_IMPLEMENTATION.md` 및 `src/ce/ce_aa_tls.c`를 읽어 실제 광고된 channel/config bytes, `AUTH_COMPLETE`/SERVICE_DISCOVERY/CHANNEL_OPEN/AV_SETUP/AV_START/FOCUS 순서 기록.
- 실제 스마트폰에서 전송되는 `ServiceDiscoveryRequest`, `AVChannelSetupRequest`의 config_index, profile, 해상도, 지원 채널을 **로깅**. 현재 schema와 다르다면 그 차이부터 보고.
- **수정 조건:** 스마트폰이 영상-only 서비스를 수용하지 않거나, 승인된 최소 기능 범위와 채널 광고가 불일치한다는 패킷 근거가 있을 때만 개선 설계.
- 성공 기준: AUTH 뒤 서비스 탐색 완료, 영상 채널 OPEN/SETUP/START/FOCUS와 첫 codec config 도달.

코드: https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_tls.c

### P0-2. 영상 4단계 분리 진단

**근거:** Prodigy 실제 수정 `579152b` — 무타임스탬프 SPS/PPS 폐기 시 디코더 검정 화면. OHU `a3990e4` — 조각 재조립/코덱 구성/IDR 대기 복구.

- `ce_aa_projection.c:paint_packet()`의 `CODEC`/`DATA` 경로, `ce_aa_video.c:i30_video_push()`의 반환값, `paint()` 실제 디스플레이 호출을 **각기 다른 단계로 기록**.
- 최초 10개 AAP 비디오 메시지에 대해 `message code`, fragment flags, declared total, NAL 유형(7=SPS,8=PPS,5=IDR,1=non-IDR), profile_idc, timestamp 유무/값, output frame, ACK session/응답 시간을 남기되 비밀키/민감 페이로드 기록 금지.
- 이미 구현된 AAP 재조립·하드웨어 표시를 **재개발하지 말고** 1바이트 split/first total mismatch/중간 손실/IDR 없이 시작하는 fixture를 보강.
- 성공 기준: SPS/PPS 수신→파서 수용→첫 IDR 디코드→화면 표시→ACK 일치; 재시작 시 hang 없음.

근거: https://github.com/mrmees/openauto-prodigy/commit/579152ba4644424627b1b1f2cad81456d568eea9 , https://github.com/andreknieriem/open-headunit/commit/a3990e4c5b2b57a653218fe9f1aec5ce157b6ae5

### P0-3. OEM 화면 소유·후방카메라 복귀, 동작 분리

- `ce_aa_projection.c:update_focus()/begin_paint()`, `LibVideo.dll` `lVideo*Authority`, `LibSystem.dll`의 rearview state. OEM 화면 1순위 원칙 확인.
- 벤치에서 순정 지도↔프로젝션 창↔후방 카메라 모의 이벤트 전환 후 첫 표시 지연, LCD 내용, touch 소유권, 복귀 여부 확인. 현재 가상폰 시험과 중복된 정상 경로는 제외하고 **동시 경합**을 겨냥.
- 실제 후진 기어 테스트/운행 중 실험 금지.

## P1 — 가속 및 TLS 경계

### P1-1. DSP 경로 존재/코덱 지원 정적 결정

**신규 근거:** TI 2011 WinCE DVSDK의 OMAP3530 H.264 BP 디코더, 2010 OMAP3530 코덱 성능표, DSPLink 자원 중재 제한.

1. `LibMMCodec.dll:CreateFileW("VID1:")`의 `DeviceIoControl` 호출들을 숫자 IOCTL, input/output 버퍼 구조체로 정리; `videodev.dll:VID_IOControl` → `DSP1:` 및 `dsp_bridge.dll:DSP_IOControl` 연결 여부 확인.
2. `"H264(H263) Codec is not support !"` 분기의 조건/실행 영역을 정적 교차 참조 분석하여 지원 불가가 **어떤 path**에 해당하는지 표기.
3. DSP binary/codec server의 이름/프로파일/메모리 할당 근거 확보. TI 원격 WinCE 예제의 `remote.cfg` / `all.x64P` 서버 형식은 **검색 힌트**로만 사용하며 OEM 포맷을 동일하다고 가정하지 말 것. 없으면 **DSP 연결 구현은 보류**.
4. `h264bsd`의 단계별 성능(디코드/YUV→BGRA/GDI 출력) 기준선 측정. 목표 800×480 30fps, 평균과 p95 latency, FPS, CPU, heap peak, 1시간 자원 안정성.
5. DSP 위임 가능성 입증 후에만 별도 격리 브랜치 설계. 실험 중 순정 미디어 동시 점유 허용 여부 확인.

원본: https://software-dl.ti.com/sdoemb/sdoemb_public_sw/wince_sdk/01_01_00/exports/dvsdk_wince_01_11_00_03_patch_01_release_notes.html ; https://software-dl.ti.com/dsps/dsps_public_sw/codecs/OMAP35xx/OMAP35xx_latest/H264_Decoder_OMAP3530_Datasheet_2_01_007.pdf

### P1-2. AAP/TLS 레코드 경계와 완료 상태 fixture

- `ce_aa_tls.c:secure_read_fragment()`의 `if (!decoded)` 분기가 **TLS 제어 전용 레코드**에서 정상적인 0-byte plaintext를 오류로 오인하는지 mock에서 확인. 실제 기록에 없는 문제를 단정하지 않는다.
- USB bulk 하나에 AAP 두 개 병합, 6B 헤더 split, TLS record split, 0-byte LAST continuation, 늦은 VersionResponse/이전 세션 envelope 경우. 기존 AA wire tests 재사용.
- 실제 BearSSL 상태 `BR_SSL_SENDAPP` 및 `CipherSuite`, 정상 `AUTH_COMPLETE` 송신 조건 확보. 단순 CCS 출력만으로 인증 성공 판정 금지.
- 실패에서만 최소 수정 제안. **BearSSL→Conscrypt 이식/교체 요구하지 말 것**.

참고: https://github.com/andreknieriem/open-headunit/commit/67bcae278418d75528b882567877f0e6ed4aa2ba , https://github.com/andreknieriem/open-headunit/commit/ae83901e36ebad1765049202efcf001262566bde

## P2 — 오디오·입력 신규 기능 도입 전 실험

### P2-1. WaveOut/WaveIn + OEM 권한 관측

- `ce_wave.c`의 포맷·buffer helper 존재 확인, WinCE Wave mixer 지원 드라이버 실제 능력 `waveOutGetDevCaps`, `WAVE_FORMAT_QUERY`로 조사.
- `LibSound.dll` `lSoundGet/SetSoundAuthority`, `lSoundGetNaviVolume`, `lSoundGetBTVolume`의 실제 인자와 **동일 프로세스 vs 타 프로세스 공유 state** 확인.
- 음악 + OEM 음성 안내 + BT 통화 동시 시 각 단의 실제 route/duck/mic ownership 추적. 테스트 전역 볼륨 변경·ASR 강제 종료 금지.
- **현재 AA는 영상-only**이므로 오디오 지원은 증거를 확보한 후 별도 요구사항/아키텍처 결정 작업으로 분류.

### P2-2. 입력 채널·MICOM의 후속 조사

- `uComH_New.exe`/`MIM_IOControl` 이벤트, CE의 터치 화면 raw range 및 클리핑 viewport 기록. `touch_screen_config`와 800×480 비디오 좌표 맵의 관계 확인.
- **현재 AA 입력 채널 광고 없음**: 미구현 상태를 단순 버그로 분류하지 말고 입력 채널 설계 및 OEM 안전 정책을 먼저 검증.

원본: https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/VIDEO_AUDIO_ANALYSIS.md ; https://github.com/andreknieriem/open-headunit/commit/808a5581dd74c8605c7f37432726697216eb287c

## 3. 중복 개발 금지 표

| 이미 존재 | 확인할 것 / 아직 없는 부분 |
|---|---|
| BearSSL TLS1.2, RSA 신원, CA 검증, guest clock, TLS handshake logger | 실제 폰의 cipher/CertificateRequest 및 empty plaintext 경계 |
| 가상폰 AUTH_COMPLETE/Service Discovery, 영상 채널 | 실폰 영상-only 광고 수용 및 새로운 프로토콜 응답 |
| AAP fragment 재조립/길이 상한 | 비정상 split/coalescence/zero-plaintext 사례 테스트 |
| h264bsd Baseline 디코더, WinCE 800×480 paint, video ACK | 실제 AA SPS/PPS→IDR→frame/present/ACK 일치 |
| WinCE WaveOut/WaveIn helper | AA 오디오/마이크 서비스 광고·라우팅/권한은 미구현 |
| OEM 화면/터치 메뉴 및 표시 복귀 | 프로젝션 입력 AA 채널 자체 및 긴 경합/복귀 안정성 |
| USB 재연결/벤치 시험 | 실제 폰에서 불량 read/연결 반복 시 자원 누수 없는지 |

## 4. Codex 보고 형식

매 항목마다 다음 형식을 유지한다:

```
과제 ID / 현재 repo commit:
기존 구현 확인 파일·함수:
신규 외부 근거와 원본 URL:
실험 환경(가상폰/순정 에뮬레이터/오프차량 실기기/실폰):
시험 입력 및 캡처:
PASS/FAIL/NOT_RUN (NOT_RUN이면 이유):
관측 수치·로그 원본 경로:
재현 단계:
판정(확인/추론/미검증) 및 다음 분기:
소스 수정 여부: 없음(연구 단계)
```

**발견 없음 명시:** 정확한 OEM IOCTL 공개 원본 없음, GD13MY DSP 800×480/30fps 실측 없음, OEM SAF7730 오디오 권한 API 계약 없음, GD13MY/실폰 post-auth 호환성 실제 수신 로그 없음. 이 항목은 추가 근거가 나올 때까지 완료로 표시하지 않는다.
