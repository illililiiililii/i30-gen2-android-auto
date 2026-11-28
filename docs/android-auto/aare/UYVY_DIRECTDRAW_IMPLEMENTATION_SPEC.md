# UYVY DirectDraw 구현 명세 — Codex 인계용

작성일: 2026-11-28 · 기준 커밋: `68ed2f4`

## 1. 범위

이 문서는 GD13MY Windows CE 6.0에서 AARE 영상을 UYVY DirectDraw 오버레이로 출력하기 위한 **설계 명세**다. 데스크톱 Windows DirectDraw 문서를 CE 근거로 사용하지 않는다. 제공된 `ms893918`은 CE .NET 4.2 계열, `ms923165`는 CE 5.0 드라이버 DDHAL 콜백이므로 CE6 앱 API 계약으로 쓰지 않는다.

분류:

- **VERIFIED**: 인용한 문서/로컬 파일이 명시적으로 보여줌.
- **INFERRED**:VERIFIED 사실에서 도출한 구현 방침. GD13MY 동작 확정 아님.
- **UNKNOWN**: 공개 문서나 현재 증거로 확인되지 않음.

**현재 상태: 구현 전.** 기존 기본 배포 경로는 BGRA + GDI이며, 변경하지 않는다. 새로운 DDRAW 백엔드는 별도 opt-in 매크로와 별도 브랜치에서만 실험한다. 실폰/실차 검증 전에는 기본값으로 켜지 않는다.

## 2. 기존 코드 연결 지점 (VERIFIED)

| 위치 | 현재 계약 |
|---|---|
| `src/ce/ce_aa_video.h:14-23` | `I30VideoTarget`에 `begin`, `end`, 조건부 `present_yuv(context, geometry, i420)` 존재. `present_yuv`는 동기 I420 소비자이며 성공 시 1, 실패 시 0 반환. 디코더가 반환 후 입력 버퍼를 재사용할 수 있음 |
| `src/ce/ce_aa_video.c:196-210` | `I30_VIDEO_UYVY_STAGING`일 때 `h264bsdNextOutputPicture()` 결과를 `present_yuv`에 먼저 넘기고, 실패하면 RGB565/BGRA 폴백 |
| `src/ce/ce_aa_video.h:6`, `src/ce/ce_aa_video.c:178-190` | 출력 계약은 800×480. crop/stride 검사와 `I30VideoGeometry{coded_w,coded_h,left,top,width,height}` 유지 |
| `src/ce/ce_aa_uyvy.h:11-43` | `i30_pack_uyvy()`는 이미 잠긴 top-down 표면에 `U Y0 V Y1` 순서로 기록. even width/height/left/coded 치수 요구. pitch/size 경계 검사. 행 패딩은 건드리지 않음 |
| `tools/verify_ce_uyvy_staging.py` | 메모리 fixture. `PITCH=800*2+32`, `SURFACE_SIZE=PITCH*480`, padding `0xA5`. 실제 DDRAW Lock 결과가 아님 |
| `docs/testing/AARE_STOCK_RESOURCE_BASELINE.md` §순정 영상 출력 / §HAL과 ARM 성능 대조 | 순정 `.061 LibVideo.dll`의 `lVideoShowOverlay`(`0x1011d0`)가 상태 객체와 32바이트 픽셀 포맷(`0x10b0e4`, flags `0x4`, FourCC `UYVY`)을 사용. 기본 720×576, backbuffer 요청 2, 생성 `0x1033b0`, 표시/숨김 `0x10352c`/`0x1035bc`, Lock 실패 `0x103ce4`, 크기 변경 `0x103898`/`0x1038c4`, 해제 시 숨김 `0x102b34`. `.061 DDRAW.dll` ordinal 1에 `DirectDrawCreate` 존재 |

ARM fixture 수치(BGRA 변환 263.62 ms → UYVY 패킹 55.19 ms, video push 504.58 ms → 292.90 ms)는 Unicorn 벽시계 시간이며 실제 오버레이 전송, VSync, USB ACK를 포함하지 않는다. **실기 표시 성능은 UNKNOWN.**

## 3. 구현 명세 표

| 구현 항목 | 대상 파일/함수 | 호출 계약 | 직접 근거 | 미확인 사항 | 실패 처리 |
|---|---|---|---|---|---|
| CE6 API 세대 | 신규 `src/ce/ce_aa_uyvy_ddraw.h/.c` | `IDirectDraw`, `IDirectDrawSurface`, `DDSURFACEDESC`, `DDSCAPS` 사용. `IDirectDraw4`, `IDirectDrawSurface5`, `DDSURFACEDESC2`, `DDSCAPS2` 사용 금지 | CE6 migration: `https://learn.microsoft.com/en-us/previous-versions/aa916681(v=msdn.10)` §Interfaces, `https://learn.microsoft.com/en-us/previous-versions/aa919057(v=msdn.10)` §Structures, `https://learn.microsoft.com/en-us/previous-versions/aa915462(v=msdn.10)` §Flags. VERIFIED | 순정 DLL이 내부적으로 사용하는 인터페이스 버전. UNKNOWN | 헤더 컴파일 실패 시 백엔드 비활성화 |
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
| 후방카메라 충돌 | 신규 게이트 | 카메라 점유 상태를 확인할 수 있을 때만 오버레이 표시. 상태를 얻지 못하면 백엔드 자체를 켜지 않음 | `docs/testing/AARE_STOCK_RESOURCE_BASELINE.md`는 점유/반환 미검증으로 명시 | 카메라 표시와 투사 오버레이의 z-order/반환 계약 UNKNOWN | 충돌 가능 상태에서는 GDI 유지. 카메라 프로세스 종료·일시정지 금지 |
| 800×480 제한 | 초기화 게이트 | 800×480 요청 전 caps와 CreateSurface 결과를 직접 확인. fixture의 800×480 메모리 성공을 근거로 쓰지 않음 | CE6 caps 문서 위. VERIFIED | GD13MY가 800×480 UYVY surface를 만드는지 UNKNOWN | 실패 시 720×576 순정 기본값으로 임의 변경하지 않고 GDI 폴백 |

## 4. 의사코드 (INFERRED — 구현 전 설계)

```c
/* opt-in 전용. 기본 빌드에서는 호출되지 않는다. */
dd = i30_ddraw_open(hwnd);                 /* DirectDrawCreate(NULL,...) */
if (!dd || !i30_ddraw_check_caps(dd))      return gdi_target;

desc = zeroed_surface_desc(800, 480, UYVY_FOURCC, DDSCAPS_OVERLAY | maybe_FLIP);
if (FAILED(CreateSurface(&desc, &overlay, NULL))) return gdi_target;
if (FAILED(UpdateOverlay(overlay, NULL, NULL, DDOVER_HIDE, &fx))) goto release;

target.context = ddraw_state;
target.begin   = NULL;                     /* DDRAW는 GDI DC를 쓰지 않는다 */
target.end     = NULL;
target.present_yuv = i30_ddraw_present_yuv;

/* i30_ddraw_present_yuv(context, geometry, i420) */
Lock(NULL, &locked, DDLOCK_WAITNOTBUSY | DDLOCK_WRITEONLY, NULL);
if (locked.lPitch <= 0 || !i30_pack_uyvy(geometry, i420, locked.lpSurface,
                                         locked.dwSurfaceSize, (size_t)locked.lPitch)) {
    Unlock(NULL);
    return 0;                              /* ce_aa_video.c가 BGRA GDI로 폴백 */
}
Unlock(NULL);
UpdateOverlay(overlay, NULL, NULL, DDOVER_SHOW | DDOVER_WAITNOTBUSY, &fx);
if (has_flip_chain) Flip(NULL, DDFLIP_WAITNOTBUSY);
return 1;
```

 CE6 문서와 충돌하는 기존 문구 `DDLOCK_WAIT`는 사용하지 않고 `DDLOCK_WAITNOTBUSY`를 사용한다. 근거: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491248(v=winembedded.60)`와 `https://learn.microsoft.com/en-us/previous-versions/aa915462(v=msdn.10)`.

## 5. 활성화 전 검증 게이트

모두 통과하기 전까지 기본 활성화 금지.

1. DDRAW.dll의 `DirectDrawCreate` export와 CE6 헤더 시그니처가 일치하는지 확인.
2. GD13MY에서 `GetCaps` / `GetFourCCCodes` 결과를 캡처해 UYVY와 오버레이 caps 확인.
3. 800×480 UYVY surface를 backbuffer 0/1/2 각각으로 생성 시도. 생성 반환 코드 기록.
4. `Lock`이 반환하는 `lPitch`, `lXPitch`, `lpSurface`, `dwSurfaceSize`, 방향 기록.
5. `i30_pack_uyvy` 결과를 Unlock 전에 검증하고, 표시 후 crop/stride가 800×480 계약과 일치하는지 확인.
6. `UpdateOverlay` show/hide, Z-order, color key, stretch 제한 확인.
7. `Flip` 완료 상태와 버퍼 수명을 `GetFlipStatus`로 확인. 비동기면 프레임 드랍 계약 결정.
8. 후방카메라 점유 중 표시/숨김/반환, disconnect, 재연결, 종료 시 hide→Release 확인.
9. 같은 H.264 입력으로 BGRA GDI 대비 실제 head unit FPS, ACK gap, 화면 품질 측정. 개선이 입증되지 않으면 opt-in 유지.

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

- CE6 API 세대/구조/플래그: `https://learn.microsoft.com/en-us/previous-versions/aa916681(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/aa919057(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/aa915462(v=msdn.10)`
- DirectDrawCreate / 초기화: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490059(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491007(v=winembedded.60)`
- 객체 소유권/Release: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491622(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms893117(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee487697(v=winembedded.60)`
- Caps/FourCC/PixelFormat/SurfaceDesc: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491685(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490705(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490655(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491068(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490816(v=winembedded.60)`
- CreateSurface / overlay flags: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490733(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491090(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms893085(v=msdn.10)`
- Lock/Unlock/pitch: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491248(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee490723(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491507(v=winembedded.60)`
- Overlay/Flip/Lost: `https://www.e-consystems.com/articles/Windows-CE/WindowsCE-Ddraw-api.asp`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491509(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ee491631(v=winembedded.60)`, `https://learn.microsoft.com/en-us/previous-versions/aa911093(v=msdn.10)`, `https://learn.microsoft.com/en-us/previous-versions/aa919861(v=msdn.10)`
- 제공된 URL 중 `ms923165`는 CE5 DDHAL `UpdateOverlay` 드라이버 콜백: `https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms923165(v=msdn.10)`. 앱 API 계약으로 사용하지 않는다.
