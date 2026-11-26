# i30 Gen2 Android Auto

## 최신 개발 상태 및 문서 안내

[현재 상태](docs/PROJECT_STATUS.md) · [다음 작업](docs/NEXT_TASKS.md) · [최신 인계](docs/HANDOFF.md) · [전체 문서 색인](docs/INDEX.md)

아래 Phase별 내용은 당시의 연구 기록이다. 최신 AARE 자동 실행과 실폰 검증 상태는 위 문서를 우선한다.

## Phase 7·8 · 순정 CE 에뮬레이터 시험판

순정 내비의 `내비설정 → 기타 → Android Auto`에서 USB 버전 협상을 시험하고 부팅 시 연결 시도 여부를 저장할 수 있다. [실행 방법과 검증 결과](docs/testing/PHASE7_8_RESULTS.md) · [에뮬레이터 아키텍처](docs/emulator/EMULATOR_ARCHITECTURE.md)

## Phase 6 · 에뮬레이션 우선 검증

OMAP3530 EVM Gen2에서 순정 커널의 초기 RAM 쓰기 주소와 에뮬레이터의 메모리 맵이 불일치함을 확인했다. ARM 진단 앱의 정상 및 오류 경로와 짧은 Windows 통합 시험을 검증했다. 실물은 본체 식별부터 진행하며, 펌웨어 변경은 복구 검증까지 보류한다. [준비 상태](docs/safety/PHASE6_READINESS_REPORT.md) · [에뮬레이션 결과](docs/emulator/PHASE6_EMULATION_RESULTS.md) · [벤치 가이드](docs/safety/PHASE6_BENCH_TEST_GUIDE.md) · [벽돌 위험 평가](docs/safety/PHASE6_BRICK_RISK_ASSESSMENT.md)

후속 시험에서는 GD13MY 순정 BIN의 OEM 테이블로 보드 모델을 구성해 RAM 초기화, CE의 페이지 처리, `filesys.dll`과 `pm.dll`의 초기 코드 실행을 확인했다. [순정 커널 메모리 맵과 재현 절차](docs/emulator/GD13MY_EMULATION.md)

## Phase 5 · ARM 빌드와 에뮬레이션

GD13MY ROM의 `coredll.dll` export를 기준으로 CE 6.0 PE 진단 앱과 Android Auto 버전 협상 라이브러리를 크로스 컴파일했다. 진단 앱은 ARM 명령어 에뮬레이터와 CE API 모의 구현에서 실행했다. 순정 커널은 OMAP3530 평가보드 모델에서 초기 실행 후 메모리 매핑 오류로 중단됐다. [빌드 및 ABI](docs/architecture/CE_SDK_RESEARCH.md) · [에뮬레이션](docs/emulator/CE_EMULATION_FEASIBILITY.md) · [포팅](docs/archive/CE_PORTING_STATUS.md) · [펌웨어 구조](docs/firmware/FIRMWARE_PACKAGING.md) · [테스트 결과](docs/testing/PHASE5_TEST_RESULTS.md) · [Phase 6 계획](docs/archive/PHASE6_PLAN.md)

## Phase 3·4 · PC 통합 및 CE 어댑터

기존 수신기에 물리 버튼 라우팅, PCM 음악·안내음 믹싱, 마이크 채널, PC 프로젝션 창을 추가했다. 모의 TLS 세션에서 버튼·터치, 오디오 덕킹, 마이크 전송, USB 분리·재연결, 순정 화면 우선 전환을 검증했다. CE 6.0 ARMV4I용 WaveDev 어댑터와 수신기 프로세스 감독 코드가 있으며, 대상 SDK를 사용한 빌드와 실물 벤치 검증은 남아 있다.

[실행 방법, 테스트 결과 및 순정 통합 상태](docs/archive/PHASE3_PHASE4_STATUS.md)

## Phase 2 결과 · 실폰 USB 및 버전 협상 확인

Windows PC용 USB·프로토콜 진단 앱을 빌드했다. 삼성 테스트폰에 대해 PC 쪽 WinUSB 환경에서 AOA 2 전환, bulk 연결과 Android Auto 1.7 버전 응답을 확인했다. 같은 폰과 케이블로 Google DHU 2.0의 TLS 1.2 연결, 800×480 화면 표시 및 앱 런처 탭에 대한 화면 반응을 확인했다. 프로젝트 수신기는 모의 TLS 세션에서 H.264 영상 프레임 출력과 터치 누름·뗌 전송을 검증했다. 이 수신기의 실폰 TLS·서비스·영상·입력 검증에는 등록된 테스트 인증 자료가 필요하다.

| Phase 2 문서 | 내용 |
|---|---|
| [아키텍처와 빌드](docs/architecture/PHASE2_ARCHITECTURE.md) | PC 실행 패키지, 수신기 구성, 테스트 재현 |
| [프로토콜 구현](docs/android-auto/PROTOCOL_IMPLEMENTATION.md) | 프레임, 버전, TLS, 서비스·채널 |
| [USB 연결 시험](docs/testing/USB_CONNECTION_TEST.md) | 실제 열거, 모의 결과, 실폰 절차 |
| [포팅 상태](docs/archive/PORTING_STATUS.md) | 후보 빌드 및 Windows CE 적용 조건 |
| [Phase 3 계획](docs/archive/PHASE3_IMPLEMENTATION_PLAN.md) | 착수 조건, 영상·오디오·입력 계획 |

## Phase 1 결과

PC 기반 Phase 2 MVP는 착수 가능하다. 실물 적용은 USB AOA, Android Auto에 필요한 H.264 스트림 처리, 실행·복구 경로의 벤치 검증까지 보류한다. Phase 1은 CE ROM에서 영상 장치와 레지스트리를 복원하고, 실제 ROM의 ordinal을 사용해 APP의 I/O 호출을 식별했다.

| Phase 1 문서 | 범위 |
|---|---|
| [심층 역공학](docs/research/DEEP_REVERSE_ENGINEERING.md) | ROM/CE ABI, 부팅, 런타임, 재현 절차 |
| [USB 분석](docs/android-auto/USB_ANALYSIS.md) | 호스트, 열거, 미디어 및 AOA |
| [영상·오디오·입력](docs/android-auto/VIDEO_AUDIO_ANALYSIS.md) | 디코더, 출력과 순정 통합 |
| [수신기 포팅](docs/android-auto/ANDROID_AUTO_PORTING.md) | 소스 단위 비교와 방안 선택 |
| [하드웨어 판정](docs/hardware/HARDWARE_COMPATIBILITY.md) | 확인 수준과 추가 실물 자료 |
| [Phase 2 구현 계획](docs/archive/PHASE2_IMPLEMENTATION_PLAN.md) | PC MVP 및 벤치 통과 기준 |

## Phase 0 결과

2013년형 i30 GD 한국형 패키지 `GD13MY.KOR.SOP.00.061`에서 **32비트 ARM/Thumb용 Windows Embedded CE 6.0 계열**의 BSP와 순정 애플리케이션을 확인했다. 순정 디스플레이, USB 호스트, 오디오, 터치용 구성은 존재한다. 현 단계 판정은 **D · 구현 보류**다. 실물 식별, USB AOA, 영상 디코딩 및 설치 경로의 검증을 통과하면 **B · CE용 경량 수신기**를 우선 검토한다.

| 문서 | 내용 |
|---|---|
| [펌웨어](docs/firmware/FIRMWARE.md) | 버전, 파일 구성, 추출, 무결성, 저장 볼륨 |
| [하드웨어와 순정 기능](docs/hardware/HARDWARE.md) | ROM 및 APP에서 확인한 인터페이스와 미확인 사양 |
| [Android Auto](docs/android-auto/ANDROID_AUTO.md) | 요구사항 10개와 수신기 후보 |
| [선행 조사](docs/research/RESEARCH.md) | 요청받은 12개 저장소와 대안 |
| [타당성](docs/research/FEASIBILITY.md) | 방안 A–D와 판정 기준 |
| [다음 단계](docs/archive/DEVELOPMENT_PLAN.md) | 장비, 벤치 테스트, 통과 조건 |
| [Windows 분석 환경](docs/architecture/ENVIRONMENT.md) | 설치 버전과 재현 명령 |

`firmware/original/`에 원본과 SHA-256이 일치하는 44개 파일(2,641,179,073바이트)이 있다. `firmware/extracted/`에 분석용 파일이 있다. 두 경로는 Git에서 제외된다. 패키지, 실물 기기, 공개 저장소에 대한 쓰기 작업은 Phase 0 범위에서 제외했다.

주요 근거는 [전체 파일 목록](research/evidence/inventory.csv), [추출 목록 및 패키지 오프셋](research/evidence/gd13my-streams.json), [CE ROM 목록](research/evidence/ce-rom.json), [상류 저장소 커밋](research/evidence/upstream-metadata.json)에 있다. 오프셋은 별도 표기가 없으면 해당 파일 시작부터 계산한다.
