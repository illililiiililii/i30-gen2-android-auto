# Phase 6 에뮬레이션 및 PC 검증 결과

2026-11-21 KST. 순정 CE 커널 초기 코드는 평가보드 에뮬레이션에서 실행됐다. CE 전체 부팅과 CE 로더에서의 진단 PE 시작은 확인되지 않았다. 같은 PE는 Unicorn의 ARM 명령어 환경과 모의 CE API에서 실행했다.

후속 실험에서 순정 BIN의 OEM 테이블을 복원해 이 문서의 평가보드 중단 지점을 넘겼다. [GD13MY 보드 메모리 맵과 커널 실행](GD13MY_EMULATION.md)

## 실행 경로

| 경로 | 결과 |
|---|---|
| 공식 Windows CE 6.0 Device Emulator | Phase 5의 Microsoft 배포 경로 조사와 로컬 도구를 재사용했다. GD13MY BSP 또는 합법적으로 확보한 호환 CE 6.0 런타임 이미지가 현재 없다. Microsoft의 Device Emulator BSP는 별도 보드 대상이다. [CE 6.0 개발 환경](https://learn.microsoft.com/en-us/archive/msdn-magazine/2006/december/mobilize-explore-the-new-features-in-windows-embedded-ce-6-0) |
| 순정 이미지와 CERF | 기존 `BSP.spd.000`에서 복원한 `B000FF` 형식의 CE BIN을 사용했다. CERF 8.1.3.669의 Phase 5 OMAP3530 EVM Gen1 로그와 Phase 6 Gen2 로그를 대조했다. Gen2는 복사본 해시를 전후 비교하고, 게스트 네트워크 없이 7초 제한으로 한 번 실행했다. [CERF 지원 보드](https://cerf.cx/devices/) · [Gen2 실행 로그](../build/phase6-evidence/cerf-gen2.log) |
| ARMv4T 부분 실행 | `build/ce-minimal/i30-ce-probe.exe`의 ARM 코드를 TI925T 모델에서 실행했다. IAT를 모의 API에 연결하고 PE 섹션 속성을 Unicorn 페이지 권한에 반영했다. 정상(0), 파일 열기 거부(1), 스레드 생성 거부(2) 경로가 끝까지 실행됐고 각 경로에서 힙을 반환했다. [정상](../build/phase6-evidence/arm-normal.json) · [파일 거부](../build/phase6-evidence/arm-deny-file.json) · [스레드 거부](../build/phase6-evidence/arm-deny-thread.json) |
| QEMU | 순정 BSP가 기대하는 메모리·주변장치 모델이 확인되지 않았다. 지원되는 보드 모델을 지정해야 한다는 upstream 조건과 대상 보드 자료 부족으로 QEMU 구성은 진행하지 않았다. [QEMU ARM 보드 요구조건](https://www.qemu.org/docs/master/system/target-arm) |
| 정적 ABI·의존성 | 진단 파일 3,584 B, PE32 머신 `0x01c2`, CE 서브시스템 6.0, `coredll.dll` ordinal 13개를 확인했다. REA가 독립적으로 import 한 모듈과 13개 함수를 판독했다. 진단 PE의 SHA-256은 `17fcc03b4b03b41aa2c1d3ce3f98bbb8f27d593caf1d3382057660a2f05f5b97`이다. [ABI 데이터](../build/ce-minimal/abi.json) |

## 부팅을 중단한 근거

Gen2 로그에서 에뮬레이터가 연 RAM은 `0x80000000–0x87ffffff`와 `0xa0000000–0xa7ffffff`였다. 커널은 가상 진입 주소 `0x8400aadc`에서 실행을 시작했지만, 게스트 PC `0x8400b0b0`의 `stmia r3!, {r1, ip}`가 실행될 때 CERF 주소 변환이 물리 주소 `0x8ff00000`을 매핑하지 못했다. 로그의 `r3` 값은 `0xb3f00000`, `r1`은 0이었다. ROM에서 읽은 호출부 `0x84017eec`는 값 0과 길이 `0x00100000`을 설정한 후 이 저장 루프가 있는 함수 `0x8400b084`를 호출한다. 이 근거는 1 MiB 영역 초기화와 EVM 메모리 맵 불일치를 보여준다. 해당 영역의 실제 보드 용도와 후속 주변장치 요구사항은 미확인이다. 로그의 최종 종료 코드 124는 7초 제한이다. 실제 실패는 제한 전에 발생한 매핑 오류다. [ARM 저장 루프](../build/phase6-evidence/arm-boot-disasm.txt) · [호출부](../build/phase6-evidence/arm-caller-disasm.txt) · [Gen2 실행 로그](../build/phase6-evidence/cerf-gen2.log)

두 평가보드 모델에서 실패 지점이 같고 GD13MY의 RAM 뱅크·BSP 초기화 자료가 없어 전체 부팅 시도를 여기서 종료했다. 매핑과 주변장치를 추정해서 바꾸는 방식은 본체에서의 실행 가능성을 판정하는 근거가 되기 어렵다. 후속 판단에 필요한 자료는 해당 HW 리비전의 메모리 맵과 승인된 본체 진단 실행 경로다.

부분 실행의 이미지 매핑은 16 KiB, 주 스택 쓰기 깊이 624 B, probe 힙 요청 최대 4 B였다. 작업 스레드 콜백은 정상·파일 거부 경로에서 17을 반환하며 별도 스택에 쓰지 않았다. 모두 에뮬레이션 값이다. CE의 실제 스케줄러, 저장매체 쓰기, 자식 프로세스, OS 예외 처리와 물리 I/O는 검증되지 않았다. 파일 읽기·대기·스레드 시작은 모의 API 경계이고, ARM 콜백과 버전 프레임 처리 자체는 PE의 명령어가 수행했다. [부분 실행 도구](../tools/emulate_ce_probe.py)

## 짧은 Windows 시험

| 시험 | Phase 6 실측 또는 관찰 |
|---|---|
| 800×480 / 30 fps와 음악·안내음 동시 처리 | 2.004초, 영상 60/60 프레임, 음악 PCM 100블록, 안내 믹싱 24블록, 영상·PCM 누락 0. 영상 ingress→RGB p95 36.25 ms와 예정 송신→RGB p95 37.47 ms. CPU 0.1094초(논리 코어 하나 기준 5.5%), 샘플링 최대 working set 48.53 MiB. 합성 데이터와 PC 수신기 경계에서 측정했다. [A/V 결과](../build/phase6-evidence/pc-av.json) |
| WinMM과 장치 오류 | 장치 0에서 두 재생 핸들에 무음 버퍼를 공급하고 모두 닫았다. 일부 자원을 획득한 뒤 장치 오류가 발생하는 모의 경로에서 해제를 확인했다. [WinMM 데이터](../build/phase6-evidence/pc-av.json) · [회귀 로그](../build/phase6-evidence/targeted-unittest.log) |
| 마이크 ACK 및 선점 중 분리·전환 | ACK 지연과 다른 세션 ACK를 주입해 미확인 상한 2와 정상 재개를 확인했다. 카메라가 선점한 상태의 모의 USB 재연결에서 OEM 해제 전에는 프로젝션이 재개되지 않았다. [회귀 로그](../build/phase6-evidence/targeted-unittest.log) |
| 모의 폰과 프로세스 | 암호화된 모의 링크의 분리·재연결에서 링크 2개 반환, 키 보고 8개, 터치 2개, 마이크 PCM 3블록, 디코딩 7프레임을 확인했다. 별도의 Windows 네이티브 시험에서 종료 코드 42의 비정상 종료와 heartbeat 만료·강제 종료·복구를 확인했다. [모의 링크 로그](../build/phase6-evidence/mock-usb-reconnect.jsonl) · [네이티브 로그](../build/phase6-evidence/ce-host-test.log) |

Phase 5의 기본 수신기 시험 기반을 유지하고 Phase 6의 대상 회귀만 실행했다. 장시간 부하 시험은 보류했다. 실기기용 처리량·지연으로 외삽할 수 없다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py -m unittest discover -s tests -p test_phase5.py -v
& $py tools/check_phase5_av.py --seconds 2 --wave-device 0
& $py tools/emulate_ce_probe.py build/ce-minimal/i30-ce-probe.exe --deny-thread
& ./build/ce-host-test/i30-ce-host-test.exe
```
