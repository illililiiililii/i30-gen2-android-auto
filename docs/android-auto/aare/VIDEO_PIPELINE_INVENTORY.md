# AARE 영상 처리 파이프라인 인벤토리

## 1. 개요

본 문서는 `src/ce/` 디렉터리에 위치한 GD13MY 네이티브 Windows CE Android Auto 수신기의 영상 처리 파이프라인 전 과정(USB 수신부터 화면 출력까지)을 단계별로 분석한 기술 인벤토리다.
각 단계의 소스 파일, 함수, 호출 위치, 데이터 포맷, 버퍼 크기, 메모리 복사 횟수 및 성능 측정 포인트/하드웨어 가속 현황을 명시한다.

---

## 2. 영상 처리 8단계 상세 분석

### 1단계: USB 데이터 수신 (USB Bulk Data Read)
- **소스 파일**: `src/ce/ce_aa_usb_client.c`
- **함수명**: `read_bulk_transfer()` / `usb_transfer_complete()`
- **호출 위치**: WinCE USB 드라이버 콜백 `IssueBulkTransfer()` 완료 루틴
- **입력 데이터**: USB AOA 프로토콜 벌크 패킷 (Raw Wire Data)
- **출력 데이터**: `ce_aa_tls.c`의 `secure_read()`로 전달되는 암호화된 레코드 버퍼
- **버퍼 크기**: 벌크 엔드포인트 패킷 버퍼 (보통 16KB ~ 64KB 단위 수신)
- **메모리 복사 횟수**: 1회 (USB 컨트롤러 DMA 버퍼 -> 사용자 영역 수신 큐)
- **기존 계측 기능**: 타임아웃 검사 (`USB_VERSION_MS`, `USB_TLS_MS`), `debug_number()`로 상태 출력
- **하드웨어 가속 유무**: 없음 (WinCE MUSB 드라이버 벌크 전송)

### 2단계: TLS 복호화 (TLS 1.2 Decryption)
- **소스 파일**: `src/ce/ce_aa_tls.c`
- **함수명**: `secure_read()` / `br_ssl_engine_recvrec_ack()` (BearSSL 엔진)
- **호출 위치**: `ce_aa_tls.c`의 `receive_media()` 및 `discover()` 루틴
- **입력 데이터**: TLS 1.2 암호화 레코드 (CBC/GCM 암호문)
- **출력 데이터**: 복호화된 평문 AAP 프레임 데이터
- **버퍼 크기**: TLS 최대 레코드 크기 16KB + 오버헤드 (`s->control` 또는 세션 버퍼)
- **메모리 복사 횟수**: 1회 (BearSSL 수신 엔진 버퍼 -> 평문 출력 버퍼)
- **기존 계측 기능**: BearSSL 에러 코드 디버그 출력 (`handshake_error`)
- **하드웨어 가속 유무**: 순수 소프트웨어 (ARM BearSSL 구현)

### 3단계: AAP 메시지 처리 (AAP Framing & Channel Demux)
- **소스 파일**: `src/ce/ce_aa_projection.c`
- **함수명**: `i30_projection_video()` / `receive_media()`
- **호출 위치**: `ce_aa_projection.c` 메인 이벤트 루프 (라인 400~450 부근)
- **입력 데이터**: 복호화된 AAP 메시지 헤더 + 페이로드
  - 채널 3: 비디오 채널 (`I30_PROJECTION_VIDEO_CHANNEL`)
  - 채널 1: 입력 채널 (`I30_PROJECTION_INPUT_CHANNEL`)
- **출력 데이터**: H.264 NAL 스트림 조각 (Channel 3 페이로드)
- **버퍼 크기**: 프레임 크기에 따라 가변 (비디오 버퍼 용량 2MB: `I30_VIDEO_INPUT_LIMIT`)
- **메모리 복사 횟수**: 0~1회 (채널 플래그 확인 후 직접 전달)
- **기존 계측 기능**: `report_rejected_message()` 디버그 출력
- **하드웨어 가속 유무**: 없음

### 4단계: H.264 프레임 조립 (Annex B Bitstream Assembly)
- **소스 파일**: `src/ce/ce_aa_projection.c` 및 `src/ce/ce_aa_video.c`
- **함수명**: `i30_video_push()`
- **호출 위치**: `i30_projection_video()` 내부에서 수신된 비디오 메시지 수신 시 호출
- **입력 데이터**: AAP 비디오 메시지 페이로드 (시작 코드 `00 00 00 01` 또는 길이 프리픽스 NALU)
- **출력 데이터**: Annex B 형식의 완성된 NAL 바이트 스트림
- **버퍼 크기**: 최대 2,097,152 바이트 (2MB, `I30_VIDEO_INPUT_LIMIT`)
- **메모리 복사 횟수**: 0회 (수신 버퍼를 직접 수정 및 파싱)
- **기존 계측 기능**: 타임스탬프 검증 및 디버그 문자열
- **하드웨어 가속 유무**: 없음

### 5단계: H.264 디코딩 (Video Decoding)
- **소스 파일**: `src/ce/ce_aa_video.c` (및 `h264bsd_decoder.c`)
- **함수명**: `h264bsdDecode()` / `i30_video_push()`
- **호출 위치**: `src/ce/ce_aa_video.c`의 `i30_video_push()` 내부
- **입력 데이터**: H.264 Baseline Profile Annex B 비트스트림
- **출력 데이터**: 디코딩된 YUV 4:2:0 원시 픽처 버퍼 (디코더 내부 DPB: Decoded Picture Buffer)
- **버퍼 크기**: 800×480 YUV420 기준 1프레임 약 576,000 바이트 (Y: 384,000, U: 96,000, V: 96,000)
- **메모리 복사 횟수**: 0회 (디코더 내부 DPB에서 직접 참조)
- **기존 계측 기능**: `h264bsdNextOutputPicture` 에러 카운터 (`errors`, `keyframe`)
- **하드웨어 가속 유무**: 순수 소프트웨어 디코딩 (`h264bsd` 정수 연산 라이브러리)

### 6단계: YUV to BGRA 색상 변환 (Color Conversion)
- **소스 파일**: `src/ce/ce_aa_video.c` (및 `h264bsd_decoder.c`)
- **함수명**: `h264bsdNextOutputPictureBGRA()`
- **호출 위치**: `src/ce/ce_aa_video.c`의 `paint()` (라인 83)
- **입력 데이터**: YUV 4:2:0 평면 픽셀 데이터
- **출력 데이터**: 32비트 BGRA 패킹된 픽셀 버퍼 (`const u32 *pixels`)
- **버퍼 크기**: 800 × 480 × 4 = 1,536,000 바이트 (1.46MB)
- **메모리 복사 횟수**: 1회 (YUV 평면에서 BGRA 배열로 변환하면서 복사)
- **기존 계측 기능**: 없음
- **하드웨어 가속 유무**: 소프트웨어 루프 변환 (ARM 정수 변환)

### 7단계: 프레임 버퍼 복사 및 스케일링 (Frame Buffer Blit)
- **소스 파일**: `src/ce/ce_aa_video.c`
- **함수명**: `StretchDIBits()`
- **호출 위치**: `src/ce/ce_aa_video.c`의 `paint()` (라인 92~94)
- **입력 데이터**: 32비트 BGRA 픽셀 배열 (`pixels`), `BITMAPINFOHEADER` (`info`)
- **출력 데이터**: WinCE 디스플레이 장치 컨텍스트(DC)
- **버퍼 크기**: 소스 및 목적지 800×480 (1,536,000 바이트)
- **메모리 복사 횟수**: 1회 (사용자 버퍼 -> GDI/프레임버퍼 메모리)
- **기존 계측 기능**: `OutputDebugStringW(L"i30 LCD blit begin\r\n")` 및 `end` 마커 존재
- **하드웨어 가속 유무**: WinCE GDI 드라이버 소프트웨어 래스터라이저

### 8단계: 화면 출력 (Display Presentation)
- **소스 파일**: `src/ce/ce_aa_projection.c` / `src/ce/ce_aa_native_display.cpp`
- **함수명**: `target->end()` (ReleaseDC) / `present_media()`
- **호출 위치**: `src/ce/ce_aa_video.c` 라인 95
- **입력 데이터**: 렌더링된 윈도우 DC
- **출력 데이터**: 물리 LCD 패널 (RGB565 800×480)
- **버퍼 크기**: 800 × 480 × 2 = 768,000 바이트
- **메모리 복사 횟수**: 1회 (WinCE ddi 드라이버가 LCD 컨트롤러 DMA 버퍼로 플러시)
- **기존 계측 기능**: `MediaLink`의 `video_presented()` 콜백
- **하드웨어 가속 유무**: LCD 컨트롤러 하드웨어 DMA 스캔아웃

---

## 3. 요약 및 성능 개선 검토 포인트

| 단계 | 처리 내용 | 주요 함수 | 데이터 포맷 | 복사 횟수 | 가속 현황 |
|---|---|---|---|---|---|
| 1 | USB 수신 | `IssueBulkTransfer` | Raw USB | 1회 | SW |
| 2 | TLS 복호화 | `secure_read` / BearSSL | Encrypted -> Plain | 1회 | SW |
| 3 | AAP 파싱 | `i30_projection_video` | AAP Ch3 Frame | 0~1회 | SW |
| 4 | H.264 조립 | `i30_video_push` | Annex B NALU | 0회 | SW |
| 5 | H.264 디코드 | `h264bsdDecode` | NALU -> YUV420 | 0회 | SW (h264bsd) |
| 6 | 색상 변환 | `h264bsdNextOutputPictureBGRA` | YUV420 -> BGRA32 | 1회 | SW |
| 7 | 버퍼 복사 | `StretchDIBits` | BGRA32 -> DC | 1회 | GDI SW |
| 8 | LCD 표시 | `ReleaseDC` / DMA | Framebuffer -> LCD | 1회 | HW DMA |

### 병목 지점 및 권장 측정 위치
1. **5단계와 6단계 결합 병목**: `h264bsdDecode` 소요 시간과 `h264bsdNextOutputPictureBGRA` 변환 소요 시간이 전체 CPU 점유율의 대부분을 차지함.
   - 계측 포인트: `src/ce/ce_aa_video.c`의 `i30_video_push()` 시작/종료 지점에 정밀 틱(`GetTickCount` 또는 타이머) 추가 필요.
2. **6단계 BGRA 변환 제거 가능성**: WinCE 프레임버퍼가 RGB565(16비트)이므로, YUV420에서 32비트 BGRA로 변환 후 GDI가 다시 RGB565로 다운샘플링하는 이중 변환이 발생함. YUV에서 직접 RGB565로 변환하거나 DirectDraw 오버레이 서피스를 활용할 경우 대폭적인 성능 향상이 가능함.
