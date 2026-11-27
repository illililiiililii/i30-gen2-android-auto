# AARE H.264 디코더 집중 최적화 결과

작성일: 2026-11-27 · 기준 커밋: `c815db9` (작업 시작 시점) · 대상: GD13MY.KOR.SOP.00.061 / Windows CE 6.0 guest

## 1. 목적과 판정 기준

h264bsd 내부 병목을 먼저 측정하고, 동일 H.264 입력에서 컴파일러/아키텍처 옵션과 작은 소스 최적화 후보를 짧게 선별한 뒤 유효 후보만 반복 측정했다. 목표는 실기 성능 주장이 아니라 **재현 가능한 ARM fixture에서 검증된 후보만 남기는 것**이다.

사전 판정 기준은 다음과 같다.

- 디코더 시간, `i30_video_push`, 프레임 ACK 간격, 전체 벽시계가 함께 개선되어야 후보를 유효하다고 본다.
- 60/60 ACK·표시, guest heap 피크 동일, 종료 시 live allocation 0을 유지해야 한다.
- ARM/API/Unicorn 결과는 실기 OMAP/GDI/LCD 성능으로 승격하지 않는다.
- 실기 호환성이 없는 컴파일 옵션과 NEON은 기본값에 넣지 않는다.

순정 펌웨어, 커널, BSP, 부트로더, MICOM, 파티션, TLS 인증 로직, DSP ABI는 변경하지 않았다.

## 2. 도구와 구현 변경

| 파일 | 변경 내용 |
|---|---|
| `tools/build_ce_usb.py` | `--codegen` 프리셋 6종, `--h264-profile`, `--h264-fast-copy` 추가. `abi.json`에 codegen, color path, h264bsd 함수 RVA, profile hook RVA, fast-copy 사용 여부 기록. Cortex-A8 빌드용 `-mword-relocations`와 ARM `MOVW/MOVT` 재배치 처리 추가. 기본 codegen은 기존 `armv4t-os`. |
| `tools/emulate_ce_usb.py` | `--profile-h264-functions`와 GCC `-finstrument-functions` 기반 함수별 inclusive 시간 집계 추가. Unicorn CPU 모델을 Cortex-A8로 명시해 ARMv7/NEON 산출물도 시험 가능하게 함. 모든 비교는 이 동일 설정에서 재실행했다. 실행 실패 시 PC/RVA를 포함하도록 오류 reporting 개선. |
| `src/ce/ce_aa_profile.c` | instrumented 빌드에서 `__cyg_profile_func_enter/exit`을 해석하기 위한 최소 freestanding stub. 배포 빌드에는 포함되지 않는다. |
| h264bsd fast-copy 후보 | 빌드 시 원본 h264bsd 소스를 임시 복사하고 `FillRow1()`의 `memcpy(fill, ref, center)` 한 줄만 alignment 검사 + word loop + byte fallback으로 치환. 원본 의존성과 배포 기본 빌드는 수정하지 않는다. |

`i30usb.dll` SHA-256 앞 16자리: baseline `8546BB15E0B84E68`, fast-copy `F02621825A147F11`. baseline 해시는 기존 `build/aare-bgra-compare` 산출물과 동일하다.

## 3. 내부 함수 프로파일

`--h264-profile --profile-h264-functions`로 15프레임(1초, 15 FPS)을 측정했다. 시간은 ARM 코드 + Unicorn API double의 벽시계이며 훅 오버헤드를 포함한다. 숫자 자체를 실기 ms로 해석하지 않고 순위 파악에만 사용했다.

| 함수 | baseline inclusive ms | fast-copy inclusive ms | 호출 수 |
|---|---:|---:|---:|
| `h264bsdDecode` | 22,854.92 | 21,559.86 | 109 |
| `h264bsdDecodeSliceData` | 22,245.36 | 20,982.61 | 105 |
| `h264bsdDecodeMacroblock` | 18,504.84 | 17,469.18 | 22,500 |
| `h264bsdInterPrediction` | 14,954.96 | 14,163.13 | 19,720 |
| `h264bsdPredictSamples` | 12,489.66 | 11,911.99 | 19,720 |
| `h264bsdFillBlock` | 11,099.55 | 10,617.11 | 58,010 |
| `PredictChroma` | 6,144.54 | 5,864.39 | 19,720 |
| `FillRow1` | 2,314.39 | 1,791.62 | 621,840 |

상위 병목은 inter prediction의 reference sample 복사 경로(`PredictSamples` → `FillBlock` → `FillRow1`)였다. `FillRow1`이 프레임당 약 41,456회 호출되고, 기존 코드는 out-of-line `memcpy`를 호출한다. 이 지점을 word 복사로 바꾼 것이 유일한 소스 후보다. instrumented 빌드에서는 `FillRow1`이 약 22.6% 줄었고 상위 호출자도 함께 줄었다.

## 4. 짧은 후보 선별 (1초 / 15 FPS)

같은 H.264 입력으로 각 codegen을 1회씩 실행했다. 중앙값은 프레임별 ARM 함수 시간이다.

| codegen | decode ms | BGRA 변환 ms | video_push ms | ACK 간격 ms | 벽시계 s | 결과 |
|---|---:|---:|---:|---:|---:|---|
| `armv4t-os` (현재 기본) | 86.50 | 34.96 | 124.63 | 131.51 | 2.909 | 기준 |
| `armv4t-o2` | 87.66 | 46.07 | 137.74 | 144.13 | 3.049 | 느림 |
| `armv4t-o3` | 92.09 | 36.30 | 133.38 | 139.61 | 2.975 | 느림 |
| `cortex-a8-o2` | 104.93 | 53.68 | 165.18 | 172.16 | 3.392 | 느림 |
| `cortex-a8-o3` | 97.73 | 40.38 | 143.10 | 149.61 | 3.069 | 느림 |
| `cortex-a8-neon-o3` | — | — | — | — | — | `UC_ERR_INSN_INVALID`, RVA `0x1664`의 `vld1.8`에서 중단 |

wine/ARMv4T 기본값이 모든 arithmetic codegen보다 빨랐다. Cortex-A8 빌드는 빌드는 성공했지만 `-mword-relocations`와 v5te softfp runtime 라이브러리 연결이 필요했고, Unicorn에서 실행은 됐으나 성능 이득이 없었다. NEON 산출물은 vector 명령 226개를 포함했지만 fixture가 실행할 수 없어 후보에서 제외했다.

## 5. 반복 비교 (2초 / 30 FPS, 60프레임)

짧은 선별에서 유일하게 이득 가능성이 있던 `armv4t-o2`와 fast-copy를 baseline과 같은 조건으로 3회 반복했다. 값은 3회 중앙값이다.

| 지표 | baseline | `armv4t-o2` | fast-copy (opt-in) |
|---|---:|---:|---:|
| `h264bsdDecode` | 88.057 ms | 85.863 ms | **76.206 ms (−13.5%)** |
| BGRA 변환 | 36.611 ms | 46.638 ms | 37.861 ms (차이 없음) |
| `i30_video_push` | 128.905 ms | 136.555 ms | **118.086 ms (−8.4%)** |
| 프레임 ACK 간격 | 134.826 ms | 142.757 ms | **124.117 ms (−7.9%)** |
| 전체 벽시계 | 9.187 s | 9.558 s | **8.648 s (−5.9%)** |
| guest heap 피크 | 5,231,760 B | 5,231,760 B | 5,231,760 B |
| ACK / 표시 | 60 / 60 | 60 / 60 | 60 / 60 |
| 종료 시 live allocation | 0 | 0 | 0 |

O2는 decode 단일 항목만 소폭 빨라졌고 BGRA 변환이 크게 느려져 전체적으로 손해였다. fast-copy는 decode·push·ACK 간격·벽시계가 같은 방향으로 개선됐고 프레임 완결성과 메모리 지표는 유지됐다.

현재 기본값은 **BGRA + ARMv4T/`-Os` + 일반 `memcpy` 경로**로 유지한다. fast-copy는 재현 가능한 ARM fixture 이득이 확인된 유일한 후보이지만 실기 타이밍과 WinCE 런타임 호환성이 아직 확인되지 않았으므로 `--h264-fast-copy` opt-in 빌드로만 보존한다.

## 6. 회귀 시험

최종 도구로 baseline과 fast-copy를 각각 빌드해 다음을 실행했다.

```powershell
python -m unittest discover -s tests
python tools/emulate_ce_usb.py <artifact> --tls-openssl $ssl `
    --projection --stress-rounds 5 --navigation $nav
```

| 검증 | baseline | fast-copy |
|---|---|---|
| unittest | 97개, 실패 0, skip 1 | 동일 |
| USB switch/version/오류 케이스 | PASS | PASS |
| 설정·preferences·owner | PASS | PASS |
| TLS 상호 인증 + AARE projection 4모드 | PASS | PASS |
| 디스플레이 선점 / video deadline / control interleaving | PASS | PASS |
| 분리·재연결·비정상 종료 5라운드 | PASS, live allocation 0 | PASS, live allocation 0 |
| guest heap 피크 | 5,230,808 B | 5,230,808 B |
| 순정 터치 trampoline 11케이스 | 11/11 PASS | 11/11 PASS |

TLS 로그의 leaf SHA-256은 fixture가 실행마다 새 인증서를 생성하므로 두 빌드 간 차이가 났고, 인증 자체는 양쪽 모두 성공했다. stress의 프레임 ACK 간격은 fast-copy에서 전반적으로 짧아져 성능 결과와 같은 방향이었다. 유일한 unittest skip은 native GPTimer block-clock DLL이 없는 환경 조건이다.

## 7. 한계와 결정

- Unicorn 벽시계는 실제 OMAP3530 클록, WinCE GDI, LCD DMA를 대리하지 않는다. 따라서 **실기 FPS나 ±5% 개선을 주장하지 않는다.**
- NEON은 TI OMAP3530/Cortex-A8 사양에 존재하지만 GD13MY 런타임 사용 여부, softfp 호환, 실기 WinCE 실행이 검증되지 않았다. 현재 fixture에서도 `vld1.8`에서 실패했다. 실험 옵션으로만 남긴다.
- Cortex-A8 codegen은 실기 배포 호환성이 확인되지 않았고 측정도 느렸다. 기본값으로 승격하지 않는다.
- fast-copy는 단일 소스 라인 치환이며 정렬되지 않은 포인터/길이는 byte fallback으로 처리한다. 그럼에도 실기 Measurement 전까지 기본값을 바꾸지 않는다.
- 물리 USB는 연결 대기 상태였으므로 실폰/실차 시험은 포함되지 않았다.

## 8. 재현 명령

```powershell
Set-Location F:\i30-gen2-android-auto
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$ssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'
$nav = 'build/gd13my-aa-autostart-v8/navigation/GDdNavi.exe'

# 기본 빌드와 fast-copy opt-in 빌드
python tools/build_ce_usb.py --compiler $cc `
    --bearssl-source build/ce-tls-dependency/bearssl-0.6 `
    --h264-source build/ce-video-dependency/h264bsd build/h264-final-baseline
python tools/build_ce_usb.py --compiler $cc `
    --bearssl-source build/ce-tls-dependency/bearssl-0.6 `
    --h264-source build/ce-video-dependency/h264bsd --h264-fast-copy build/h264-fast-copy-tool

# 내부 함수 프로파일
python tools/build_ce_usb.py --compiler $cc `
    --bearssl-source build/ce-tls-dependency/bearssl-0.6 `
    --h264-source build/ce-video-dependency/h264bsd --h264-profile build/h264-final-profile
python tools/emulate_ce_usb.py build/h264-final-profile --tls-openssl $ssl `
    --continuous-seconds 1 --continuous-fps 15 --profile-h264-functions `
    > build/h264-final-internal-profile.json

# codegen 선별: --codegen {armv4t-o2,armv4t-o3,cortex-a8-o2,cortex-a8-o3,cortex-a8-neon-o3}
python tools/emulate_ce_usb.py build/h264-final-baseline --tls-openssl $ssl `
    --continuous-seconds 1 --continuous-fps 15 --profile-video > build/h264-screen.json

# 반복 벤치마크: 각 빌드 3회
python tools/emulate_ce_usb.py build/h264-final-baseline --tls-openssl $ssl `
    --continuous-seconds 2 --continuous-fps 30 --profile-video `
    > build/h264-repeat-baseline-bench1.json
python tools/report_aare_video_compare.py build/h264-repeat-baseline-bench --runs 3

# 회귀
python -m unittest discover -s tests
python tools/emulate_ce_usb.py build/h264-fast-copy-tool --tls-openssl $ssl `
    --projection --stress-rounds 5 --navigation $nav > build/h264-fast-copy-regression.json
```

원본 JSON·빌드 산출물은 `build/` 아래 로컬에만 있으며 커밋하지 않는다. 색상 경로 기본값 근거는 [RGB565 결과](RGB565_OPTIMIZATION_RESULTS.md), 전체 회귀 기준은 [AARE 성능 회귀](../../testing/AARE_PERFORMANCE_REGRESSION.md)를 참고한다.
