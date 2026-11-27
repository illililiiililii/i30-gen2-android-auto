# GD13MY Android Auto 이식 — 추가 연구 및 개발 인계

기준일: 2026-11-24 | 저장소: [i30-gen2-android-auto](https://github.com/illililiiililii/i30-gen2-android-auto)

## 1. 최종 목표

2013년형 국내 i30 GD 표준형 2세대 순정 내비게이션(GD13MY.KOR.SOP.00.061, Windows CE 6.0, ARM Cortex-A8/OMAP3530)에 Google 순정 Android Auto 수신 기능을 직접 통합한다. 별도 스마트폰 앱, 루팅, 외장 동글 또는 PC를 최종 사용 조건으로 요구하지 않는다. 기존 지도, 후방카메라, 차량 경고, 오디오 및 순정 UI를 보존한다. AARE와 DHU는 연구·검증 도구로 구분한다.

## 2. 현재 개발 상태

직전 저장소 검토 기준 main `381e6c3`. 아래는 저장소 코드와 문서에 기록된 결과이며 이 문서 작성 과정에서 실기 시험을 다시 수행한 것은 아니다.

| 항목 | 상태 |
|---|---|
| Unicorn 기반 순정 WinCE 부팅 및 메뉴 | 에뮬레이터 검증 |
| 순정 메뉴 Android Auto 항목, i30nav.dll 통합 | 구현 및 모의 검증 |
| USB AOA 2, AA 1.7 버전 협상 | 실폰 응답 확인 |
| BearSSL 0.6 TLS 1.2, AUTH_COMPLETE, 서비스 탐색 | 모의 피어 검증 |
| H.264 Baseline, 800×480 LCD 출력 | 모의 영상 검증 |
| 채널별 프레임 재조립 및 Ping/Pong | 수정 ARM DLL 시험 성공 기록 |
| Python 회귀 시험 | 84개 통과 기록 |
| Google 순정 앱과 자체 수신기 상호 TLS | 미완료, 인증서 신뢰 오류 |
| 실제 폰 영상·터치·오디오 및 장시간 세션 | 미검증 |
| 실제 헤드유닛 설치 및 성능 | 미검증 |

11월 24일 격리 WinCE 시험에서는 저장된 DHU 화면을 시험 영상으로 전송했으며 LCD 원본 대비 RGB 채널 평균 절대 오차 3.15/255를 기록했다. 실제 폰의 실시간 영상 출력과 혼동하지 않는다. 최신 ARM 실폰 재시험 중 이전 세션의 잔류 프레임으로 추정되는 데이터가 관측되어 버전 단계에서 종료된 사례도 있다.

주요 자료: [인증 상태](https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/ANDROID_AUTO_AUTH_STATUS.md), [역공학 및 재시험](https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/ANDROID_AUTO_REVERSE_ENGINEERING.md), [순정 화면 통합](https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/CE_NATIVE_DISPLAY_INTEGRATION.md), [세션 인계](https://github.com/illililiiililii/i30-gen2-android-auto/blob/main/docs/SESSION_HANDOFF.md).

## 3. 오류 07과 DeepSeek 연구의 핵심

[DeepSeek 보고서 모음](https://github.com/illililiiililii/i30-gen2-android-auto/tree/main/docs/DeepSeek-search)의 1차 연구, 2차 보고서, 성공 가능성 평가를 참고한다.

- 동일 스마트폰에서 공식 DHU 2.0은 AA 1.7, TLS 1.2, ECDHE-RSA-AES128-GCM-SHA256(0xC02F) 연결에 성공했다. 이전 USB 반복 시험 10회 성공 기록이 있다.
- 자체 수신기는 TLS 서버 응답 및 CertificateRequest까지 관측했으나 자체 발급 HU 인증서를 제시한 뒤 폰에서 `Trust anchor for certification path not found`가 기록됐다.
- 자체 신원을 사용한 TCP 개발자 서버 시험에서도 오류 07이 재현됐다. 따라서 해당 시험의 직접적인 실패 원인은 HU 인증서 신뢰 체인으로 판단된다. 모든 오류 07이 같은 원인이라는 뜻은 아니다.
- BearSSL은 이미 모의 TLS 1.2 시험을 통과했으므로 근거 없이 wolfSSL 등으로 전면 교체할 필요가 없다.
- DHU 2.1 인증 자료에 관한 공개 연구가 있으나, 공개 접근 가능성과 타 수신기에서의 사용 권한은 별개다. 공식 DHU 2.0 성공도 다른 구현의 인증 성공을 보장하지 않는다.
- DeepSeek의 오류 해결 85~90%, 화면 투사 55~70%, 안정 사용 30~50% 수치는 주관적 추정이다. 측정된 확률로 사용하지 않는다.

## 4. AARE에서 얻은 단서

[AARE](https://github.com/prototux/AARE), [인증서 문서](https://github.com/prototux/AARE/blob/main/docs/certificates.md), [인증 연구 저장소](https://github.com/iscle/android-auto-certificates).

AA는 TLS 상호 인증을 사용한다. 헤드유닛은 TLS 클라이언트, 스마트폰은 서버 역할이다. AARE가 설명하는 CarService 인증 자료는 스마트폰 측 신원이며 HU 신원과 다르다. Google Automotive Link 신뢰 체인, 공개 인증서 메타데이터, 유효기간 및 역할별 검증 정책을 비교하는 데 유용하다.

AARE는 사용자 승인으로 자체 시험용 HU 인증서를 신뢰할 수 있으므로 실제 스마트폰을 이용한 USB/TLS/영상/입력 진단에 활용할 수 있다. AARE 연결 성공은 Google 순정 앱의 인증 성공을 의미하지 않는다. 최종 제품에는 AARE를 요구하지 않는다. 제3자 개인키의 추출·재사용 대신 사용 권한이 확인된 시험 신원과 공개 인증서 메타데이터를 사용한다.

## 5. 새 연구 방향: 현대·기아 순정 AA 펌웨어 비교

### 5.1 최우선 후보 — 북미 Elantra GT (GD)

현대자동차의 2016년 서비스 공지 [TSB 16-BE-005-2](https://static.nhtsa.gov/odi/tsbs/2016/SB-10081532-0699.pdf)는 호환되는 2016년형 Elantra GT 순정 8인치 내비게이션에 Android Auto와 Apple CarPlay를 추가하는 업데이트를 명시한다.

- 초기 AA 지원 SW: `ST.GD.USA.E509.160417`
- 공식 북미 업데이트 목록에서 이전 대화 중 확인한 모델: `GDAS.S4AMC.US` (2016~2017)
- 당시 확인한 SW: `ST.GD.USA.E543.250408`
- [북미 공식 업데이트 목록](https://update.hyundai.com/US/EN/updateNoticeView/software-version)

동일 GD 차량이라는 점이 유용하지만 국내 2013년형 표준형 2세대와 동일 OS/CPU/ABI라는 증거는 없다. 실제 차량 펌웨어를 확보해 확인해야 한다. 최신 버전의 다운로드 가능 여부도 별도 확인한다.

### 5.2 추가 후보

| 우선순위 | 차량/계열 | 비교 SW 후보 |
|---|---|---|
| 1 | 북미 Elantra GT GD | ST.GD.USA.E509.160417 |
| 2 | 북미 Genesis DH | ST.DH.USA.E509.160420 |
| 3 | 국내 G80 고급형 2세대 | DHPE.KOR.SOP.00.057 / DHBS.P2ALC.KR |
| 4 | 북미 Sonata LF | ST.LF.USA.E507.160415 |
| 5 | 북미 Tucson TL | ST.TL.USA.E509.160516 |
| 6 | 기타 현대·기아 표준형 4세대 | AA 지원 모델별 확인 |

북미 초기 SW는 위 TSB를 참고한다. 국내 G80 모델은 [제네시스 공식 목록](https://update.genesis.com/KR/KO/updateNoticeView/software-version)을 참고한다. 국내 고급형 2세대의 정확한 AA 지원 빌드와 OS/CPU는 아직 확인해야 한다. PC용 업데이트 프로그램과 실제 차량 펌웨어를 혼동하지 않는다.

### 5.3 비교 분석 항목

1. 공식 배포 경로에서 사용 권한이 있는 펌웨어 확보. 가능하면 AA 지원 전후 버전을 확보하고 해시·출처·모델·버전을 기록한다.
2. 컨테이너, 파일시스템, 실행 파일 형식, CPU, OS, ABI 및 라이브러리 의존성 식별.
3. AA 수신기, SDK, USB/AOA, TLS 라이브러리, 서비스 탐색 모듈 식별.
4. 공개 인증서의 발급자·체인·확장 필드·유효기간과 인증 자료 공급/등록 방식 분석. 정식 평가 SDK 및 발급 경로 조사.
5. 영상 하드웨어 가속, 코덱, 프레임버퍼, 터치, PCM, 마이크, 오디오 포커스, 후방카메라·OSD 선점 구조 비교.
6. 현재 구현과 차이를 기록하고 적용 가능한 독립 구현 개선안을 제시한다. 호환성·라이선스가 확인되지 않은 바이너리를 그대로 이식하지 않는다.

인증서의 필드와 형식을 재현하더라도 신뢰된 CA의 전자서명이 없으면 Google 앱의 신뢰 검증을 통과할 수 없다. 순정 인증 로직 분석의 가치는 공급 구조, 호환성 및 정당한 평가 자료 확보 경로를 밝히는 데 있다.

## 6. 참고 프로젝트 및 자료

| 자료 | 활용 목적 |
|---|---|
| [aasdk](https://github.com/f1xpl/aasdk), [openauto](https://github.com/f1xpl/openauto) | AAP 프레이밍, 세션, TLS 구조 |
| [JanRi3D/OpenAuto](https://github.com/JanRi3D/OpenAuto) | 채널별 프레임 조립, 실폰 상호운용 사례 |
| [headunit-revived](https://github.com/geraldhoong/headunit-revived) | Android 수신기 TLS 및 채널 처리 비교 |
| [open-headunit](https://github.com/andreknieriem/open-headunit) | 오류 07 및 최신 상호운용 보고 |
| [aa-proxy-rs](https://github.com/aa-proxy/aa-proxy-rs) | USB/AOA 및 전달 구조; 자체 HU 인증 해결책은 아님 |
| [Ford WinCE AutoKit](https://github.com/typlo-gh/Ford-WINCE-Autokit) | WinCE 동글 방식 비교; 독립 수신기와 구분 |
| [XDA WinCE 이식 논의](https://xdaforums.com/t/porting-android-auto-to-existing-windows-ce-car-headunits.2795971/page-5) | 과거 이식 시도 및 동글 사례 |
| [XDA AutoLink 오류 7](https://xdaforums.com/t/need-firmware-for-autolink-mp5-zcd-mcu-android-auto-error-7-came-with-used-car.4761332/) | 다른 TLS 실패 사례; GD13MY 원인과 구분 |

외부 프로젝트의 소스 라이선스와 인증 자료 사용 권한은 별도로 검토한다. XDA 접근 실패 시 공개 웹 아카이브를 이용하며 확인하지 못한 내용을 추정으로 채우지 않는다.

## 7. Codex 한도 초기화 전 작업 계획

약 5일의 공백 동안 무료 AI를 활용해 독립적인 연구를 수행한다. 기존 main 핵심 코드를 무리하게 변경하지 않는다.

- 1일차: 공식 펌웨어 확보 경로 및 비교 버전 확인.
- 2일차: REA/Ghidra 등으로 OS·CPU·ABI·파일 목록 분석.
- 3일차: AA 모듈, 공개 인증 구조, SDK 및 공급 경로 분석.
- 4일차: USB/TLS/영상/오디오/순정 UI 구조 비교.
- 5일차: 근거와 미확인 사항, 재현 절차, 적용 후보를 문서화하여 Codex에 인계.

도구가 실제로 설치되어 있다면 Serena, Code Review Graph, RTK, Ponytail, Caveman, REA, Ghidra/MCP를 활용한다. 분석은 별도 로컬 폴더 또는 연구 브랜치에서 진행한다. 원본 펌웨어, 독점 바이너리, 개인키 및 대용량 로그는 GitHub에 올리지 않는다.

## 8. 다음 구현 단계와 성공 판정

1. 공식 DHU 기준 연결과 자체 수신기 연결을 독립적으로 비교한다. 케이블 재연결 및 USB 초기 열거를 포함한다.
2. 사용 권한이 확인된 HU 시험 신원으로 실폰 TLS 완료, AUTH_COMPLETE, 암호화 서비스 탐색을 검증한다.
3. 실제 폰의 첫 H.264 프레임을 WinCE 순정 창에서 표시한다. PC 수신기 인계나 저장 영상 재생은 성공으로 계산하지 않는다.
4. 터치, 오디오, 마이크, USB 재연결 및 장시간 세션을 검증한다. `src/ce/ce_aa_usb_client.c`의 TLS 8초·영상 20초 제한과 작업 스레드 수명 구조를 검토한다.
5. 실제 헤드유닛 벤치에서 CPU 부하, FPS, 지연, 발열, 순정 화면·후방카메라·경고·오디오 선점 및 복귀를 검증한다.
6. 복구 절차와 사용자 승인이 확보되기 전 실제 차량에 플래시하지 않는다. 타 차종 펌웨어 전체를 설치하지 않는다.

## 9. 실현 가능성 판단

WinCE 네이티브 수신기 및 순정 UI 통합은 상당한 구현 근거가 있다. 다만 Google 순정 앱의 인증 성공은 신뢰된 HU 신원 확보에 달려 있고 실제 하드웨어 성능은 아직 불확실하다. 이전 전체 작업량 약 55% 평가는 주관적인 진행도이지 성공 확률이 아니다.

가장 중요한 다음 이정표는 **Google 순정 Android Auto 앱과 GD13MY 네이티브 수신기 사이의 TLS 완료 및 암호화 서비스 탐색**이다. 순정 펌웨어 비교 연구는 이 장애물과 실기 성능 문제를 줄일 새로운 단서를 찾기 위한 병행 과제다.

---

## 추가 연구 부록 — OMAP3530 영상 가속, 초기 업데이트 패키지 및 참고 구현

추가일: 2026-11-24. 아래는 후속 조사 후보이며, 링크된 자료의 최신 접근 가능 여부와 실제 바이너리 호환성은 별도로 검증한다. 기존 인증 연구와 병행하되 현재 구현을 대체하거나 실기 성공을 전제하지 않는다.

### A. TI OMAP3530 공식 기술 자료

OMAP3530은 Cortex-A8, NEON, C64x+ DSP, IVA2.2 멀티미디어 서브시스템 및 PowerVR SGX 그래픽 기능을 갖춘 SoC다. DSP 기반 영상 처리 가능성은 있으나 실제 GD13MY 보드에서의 활성화 여부, WinCE 드라이버, 코덱 라이선스 및 지원 프로파일은 미확인이다. GPU가 존재한다는 사실만으로 H.264 하드웨어 디코딩을 보장하지 않는다.

| 자료 | 조사 목적 |
|---|---|
| [OMAP3530 Datasheet](https://www.ti.com/lit/ds/symlink/omap3530.pdf) | SoC 구성, 메모리 및 주변장치 |
| [OMAP35x Technical Reference Manual](https://www.ti.com/lit/ug/spruf98y/spruf98y.pdf) | MUSB, DMA, INTC, DISPC, DSP 레지스터와 에뮬레이터 검증 |
| [TI OMAP35x CODECS](https://www.ti.com/tool/OMAP35XCODECS) | 최적화 코덱, 지원 플랫폼 및 배포 조건 |
| [DaVinci/OMAP Workshop](https://software-dl.ti.com/trainingTTO/trainingTTO_public_sw/davinci/TTO_Workshop_%28v2.10%29/DaVinci-OMAP_Workshop_%28v2.1%29.pdf) | DSP 및 Codec Engine 구조 |
| [OMAP3530 Errata](https://www.ti.com/lit/er/sprz278f/sprz278f.pdf) | 실리콘 리비전별 USB/DMA 등 알려진 제약 |

추가 확보 대상: OMAP3530 WinCE 6.0 BSP, OEM adaptation layer 및 USB host 드라이버 자료, WinCE용 DSP/Codec Engine SDK, 영상 코덱 지원 목록, 순정 보드 서비스 매뉴얼과 회로도. 실제 자료 확보 여부는 별도 기록한다.

### B. 순정 영상 처리 경로 분석

기존 역공학에서 확인된 `LibUSB.dll`, `LibVideo.dll`, `LibMMCodec.dll`, `LibSound.dll`을 우선 조사한다. `LibMMCodec.dll` 존재 자체는 DSP H.264 지원의 증거가 아니다.

1. REA/Ghidra로 PE 아키텍처, import/export, 호출 관계, 문자열, IOCTL, DSP 관련 드라이버 의존성을 조사한다.
2. 기존 순정 영상 재생 경로에서 코덱 초기화, 입력 버퍼, SPS/PPS 및 NAL 처리, 출력 픽셀 포맷, stride, 메모리 소유권, 종료 절차를 식별한다.
3. 실제 하드웨어 가속 호출인지 CPU 디코딩인지 구분한다. 에뮬레이터의 DSP 미구현을 실제 보드의 미지원으로 해석하지 않는다.
4. 확인된 API만 별도 어댑터로 연결하고 기존 h264bsd 경로를 폴백으로 유지한다. 확인 전 순정 DLL의 ABI를 추측해 호출하지 않는다.
5. 동일한 800×480 시험 영상으로 프레임률, 디코딩 지연, CPU 사용량, 메모리, 프레임 드롭을 비교한다. 실기와 에뮬레이터 수치를 분리한다. 30fps는 초기 목표이지 달성된 성능이 아니다.
6. 화면 전환, 후방카메라 우선권, 오디오, 터치 및 종료 시 자원 회수를 회귀 시험한다.

### C. 현대자동차 초기 Android Auto 업데이트 추가 단서

- [2020년 TSB 20-BE-008H](https://static.nhtsa.gov/odi/tsbs/2020/MC-10177130-0001.pdf): 초기 폰 프로젝션 추가 업데이트의 후속 서비스 공지. 패키지 부품 번호 `98000-AACP1`(GD/DH/LF/TL 등), `98000-AACP2`(HG/FS/LF HEV/PHEV 등)를 검색 단서로 사용한다. 정확한 적용 차종과 연식은 원문 표를 기준으로 재확인한다.
- [2016년 서비스 공지](https://static.nhtsa.gov/odi/tsbs/2016/SB-10081532-0699.pdf): 북미 Elantra GT GD의 초기 AA 지원 버전 `ST.GD.USA.E509.160417` 비교 후보.
- [북미 공식 업데이트 사이트](https://update.hyundai.com/US/EN/updateNoticeView/software-version): `GDAS.S4AMC.US` 모델의 현재 제공 버전 및 다운로드 가능 여부 확인.

부품 번호는 다운로드 링크나 개별 펌웨어 식별자와 동일하지 않다. 정식 확보 가능한 패키지를 우선하며 AA 지원 이전/최초 지원/최신 버전의 파일 목록, 해시, OS/ABI, SDK 및 공개 인증서 메타데이터를 비교한다. 다른 차량용 펌웨어를 GD13MY에 설치하지 않는다.

### D. 추가 오픈소스 참고 자료

| 프로젝트 | 조사할 내용 | 주의점 |
|---|---|---|
| [stf-ftw/LibAuto](https://github.com/stf-ftw/LibAuto) | USB 수신기, TLS, 영상·오디오·터치·마이크, 재연결 | README 주장과 실제 코드·실폰 시험을 구분 |
| [mretallack/AndroidAuto](https://github.com/mretallack/AndroidAuto) | 장시간 세션, USB 전원 및 연결 실패 복구 | 현재 프로젝트와 통신 역할이 다를 수 있음 |
| [rgerganov/gen5fw](https://github.com/rgerganov/gen5fw) | 현대·기아 Gen5 패키지 분석 도구 및 파일 구조 | Gen2 직접 호환 미확인 |
| [cantcs/HKG_Gen5W_ReverseEngineer](https://github.com/cantcs/HKG_Gen5W_ReverseEngineer) | Gen5W 업데이트 에이전트, 무결성 검증 구조 | 세대 차이, 실제 수정 이미지 설치 금지 |

각 저장소의 접근 가능 여부, 커밋 SHA, 라이선스, 실제 관련 함수와 테스트 기록을 확인한 후 참고한다. AllGo/Motrex의 초기 폰 프로젝션 SDK 및 TI/WinCE 자료도 정식 공개·평가 경로를 조사한다.

### E. 병행 연구 우선순위 및 산출물

| 우선순위 | 작업 | 완료 기준 |
|---|---|---|
| 1 | 인증 및 초기 OEM 펌웨어 비교 | 확보 경로, OS/ABI, TLS 구조, 인증 공급 방식 및 권한 확인 |
| 2 | 순정 DSP 영상 가속 | LibMMCodec 호출 관계, 지원 코덱 및 가속 가능성 근거 확보 |
| 3 | USB 안정성 | TRM/BSP와 기존 MUSB 모델 비교, timeout·잔류 프레임·재연결 분석 |
| 4 | 에뮬레이터 정확도 | 레지스터/IRQ/DMA 동작과 공식 문서의 차이 기록 |
| 5 | 배포 및 복구 | 원본 백업, 패키지 무결성, 안전한 복구 계획 문서화 |

권장 산출물: `docs/OEM_FIRMWARE_COMPARISON.md`, `docs/OMAP3530_VIDEO_ACCELERATION.md`, `docs/USB_STABILITY_RESEARCH.md`. 분석마다 출처 URL, 확인 날짜, 파일 해시, 함수/주소, 확인 사실과 가설, 미확인 항목을 기록한다. 기존 main의 동작하는 코드는 보존하고 실험은 별도 브랜치에서 진행한다. 원본 펌웨어, 비공개 SDK, 개인키 및 민감한 인증 자료는 저장소에 올리지 않는다.

인증 해결과 영상 가속은 독립적인 과제다. 모의 영상 출력 성공은 실폰 인증 성공을 의미하지 않으며, 영상 가속 발견도 오류 07을 해결하지 않는다. 최종 목표는 여전히 별도 앱·동글 없는 순정 Google Android Auto의 실제 GD13MY 통합이다.
