# 티맵 분할 화면: 프로토콜 실증과 구현 결정

작성일: 2026-11-27 · 브랜치: `feature/aare-performance-display` · 기준 커밋: `aaec50e`

## 1. 목적

`TMAP_DISPLAY_EVIDENCE.md`에 정리된 가설을 그대로 채택하지 않고, 로컬 AARE upstream protobuf/코드에서 필드 번호와 메시지 전달 경로를 직접 확인했다. 이 문서는 **검증된 프로토콜 사실**과 **실폰에서 아직 검증되지 않은 증상 해결 여부**를 구분한다.

## 2. AARE upstream 실증 결과

읽은 파일(로컬 종속성 `build/aare-upstream/`):

- `aap/src/main/proto/aap_protobuf/service/media/sink/message/VideoConfiguration.proto`
- `aap/src/main/proto/aap_protobuf/service/media/shared/message/UiConfig.proto`
- `aap/src/main/proto/aap_protobuf/service/media/shared/message/Insets.proto`
- `aap/src/main/proto/aap_protobuf/service/control/message/UpdateUiConfigRequest.proto`
- `aap/src/main/proto/aap_protobuf/service/media/sink/MediaMessageId.proto`
- `aap/src/main/kotlin/net/prototux/aare/aap/channels/UiConfigUpdate.kt`
- `headunit/src/main/kotlin/net/prototux/aare/headunit/HeadUnit.kt` (333~339행)

확인된 구조:

| 메시지/값 | 필드 번호 | 내용 |
|---|---:|---|
| `VideoConfiguration.codec_resolution` | 1 | GD13MY는 `VIDEO_800x480` = 1 |
| `VideoConfiguration.frame_rate` | 2 | GD13MY는 `VIDEO_FPS_30` = 2 |
| `VideoConfiguration.width_margin` / `height_margin` | 3 / 4 | GD13MY 미지정(암시적 0) |
| `VideoConfiguration.density` | 5 | `0xa0, 0x01` = 160 DPI |
| `VideoConfiguration.ui_config` | **11** | `shared.message.UiConfig`, 선택 필드 |
| `UiConfig.margins` | **1** | `Insets` |
| `UiConfig.content_insets` | **2** | `Insets` |
| `UiConfig.stable_content_insets` | **3** | `Insets` |
| `UiConfig.ui_theme` | 4 | 갱신 시 변경하지 않음 |
| `Insets.top` / `bottom` / `left` / `right` | **1 / 2 / 3 / 4** | 모두 `uint32` |
| `UpdateUiConfigRequest.ui_config` | **1** | 런타임 갱신 본문 |
| `MEDIA_MESSAGE_UPDATE_UI_CONFIG_REQUEST` | **32777** (0x8009) | **video 채널**로 전송 |

`HeadUnit.kt`의 실제 전달 단계는 `send(chVideo, MediaMsg.UPDATE_UI_CONFIG_REQUEST, UpdateUiConfigRequest.newBuilder().setUiConfig(UiConfig.newBuilder().setContentInsets(insets).setStableContentInsets(insets)).build())`이다. 즉 인셋 갱신은 control 채널이 아니라 **video 채널의 미디어 메시지 32777**로 보낸다. `UiConfigUpdate.kt`에 따르면 프로토콜 4.3 미만 head unit은 변경 필드를 merge하고, 4.3 이상은 전체 config로 replace하며, theme은 요청에서 제외된다.

## 3. GD13MY 현재 구현과 800×480/160 DPI 대조

`src/ce/ce_aa_tls.c`의 서비스 디스커버리 video channel descriptor는 다음과 같다.

```c
static const uint8_t video_channel[] = {0x0a, 0x0f, 8, 3, 0x1a, 11, 8, 3,
                                        0x22, 7, 8, 1, 16, 2, 40, 0xa0, 1};
```

- `VideoConfiguration` 길이 7: `codec_resolution=1`, `frame_rate=2`, `density=160`
- `width_margin`/`height_margin`/`ui_config`는 전송하지 않음
- 입력 채널은 터치 800×480을 1:1로 보고하고, 수신기 변환은 800×480 고정

계산상 800 px / (160 DPI / 160) = **800 dp** 폭이다. AARE upstream의 분할 화면 최소 폭 기준은 900 dp이므로 upstream 정책만 보면 800 dp는 단일 화면이다. 그럼에도 티맵에서 분할 화면이 관측된다는 보고는 헤드유닛 인셋 부재와 앱 자체 반응형 레이아웃이 결합된 가능성을 남긴다. 네이버 지도가 정상이라는 대조 사례도 앱별 차이를 시사한다.

## 4. 구현 결정

이 브랜치에서는 **티맵 전용 좌표, 임의 DPI/해상도 변경, 영상 강제 확대·이동, 분할 화면 강제 비활성화를 추가하지 않았다.** 이유는 다음과 같다.

1. upstream 예시 인셋(상/하 32, 좌/우 96)은 AARE 자체 UI 기준이며 GD13MY 순정 화면의 안전 영역 실측값이 아니다. 이를 그대로 넣는 것은 근거 없는 하드코딩이다.
2. 실폰/실차에서 티맵의 분할 화면 뷰포트와 인셋 반응을 측정하지 않았으므로 "해결"을 주장할 수 없다.
3. 필드 번호는 위에서 실증했으므로, 나중에 실측 안전 영역이 나오면 추측 없이 아래 **올바른 경로**에만 실험 설정을 추가하면 된다.

실측 후 사용할 경로(오늘 구현하지 않음):

- 초기 협상: 서비스 디스커버리의 `VideoConfiguration.ui_config`(필드 11)에 `content_insets`(필드 2)와 `stable_content_insets`(필드 3) 포함
- 주행 중 변경: video 채널로 `MEDIA_MESSAGE_UPDATE_UI_CONFIG_REQUEST`(32777) + `UpdateUiConfigRequest.ui_config`(필드 1) 전송
- `Insets`는 top=1, bottom=2, left=3, right=4. theme은 갱신에서 제외

## 5. 검증 상태

| 항목 | 상태 |
|---|---|
| protobuf 필드 번호/메시지 구조 | **정적 실증 완료** (upstream proto 파일) |
| 인셋 갱신 메시지 ID·채널·전달 방향 | **정적 실증 완료** (upstream Kotlin) |
| GD13MY가 인셋을 보내지 않는 현재 상태 | **정적 실증 완료** (CE discovery 바이트열) |
| 800×480 / 160 DPI → 800 dp 계산 | **정적 실증 완료** |
| 실폰 티맵 분할 화면 개선 여부 | **미검증** (실폰/실차 시험 없음) |
| 실폰 카카오내비 동작 | **미검증** |

`TMAP_DISPLAY_EVIDENCE.md`의 진술은 유지하며 이 브랜치에서 수정하지 않았다. 근거 문서와 구현 결정만 위에 분리해 기록한다.
