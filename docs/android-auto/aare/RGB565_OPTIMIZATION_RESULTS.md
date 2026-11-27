# AARE YUV420 → RGB565 직접 변환 비교 결과

작성일: 2026-11-27 · 브랜치: `feature/aare-performance-display` · 기준 커밋: `aaec50e`

## 1. 목적과 범위

WinCE 수신기의 800×480 영상 경로에서 `YUV420 → BGRA32 → RGB565` 이중 변환을 제거하는 직접 변환을 구현하고, 기존 경로와 **동일한 H.264 입력**으로 반복 비교했다. 비교 목표는 색상·레이아웃 정확성, 재할당/누수 없음, 프레임 표시 완결성, 사이클 시간 변화다. 실측에서 개선이 없으면 기존 BGRA 경로를 기본값으로 유지한다는 조건을 사전에 설정했다.

DSP 디코더, 커널/BSP/MICOM, 파티션, 순정 펌웨어 원본은 변경하지 않았다.

## 2. 구현

| 파일 | 변경 내용 |
|---|---|
| `src/ce/ce_aa_rgb565.h` | h264bsd BGRA 변환과 **동일한 정수 계수·반올림**을 사용하는 `i30_yuv_pixel_rgb565()`와 tight planar YUV420 → top-down RGB565 변환기. 마스크는 `R=0xf800`, `G=0x07e0`, `B=0x001f`. |
| `src/ce/ce_aa_video.c` | `-DI30_VIDEO_RGB565`일 때 52바이트 `BITMAPINFOHEADER + BI_BITFIELDS` DIB를 `StretchDIBits`로 전달. 기존 32bpp 경로는 그대로 보존. 800×480 프레임 버퍼(768,000바이트)를 스트림당 한 번 할당해 재사용하고 `i30_video_close()`에서 해제. 매 프레임 할당 없음. GDI가 16bpp DIB를 거부하면 같은 DPB 프레임으로 `h264bsdConvertToBGRA()` → 32bpp 블릿 폴백. crop/source rect, 목적지 800×480, negative-height(top-down), SRCCOPY, 터치 좌표 경로는 기존과 동일. |
| `tools/build_ce_usb.py` | `--video-format {bgra,rgb565}` 추가. **기본값은 `bgra`**. `abi.json`에 `video_format`과 프로파일 심볼(`i30_yuv420_to_rgb565`, `h264bsdConvertToBGRA` 등)을 기록. |
| `tools/emulate_ce_usb.py` | 16bpp DIB 헤더·마스크·center pixel·행 순서를 검증. `--reject-rgb565`로 16bpp 블릿 1회 거부를 주입해 BGRA 폴백을 검증. ARM 함수별/블릿별 시간을 JSON에 기록. |
| `tests/test_aare_rgb565.py` | 호스트 C 컴파일러(Zig)로 빌드한 변환기에 대해 마스크, RGB/BGR 순서, 흑백/3원색, BGRA와 동일한 정수 반올림, top-down 밀도/packages 4개 단위 시험. |
| `tools/report_aare_video_compare.py` | 반복 벤치마크 JSON의 중앙값 요약. |

## 3. 시험 조건

- 컴파일러: `arm-gnu-14.2/bin/arm-none-eabi-gcc.exe`
- 실행기: Unicorn 2.1.4 WinCE API double, PyAV 19.0.2 H.264 Baseline
- 입력: 800×480 YUV420, 명목 30 FPS, 2초(60프레임), 동일 인코딩을 두 빌드에 사용
- 반복: 각 경로 4회. 디코딩·색 변환·`i30_video_push`·GDI 블릿·ACK 간격·벽시계·guest heap 피크를 수집
- 빌드: `bgra`(기준)와 `rgb565`(실험)를 별도 디렉터리에 생성. `abi.json`의 SHA-256/RVA 검증을 통과

## 4. 측정 결과

중앙값(4회, 밀리초):

| 지표 | BGRA 기준 | RGB565 직접 | 해석 |
|---|---:|---:|---|
| `h264bsdDecode` | 87.84 | 86.28 | 디코더 cost는 사실상 동일 |
| 색 변환 | 37.39 (`NextOutputPictureBGRA`) | 55.58 (`i30_yuv420_to_rgb565`) | **직접 경로가 약 18.2 ms 느림** |
| `i30_video_push` | 128.42 | 145.93 | 프레임 처리 전체도 느림 |
| GDI 블릿(double) | 0.0103 | 0.0174 | Unicorn 훅 시간, 실기 GDI 시간 아님 |
| 프레임 ACK 간격 | 134.50 | 152.14 | 약 17.6 ms 증가 |
| 전체 벽시계 | 9.203 s | 10.219 s | 약 1.02 s 증가 |
| guest heap 피크 | 5,231,760 B | 4,463,760 B | 프레임 버퍼가 절반이라 감소(속도 개선 아님) |
| 종료 시 live allocation | 0 | 0 | 누수 없음 |
| ACK/표시 프레임 | 60/60 | 60/60 | 누락 없음 |

고동작 패턴 30 FPS 2초에서도 두 경로 모두 60/60 ACK·표시, 전송 바이트 453,452바이트로 동일했다. center pixel 색상 샘플 수는 BGRA 24, RGB565 6으로, 양자화로 인해 단일 임계값 기반 샘플 수가 줄었다(표시 실패 아님). 색상 자체는 단위 시험과 16bpp center-pixel 검증에서 FG/배경 기대치를 만족했다.

중간에 시도한 `col += 2` chroma 포인터 전진 최적화는 단일 실행에서 102 ms로 오히려 느려 원래 루프로 되돌렸다. 추가 최적화를 추측하지 않고 실측 결과를 기준으로 판정했다.

## 5. 판정

**개선 없음.** 이 환경(ARM 코드 + Unicorn API double)에서 RGB565 직접 변환은 BGRA 기준보다 색 변환과 프레임 간격이 일관되게 느렸다. 따라서 다음을 유지한다.

- 빌드/배포 기본값: **기존 BGRA 경로** (`--video-format bgra`, 기본값)
- RGB565 경로: 실기 measurement용 **opt-in 실험 빌드**로만 남김
- BGRA 폴백: 항상 유지. 16bpp `BI_BITFIELDS` 지원 여부는 WinCE 실기에서 직접 검증되지 않았다.

"버퍼가 절반이므로 2배 빠르다"는 결론은 내리지 않는다. 위 수치는 호스트 Unicorn 벽시계 기반이며 실제 OMAP/GDI/LCD 처리량이나 실차 FPS를 대표하지 않는다. 실기에서 16bpp DIB 경로가 검증되고 동일 계측으로 BGRA보다 빠르기 전까지 기본 경로를 바꾸지 않는다.

## 6. 재현 명령

```powershell
Set-Location F:\i30-gen2-android-auto
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$ssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'

python -m unittest tests.test_aare_rgb565 -v
foreach ($format in 'bgra','rgb565') {
    python tools/build_ce_usb.py --compiler $cc `
        --bearssl-source build/ce-tls-dependency/bearssl-0.6 `
        --h264-source build/ce-video-dependency/h264bsd `
        --video-format $format "build/aare-$format-compare"
    foreach ($n in 1,2,3,4) {
        python tools/emulate_ce_usb.py "build/aare-$format-compare" --tls-openssl $ssl `
            --continuous-seconds 2 --continuous-fps 30 --profile-video `
            > "build/aare-$format-bench$n.json"
    }
    python tools/report_aare_video_compare.py "build/aare-$format-bench" --runs 4
}
python tools/emulate_ce_usb.py build/aare-rgb565-compare --tls-openssl $ssl `
    --projection --reject-rgb565
```

원본 계측 JSON: `build/aare-{bgra,rgb565}-bench{1..4}.json`, 요약: `build/aare-{bgra,rgb565}-summary.json`, 회귀: `build/aare-{bgra,rgb565}-regression.json`. 이 파일들은 빌드 산출물로 커밋하지 않는다.
