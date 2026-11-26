# CE OS 이미지 및 에뮬레이션

## 확보 이미지

`F:\`의 순정 GD13MY 배포본과 프로젝트 분석 복사본에서 `BSP.spd.000`의 `kernel`을 확인했다. 이 파일은 평탄한 raw NB0이 아니라 `B000FF` 레코드를 가진 CE BIN 이미지다. 21,599,691 B, 체크섬을 확인한 레코드 160개, ROM TOC의 모듈 189개와 일반 파일 75개, BIN 진입 주소 `0x8000aadc`, ROMHDR `0x854f47ec`다. ROM이 저장된 주소와 XIP 가상주소 사이에 `0x04000000` 차이가 있다. [Windows CE Romimage](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms938650(v=msdn.10)) · [읽기 전용 감사 결과](../build/phase5-evidence/firmware-audit.json)

| 방식 | 확인 결과 |
|---|---|
| Microsoft Device Emulator | CE 6.0에 ARMV4I Device Emulator BSP가 제공됐음을 확인했다. 로컬에는 해당 환경이나 Device Emulator용으로 빌드된 이미지가 없었고, 공식 평가판 다운로드 경로는 404였다. [Microsoft CE 6.0 설명](https://learn.microsoft.com/en-us/archive/msdn-magazine/2006/december/mobilize-explore-the-new-features-in-windows-embedded-ce-6-0) |
| QEMU | ARM CPU 외에 대상 보드의 메모리와 주변장치 모델을 선택해야 한다. 현재 upstream 문서에서 현대 GD13MY 보드 모델을 확인하지 못했고, 로컬에 `qemu-system-arm`도 없었다. [QEMU ARM 시스템 에뮬레이션](https://www.qemu.org/docs/master/system/target-arm) |
| CERF | 8.1.3.669의 `omap_3530_evm`에서 GD13MY 커널 복사본을 읽었다. CE 6.0과 진입 가상주소 `0x8400aadc`를 인식해 커널 초기 코드를 실행했다. 게스트 PC `0x8400b0b0`에서 매핑되지 않은 `0x8ff00000` 접근으로 중단됐다. 완전 부팅, 셸 시작 및 진단 앱의 CE 로딩까지는 도달하지 못했다. [CERF 지원 보드](https://cerf.cx/devices/) · [실행 로그](../build/phase5-evidence/cerf-gd13my.log) |
| 정적 PE/API 검증 | 진단 PE의 ARM/Thumb 헤더, ARM 진입점과 IAT를 `pefile`, REA, 순정 ROM export로 대조했다. [SDK 및 ABI](CE_SDK_RESEARCH.md) |
| Unicorn | `TI925T` 모델에서 진단 PE를 매핑하고 모의 `coredll`을 연결했다. ARM 코드, 파일 읽기 및 오류 처리, 힙, 스레드 콜백, 정상 종료, Android Auto 버전 프레임 왕복을 재현했다. 파일·힙·동기화 서비스는 테스트 코드가 제공하며 실제 CE 스케줄러나 USB 주변장치 동작은 실물 시험에 남아 있다. [Unicorn 2.1.4](https://github.com/unicorn-engine/unicorn/releases/tag/2.1.4) · [정상 결과](../build/phase5-evidence/arm-emulation.json) · [파일 실패 결과](../build/phase5-evidence/arm-emulation-denied-file.json) |

CERF에서는 제공된 커널 복사본, 기본 EVM 보드, 게스트 네트워크 끄기, 7초 제한을 사용했다. 종료 코드 `124`는 실행 시간 제한이며, 최초 실패는 로그의 메모리 매핑 오류다. 커널 복사본의 SHA-256은 실행 후에도 `272b17f49f8c3dd9854755b25a7e6f0173bffb9b53798126c1ecb3f025f7c91e`였다. GD13MY 전용 메모리 맵 및 초기화 자료가 확보되면 오류 주소의 소유 영역을 확인할 수 있다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py tools/emulate_ce_probe.py build/ce-minimal/i30-ce-probe.exe
& $py tools/emulate_ce_probe.py build/ce-minimal/i30-ce-probe.exe --deny-file
```

사용한 CERF 실행 파일은 `%LOCALAPPDATA%\i30-phase5-tools\cerf-8.1.3\cerf.exe`다. ROM 복사본을 입력으로 지정해 짧은 초기화 시험을 재현할 수 있다. [CERF 8.1.3.669 배포](https://github.com/gweslab/cerf/releases/tag/8.1.3.669)

```powershell
$cerf = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/cerf-8.1.3/cerf.exe'
$rom = (Resolve-Path build/phase5-evidence/GD13MY-kernel.bin).Path
& $cerf --device=gd13my_lab --board-id=omap_3530_evm "--rom-primary=$rom" --boot=cold --disable-network --no-focus --timeout=7 --log=BOOT,BOARD,NKDBG,CAUTION
```
