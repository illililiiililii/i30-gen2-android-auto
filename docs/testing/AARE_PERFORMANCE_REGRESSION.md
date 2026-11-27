# AARE 영상 성능 변경 회귀 시험 결과

작성일: 2026-11-27 · 브랜치: `feature/aare-performance-display` · 기준 커밋: `aaec50e`

## 1. 범위와 빌드

| 빌드 | `--video-format` | 용도 |
|---|---|---|
| `build/aare-bgra-compare` | `bgra` (기본값) | 기존 경로 / 배포 기본값 유지 확인 |
| `build/aare-rgb565-compare` | `rgb565` | 직접 변환 실험 경로, 16bpp 거부 폴백까지 확인 |

두 빌드는 같은 ARM 컴파일러(`arm-gnu-14.2`)와 같은 bearssl/h264bsd 소스로 만들고, `abi.json`의 SHA-256·RVA를 emulated fixture가 검증했다. 실폰, 실차, 물리 헤드유닛 시험은 포함하지 않는다.

## 2. 실행 명령

```powershell
Set-Location F:\i30-gen2-android-auto
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$ssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'
$nav = 'build/gd13my-aa-autostart-v8/navigation/GDdNavi.exe'

python -m unittest discover -s tests
python -m unittest tests.test_aare_rgb565 -v

foreach ($format in 'bgra','rgb565') {
    python tools/build_ce_usb.py --compiler $cc `
        --bearssl-source build/ce-tls-dependency/bearssl-0.6 `
        --h264-source build/ce-video-dependency/h264bsd `
        --video-format $format "build/aare-$format-compare"
}
python tools/emulate_ce_usb.py build/aare-bgra-compare --tls-openssl $ssl `
    --projection --stress-rounds 5 --navigation $nav > build/aare-bgra-regression.json
python tools/emulate_ce_usb.py build/aare-rgb565-compare --tls-openssl $ssl `
    --projection --reject-rgb565 --stress-rounds 5 --navigation $nav > build/aare-rgb565-regression.json
```

성능 비교 명령과 수치는 [RGB565_OPTIMIZATION_RESULTS.md](../android-auto/aare/RGB565_OPTIMIZATION_RESULTS.md)에 정리했다.

## 3. 결과 요약

| 검증 | BGRA 빌드 | RGB565 빌드 | 근거 |
|---|---|---|---|
| 단위 테스트 전체 | `Ran 97 tests … OK (skipped=1)` | 동일 | `build/unittest-full.log` |
| RGB565 변환 단위 시험 | 해당 없음 | 4/4 PASS | `tests.test_aare_rgb565`: 마스크, 채널 순서, BGRA 동일 반올림, top-down 밀도 |
| USB switch/version/오류 케이스 fixture | PASS | PASS | `emulate_ce_usb.py` 종료 코드 0, `client` 결과 |
| 설정 저장·독립 플래그·preferences·owner | PASS | PASS | same `settings`/`preferences`/`projection_owner` 결과 |
| TLS 1.2 상호 인증 + AARE 프로파일 | PASS | PASS | `native_tls` |
| 첫 프레임 및 GDI 블릿 | 32bpp 800×480 | 16bpp `BI_BITFIELDS` 800×480, 마스크 검증 | `video` projection mode |
| 디스플레이 선점 / video deadline / control interleaving | PASS | PASS | 4개 projection mode |
| BGRA 폴백 (16bpp 거부 주입) | 기본 경로로 상시 사용 | PASS: 거부 후 32bpp 블릿으로 복구, live allocation 0 | `--reject-rgb565`, `rgb565_fallback` |
| USB 분리/재연결·카메라 우선·비정상 종료 정리 | PASS (5 라운드) | PASS (5 라운드) | `native_stress`: `abrupt_cleanup=5`, `video_restart_painted_frames=2`, `resident_painted_frames=5`, 종료 할당 0 |
| 순정 터치 trampoline | 11/11 PASS | 11/11 PASS | v8 `GDdNavi.exe`, `stock_touch_route` |
| 고동작 30 FPS 2초 | 60/60 ACK·표시 | 60/60 ACK·표시 | `build/aare-{bgra,rgb565}-motion.json` |
| 영상 성능 | 기준 | **개선 없음, 느림** | 중앙값 변환 37.39 ms → 55.58 ms, ACK 간격 134.50 → 152.14 ms |

### Skip/Fail 분류

- 전체 unittest의 유일한 skip은 `test_counter_matches_python_bank_at_multiple_guest_times`로, `"Requires a native block-clock DLL with GPTimer read support"` 환경 조건이다. 코드 회귀가 아니라 네이티브 DLL 미보유에 따른 환경 skip이다.
- 이전 문서의 `93 PASS / 7 Skip` 보고는 당시 테스트 discovery 집합과 환경이 달라 직접 비교할 수 없다. 이번 실행은 97개 발견/1 skip이며 실패는 0이다. skip 증가로 해석하지 않는다.
- 초기 회귀 실행에서 `build/codex-post-auth-integration/navigation/GDdNavi.exe`로 `before-projection` 터치 케이스가 실패했다. 이는 최신 v8 이미지의 `GDdNavi.exe`와 해당 오래된 패치 산출물의 thunk 불일치(환경/산출물 버전 문제)였고, 최신 `build/gd13my-aa-autostart-v8/navigation/GDdNavi.exe`로 재실행해 11/11 PASS했다. 이번 소스 변경과 무관하다.
- RGB565 fallback 시험 최초 버전은 거부 후에도 fixture가 16bpp 헤더를 기대해 실패했다. 검증기를 실제 DIB 비트수(base 16, fallback 32)를 보도록 수정했고, guest 코드 변경 없이 통과했다.

## 4. 한계

- Unicorn/WinCE API double의 벽시계 시간은 실제 OMAP CPU, GDI 구현, LCD DMA 처리량을 대리하지 않는다. 실기 계측 없이는 성능 개선을 주장하지 않는다.
- 16bpp `BI_BITFIELDS` DIB 수용 여부와 실기 색상은 WinCE 실기에서 검증되지 않았다. 따라서 BGRA가 배포 기본값이고 폴백이 유지된다.
- 실폰 USB 권한 대화상자, 티맵 분할 화면, 카카오내비, 물리 후방카메라 타이밍은 이 시험에 포함되지 않았다. 관련 문서: [TMAP_DISPLAY_IMPLEMENTATION.md](../android-auto/aare/TMAP_DISPLAY_IMPLEMENTATION.md)

## 5. 판정

회귀 항목은 모두 통과했고 메모리 누수·누락 프레임·좌표/헤더 회귀는 관측되지 않았다. 다만 목적인 성능 개선은 이 환경에서 재현되지 않았으므로 **기본 경로를 BGRA로 유지**하고 RGB565는 실기 측정을 위한 opt-in 빌드로만 남긴다.
