# Android Auto 인증 이후 호환성: 실수정 사례 중심

- 조사 기준: 2026-11-25. 실제 코드 및 GitHub 커밋 대조. **실폰 연결·빌드·실기기 재시험 없음**.
- 목적: 인증 이후 **통신/영상/입력/음성** 결함을 구분하고 이미 구현된 GD13MY 기능 중복 개발을 방지.
- 프로젝트: https://github.com/illililiiililii/i30-gen2-android-auto

## 1. 확인된 수정 사례

| 증상/원인 | 프로젝트·커밋 | 변경 함수·파일 | GD13MY 적용 |
|---|---|---|---|
| TLS와 채널 개통 이후 검은 화면: 타임스탬프 없는 SPS/PPS를 폐기 | OpenAuto Prodigy **`579152ba4644424627b1b1f2cad81456d568eea9`** | `src/core/aa/VideoService.cpp`의 `VideoService::onAVMediaIndication()`에서 `videoFrameData(...)`로 전달 | **높음:** `ce_aa_projection.c:paint_packet()`의 `CODEC=1` 패킷 처리 및 `ce_aa_video.c:i30_video_push()` 경로를 실제 SPS/PPS/IDR fixture로 확인 |
| H.264 start code를 이중으로 붙여 파서 손상 | Prodigy 디버깅 노트, 같은 수정 세션. 관련 특정 파일/커밋은 별도 검증 필요 | `VideoDecoder::processData()` / FFmpeg `av_parser_parse2()` | **높음:** AA 입력은 Annex-B start code를 이미 포함할 수 있음. h264bsd 입력 앞에 추가 프리픽스를 삽입하지 않도록 바이트 비교 |
| 영상 프레임 조각 손실을 정상 데이터처럼 처리, 복구 시 키프레임 대기 | Open Headunit **`a3990e4c5b2b57a653218fe9f1aec5ce157b6ae5`** | `AapVideo`, `AapReadMultipleMessages`, `AapReadSingleMessage`, `FragmentedMessageAudit`, `CodecConfigScanner`, `KeyframeCycleEscalationPolicy` | **높음:** GD13MY의 AAP 첫 fragment 선언 총길이 검증과 중간 fragment 손실 시 디코더 reset/ACK 정책 확인. Android MediaCodec 코드는 이식 불가 |
| TLS 제어 전용 레코드의 빈 plaintext/빈 LAST 조각 때문에 세션 메시지 유실 | Open Headunit **`ae83901e36ebad1765049202efcf001262566bde`** | `AapMessageIncoming`, `AapReadMultipleMessages`, `AapSslContext`, `AapTransport` | **높음:** GD13MY `secure_read_fragment()`가 `!decoded`를 오류로 처리하는 경계, 0-byte TLS 처리 및 LAST 조각 회귀 fixture 추가 가치 |
| 버전 교환 중 USB bulk 조각·병합이 깨져 TLS 시작 오인 | Open Headunit **`67bcae278418d75528b882567877f0e6ed4aa2ba`** | `HandshakeFrameReader`, `AapVersionNegotiation`, `AapSslContext`, `AapTransport` | **중간:** GD13MY `aa_wire.c:i30_aa_negotiate_version()` 및 `ce_aa_tls.c:receive_record()`가 경계 분할을 이미 다루는지 **새로 구현하지 말고 fixture 확인** |
| 2026년 이후 일부 버전 응답의 non-zero 상태를 무조건 오류로 취급 | Open Headunit **`06d7d33c9db10dff76d1ac669085dd42a0f569d2`** | `AapVersionNegotiation`, `AapTransport` | **중간:** 현재 GD13MY는 버전 상태 0만 수락하는 경로. 스마트폰 실측 non-zero 응답이 나온 때에만 정확한 상태 의미를 확인 후 분기 검토 |
| 입력 화면 실제 크기 vs 협상 해상도 불일치 | Open Headunit **`808a5581dd74c8605c7f37432726697216eb287c`** | `TouchCoordinateMapper`, `AapProjectionActivity` | **높음:** 렌더링 viewport, letterbox, 실제 터치 범위, AA 협상 `touch_screen_config`를 분리. Qt/Android View 좌표계는 직접 재사용 불가 |
| 마이크 요청 응답 및 캡처 데이터의 형식 불일치 | Open Headunit **`1f23aa48848590e8ad456423ce980df2cbc58015`** | `MicrophoneResponse`, `MicCaptureFormat`, `MicChunkAccumulator`, `MicPcmDecimator`, `MicUplinkMonitor`, `ServiceDiscoveryResponse` | **향후 오디오 단계:** WinCE WaveIn 장치 포맷과 실제 광고 PCM 포맷, 응답/버퍼 단위 일치성 확인. Android AudioRecord/AudioTrack 이식 불가 |
| 손상/중단 연결 이후 USB 세션 복구 | Open Headunit **`649566854379ff8dec2ca8c0fa4b5b553448c7fd`** | `UsbPlugInPolicy`, `UsbLauncherManager`, `UsbAttachedActivity` 등 | **제한적:** Android USB attach UI/권한 로직은 WinCE에 해당 없음. 재연결 이벤트, 세션 ID 및 자원 회수의 **행동 시나리오만 참조** |

### 원본 커밋

- https://github.com/mrmees/openauto-prodigy/commit/579152ba4644424627b1b1f2cad81456d568eea9
- https://github.com/mrmees/openauto-prodigy/blob/main/docs/how-to/debugging-notes.md
- https://github.com/andreknieriem/open-headunit/commit/a3990e4c5b2b57a653218fe9f1aec5ce157b6ae5
- https://github.com/andreknieriem/open-headunit/commit/ae83901e36ebad1765049202efcf001262566bde
- https://github.com/andreknieriem/open-headunit/commit/67bcae278418d75528b882567877f0e6ed4aa2ba
- https://github.com/andreknieriem/open-headunit/commit/06d7d33c9db10dff76d1ac669085dd42a0f569d2
- https://github.com/andreknieriem/open-headunit/commit/808a5581dd74c8605c7f37432726697216eb287c
- https://github.com/andreknieriem/open-headunit/commit/1f23aa48848590e8ad456423ce980df2cbc58015
- https://github.com/andreknieriem/open-headunit/commit/649566854379ff8dec2ca8c0fa4b5b553448c7fd

## 2. 프로토콜 특이점과 직접 관측 사례

- OpenAuto Prodigy 관측상 `AV_MEDIA_INDICATION (0x0001)`에 4-byte Annex-B start code의 SPS(0x67)/PPS(0x68)가 오고, 이후 `AV_MEDIA_WITH_TIMESTAMP_INDICATION (0x0000)`에 8-byte timestamp+IDR(0x65)가 온다. 핸드셰이크 성공 ≠ 디코딩 가능. 출처: https://github.com/mrmees/openauto-prodigy/blob/main/docs/how-to/debugging-notes.md
- `open-android-auto` 현장 문서: 휴대폰의 `AVChannelSetupRequest.config_index`가 광고 배열 index와 별개 ID일 수 있고, `touch_screen_config`는 물리 패널이 아닌 **협상한 비디오 콘텐츠 좌표**에 맞춰야 한다는 구현 경험. **이 정보는 특정 사용자/구현의 관측이며 모든 AA 버전에 보장되지 않음.** 출처: https://github.com/mrmees/open-android-auto/blob/main/docs/field-notes.md
- Open Headunit #696에서는 HEVC가 지원되지 않는 PX5에서 오디오만 나오고 영상이 없는 증상이 H.264 선택으로 개선됨. GD13MY은 h264bsd Baseline만 있으므로 H.264만 광고하는 현재 결정 유지. https://github.com/andreknieriem/open-headunit/issues/696
- OpenAuto Prodigy의 별도 기록에는 핸드셰이크 이후에도 폰이 사용자 승인 대기 상태에서 영상 전송을 시작하지 않는 사례가 있다. 이 사례는 코드 수정으로 해결되었다는 검증은 확인하지 못함. https://github.com/mrmees/open-android-auto/blob/main/docs/troubleshooting.md
- 다른 Raspberry Pi 구현은 `PING` 미응답으로 TCP 연결이 끊겨 검은 화면에 도달했고, video config_index 응답도 함께 변경되어 **단일 변경의 효과는 분리 불가**. GD13MY의 `PING/PONG` 회귀 시험은 유효하지만 이미 `ce_aa_projection.c`에 응답 로직 존재. https://github.com/ngocthang2710/Android-Auto-for-Pi4-Android-16/blob/main/docs/wireless-android-auto.md

## 3. 현재 GD13MY 코드가 실제로 하는 것: 중복 개발 방지

- `src/ce/ce_aa_tls.c:discover()`는 TLS 이후 `AUTH_COMPLETE`(`AuthResponse` status 0)를 송신하고 암호화된 `SERVICE_DISCOVERY_REQUEST`를 수신한다. `I30_NATIVE_VIDEO`이고 표시 surface를 확보한 경우에만 **영상 채널 하나**를 광고한다. 오디오·마이크·입력 센서 채널 광고는 현재 없음. 이 기능을 "전체 Android Auto 완성"으로 오해하면 안 된다.
- `src/ce/ce_aa_projection.c:i30_projection_video()`는 `PING`에 대응하고 영상 채널 열기/설정/시작/중지/FOCUS, 수신 영상 프레임에 대한 ACK를 처리한다. 오디오 포커스는 `AUDIO_FOCUS_REQUEST`에 대해 순정 오디오 소유 응답을 내며 **AA 오디오 처리는 하지 않는다**.
- `src/ce/ce_aa_video.c:i30_video_push()`는 h264bsd Baseline 디코드만 수행한다. profile_idc 66 이외는 현재 거부. DSP 가속/화면 터치 프로토콜 전달은 이 경로에 없음.
- `src/ce/ce_aa_tls.c:secure_read()`는 control/video fragment 재조립, FIRST 총길이 검사와 버퍼 제한 검사 구현. 누락됐다고 가정해 재구현하지 말 것.
- `src/ce/ce_wave.c`는 PCM WaveOut/WaveIn 질의 및 버퍼 준비·쓰기·읽기·정리 유틸리티를 제공하나 **AA 오디오 채널에 연결됐다는 근거는 없음**.

소스:
- https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_tls.c
- https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_projection.c
- https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_aa_video.c
- https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/src/ce/ce_wave.c

## 4. 인증 직후 체크포인트와 진단 분기

| 종료 지점 | 필요한 분리 증거 | 다음 행동 |
|---|---|---|
| TLS 완료, AUTH 실패 | `AUTH_COMPLETE` 송신 바이트/폰 상태 | wire trace 및 응답 확인, 인증 연구는 별도 트랙 |
| AUTH 완료, Discovery 실패 | 암호화 프레임 / service discovery 응답 길이 / 폰 요청 | 광고 필드 및 version/schema fixture 비교. 기존 `discover()` 재사용 |
| Discovery 성공, 영상 open 없음 | `CHANNEL_OPEN`, AAP ping, video config | 광고된 채널 ID/config/dpi와 실제 폰 요구값 비교 |
| Video start 성공, 화면 검정 | SPS/PPS, Annex-B, IDR, focus, decoder 결과와 paint | **codec config / frame data / present** 3개의 별도 수치 기록 |
| 첫 프레임만 출력 | ACK session 일치, fragment 총길이, P-frame/IDR 및 focus | `paint_packet()` ACK 정책과 프레임 타이밍 비교 |
| 재연결 시 화면/오디오 불능 | USB pipe closed, WaveOut reset, decoder buffers, 세션 소유권 | 기존 close/cleanup 진단, 누수 계측 |
| 장시간 불안정 | ARM/CE 작업집합, heap, fragment 큐, FPS, 30/60/120분 | 단순 누수 신고 대신 단계별 재현 로그 |

## 5. Linux/Android 전용 주의

- Android MediaCodec, Android AudioTrack/AudioFocus, evdev/Wayland, libusb 권한 UI, OMX/V4L2/VAAPI/DRM zero-copy, FFmpeg 스레딩은 WinCE 6.0에서 동일 API 없음.
- Open Headunit의 복구 **원칙**(fragment 총길이, IDR 대기, 단일 상태 소유권, 유효 PCM 프레임)은 재사용 가치 있음. 구현을 그대로 복사하지 말 것.
- LIVI는 https://github.com/f-io/LIVI , OpenAuto는 https://github.com/f1xpl/openauto , AASDK는 https://github.com/f1xpl/aasdk . 이번 조사에서 이들 프로젝트의 **확정된 최신 WinCE 이식 해결 커밋**은 새로 발견하지 못함.

## 6. 미검증 사항

- 실제 GD13MY 실폰의 서비스 탐색·영상 ACK, 터치 및 오디오 동작은 **미검증**.
- AA 17.x 모든 기기의 config_index, DPI, SPS/PPS 순서가 위 사례와 동일한지 불명.
- 장시간 메모리 누수는 개별 사례에 적용되는 특정 수정 원인을 이번 조사에서 확정하지 못함.
