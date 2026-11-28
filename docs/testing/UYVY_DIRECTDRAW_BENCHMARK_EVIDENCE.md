# UYVY DirectDraw 3경로 벤치마크 증거 — 2026-11-28

작업 기준: `feature/uyvy-directdraw-backend`, `31e02e7` 위 작업 트리. 이 문서는 로컬 ARM fixture 증거만 다룬다. 기본 배포 경로는 여전히 BGRA + GDI이며, DirectDraw는 별도 opt-in이다.

분류:

- **VERIFIED**: 이 세션의 로컬 파일, 실행 반환값, Unicorn 벽시계 시간, mock 호출 기록이 직접 보여줌.
- **INFERRED**: 동일 코드 경로와 측정값에서 도출한 해석. GD13MY 실제 동작 확정 아님.
- **UNKNOWN**: 공개 문서 또는 현재 로컬 증거만으로 확인되지 않은 실기 동작.

## 1. VERIFIED — 측정 조건

동일한 H.264 입력 바이트를 네 출력 모드에 사용했다.

| 항목 | 값 |
|---|---|
| 프레임 | 800×480, libx264 `yuv420p ultrafast zerolatency baseline` |
| 픽셀 | Y=81, U=90, V=240 |
| mock surface pitch | 1,632 B (`800*2+32`) |
| 반복 | 모드당 5회, 중앙값 사용 |
| 실행기 | ARM Unicorn, host API/COM doubles |
| 시간 의미 | guest ARM 코드 + double 호출의 호스트 벽시계 ms |

DirectDraw double은 CE6 `IDirectDraw`/`IDirectDrawSurface` vtable 슬롯, 108-byte `DDSURFACEDESC`, `LoadLibraryW`/`GetProcAddressA`/`FreeLibrary`, `DDSCL_NORMAL(0)`, 112/128-byte `DDCAPS` 시도를 기록한다. mock `DDRAW.dll`은 실기 드라이버가 아니다.

측정 산출물 `build/uyvy-three-path-benchmark.json`은 로컬 `build/` 아래에 있으며 원격 배포 산출물이 아니다.

## 2. VERIFIED — 결과

각 모드 5회 중앙값이다. `video push`는 디코더 초기화와 1프레임 출력까지 포함한다. 할당 14회는 입력·디코더·출력 초기화와 1프레임을 합친 수이며, 반복 종료 시 잔존 할당은 0이었다.

| 모드 | 변환/패킹 | `i30_video_push` | 할당 | peak 요청 바이트 |
|---|---:|---:|---:|---:|
| BGRA + GDI | `h264bsdConvertToBGRA` 305.584 ms | 550.022 ms | 14 | 5,122,662 |
| UYVY staging + BGRA/GDI | `stage_uyvy` 56.251 ms | 290.659 ms | 14 | 4,370,022 |
| UYVY DirectDraw | `i30_ddraw_present` 64.257 ms | 295.923 ms | 14 | 3,586,662 |
| UYVY DirectDraw + flip | `i30_ddraw_present` 69.717 ms | 334.510 ms | 14 | 3,586,662 |

DirectDraw 성공 경로에서는 `StretchDIBits`가 호출되지 않았다. 매 실행에서 `DDRAW.dll` 로드 1회, `FreeLibrary` 1회, surface/DD 참조 잔존 0, `Lock`/`Unlock` 각 1회, overlay `Show` 1회를 확인했다. flip 빌드는 `Flip` 1회와 `GetFlipStatus` 1회를 기록했다. UYVY 바이트는 기대값 `(U,Y0,V,Y1)=(90,81,240,81)`과 행 패딩까지 일치했다.

빌드 산출물 SHA-256:

| 모드 | artifact | `abi.json` 상태 |
|---|---|---|
| BGRA | `06776a82351beba3a5ae2ccfce838c56bb233868f09448bdbe534e17fe904224` | `bgra`, flip `false` |
| Staging | `009059b91ed583c5e3d67d82e7b9d9e5346415ae60332723f4be4bfa61b7fc1b` | `uyvy-staging`, flip `false` |
| DirectDraw | `577353493da86b6d9ae39387a7139df8da53b7848187b4de8e65bfe60e043006` | `ddraw`, flip `false` |
| DirectDraw flip | `f461ed50825c6fffad8ac3e67a9cb639771b467f5323e040e8e884097d95b224` | `ddraw`, flip `true` |

기본 USB artifact `build/gd13my-ce-usb-bgra-final/i30usb.dll`의 ABI는 `video_format='bgra'`, `uyvy_ddraw=False`, DirectDraw loader import 없음이다. `--video-format ddraw` artifact는 세 loader import와 `uyvy_ddraw=True`를 가지며 PE import table에는 `DDRAW.dll` 정적 import가 없다.

## 3. VERIFIED — 회귀 시험

| 시험 | 결과 |
|---|---|
| `tests.test_aare_uyvy_ddraw`, `tests.test_aare_uyvy_ddraw_arm` | 20개 통과 |
| `tests.test_aare_uyvy_ddraw_virtual` | 6개 통과, skip 없음 |
| `python -m unittest discover -s tests` | 141개 실행, 1개 환경 조건 skip, 실패 0 |
| `build/gd13my-ce-usb-ddraw`, USB/TLS + projection + 5 stress rounds | 통과, 5/5 표시, 세션 종료 후 live allocation 0 |
| `build/gd13my-ce-usb-ddraw-flip`, 동일 조건 | 통과, 5/5 표시, 세션 종료 후 live allocation 0 |

mock 실패 주입(`library`, `proc`, `create`, `cooperative`, `caps`, `fourcc`, `surface`, `lost`, `restore`, `lock`, `bad-pitch`, `bad-xpitch`, `zero-fields`, `unlock`, `overlay`, `overlay-lost`, `no-back`, `flip`, `flip-timeout`)에서 거부된 프레임은 같은 디코딩 결과로 BGRA+GDI 폴백했고, overlay를 숨기며, flip 실패 시 백엔드를 세션에서 비활성화했다. 참조와 힙 잔존은 0이었다.

## 4. INFERRED — 해석

- DirectDraw 경로가 BGRA보다 짧은 벽시계를 보인 것은 UYVY 쓰기량이 프레임당 768,000 B, BGRA가 1,536,000 B이고 성공 경로에서 BGRA 임시 버퍼를 만들지 않기 때문으로 보인다. peak 요청 바이트 차이(5,122,662 → 3,586,662)는 이와 일치한다.
- flip 중앙값이 no-flip보다 느렸으므로 이 fixture가 flip 이득을 입증하지는 않는다. flip은 실패 시 즉시 비활성화되는 안전 옵션으로만 남긴다.
- `DDSCL_NORMAL`은 순정 지도의 전체 화면 소유권을 가져가지 않기 위한 선택이다. 실기 z-order 결과는 측정하지 않았다.

이 수치는 이전 `docs/testing/AARE_STOCK_RESOURCE_BASELINE.md`의 BGRA 263.62 ms / push 504.58 ms와 실행 조건이 달라 직접 비교·합산하지 않는다. 위 표는 한 번의 5회 반복 실행에서 네 모드를 함께 측정한 값이다.

## 5. UNKNOWN — 실기 게이트

다음은 mock이 증명하지 못한다.

- GD13MY `DDRAW.dll`의 실제 overlay caps, UYVY FourCC 수락, 800×480 UYVY surface 생성.
- `DDCAPS` 오프셋 `+0x48`의 overlay-cap 해석과 `GetFlipStatus` vtable 슬롯 `+0x34`는 CE6 선언 순서와 순정 호출 흐름에서 도출한 **INFERRED** 값이다. stock ARM 직접 호출처는 확인하지 못했다.
- 실제 `Lock`의 pitch 부호, 회전 방향, `lXPitch`, `dwSurfaceSize`, surface 메모리 정렬.
- 실제 overlay show/hide, z-order, color key, stretch 제한, backbuffer 수, Flip 완료와 VSync.
- 후방카메라 점유 중 overlay 반환과 순정 지도 표시권 복구. 카메라/지도 프로세스 종료는 하지 않는다.
- 실제 LCD 출력, 화면 품질, guest/head-unit FPS, USB ACK 간격, 장시간 누수. 가상폰 LCD 검증은 mock overlay가 LCD를 칠하지 않으므로 DirectDraw 출력 증거로 사용할 수 없다.

따라서 기본 빌드는 변경하지 않고, 실기 게이트를 통과하기 전까지 `--video-format ddraw` / `--uyvy-ddraw` / `--ddraw-flip`은 opt-in으로 유지한다.

## 6. 재현 명령

PowerShell, 저장소 루트에서 실행:

```powershell
$py = "$env:LOCALAPPDATA/i30-phase2-venv/Scripts/python.exe"
$cc = "$env:LOCALAPPDATA/i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe"
$h = 'build/ce-video-dependency/h264bsd'
$bear = 'build/ce-tls-dependency/bearssl-0.6'
$ssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'

# standalone probe artifacts
& $py tools/build_ce_minimal.py --compiler $cc --h264-source $h
& $py tools/build_ce_minimal.py --compiler $cc --h264-source $h --uyvy-staging
& $py tools/build_ce_minimal.py --compiler $cc --h264-source $h --uyvy-ddraw
Copy-Item -Recurse build/gd13my-ce-uyvy-ddraw build/gd13my-ce-uyvy-ddraw-noflip
& $py tools/build_ce_minimal.py --compiler $cc --h264-source $h --uyvy-ddraw --ddraw-flip

# USB/TLS artifacts
& $py tools/build_ce_usb.py --compiler $cc --bearssl-source $bear --h264-source $h build/gd13my-ce-usb-bgra-final
& $py tools/build_ce_usb.py --compiler $cc --bearssl-source $bear --h264-source $h --video-format uyvy-staging build/gd13my-ce-usb-staging-final
& $py tools/build_ce_usb.py --compiler $cc --bearssl-source $bear --h264-source $h --video-format ddraw build/gd13my-ce-usb-ddraw
& $py tools/build_ce_usb.py --compiler $cc --bearssl-source $bear --h264-source $h --video-format ddraw --ddraw-flip build/gd13my-ce-usb-ddraw-flip

# focused and full tests
& $py -m unittest tests.test_aare_uyvy_ddraw tests.test_aare_uyvy_ddraw_arm -q
& $py -m unittest tests.test_aare_uyvy_ddraw_virtual -q
& $py -m unittest discover -s tests

# ARM USB/TLS regression
& $py tools/emulate_ce_usb.py build/gd13my-ce-usb-ddraw --tls-openssl $ssl --projection --stress-rounds 5
& $py tools/emulate_ce_usb.py build/gd13my-ce-usb-ddraw-flip --tls-openssl $ssl --projection --stress-rounds 5

# three-path benchmark
& $py tools/verify_ce_uyvy_three_path_benchmark.py `
    --bgra build/gd13my-ce-video/i30video.exe `
    --staging build/gd13my-ce-uyvy-staging/i30video.exe `
    --ddraw build/gd13my-ce-uyvy-ddraw-noflip/i30video.exe `
    --ddraw-flip build/gd13my-ce-uyvy-ddraw/i30video.exe `
    --runs 5 --output build/uyvy-three-path-benchmark.json
```

원본 로그: `build/uyvy-directdraw-final-regression.log`, `build/gd13my-ce-usb-ddraw-regression.log`, `build/gd13my-ce-usb-ddraw-flip-regression.log`, `build/uyvy-three-path-benchmark-stdout.json`.
