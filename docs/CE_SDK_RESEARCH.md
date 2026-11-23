# Windows CE 6.0 ARMV4I 최소 개발 환경

2026-11-21 KST 기준. GD13MY ROM용으로 확인한 CE API에 맞춰 3,584 B의 `i30-ce-probe.exe`와 ARM 라이브러리 `libi30_aa_wire.a`를 빌드했다. 산출물은 [build/ce-minimal](../build/ce-minimal/)에 있다. CE 장치 및 CE OS 내부 로더에서의 실행은 대기 중이다.

| 경로 | 조사 결과 |
|---|---|
| Microsoft Platform Builder | CE 6.0의 ARMV4I Device Emulator BSP와 SDK 개발 환경은 Visual Studio 2005 세대에 제공됐다. 공식 SP1·업데이트 롤업은 기존 제품을 요구한다. Microsoft 평가판과 독립 에뮬레이터의 기존 Download Center 주소를 조회했으나 404였다. GD13MY 전용 SDK는 확보되지 않았다. [Microsoft CE 6.0 소개](https://learn.microsoft.com/en-us/archive/msdn-magazine/2006/december/mobilize-explore-the-new-features-in-windows-embedded-ce-6-0) · [공식 SP1 요건](https://www.microsoft.com/en-us/download/details.aspx?id=4097) |
| 이전 빌드 경로 | `build_ce.py`는 OEM 환경에서 레거시 `cl.exe`/`link.exe`, CE 헤더, `coredll.lib`/`corelibc.lib`로 이전 Phase 4 어댑터를 빌드하는 경로다. 이 컴파일러와 OEM 헤더는 현재 PC에서 확보하지 못했다. [TI의 레거시 ARM 설정](https://software-dl.ti.com/dsps/dsps_public_sw/sdo_sb/targetcontent/rtsc/3_16_02_32/exports/docs/cdoc/microsoft/targets/arm/WinCE-src.html) |
| CeGCC | Windows CE 전용 공개 도구군이다. 공식 사전 빌드는 Cygwin 또는 Linux 환경을 사용한다. 이 PC에는 사용 가능한 WSL 배포판이나 기존 CeGCC가 없었다. [CeGCC 배포 목록](https://cegcc.sourceforge.net/download.html) |
| 이번 빌드 | Arm GNU Toolchain 14.2.Rel1의 `arm-none-eabi-gcc`, GNU 링커와 `ar`를 사용한다. 아카이브 SHA-256은 Arm 배포처의 값 `6facb152ce431ba9a4517e939ea46f057380f8f1e56b62e8712b3f3b87d994e1`과 대조했다. [Arm GNU Toolchain](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads) |

`ce_minimal.h`는 진단 앱에 필요한 13개 API의 32비트 선언을 갖는다. 링크 과정에서 `coredll.dll` ordinal의 IAT와 ARM 인터워킹 호출 스텁을 생성하고, ARMv4T 고정 주소 코드 섹션을 Windows CE용 PE32로 배치한다. ARM 명령어 진입점은 순정 `uComH_New.exe`와 동일하게 짝수 RVA이며, PE 헤더는 머신 `0x01c2`, subsystem `9`, 버전 `6.0`, 이미지 베이스 `0x10000`이다. ELF 속성에서 ARMv4T와 Thumb-1 상한을 확인했다. REA는 독립적으로 `coredll.dll` 하나와 ordinal 13개를 동일하게 읽었다. [PE 형식](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) · [ABI 보고서](../build/ce-minimal/abi.json)

`tools/audit_ce_firmware.py`는 원본 BSP에서 커널을 풀어 실제 `coredll.dll` export를 다시 읽고, 빌드가 참조한 13개 ordinal을 대조한다. 진단 앱은 CRT 없이 시작해 디버그 로그를 남기고, 자기 파일의 `MZ`를 읽고, 힙과 작업 스레드를 사용해 완료 코드를 확인한다. 모의 USB 전송 인터페이스로 Android Auto 1.6 요청과 1.7 응답을 검증한 후 `ExitThread`를 호출한다. 고정 베이스 단일 EXE의 범위이며 범용 OEM SDK, C++ 런타임 및 드라이버 헤더는 별도 과제다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
& $py -m pip install -r requirements-phase5.txt
& $py tools/build_ce_minimal.py --compiler $cc
& $py tools/inspect_ce_pe.py build/ce-minimal/i30-ce-probe.exe
& $py tools/audit_ce_firmware.py
```
