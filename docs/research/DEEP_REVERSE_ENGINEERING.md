# Phase 1 · GD13MY 심층 펌웨어 분석

**결론:** Phase 2의 PC MVP는 착수할 수 있다. 순정 기기용 배포는 아직 보류한다. ROM을 더 분석해 CE의 USB 클라이언트 등록 경로와 OEM의 H.264 영상 드라이버를 확인했다. 다만 실물에서 새 소프트웨어를 실행하고 장치 자원을 사용할 수 있어야 이 경로를 적용할 수 있다.

분석 범위는 `GD13MY.KOR.SOP.00.061` 작업본이다. Phase 0에서 검증한 123개 파일 및 Ghidra ARMv7 프로젝트를 재사용했다. 이 단계에서 21개 XIP 모듈의 E32/O32 메타데이터와 이름 있는 export를 조사하고, 같은 ROM의 파일 엔트리에서 6개를 추가 복원했다. 커널 원본과 작업본의 ROM 오프셋을 구분하기 위해 전체 BSP가 아닌 압축이 풀린 `BSP/0002dfc7_kernel`을 기준으로 표기한다. Ghidra VA는 각 프로그램의 이미지 베이스 기준이고, RVA는 해당 이미지 내부 상대 주소다.

| 구성 | 근거와 판정 |
|---|---|
| Boot | BSP `raw` 파일 `0x13a4`에 TI iNAND X-Loader, `0x216ec`에 Autonet EBOOT. CE BIN 최종 레코드의 entry는 `0x8000aadc`. ROM의 링크 주소와 BIN 저장 주소 사이에 `0x04000000` 차이가 있다. 물리 플래시 상의 단계별 배치와 부팅 중 장치 설정은 미확인이다. |
| Kernel/ABI | `nk.exe`의 E32가 ROM `0x2f4573`, `kernel.dll`이 `0xcee9ab`이며 두 Subsystem 버전은 6.0이다. ROMHDR Machine `0x01c2`와 앱 PE를 종합하면 구형 32비트 ARM/Thumb Windows CE ABI다. Cortex-A8을 가리키는 BSP 자료는 [Phase 0 하드웨어 문서](HARDWARE.md)에 있다. Linux armhf ABI 및 데스크톱 Win32 ABI는 호환 대상으로 확인되지 않았다. |
| XIP와 RAM | ROMHDR `0x149758b`의 범위는 `0x85500000–0x86800000`으로 19 MiB다. `0x9adf4f`, `0x9adf5f`의 COPYentry는 초기화 데이터 원본과 RAM 목적지를 각각 기술한다. 예를 들어 첫 레코드의 목적지는 `0x85506000`이다. XIP 모듈의 ROM 저장 위치와 실행 중의 가상 주소도 O32에서 구별된다. 이 크기로 기기의 총 RAM과 상시 여유 메모리를 산정할 수 없다. |
| 시스템 시작 | 복원한 `default.hv`의 UTF-16LE에서 `Launch20device.dll`(`0x3102e`), `Launch25AVNSysInit.exe`(`0x30e36`), `Launch30gwes.dll`(`0x30ff2`), `Launch60servicesStart.exe`(`0x30f7a`), `Launch100AutoStartUp.exe`(`0x30eaa`)를 읽었다. ROM `0xd07b73`의 AVNSysInit 문자열은 HKLM Init을 참조한다. 이 기록은 시작 항목과 후보 순서를 보여 준다. Depend 값과 실제 스케줄은 해석하지 않았다. |
| OEM 앱 시작과 종료 | `AutoStartUp.exe`의 `\DiskA\Application\UComH_New.EXE`가 ROM `0xceeb93`에 있다. APP `uComH_New.exe`가 `systemCfg.xml` 파일 오프셋 `0x2c728`을 참조하는 함수는 VA `0x00019f94`다. `CreateProcessW`, `TerminateProcess`, 윈도 메시지 및 장치 I/O import가 있다. PowerOff 상태 문자열 `0x2b350`의 참조는 VA `0x0001588c`, 해당 상태의 응용/MCU 이벤트 문자열은 VA `0x0001968c`를 가리킨다. 실제 종료 타이밍, 전원 차단 및 영속화 순서는 실물 필요. |
| 런타임과 의존성 | 같은 ROM의 `coredll.dll` export를 써서 Phase 0의 PE ordinal들을 이름으로 확인했다. 예를 들어 `168 → CreateFileW`, `179 → DeviceIoControl`. `device.dll`, `udevice.exe`, `gwes.dll` 및 `servicesStart.exe`가 각각 목차 또는 hive에서 확인된다. native APP의 Win32 CE API 및 DLL 의존 경로는 [PE 스캔](../research/evidence/phase1-scan.json)에 있다. ROM에 있는 .NET CF가 수신기 실행에 필요한 정황은 없다. |
| 복구 | ROM `AutoStartUp.exe`의 `\Windows\AVNRecovery.exe`, `\Temp\AVNRecovery.exe`, DiskA/DiskB 복구 경로는 `0xceea6f` 일대에 있다. Phase 0에서 루트 복구 실행 파일과 체크섬 구조를 확인했다. 해당 기기의 벤치 복구 성공, 서명 정책, 사용자 앱 실행 허가 여부는 미확인이다. |

복원한 파일은 `default.hv`, `boot.hv`, `user.hv`, `videodev.dll`, `dsp_bridge.dll`, `AComH_New.exe`다. ROM에 포함된 `AComH_New.exe`에는 YF 계열 앱 경로가 있으므로 GD13MY의 실행 체인을 해당 문자열에 기대어 확정하지 않았다. GD 패키지의 실제 앱 구성은 별도의 `systemCfg.xml`에서 확인했다.

### 재현 및 검증

프로젝트 루트에서 실행한다.

```powershell
python tools/phase1_rom.py
python tools/phase1_scan.py
python tools/check_rea.py --target firmware/extracted/GD13MY/ROM/videodev.dll
python tools/projection_frames.py --mock
python -m unittest discover -s tests -v
```

- CE ROM의 전개에는 [고정한 MIT wince-decompr](https://github.com/KodaSec/wince-decompr/tree/d08163aeda0dec22dbcc363dabf80606413d119c)의 `wincedecompr.py`와 `LICENSE`를 `tools/vendor/wince-decompr/`에 두고 사용한다. 소스의 LF 정규화 후 SHA-256은 `42693ba5e756f664d2405bdaa2f6f9bc5671b5956439aeed581c8e7e89f2e72d`다. 복원한 펌웨어 코드는 실행하지 않았다. [ROM 포맷 참고](https://github.com/pinkavaj/romtools/blob/master/dumprom.cpp)
- Ghidra 12.2는 `gd13my_armv7`에 `-processor ARM:LE:32:v7 -cspec windows`로 APP 6개와 복원한 `videodev.dll`을 추가했다. Phase 0의 USB·영상 DLL을 포함해 기존 분석 결과를 `-process '*' -readOnly -noanalysis`로 열었다. `tools/Phase1Evidence.java`에 `research/evidence/phase1-markers.tsv`와 새 출력 TSV를 넘겨 참조를 기록했다. `tools/Phase1Functions.java`는 `tools/phase1-functions.tsv`에 지정한 함수 9개의 결과를 로컬 분석 폴더에 저장한다. 참조를 찾지 못한 문자는 미확인으로 남겼다.
- REA 6.10.1로 ROM에서 복원한 `videodev.dll`의 PE 메타데이터를 다시 교차 확인했다. REA Windows Ghidra provider의 `0x01c2` 제약 때문에 디컴파일은 Ghidra를 직접 사용했다. Binwalk v3.1.0에 공식 Windows 릴리스 자산이 없고, unblob 26.6.4의 공개 사전 빌드 휠은 Linux/macOS 대상이다. 현재 Windows 작업에서 두 도구 대신 기존 CE BIN 파서, LZX 전개 및 `file` 5.48을 사용했다. [Binwalk 릴리스](https://github.com/ReFirmLabs/binwalk/releases/tag/v3.1.0) · [unblob 릴리스](https://github.com/onekey-sec/unblob/releases/tag/26.6.4)

[ROM 구조와 복원 파일 해시](../research/evidence/phase1-rom.json) · [실제 파일 분류 및 ordinal 해석](../research/evidence/phase1-scan.json) · [Ghidra 문자열 참조](../research/evidence/phase1-xrefs.tsv)
