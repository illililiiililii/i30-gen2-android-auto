# 티맵(TMAP) 분할 화면 이상 현상 조사 및 증거

## 1. 개요 및 사용자 보고 증상

### 사용자 보고 내용
1. Android Auto의 티맵(TMAP) 분할 화면(Coolwalk) 실행 시, 차량 위치 아이콘 표시가 화면 왼쪽으로 과도하게 치우침.
2. 속도계가 정상적인 위치에 표시되지 않거나 잘리는 현상이 발생함.
3. 동일한 분할 화면 환경에서 **네이버 지도(Naver Map)**는 정상 표시됨.
4. 카카오내비(Kakao Navi)는 현재 미검증 상태.

본 문서는 원인을 임의로 단정하거나 수치를 수정하지 않고, 현재 프로젝트 구현과 오픈소스 구현(AARE upstream, aasdk)의 비디오 파라미터 및 프로토콜 규격을 객관적으로 대조하여 기록한다.

---

## 2. 현재 GD13MY 수신기(WinCE) 구현 현황

### 2.1 위치 및 설정값
- **소스 파일**: `src/ce/ce_aa_tls.c` (라인 972~975)
- **비디오 채널 서비스 디스커버리 응답 바이트열**:
  ```c
  static const uint8_t video_channel[] = {
      0x0a, 0x0f, 8, 3, 0x1a, 11, 8, 3,
      0x22, 7, 8, 1, 16, 2, 40, 0xa0, 1
  };
  ```
  - `0x0a, 0x0f`: Channel descriptor (length 15)
  - `8, 3`: Channel ID 3 (비디오 채널)
  - `0x1a, 11`: MediaSinkService descriptor
  - `8, 3`: Service ID 3
  - `0x22, 7`: VideoConfiguration
    - `8, 1`: `codec_resolution` = 1 (`VIDEO_800x480`)
    - `16, 2`: `frame_rate` = 2 (`VIDEO_FPS_30`)
    - `40, 0xa0, 1`: `density` = 160 (160 DPI)
  - **여백 및 인셋 설정**:
    - `width_margin`: **0 (미지정/기본값 0)**
    - `height_margin`: **0 (미지정/기본값 0)**
    - `UiConfig` (`margins`, `content_insets`, `stable_content_insets`): **미제공 (부재)**
    - `display_cutouts`: **미제공 (부재)**

### 2.2 입력 채널 및 터치 좌표
- **소스 파일**: `src/ce/ce_aa_tls.c` (라인 974~975)
  ```c
  static const uint8_t input_channel[] = {
      0x0a, 12, 8, 1, 0x22, 8, 0x12, 6,
      8, 0xa0, 6, 16, 0xe0, 3
  };
  ```
  - TouchScreen 해상도: 폭 800 (`0xa0, 6` = 800), 높이 480 (`0xe0, 3` = 480)
- **터치 좌표 디코딩**: `src/ce/ce_aa_native_display.h`
  - `I30_TOUCH_X(sample)`: `(sample) & 1023U`
  - `I30_TOUCH_Y(sample)`: `((sample) >> 10) & 511U`
  - 800×480 절대 좌표를 그대로 1:1 전달하며 인셋이나 분할 화면 오프셋 보정은 수신기에 존재하지 않음.

---

## 3. 관련 공개 구현 대조

### 3.1 AARE Upstream (prototux)
- **저장소**: https://github.com/prototux/aare
- **참조 파일**:
  - `aap/src/main/proto/aap_protobuf/service/media/sink/message/VideoConfiguration.proto`
  - `aap/src/main/proto/aap_protobuf/service/media/shared/message/UiConfig.proto`
  - `headunit/src/main/kotlin/net\prototux\aare\headunit\HeadUnit.kt` (라인 333~338, 615~635)
  - `app/src/test/java/net/prototux/aare/ui/car/CarSplitTest.kt`

#### AARE Upstream의 VideoConfiguration 및 Insets 처리:
- AARE는 `VideoConfiguration`에 `codec_resolution`, `frame_rate`, `density`, `width_margin`, `height_margin` 외에도 `UiConfig`를 적극적으로 포함할 수 있도록 구현되어 있음.
- `HeadUnit.kt`의 동적 인셋 갱신:
  ```kotlin
  val insets = Insets.newBuilder().setTop(32).setBottom(32).setLeft(96).setRight(96)
  send(chVideo, MediaMsg.UPDATE_UI_CONFIG_REQUEST, UpdateUiConfigRequest.newBuilder()
      .setUiConfig(UiConfig.newBuilder().setContentInsets(insets).setStableContentInsets(insets)).build())
  ```
- `CarSplitTest.kt`의 분할 화면 기준:
  - `SPLIT_MIN_SCREEN_WIDTH`가 최소 900.dp 이상이어야 분할 화면을 활성화(`splitScreenFits(900.dp) == true`, `splitScreenFits(899.dp) == false`).
  - 800×480은 기본적으로 단일 화면(Single pane)에 적합한 해상도이며, Coolwalk이 강제로 분할 화면을 시도할 때 가용 너비(Width in DP) 부족 문제가 발생할 수 있음.

### 3.2 공개 구현 비교표

| 항목 | 현재 GD13MY 수신기 (`src/ce`) | AARE Upstream (`headunit`) | AAP 프로토콜 표준 사양 |
|---|---|---|---|
| **해상도** | 800 × 480 (`VIDEO_800x480`) | 1280×720 기본 (800x480 클러스터 지원) | `VideoCodecResolutionType` |
| **DPI** | 160 (`0xa0, 1`) | 160 기본 (설정 가능) | `density` (보통 120~240) |
| **Margins** | 미전송 (암시적 0) | 명시적 `width_margin=0`, `height_margin=0` | `width_margin`, `height_margin` |
| **Content Insets** | **미지원 (전송 안 함)** | `UiConfig.content_insets` 지원 (런타임 변경 가능) | 상/하/좌/우 패딩 (Status bar, Nav bar) |
| **Stable Insets** | **미지원 (전송 안 함)** | `UiConfig.stable_content_insets` 지원 | 안전 영역 경계 |
| **UI Config Update** | **미구현 (수신 시 무시)** | `UPDATE_UI_CONFIG_REQUEST` 메시지 송수신 | 동적 화면 분할/전환 알림 |
| **운전석 위치** | 미지정 (Android 기본값 의존) | `rightHandDrive` 플래그 설정 지원 | `DriverPosition` |

---

## 4. 유사 사례 및 외부 조사 결과

국내외 Android Auto 및 내비게이션 포럼(Tistory, Arca.live, Reddit 등)에서 보고된 유사 사례 분석:

1. **쿨워크(Coolwalk) 레이아웃과 앱별 반응형 UI 처리 차이**:
   - Android Auto 쿨워크 분할 화면에서 스마트폰의 Android Auto 호스트는 헤드유닛이 보고한 `density`와 가용 해상도(`content_insets` 제외 영역)를 기준으로 앱에 렌더링 뷰포트를 제공함.
   - **네이버 지도**: 내비게이션 뷰포트 변경 시 지도 중심점(POI)과 차량 마커를 가용 뷰포트의 정중앙에 동적으로 재계산하도록 구현되어 있음.
   - **티맵(TMAP)**:
     - 분할 화면 진입 시 가로 해상도가 좁은 상태(800px 화면에서 약 500px 수준으로 축소)에서 상단 차로 안내와 좌측 속도계 UI 오버레이가 고정 오프셋(Fixed DP)으로 계산되어, 차량 위치 마커가 화면 좌측(또는 조수석 방향)으로 치우치거나 속도계 영역이 뷰포트 밖으로 잘리는 현상이 지속적으로 보고됨.
     - 사용자들은 "전체화면(최대화)으로 전환하면 정상 위치로 복귀함"을 공통적으로 보고하고 있음.
2. **헤드유닛 DPI 및 해상도 설정의 영향**:
   - 800×480에서 DPI가 160일 경우, dp 단위 가로 해상도는 `800 / (160 / 160) = 800dp`임.
   - 만약 헤드유닛이 Content Insets(예: 좌측 사이드 레일 바 너비)를 보고하지 않으면, 스마트폰의 티맵은 전체 800px을 모두 그릴 수 있는 영역으로 간주하지만, 실제 Android Auto 시스템 UI(작업 표시줄/사이드바)가 화면의 일정 부분을 가려버리므로 상대적 오차가 발생할 수 있음.

---

## 5. 결론 및 후속 작업(Codex)을 위한 제언

- **원인 단정 금지**: 본 증상은 단순 AARE 수신기 버그라기보다는 티맵의 좁은 화면(800×480) 분할 화면 UI 레이아웃 로직과 AAP `UiConfig` (Content Insets) 미제공이 복합적으로 얽혀 발생했을 가능성이 높음.
- **후속 구현 시 검토 가능한 포인트**:
  1. `src/ce/ce_aa_tls.c`의 `ServiceDiscoveryResponse` 내 `VideoConfiguration`에 `UiConfig`를 명시하여 정확한 `content_insets`와 `stable_content_insets`를 휴대폰에 보고하는 방법.
  2. DPI 설정을 160에서 다른 값(예: 140 또는 180)으로 조정했을 때 티맵의 스케일링 반응 관찰.
  3. 티맵 화면을 탭하여 전체 화면으로 전환했을 때 정상 복귀되는지 여부를 실폰 테스트에서 확인.
