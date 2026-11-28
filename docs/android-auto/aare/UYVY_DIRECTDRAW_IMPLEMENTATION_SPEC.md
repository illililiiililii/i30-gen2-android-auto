# UYVY DirectDraw 구현 명세 — Codex 인계용

작성일: 2026-11-28 · 명세 기준 커밋: `68ed2f4` · 구현 작업 기준: `31e02e7` / `feature/uyvy-directdraw-backend`

## 1. 범위

이 문서는 GD13MY Windows CE 6.0에서 AARE 영상을 UYVY DirectDraw 오버레이로 출력하기 위한 **설계·구현 명세**다. 데스크톱 Windows DirectDraw 문서를 CE 근거로 사용하지 않는다. 제공된 `ms893918`은 CE .NET 4.2 계열, `ms923165`는 CE 5.0 드라이버 DDHAL 콜백이므로 CE6 앱 API 계약으로 쓰지 않는다.

분류:

- **VERIFIED**: 인용한 문서/로컬 파일이 명시적으로 보여줌.
- **INFERRED**:VERIFIED 사실에서 도출한 구현 방침. GD13MY 동작 확정 아님.
- **UNKNOWN**: 공개 문서나 현재 증거로 확인되지 않음.

**현재 상태: opt-in 구현 및 ARM/mock 검증 완료, 실기 검증 전.** 기존 기본 배포 경로는 BGRA + GDI이며, 변경하지 않는다. DDRAW 백엔드는 별도 매크로와 `feature/uyvy-directdraw-backend` 브랜치에만 있다. 실폰/실차 검증 전에는 기본값으로 켜지 않는다. 같은 H.264 입력의 4경로 ARM fixture 중앙값과 한계는 [3경로 벤치마크 증거](../../testing/UYVY_DIRECTDRAW_BENCHMARK_EVIDENCE.md)에 있다.

## 2. 기존 코드 연결 지점 (VERIFIED)

| 위치 | 현재 계약 |
|---|---|
| `src/ce/ce_aa_video.h:14-23` | `I30VideoTarget`에 `begin`, `end`, 조건부 `present_yuv(context, geometry, i420)` 존재. `present_yuv`는 동기 I420 소비자이며 성공 시 1, 실패 시 0 반환. 디코더가 반환 후 입력 버퍼를 재사용할 수 있음 |
| `src/ce/ce_aa_video.c:196-210` | `I30_VIDEO_UYVY_STAGING`일 때 `h264bsdNextOutputPicture()` 결과를 `present_yuv`에 먼저 넘기고, 실패하면 RGB565/BGRA 폴백 |
| `src/ce/ce_aa_video.h:6`, `src/ce/ce_aa_video.c:178-190` | 출력 계약은 800×480. crop/stride 검사와 `I30VideoGeometry{coded_w,coded_h,left,top,width,height}` 유지 |
| `src/ce/ce_aa_uyvy.h:11-43` | `i30_pack_uyvy()`는 이미 잠긴 top-down 표면에 `U Y0 V Y1` 순서로 기록. even width/height/left/coded 치수 요구. pitch/size 경계 검사. 행 패딩은 건드리지 않음 |
| `tools/verify_ce_uyvy_staging.py` | 메모리 fixture. `PITCH=800*2+32`, `SURFACE_SIZE=PITCH*480`, padding `0xA5`. 실제 DDRAW Lock 결과가 아님 |
| `docs/testing/AARE_STOCK_RESOURCE_BASELINE.md` §순정 영상 출력 / §HAL과 ARM 성능 대조 | 순정 `.061 LibVideo.dll`의 `lVideoShowOverlay`(`0x1011d0`)가 상태 객체와 32바이트 픽셀 포맷(`0x10b0e4`, flags `0x4`, FourCC `UYVY`)을 사용. 기본 720×576, backbuffer 요청 2, 생성 `0x1033b0`, 표시/숨김 `0x10352c`/`0x1035bc`, Lock 실패 `0x103ce4`, 크기 변경 `0x103898`/`0x1038c4`, 해제 시 숨김 `0x102b34`. `.061 DDRAW.dll` ordinal 1에 `DirectDrawCreate` 존재 |
| `src/ce/ce_aa_uyvy_ddraw.h/.c` | opt-in 백엔드 구현. `LoadLibraryW`/`GetProcAddressA`/`FreeLibrary`, CE6 vtable wrapper, caps/FourCC 확인, primary+UYVY overlay 생성, Lock/Unlock, `UpdateOverlay`, restore, hide, release. 정적 `DDRAW.dll` import 없음 |
| `src/ce/ce_aa_projection.c`, `src/ce/ce_aa_video.c/.h` | 카메라/네이티브 표시권이 안전할 때만 `present_yuv` 호출. 실패하면 같은 디코딩 결과로 BGRA/GDI. reset, STOP/CLOSE, disconnect, unsafe frame에서 overlay 숨김 |
| `tools/build_ce_minimal.py`, `tools/build_ce_usb.py` | `--uyvy-ddraw`, `--video-format ddraw`, `--ddraw-flip`, `I30_VIDEO_UYVY_DIRECTDRAW`, `I30_DDRAW_FLIP`. `abi.json`에 loader import와 상태 기록. 기본값은 `bgra` |
| `tests/test_aare_uyvy_ddraw*.py`, `tools/emulate_ce_usb.py` | host C harness, ARM Unicorn COM double, 가상 USB/TLS 계약 테스트. 실기 드라이버가 아님 |

ARM fixture 수치(BGRA 변환 263.62 ms → UYVY 패킹 55.19 ms, video push 504.58 ms → 292.90 ms)는 Unicorn 벽시계 시간이며 실제 오버레이 전송, VSync, USB ACK를 포함하지 않는다. 최종 4경로 재측정은 [별도 증거](../../testing/UYVY_DIRECTDRAW_BENCHMARK_EVIDENCE.md)에 있다. 두 실행의 호스트 조건이 달라 수치를 직접 합치지 않는다. **실기 표시 성능은 UNKNOWN.**

## 3. 구현 명세 표

| 구현 항목 | 대상 파일/함수 | 호출 계약 | 직접 근거 | 미확인 사항 | 실패 처리 |
|---|---|---|---|---|---|
| CE6 API 세대 | `src/ce/ce_aa_uyvy_ddraw.c/.h` | `IDirectDraw`, `IDirectDrawSurface`, `DDSURFACEDESC`, `DDSCAPS` 사용. `IDirectDraw4`, `IDirectDrawSurface5`, `DDSURFACEDESC2`, `DDSCAPS2` 사용 금지 | CE6 migration: `https://learn.microsoft.com/en-us/previous-versions/aa916681(v=msdn.10)` §Interfaces, `https://learn.microsoft.com/en-us/previous-versions/aa919057(v=msdn.10)` §Structures, `https://learn.microsoft.com/en-us/previous-versions/aa915462(v=msdn.10)` §Flags. VERIFIED | 순정 DLL이 내부적으로 사용하는 인터페이스 버전. UNKNOWN | 헤더 컴파일 실패 시 백엔드 비활성화 |
| DD 객체 생성 | `i30_ddraw_open()` | `DirectDrawCreate(NULL, &dd, NULL)`; active display. `pUnkOuter`는 NULL. CE6 권장: `SetCooperativeLevel(hwnd, DDSCL_FULLSCREEN)` | `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490059(v=winembedded.60)` §Syntax/Parameters/Remarks, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491007(v=winembedded.60)` §Initializing DirectDraw. VERIFIED | GD13MY에서 cooperative level 요구 여부. UNKNOWN | 실패 시 기존 `I30VideoTarget` GDI 경로 유지 |
| capability 확인 | `i30_ddraw_check_caps()` | `GetCaps(&driver_caps,&emulation_caps)` 후 overlay/video-memory/align/stretch caps 검사. `GetFourCCCodes()`는 count-then-fill로 UYVY 존재 확인 | `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491685(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490705(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490655(v=winembedded.60)`. VERIFIED | GD13MY caps 덤프 없음. UYVY 800×480 허용 여부 UNKNOWN | caps 부족이면 생성 시도 전에 포기하고 GDI 폴백 |
| 표면 설명 초기화 | `i30_ddraw_create_surface()` | `memset(&desc,0,sizeof(desc)); desc.dwSize=sizeof(desc)`. `dwFlags`에 width/height/pixelformat/caps/backbuffer. `DDSURFACEDESC`의 `dwSize,dwFlags,dwWidth,dwHeight,lPitch,lXPitch,lpSurface,ddpfPixelFormat,ddsCaps,dwSurfaceSize` 사용 | `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490816(v=winembedded.60)` §Members, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491090(v=winembedded.60)` §Parameters. VERIFIED | 실제 반환 pitch, orientation, surface size. UNKNOWN | 미사용 필드가 0이 아님 → 초기화 후 재시도 |
| UYVY 픽셀 포맷 | 동일 | `ddpfPixelFormat.dwSize` 설정, `dwFlags=DDPF_FOURCC`, FourCC 바이트 `U,Y,V,Y`. RGB mask나 `DDPF_YUV` 사용 금지. CE6에서 U/V mask는 지원되지 않음 | `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491068(v=winembedded.60)` §Members, `https://learn.microsoft.com/en-us/previous-versions/aa915462(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms919460(v=msdn.10)` §MEDIASUBTYPE_UYVY. VERIFIED. 순정 포맷 flags `0x4`+UYVY도 VERIFIED | DDRAW가 이 요청을 실제로 수락하는지 UNKNOWN | `DDERR_INVALIDPIXELFORMAT`이면 GDI 폴백 |
| 표면 생성 | 동일 | `CreateSurface(&desc,&overlay,NULL)`. overlay는 `DDSCAPS_OVERLAY`, front/back chain은 `DDSCAPS_FLIP` + `dwBackBufferCount>=1`. 순정 기본값을 그대로 복사하지 말고 0/1/2 backbuffer를 단계적으로 시험 | `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490733(v=winembedded.60)` §dwCaps, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491090(v=winembedded.60)` §Remarks/Return Value, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms893085(v=msdn.10)`. VERIFIED | 800×480 수락, backbuffer 수, VRAM. UNKNOWN | `DDERR_NOOVERLAYHW`, `DDERR_NOFLIPHW`, `DDERR_OUTOFVIDEOMEMORY` → GDI 폴백 |
| 프레임 Lock | `i30_ddraw_present_yuv()` | `Lock(NULL,&desc,DDLOCK_WAITNOTBUSY | DDLOCK_WRITEONLY,NULL)`. `hEvent`는 NULL. 단일 사각형만 lock. 반환된 `lpSurface`, `lPitch`, `lXPitch`, `dwSurfaceSize` 사용 | `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491248(v=winembedded.60)` §Parameters/Remarks, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490723(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491507(v=winembedded.60)`. VERIFIED | GD13MY pitch 부호/회전, `lXPitch` 의미. UNKNOWN | `DDERR_WASSTILLDRAWING`은 재시도. `DDERR_SURFACELOST`는 Restore 후 재시도. pitch가 음수이거나 packer 제약 위반이면 GDI 폴백 |
| UYVY 패킹 | `i30_pack_uyvy()` 호출 | `i30_pack_uyvy(geometry,i420,surface,desc.dwSurfaceSize,(size_t)desc.lPitch)`. crop된 `width/height/left/top`과 coded 크기 사용. source/dest 비겹침 전제 | `src/ce/ce_aa_uyvy.h:11-43`. VERIFIED | 홀수 crop, 음수 pitch, 실제 surface 크기. UNKNOWN | packer가 0 반환 → Unlock 후 GDI 폴백 |
| Unlock | 동일 | 같은 사각형으로 `Unlock(NULL)` 호출. lock 후 포인터는 Unlock 뒤 사용 금지 | CE6 Lock/Unlock 문서 위. VERIFIED | 드라이버가 Lock 중 blit을 금지하는지. UNKNOWN | Unlock 실패 시 surface를 lost로 간주하고 다음 프레임 Restore |
| 오버레이 표시 | `i30_ddraw_update_overlay()` | 앱 레벨 `UpdateOverlay(src,NULL,NULL,DDOVER_SHOW|DDOVER_WAITNOTBUSY,&fx)`로 표시, `DDOVER_HIDE`로 숨김. `DDOVERLAYFX.dwSize` 초기화. 필요 시 `DDOVER_WAITVSYNC` | CE/WinCE tutorial: `https://www.e-consystems.com/articles/Windows-CE/WindowsCE-Ddraw-api.asp` §Utilization of the Hardware Layers / §DDraw Surface Creation. `DDOVERLAYFX` CE6: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491509(v=winembedded.60)`. VERIFIED(3rd-party + CE6 members) | 정확한 CE6 앱 메서드 시그니처는 헤더 확인 필요. Z-order, color key, stretch 제한 UNKNOWN | `DDERR_HEIGHTALIGN`, `DDERR_NOSTRETCHHW`, `DDERR_NOTAOVERLAYSURFACE` → hide 후 GDI 폴백. 제공된 `ms923165`는 DDHAL 콜백이므로 앱 계약으로 쓰지 않음 |
| Flip과 완료 | `i30_ddraw_flip()` | chain이 있을 때만 `Flip(NULL,DDFLIP_WAITNOTBUSY)`; 필요 시 `GetFlipStatus(DDGFS_CANFLIP/DDGFS_ISFLIPDONE)` 확인. 기본은 VSync 동기화 아님 | `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491631(v=winembedded.60)` §Parameters/Remarks, `https://learn.microsoft.com/en-us/previous-versions/aa911093(v=msdn.10)`. VERIFIED | GD13MY에서 Flip이 비동기인지, overlay chain에서 ISFLIPDONE이 동작하는지 UNKNOWN | `DDERR_WASSTILLDRAWING`은 다음 프레임까지 대기. 미완료 상태가 계속되면 flip 사용 중단 |
| Surface lost/Restore | 프레임 경로와 종료 경로 | `DDERR_SURFACELOST` 수신 시 `Restore()`, 다시 `Lock`해 pitch/size 재조회. 회전·exclusive 전환에서 발생 가능 | `https://learn.microsoft.com/en-us/previous-versions/aa919861(v=msdn.10)` §Losing and Restoring Surfaces. VERIFIED | GD13MY에서 loss를 유발하는 이벤트, 카메라 상태 중 Restore 안전성 UNKNOWN | Restore 실패 → 오버레이 해제 후 GDI 폴백 |
| 참조 해제 | `i30_ddraw_close()` | hide → overlay Release → primary Release → `dd` Release. 자식 surface를 부모 해제 후 사용하지 않음 | `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee487697(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms893117(v=msdn.10)`, 순정 해제 경로 `0x102b34`. VERIFIED | 다른 프로세스와의 소유권 이전 UNKNOWN | Release 전에 반드시 hide. 실패해도 나머지 Release 수행 |
| 후방카메라 충돌 | `ce_aa_projection.c` 게이트 | `i30_stock_display_safe()`가 허용할 때만 오버레이 표시. 상태가 안전하지 않으면 숨기고 GDI 유지 | `docs/testing/AARE_STOCK_RESOURCE_BASELINE.md`는 점유/반환 미검증으로 명시 | 카메라 표시와 투사 오버레이의 z-order/반환 계약 UNKNOWN | 충돌 가능 상태에서는 GDI 유지. 카메라 프로세스 종료·일시정지 금지 |
| 800×480 제한 | 초기화 게이트 | 800×480 요청 전 caps와 CreateSurface 결과를 직접 확인. fixture의 800×480 메모리 성공을 근거로 쓰지 않음 | CE6 caps 문서 위. VERIFIED | GD13MY가 800×480 UYVY surface를 만드는지 UNKNOWN | 실패 시 720×576 순정 기본값으로 임의 변경하지 않고 GDI 폴백 |

## 4. 구현 흐름 (ARM/mock VERIFIED, GD13MY 실기 INFERRED)

```text
/* opt-in 전용. 기본 빌드에서는 호출되지 않는다. */
i30_ddraw_open(window, &state)
  LoadLibraryW("DDRAW.dll" | "\Windows\DDRAW.dll")
  GetProcAddressA("DirectDrawCreate") -> DirectDrawCreate(NULL, &dd, NULL)
  SetCooperativeLevel(hwnd, DDSCL_NORMAL)        /* 전체 화면 소유권 회피 */
  GetCaps(112), 필요 시 GetCaps(128)
  GetFourCCCodes(count -> fill); UYVY 요구
  CreateSurface(primary)
  CreateSurface(800x480 UYVY overlay [, backbuffer])
  flip 빌드: EnumAttachedBackBuffers + AddRef(back)

i30_ddraw_present(context, geometry, i420)
  pending flip이면 GetFlipStatus(DDGFS_ISFLIPDONE) 확인
  실패/시간 초과 시 backend 즉시 비활성화
  lost/needs_restore면 Restore 후 Lock 재시도
  Lock(NULL, desc, DDLOCK_WAITNOTBUSY | DDLOCK_WRITEONLY, NULL)
  lPitch, lXPitch, lpSurface, width, height, size 검증
  i30_pack_uyvy(geometry, i420, lpSurface, pitch*height, pitch)
  Unlock
  UpdateOverlay(src, ..., DDOVER_SHOW | DDOVER_WAITNOTBUSY)
  flip이면 Flip + GetFlipStatus 완료 후에만 front/write 교체
  return 1은 표시 완료만 의미; 0이면 같은 i420로 BGRA+GDI 폴백
```

`DdrawTarget`은 DirectDraw 상태와 GDI window/DC를 함께 보관하므로, 거부된 프레임이 `i30_video_push()` 안에서 추가 디코딩 없이 BGRA+GDI로 다시 그려진다. 일반 실패 3회 또는 flip 실패 1회로 세션 백엔드를 비활성화한다. reset, STOP/CLOSE, disconnect, 네이티브 표시권·카메라 위험 상태에서는 overlay를 숨긴다. `i30_ddraw_close()`는 hide 후 overlay, back, primary, dd 참조를 차례로 놓고 `FreeLibrary`한다.

CE6 문서와 충돌하는 기존 문구 `DDLOCK_WAIT`는 사용하지 않고 `DDLOCK_WAITNOTBUSY`를 사용한다. 근거: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491248(v=winembedded.60)`와 `https://learn.microsoft.com/en-us/previous-versions/aa915462(v=msdn.10)`. DDCAPS의 overlay-cap 워드 오프셋 `+0x48`는 순정 호출 흐름과 CE6 선언 순서에서 도출한 **INFERRED** 값이며, stock ARM 직접 call site는 확인하지 못했다.

## 5. 활성화 전 검증 게이트

모두 통과하기 전까지 기본 활성화 금지. 아래 로컬 상태는 mock/ARM fixture에만 적용된다.

| 게이트 | 로컬 상태 | 실기 상태 |
|---|---|---|
| 1. `DirectDrawCreate` export와 CE6 헤더 시그니처 | VERIFIED: loader 호출과 mock export 확인, 정적 import 없음 | UNKNOWN: 실제 DLL 시그니처 |
| 2. `GetCaps` / `GetFourCCCodes` 결과 | VERIFIED: 112/128 시도와 UYVY 코드 확인을 mock이 검증 | UNKNOWN: 실제 caps 및 `+0x48` 해석 |
| 3. 800×480 UYVY surface 생성 | VERIFIED: mock이 primary/overlay/back 생성 기록 | UNKNOWN: backbuffer 0/1/2 수용 여부 |
| 4. `Lock` 반환 필드 | VERIFIED: pitch 1,632, width/height, pointer, size 검증 | UNKNOWN: 실제 pitch/xPitch/방향/size |
| 5. packing과 crop/stride | VERIFIED: fixture 바이트와 패딩 일치 | UNKNOWN: 실제 overlay 표시 좌표 |
| 6. show/hide, z-order, color key, stretch | VERIFIED: show/hide 호출과 fallback hide만 확인 | UNKNOWN: 실제 표시 권한과 제한 |
| 7. `Flip` 완료 | VERIFIED: mock `Flip`/`GetFlipStatus`, 완료 후에만 교체 | UNKNOWN: 실제 비동기 동작과 buffer 수명 |
| 8. 카메라·disconnect·재연결·종료 | VERIFIED: 안전 이벤트 주입, hide→Release, 참조 0 | UNKNOWN: 실제 후방카메라 점유와 반환 |
| 9. 동일 입력 실기 FPS/ACK/화면 품질 | UNKNOWN: ARM 벽시계만 측정, USB ACK/LCD 없음 | UNKNOWN: 개선 입증 전까지 opt-in 유지 |

게이트 2의 `DDCAPS +0x48`와 게이트 7의 `GetFlipStatus +0x34`는 CE6 선언 순서에서 도출한 INFERRED 값이다. 하드웨어 검증 전에는 정적 호출을 근거로 VERIFIED로 승격하지 않는다.

## 6. 미해결 질문 (모두 UNKNOWN)

- GD13MY `DDRAW.dll`/`ddi.dll`이 800×480 UYVY 오버레이와 1~2 backbuffer를 허용하는가.
- 실제 `Lock`의 pitch/orientation이 top-down 양수인가. 현재 packer가 demanding하는 even 조건을 만족하는가.
- source/destination 정렬, stretch 범위, Z-order, color key 제한은 무엇인가.
- `Flip`이 비동기인가. `DDGFS_ISFLIPDONE`이 오버레이 chain에서 동작하는가.
- 어떤 이벤트가 surface를 lost시키고, 카메라 active 중 `Restore`가 안전한가.
- 별도 프로세스가 `LibVideo` 오버레이를 점유/인계할 수 있는가.
- hide→update→release 순서가 카메라 선점·연결 해제·종료에서 안전한가.
- 실제 오버레이 표시가 ACK gap과 FPS를 개선하는가.

## 7. 출처

- 구현·회귀·ARM 4경로 중앙값: [UYVY DirectDraw 3경로 벤치마크 증거](../../testing/UYVY_DIRECTDRAW_BENCHMARK_EVIDENCE.md)
- CE6 API 세대/구조/플래그: `https://learn.microsoft.com/en-us/previous-versions/aa916681(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/aa919057(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/aa915462(v=msdn.10)`
- DirectDrawCreate / 초기화: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490059(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491007(v=winembedded.60)`
- 객체 소유권/Release: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491622(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms893117(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee487697(v=winembedded.60)`
- Caps/FourCC/PixelFormat/SurfaceDesc: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491685(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490705(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490655(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491068(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490816(v=winembedded.60)`
- CreateSurface / overlay flags: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490733(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491090(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms893085(v=msdn.10)`
- Lock/Unlock/pitch: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491248(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490723(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491507(v=winembedded.60)`
- Overlay/Flip/Lost: `https://www.e-consystems.com/articles/Windows-CE/WindowsCE-Ddraw-api.asp`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491509(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491631(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/aa911093(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/aa919861(v=msdn.10)`
- 제공된 URL 중 `ms923165`는 CE5 DDHAL `UpdateOverlay` 드라이버 콜백: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms923165(v=msdn.10)`. 앱 API 계약으로 사용하지 않는다.
