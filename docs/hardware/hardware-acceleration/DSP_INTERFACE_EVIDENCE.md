# DSP 및 비디오 드라이버 인터페이스 분석 근거

## 1. 개요 및 대상 바이너리

본 문서는 현대 2013년형 i30 2세대 순정 내비게이션(GD13MY.KOR.SOP.00.061, Windows CE 6.0 ARM) 펌웨어에 실제 존재하는 멀티미디어 및 비디오 드라이버 바이너리를 정적 역공학 분석한 결과다.
추정이나 가설을 배제하고 실제 PE 헤더, Import/Export 테이블, 디스어셈블리, 문자열 참조를 교차 검증하여 기록했다.

### 바이너리 기본 정보

| 바이너리 | 파일 시스템 위치 | 크기 (Bytes) | SHA-256 | 머신 / 서브시스템 |
|---|---|---|---|---|
| `LibMMCodec.dll` | `firmware\extracted\GD13MY\APP\002c98d9_LibMMCodec.dll` | 580,608 | `b152e2238304acd3aa2dae947a17872ec3cff7165995faa87f802d09543bbfc2` | ARM (0x1c2) / WinCE (0x9) |
| `videodev.dll` | `firmware\extracted\GD13MY\ROM\videodev.dll` | 60,928 | `8ea6bc31284d8225680ff0dad537e037df2126f7bdf05de490739c7771787ebf` | ARM (0x1c2) / WinCE (0x9) |
| `dsp_bridge.dll` | `firmware\extracted\GD13MY\ROM\dsp_bridge.dll` | 2,465,792 | `4e70275cd88034a63710cf863b663fb29d863811bf717b35a9bd2e70b9f665ae` | ARM (0x1c2) / WinCE (0x9) |
| `LibVideo.dll` | `build\gd13my-aa-error07\display\LibVideo.dll` | 41,984 | `95a201507f584a829767ffd3db8ae78e6a1c41662b3e9e44aaf393d5494e66b1` | ARM (0x1c2) / WinCE (0x9) |

---

## 2. 드라이버 Export 및 Import 인터페이스

### 2.1 videodev.dll (스트림 인터페이스 드라이버)
표준 Windows CE 스트림 디바이스 드라이버 프리픽스 `VID`를 구현하고 있다:
- `VID_Init` (VA: `0x1000a4b4`): 드라이버 인스턴스 0x1cc 바이트 컨텍스트 할당, 16개 내부 슬롯(0x10) 초기화
- `VID_Deinit` (VA: `0x1000a2d0`): 드라이버 인스턴스 정리 및 자원 해제
- `VID_Open` (VA: `0x10009c68`): 디바이스 오픈 핸들 컨텍스트 반환
- `VID_Close` (VA: `0x1000a42c`): 디바이스 클로즈
- `VID_IOControl` (VA: `0x10009cd0`): IOCTL 디스패처
- `VID_PowerDown` (VA: `0x1000a2b4`), `VID_PowerUp` (VA: `0x1000a2b0`)

### 2.2 dsp_bridge.dll (DSP Bridge 스트림 인터페이스 드라이버)
표준 Windows CE 스트림 드라이버 프리픽스 `DSP`를 구현:
- `DSP_Init` (VA: `0x10255520`)
- `DSP_Deinit` (VA: `0x10255834`)
- `DSP_Open` (VA: `0x10255864`)
- `DSP_Close` (VA: `0x102558c0`)
- `DSP_IOControl` (VA: `0x10255ba4`)
- `DSP_PowerDown` (VA: `0x10255904`), `DSP_PowerUp` (VA: `0x10255908`)
- CEDDK.dll 임포트: 물리 주소 매핑 및 DMA 관련 루틴 (`ord_8`, `ord_9`, `ord_22`)

### 2.3 LibMMCodec.dll
멀티미디어 코덱 고수준 래퍼 라이브러리 (38개 Export):
- 주요 Export: `lmmCodecInit` (0x1165b4), `lmmCodecFini` (0x1165c4), `lmmCodecClose` (0x1165e0), `lmmCodecFf` (0x116604), `lmmCodecClearScreen` (0x116720), `lmmCodecGetImageWidth` (0x116800), `lmmCodecGetImageHeight` (0x11680c), `lmmCodecSetVideoSize` (0x116818), `lmmCodecNotifyDMBState` (0x116824).
- DirectDraw: `DDRAW.dll`의 `DirectDrawCreate` 임포트.

### 2.4 LibVideo.dll
후방 카메라 및 DMB/비디오 출력 제어 라이브러리 (49개 Export):
- 후방 카메라 디바이스 `CAM1:` 접근 (`CreateFile_CAM1`, `IOCTL_CAMERA_GET_STATE`, `IOCTL_CAMERA_INIT_DECODER`)
- DirectDraw 오버레이 서피스(`g_pDDSPrimary`, `g_pDDSOverlay`) 관리

---

## 3. videodev.dll IOCTL 디스패처 분석

`VID_IOControl` (VA `0x10009cd0`)는 `r7` 레지스터에 전달된 IOCTL 코드를 기준으로 분기하며, 검증된 세부 코드는 다음과 같다:

| IOCTL 코드 (Hex) | 핸들러 VA | 요구 입력 크기 (`r8`) | 출력 버퍼 크기 / 동작 | 비고 / 문자열 매핑 |
|---|---|---|---|---|
| `0x002207fc` | `0x10009e8c` | >= 0x22c (556B) | 반환 성공 | 디코더 채널 해제 / 중지 |
| `0x00220800` | `0x10009e70` | >= 0x00c (12B) | 반환 성공 | 제어 파라미터 설정 |
| `0x00220804` | `0x10009e54` | >= 0x00c (12B) | 반환 성공 | 제어 파라미터 조회 |
| `0x00220808` | `0x10009e00` | >= 0x22c (556B) | 4바이트 출력 (`[sp, #0x1c]`) | `IOCTL_VDEV_VID_DECINIT` (디코더 슬롯 0x168 할당) |
| `0x0022080c` | `0x10009dc0` | >= 0x22c (556B) | 4바이트 출력 (`[sp, #0x1c]`) | `IOCTL_VDEV_VID_DECODE` (프레임 디코드 명령 전송) |
| `0x00220810` | `0x10009da0` | >= 0x22c (556B) | 반환 성공 | 비디오 스트림 제어 |
| `0x00220814` | `0x10009d90` | >= 0x22c (556B) | 반환 성공 | 비디오 스트림 정지/플러시 |
| `0x00220818` | `0x10009ea8` | >= 0x22c (556B) | 반환 성공 | 비디오 버퍼 설정 |
| `0x0022081c` | `0x10009fb8` | >= 0x22c (556B) | 반환 성공 | `IOCTL_VDEV_VID_DEC_DEINIT` |
| `0x00220820` | `0x10009f98` | >= 0x22c (556B) | 반환 성공 | 인코더 관련 |
| `0x00220824` | `0x10009f78` | >= 0x22c (556B) | 반환 성공 | 인코더 관련 |
| `0x00220828` | `0x10009f58` | >= 0x22c (556B) | 반환 성공 | 인코더 관련 |
| `0x0022082c` | `0x10009f38` | >= 0x22c (556B) | 반환 성공 | 이미지 쿼리 |
| `0x00220834` | `0x10009fd8` | >= 0x22c (556B) | 반환 성공 | 스트림 동기화 |
| `0x00220838` | `0x1000a0f0` | >= 0x22c (556B) | 반환 성공 | 오디오 디코드 초기화 |
| `0x0022083c` | `0x1000a0d0` | >= 0x22c (556B) | 반환 성공 | 오디오 디코드 실행 |
| `0x00220844` | `0x1000a094` | >= 0x22c (556B) | 반환 성공 | 오디오 디코드 종료 |
| `0x00220854` | `0x10009ff8` | 분기 비교 | - | 고수준 서브코드 |
| `0x00220858` | `0x1000a208` | >= 0x22c (556B) | 반환 성공 | 이미지 디코드 초기화 |
| `0x0022085c` | `0x1000a1e8` | >= 0x22c (556B) | 반환 성공 | 이미지 디코드 실행 |
| `0x00220864` | `0x1000a1c8` | >= 0x22c (556B) | 반환 성공 | 이미지 디코드 종료 |
| `0x00220868` | `0x1000a1bc` | 인자 없음 (`r0=sb`) | 반환 성공 | 디바이스 리셋 |
| `0x00220884` | `0x1000a19c` | >= 0x22c (556B) | 반환 성공 | DSP 메모리 핸들러 |

- **입력 구조체 크기 공통 요구조건**: 비디오 및 오디오 주요 명령은 `r8 >= 0x22c` (556 바이트)의 거대한 파라미터 블록을 요구한다. 입력 포인터 `r5`가 NULL이거나 길이가 556 바이트 미만이면 `0x1000a234`로 분기하여 `FALSE`(0)를 반환한다.
- **출력 구조체**: `0x00220808` (DECINIT) 및 `0x0022080c` (DECODE)는 `[sp, #0x1c]`(출력 버퍼 포인터)에 4바이트 정수(핸들 또는 상태 코드)를 리틀 엔디언 바이트 단위로 기록한다.

---

## 4. 디바이스 드라이버 호출 체인 (Xref)

### 4.1 LibMMCodec.dll -> `VID1:` 디바이스 오픈
- 함수 주소: `0x00115648` (Ghidra `FUN_00115648`)
- 문자열 위치: VA `0x00166e94` (`VID1:`)
- 호출 명령어:
  ```arm
  0x00115654  ldr r0, [str.VID1:]   ; 0x00166e94 (L"VID1:")
  0x00115658  mov r3, 0
  0x00115660  mov r5, 3             ; OPEN_EXISTING (3)
  0x00115664  mov lr, 0
  0x00115674  str lr, [sp, 8]
  0x00115678  str lr, [sp, 4]
  0x0011567c  str r5, [sp]          ; dwCreationDisposition = 3
  0x00115680  bl  0x00126638        ; coredll Ordinal_168 (CreateFileW)
  0x00115684  str r0, [r4, 4]       ; 저장된 디바이스 핸들
  0x00115688  cmn r0, 1             ; INVALID_HANDLE_VALUE (-1) 검사
  0x0011568c  bne 0x001156a8        ; 성공 시 반환
  0x00115690  ldr r0, [0x001156bc]  ; "VideoDev: Can't open device"
  0x00115694  bl  0x00126528        ; OutputDebugStringW
  0x00115698  mov r3, -0x7ffffffb
  0x0011569c  orr r0, r3, 0x4000    ; 0x80004005 (E_FAIL) 반환
  ```

### 4.2 videodev.dll -> `DSP1:` 브리지 오픈
- 문자열 위치: VA `0x10004510` (`DSP1:`)
- `videodev.dll` 내부에서 `DSP1:` 장치를 `CreateFileW`로 열고, DSP 명령 큐(`m_DecInitCmd`, `m_DecodeCmd`)를 생성하여 DSP 브리지 드라이버로 전달한다.
- `dsp_bridge.dll`은 메일박스(`MBOX_Write`, `MBOX_IsFull`) 및 공유 메모리(`RDRV_DSP_SPEC_Init`)를 통해 실제 칩셋 DSP 코어와 통신한다.

---

## 5. H.264 지원 여부 분석

`LibMMCodec.dll` 내 문자열 검사 결과:
- VA `0x0015f66e`: `L"[0m : H264(H263) Codec is not support ! \r\n"`
- VA `0x00164cbc`: `L"nit: H264 Video\r\n"`
- FourCC 매핑: `ASCII 0xa024`: `idMJPGXVIDh264H264WMV3MP43WMV2M4S2`

`videodev.dll` 내 문자열 검사 결과:
- VA `0x10003008`: `L"DUMPING H264_CODEC specific encoder params"`
- VA `0x1000309e`: `L"nion.h264e.profile - "`
- VA `0x10003116`: `L"nion.h264e.level - "`

### 분석 결론
`videodev.dll`에는 H.264 인코더(`h264e`) 파라미터 구조체 및 오프셋 디버그 코드가 존재하지만, 순정 미디어 재생기인 `LibMMCodec.dll`에서는 특정 조건에서 `H264(H263) Codec is not support !` 메시지를 출력하며 재생을 거부하는 분기가 존재한다.
또한 `VID_IOControl`의 디코더 입력 구조체(556 바이트) 내부 필드 오프셋과 NAL 유닛 패킷 전달 방식이 공식 문서화되어 있지 않아, 현재 검증되지 않은 DSP IOCTL을 호출할 경우 드라이버 크래시 또는 커널 패닉을 유발할 수 있다.

---

## 6. 미확인 항목 및 제약사항

1. **556 바이트 입력 파라미터 구조체 상세 레이아웃**:
   - `0x00220808` (`DECINIT`) 및 `0x0022080c` (`DECODE`) 전달 구조체의 폭, 높이, 프레임레이트, NAL 헤더, 비트스트림 포인터의 정확한 멤버 오프셋은 현재 정적 역공학만으로 완전히 증명되지 않음.
2. **DMA 물리 버퍼 주소 전달 방식**:
   - 디코딩된 YUV 프레임이 DSP 공유 물리 메모리에 저장되는지, 가상 메모리 포인터로 반환되는지 여부 미확인.
3. **결론**:
   - 후속 작업(Codex)에서 안전하게 하드웨어 디코더를 연결하기 위해서는 WinCE 링0 드라이버 레벨에서 `VID1:`의 입력 구조체 556바이트를 모니터링하는 프로브 또는 진단기가 선행되어야 하며, 현재 단계에서는 안정성이 입증된 `h264bsd` 소프트웨어 디코더를 유지하는 것이 타당하다.
