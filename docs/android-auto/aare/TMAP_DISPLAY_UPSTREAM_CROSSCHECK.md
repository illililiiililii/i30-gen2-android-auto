# 티맵 분할 화면: Upstream/구현 재대조 — 2026-11-28

## 1. 범위와 판정 규칙

이 문서는 기존 [증거 문서](TMAP_DISPLAY_EVIDENCE.md)와 [구현 결정 문서](TMAP_DISPLAY_IMPLEMENTATION.md)를 덮어쓰지 않고, 외부 upstream 자료와 현재 GD13MY 코드를 다시 대조한 결과다.

- **VERIFIED**: 로컬 소스 또는 직접 확인한 원문에서 확인.
- **INFERRED**: 검증된 사실을 조합한 가설. 원인 확정 아님.
- **UNKNOWN**: 공개 자료에서 확인하지 못했거나 실폰/가상폰에서 측정하지 않음.

이 조사만으로 티맵 좌표 보정, 임의 DPI 변경, 강제 확대, 분할 화면 강제 비활성화를 적용하지 않는다. AARE upstream의 예제 인셋(`top/bottom=32`, `left/right=96`)도 GD13MY 값으로 복사하지 않는다.

## 2. 현재 GD13MY 구현 (VERIFIED)

| 항목 | 위치 | 확인 내용 |
|---|---|---|
| 비디오 디스커버리 | `src/ce/ce_aa_tls.c:972-973` | `codec_resolution=VIDEO_800x480`, `frame_rate=30`, `density=160`. `width_margin`, `height_margin`, `ui_config`, cutouts 없음 |
| 입력 디스커버리 | `src/ce/ce_aa_tls.c:974-975` | TouchScreen `800×480`, key codes 없음 |
| 수신 측 동일 해석 | `src/i30_receiver/protocol.py:218-220` | 동일 비디오 파라미터를 읽음 |
| 메시지 허용 목록 | `src/ce/ce_aa_projection.c:26-32` | `DATA`, `CODEC`, `SETUP`, `START`, `STOP`, `FOCUS`만 나열. `UPDATE_UI_CONFIG_REQUEST(0x8009)` 없음 |
| 미지원 메시지 처리 | `src/ce/ce_aa_projection.c:431-433,480-485` | `media()`의 `default: return 0`; 호출부는 `report_rejected_message()` 후 projection 루프 종료 |
| 거부 로그 | `src/ce/ce_aa_projection.c:48-58` | 거부된 채널·플래그·메시지 ID를 `OutputDebugStringW`로 기록 |

따라서 GD13MY는 `--h264`나 다른 영상Backend와 무관하게, 들어온 `0x8009`를 **무시만 하는 것이 아니라 거부하고 세션을 끊는다**. 로컬 코드에는 `0x8009`/`0x800A`를 보내는 경로도 없다. 이는 기존 증거 문서의 더 느슨한 표현보다 강한 코드 사실이다.

## 3. 외부 자료 대조

| 판정 | 출처 | 확인 내용 | GD13MY 관련성 |
|---|---|---|---|
| VERIFIED | [AARE gearhead notes](https://raw.githubusercontent.com/prototux/AARE/main/docs/research/gearhead-notes.md), §2.6, §4.1, §7.1-7.2 | Gearhead 17.7.663653 정적 분석. `VideoConfiguration`은 1=800×480, 2=fps, 3=width_margin, 4=height_margin, 5=density(필수), 11=UiConfig. `0x8009`는 HU→phone `UPDATE_UI_CONFIG_REQUEST`, `0x800A`는 phone→HU reply. 가시 영역은 codec frame − margins. `ui_config.margins`가 없으면 width/height margin을 중심 기준으로 균등 분할 | 현재 GD13MY는 margin/UiConfig를 보내지 않으므로 폰은 전체 프레임을 가시 영역으로 간주 |
| VERIFIED | 동일 문서, §7.2 | dp = px × 160 / dpi (content area 기준). 분할 임계값: 1240 dp widescreen, 880 dp semi-widescreen, 900 dp portrait, 450 dp horizontal rail. 800×480 @160 dpi, insets 없음 → `canonical` 하단 rail 예시 | GD13MY는 이 예시와 정확히 같은 기하값. 티맵의 분할 배치가 이 경계 근처에서 민감할 가능성은 있으나 원인 확정 아님 |
| VERIFIED | [UiConfigUpdate.kt](https://raw.githubusercontent.com/prototux/AARE/main/aap/src/main/kotlin/net/prototux/aare/aap/channels/UiConfigUpdate.kt) 전체 | 프로토콜 4.3 미만은 변경 필드 merge, 4.3 이상은 전체 config replace. theme은 update로 바뀌지 않음. config 없는 요청은 무변경 | 런타임 지오메트리 변경은 HU 버전별 의미가 다름. 현재 GD13MY는 이 경로 자체가 없음 |
| VERIFIED | [VideoConfiguration.proto](https://raw.githubusercontent.com/prototux/AARE/main/aap/src/main/proto/aap_protobuf/service/media/sink/message/VideoConfiguration.proto), [UiConfig.proto](https://raw.githubusercontent.com/prototux/AARE/main/aap/src/main/proto/aap_protobuf/service/media/shared/message/UiConfig.proto), [Insets.proto](https://raw.githubusercontent.com/prototux/AARE/main/aap/src/main/proto/aap_protobuf/service/media/shared/message/Insets.proto), [UpdateUiConfigRequest.proto](https://raw.githubusercontent.com/prototux/AARE/main/aap/src/main/proto/aap_protobuf/service/control/message/UpdateUiConfigRequest.proto) | margin, content/stable insets, cutouts, theme, hidden elements를 전송할 수 있는 프로토콜 표면 확인 | 누락 필드가 존재하는 것은 사실이나, 어떤 값이 정답인지는 아님 |
| VERIFIED | [AARE HeadUnit.kt](https://raw.githubusercontent.com/prototux/AARE/main/headunit/src/main/kotlin/net/prototux/aare/headunit/HeadUnit.kt) 333-338행 | AARE 데모는 `contentInsets`/`stableContentInsets` top/bottom 32, left/right 96을 전송 | 데모 UI 값일 뿐 GD13MY 실측 안전 영역 아님. 복사 금지 |
| VERIFIED | [open-headunit AapProjectionActivity.kt](https://raw.githubusercontent.com/andreknieriem/open-headunit/main/app/src/main/java/com/andrerinas/openheadunit/aap/AapProjectionActivity.kt) 2735-2769행, [AapControl.kt](https://raw.githubusercontent.com/andreknieriem/open-headunit/main/app/src/main/java/com/andrerinas/openheadunit/aap/AapControl.kt) 93-96행, [TouchCoordinateMapper.kt](https://raw.githubusercontent.com/andreknieriem/open-headunit/main/app/src/main/java/com/andrerinas/openheadunit/input/TouchCoordinateMapper.kt) 26-33행, [HeadUnitScreenConfig.kt](https://raw.githubusercontent.com/andreknieriem/open-headunit/main/app/src/main/java/com/andrerinas/openheadunit/utils/HeadUnitScreenConfig.kt) 830-838행 | 세션 시작 후 per-side margin을 다시 알리고, redraw하며, touch는 협상된 resolution−margin을 사용. `0x800A` reply 처리 존재 | 실제 수신기 구현은 margin/insets를 정적 값이 아니라 render+touch 일관성 문제로 다룸 |
| VERIFIED | [mrmees field notes](https://github.com/mrmees/open-android-auto/blob/main/docs/field-notes.md), [video.md](https://github.com/mrmees/open-android-auto/blob/main/docs/channels/video.md) | margin은 세션 시작 시 사실상 고정되며, touch config는 video resolution과 일치해야 한다는 현장 기록 | 초기에 잘못된 지오메트리가 재연결 전까지 지속될 수 있음. 원인 확정 아님 |
| VERIFIED | [aa-proxy-rs mitm.rs](https://github.com/aa-proxy/aa-proxy-rs/blob/main/src/mitm.rs), [sdr_ui.rs](https://raw.githubusercontent.com/aa-proxy/aa-proxy-rs/main/src/sdr_ui.rs) | `0x8009`/`0x800A` 및 discovery video config/insets/UI config 조작 도구 존재 | 실배포에서 이 필드들이 실제로 조작됨을 보여주나, 티맵 증상과 직접 연결되지 않음 |
| VERIFIED (cached), 재요청 403 | [HUIG13 cache](https://milek7.pl/.stuff/galdocs/huig13_cache.html), “Selecting Video Resolution”, “Selecting a Density to Report”, “Matching Physical Display Size” | UI 해상도 ≤ codec 해상도. density는 반드시 보고. margin은 padding 후 HU가 logical UI 영역을 클립. 비정방형 픽셀은 AAP 1.2+ pixel ratio | 2026-11-28 직접 재요청은 HTTP 403. 연구 중 읽은 캐시 내용으로만 인용한다 |
| VERIFIED report / UNKNOWN cause | [Google AA 2025 TMAP 스레드](https://support.google.com/androidauto/thread/372260767/?hl=en) | 티맵 차선 클리핑 보고. AA developer video resolution 변경은 도움 안 됨. 네이버 지도는 영향 없음 | 증상이 차선이지 차량 위치/속도계가 아님. 직접 원인 증거 아님 |
| VERIFIED report / INFERRED analogy | [OsmAnd #16456](https://github.com/osmandapp/OsmAnd/issues/16456), [XDA TLink guide](https://xdaforums.com/t/guide-tlink-hi-dpi-split-mode-android-auto-carplay.4505143) | 분할 화면에서 앱 측 위치 중심 문제가 보고된 적 있음. DPI/resolution 변경이 분할 레이아웃을 바꿈 | 앱 자체 결함 가능성도 배제할 수 없음 |
| UNKNOWN | 공개 검색 | 티맵 분할 화면의 **차량 마커 왼쪽 하단 치우침 + 속도계 간헐적 미표시**를 AAP UiConfig/margin/`0x8009`와 직접 연결한 공개 이슈는 찾지 못함 | 외부 검증 없음 |

## 4. 후보 가설 (모두 INFERRED)

1. **임계값 근처 레이아웃 민감성** — GD13MY의 `800×480 @160`, insets 없음은 gearhead 문서의 canonical bottom rail 예시와 같고 880 dp semi-widescreen 경계 아래다. 티맵 분할 레이아웃이 더 넓거나 inset 보정된 content area를 가정하면 차량 마커가 왼쪽으로 치우칠 수 있다. 간헐성은 내비 오버레이 상태 전환과 함께 올 수 있다.
2. **실제 가시 영역과 보고된 지오메트리 불일치** — 베젤·순정 오버레이·클립 영역이 있음에도 전체 `800×480`을 보고하면, 폰은 보이지 않는 픽셀에 UI를 배치한다. 가장자리 속도계가 상태에 따라 잘릴 수 있다. 올바른 GD13MY inset 값은 미측정이다.
3. **중심 margin 분할 가정** — gearhead notes에 따르면 `ui_config.margins`가 없으면 width/height margin을 중심 기준으로 나눈다. 실제 안전 영역이 비대칭이면 폰이 가정한 content rect와 보이는 화면이 어긋난다.
4. **런타임 UI config 경로 사용 불가** — 로컬 CE는 `0x8009`를 받으면 거부하고 종료하며, 보내지도 않는다. 세션 중 지오메트리가 확정되거나 폰/프록시가 갱신을 시도해도 복구 경로가 없다. 코드 사실은 확실하나 증상 원인으로는 미검증.
5. **DPI/분할 임계값 민감성** — HUIG는 density가 물리 화면 크기를 반영해야 한다고 설명하고 gearhead는 dp 임계값을 사용한다. `160`이 잘못되면 다른 분할 레이아웃이 선택될 수 있으나, 측정 없이 DPI를 바꾸는 것은 금지.
6. **앱 측 결함 가능성** — 티맵/AA 자체 클리핑 보고와 OsmAnd 사례는 앱 측 버그도 가능함을 보여준다. Google 스레드에서는 해상도 변경이 효과가 없었다.

## 5. 결론과 다음 측정

- **VERIFIED**: GD13MY는 현재 margin/insets/ui_config 없이 전체 프레임을 광고하고, `0x8009`를 처리하지 못한다.
- **INFERRED**: 이 지오메트리 관리 공백은 티맵 분할 화면 증상의 그럴듯한 후보다.
- **UNKNOWN**: 티맵 차량 마커·속도계 증상의 실제 원인. 실폰 또는 가상폰 검증 없이는 해결로 보고하지 않는다.

원인을 높이려면 최소한 다음을 같은 세션에서 캡처해야 한다.

1. 스마트폰/폰 측 discovery 정보: video resolution, width/height margin, density, UiConfig 전체.
2. `0x8009`/`0x800A`가 실제로 오가는지와 그 시점의 티맵 화면 상태.
3. GD13MY의 실제 가시 safe area. 순정 지도/후방 오버레이/투사 창 경계를 픽셀 단위로 측정.
4. 터치 좌표가 video frame 기준인지 content area 기준인지. 현재 계약은 800×480 전체 좌표이며 변경하지 않는다.

측정 없이 특정 인셋 값을 넣거나 티맵 전용 보정을 추가하지 않는다.

## 6. AARE 1.6.0 방향 계약 재확인 — 2026-11-28

기존 2~4절의 코드 사실은 유지하되, 메시지 방향은 설치된 AARE 1.6.0과 같은 태그의 upstream 소스로 다시 확인했다. `main`이 아니라 `v1.6.0` 태그를 기준으로 삼았다.

| 판정 | 근거 | 확인 내용 |
|---|---|---|
| VERIFIED | [AARE v1.6.0 `MessageIds.kt`](https://raw.githubusercontent.com/prototux/AARE/v1.6.0/aap/src/main/kotlin/net/prototux/aare/aap/MessageIds.kt) 38-55행 | `MediaMsg.UPDATE_UI_CONFIG_REQUEST = 0x8009`, `MediaMsg.UPDATE_UI_CONFIG_REPLY = 0x800A`. 같은 숫자 `0x8009`가 `NavStatusMsg.RAW_ROUTE_INFO`로도 정의되어 있으므로, ID 숫자만으로 방향을 판정하지 않고 채널과 메시지 종류를 함께 봐야 한다 |
| VERIFIED | [AARE v1.6.0 `MediaChannels.kt`](https://raw.githubusercontent.com/prototux/AARE/v1.6.0/aap/src/main/kotlin/net/prototux/aare/aap/channels/MediaChannels.kt) 429-449행 | `VideoChannel.onOtherMessage()`가 video 채널의 `0x8009`를 `UpdateUiConfigRequest`로 파싱해 `onUiConfigRequest()`로 넘긴다. 수신한 `0x800A`는 no-op이다 |
| VERIFIED | 동일 파일 337-342, 451-478행 | request마다 `UpdateUiConfigReply`를 `send(MediaMsg.UPDATE_UI_CONFIG_REPLY, ...)`로 폰→HU 방향 전송한다. config가 없으면 현재 config로 즉시 회신하고, config가 있으면 레이아웃 적용 후 프레임이 따라간 뒤 또는 대기 시간 초과 후 회신한다 |
| VERIFIED | [AARE v1.6.0 `UiConfigUpdate.kt`](https://raw.githubusercontent.com/prototux/AARE/v1.6.0/aap/src/main/kotlin/net/prototux/aare/aap/channels/UiConfigUpdate.kt) 전체 | 프로토콜 4.3 미만은 변경분 merge, 4.3 이상은 전체 replace. theme은 갱신 대상이 아니며 config 없는 request는 무변경 |
| VERIFIED | [AARE v1.6.0 gearhead notes](https://raw.githubusercontent.com/prototux/AARE/v1.6.0/docs/research/gearhead-notes.md) 360-361, 624행 | video 채널에서 `0x8009`는 HU→phone `xuw {1: UiConfig}`, `0x800A`는 phone→HU reply. 런타임 지오메트리 변경은 이 request/reply 쌍으로 처리된다 |
| VERIFIED | `src/ce/ce_aa_projection.c:26-32,394-433,480-485` | GD13MY의 video 채널 허용 목록에 `0x8009`가 없다. `media()`의 `default: return 0`을 거쳐 호출부가 `report_rejected_message()` 후 projection 루프를 종료한다. `src/`, `tools/`, `tests/` 어디에도 `0x8009` 송신 또는 `0x800A` 수신 처리가 없다 |
| VERIFIED | `src/ce/ce_aa_tls.c:972-975` | service discovery는 800×480@30, density 160만 광고하고 `ui_config`, margin, cutouts를 보내지 않는다 |

**방향 정정:** GD13MY가 video 채널의 `0x8009`를 받아 종료하는 것은 로컬 구현의 사실이다. 그러나 AARE phone의 정상 계약은 `0x8009`를 **수신만**하고 `0x800A`로 **응답**하는 것이다. 따라서 기대되는 HU 측 구현은 `0x8009` 송신과 `0x800A` 수신 처리이며, GD13MY에는 두 경로가 모두 없다. 이 문서는 수신 거부를 "단순 무시"나 "강제 성공"으로 바꾸지 않고, 방향 계약과 로컬 정책의 차이만 기록한다. 실제 세션에서 해당 메시지가 오가는지와 티맵 증상과의 인과는 여전히 **UNKNOWN**이다.

### 회귀 확인

2026-11-28, Python 3.15.0b3, Windows x64, `python.exe` 기준. `pytest`는 이 환경에 설치되어 있지 않아 프로젝트 문서가 사용하는 표준 라이브러리 `unittest`를 실행했다. 코드 변경은 없었다.

| 범위 | 명령 | 결과 |
|---|---|---|
| 관련 모듈 | `python -m unittest tests.test_gd13my_projection tests.test_pc_video tests.test_phase2 tests.test_aare_rgb565 -v` | 39개 통과, 2.113초, 실패 없음 |
| 전체 | `python -m unittest discover -s tests -q` | 98개 실행, 1개 환경 조건 건너뜀, 실패 없음, 23.229초 |

이 시험은 기존 동작의 회귀만 확인한다. `src/`, `tools/`, `tests/`에 `0x8009`/`0x800A` fixture나 assertion이 없으므로 UI config 계약이 구현됐음을 증명하지는 않는다. 라이브 AOA/TLS 캡처는 CE 에뮬레이터가 실행 중이지 않아 BLOCKED이며, 사용자가 직접 열거나 명시적으로 재실행을 허용한 뒤 같은 세션에서 discovery, `0x8009`/`0x800A`, safe area, 터치 좌표를 함께 캡처해야 한다.
