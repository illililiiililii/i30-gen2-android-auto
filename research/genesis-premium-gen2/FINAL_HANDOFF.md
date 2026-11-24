# FINAL_HANDOFF.md: 제네시스 고급형 2세대 역공학 연구 최종 인계서

## 1. 연구 목적 및 최종 결론 요약

본 연구는 현대 i30 GD 2013년형 표준형 2세대(GD13MY, Windows CE 6.0, ARM Cortex-A8) 순정 내비게이션에 Google 순정 Android Auto를 직접 이식하는 프로젝트의 핵심 난제인 **"실물 폰 연결 시 오류 07 (인증서 신뢰 체인 부재)"** 문제를 해결하기 위한 기술적 증거를 확보하고자, Android Auto를 공식 지원하는 제네시스 고급형 2세대(DHPE / G80 DIS Bluelink) 순정 펌웨어를 역공학 분석하였다.

### 핵심 결론 3가지 (VERIFIED)
1. **플랫폼 아키텍처 불일치 확증**:
   - 제네시스 고급형 2세대는 Windows CE가 아닌 **Intel x86 (i386) Linux (MeeGo IVI 기반, glibc, Qt 4.8, X11, GStreamer 0.10)** 플랫폼이다.
   - 따라서 제네시스 순정 바이너리(ELF)를 GD13MY(WinCE ARM PE)로 직접 이식/링크하는 것은 기술적으로 불가능하며, **프로토콜 및 인증 설계 구조의 참조 모델**로 활용해야 한다.
2. **오류 07의 명확한 기술적 실체 확증**:
   - 오류 07은 USB AOA 통신, 프로토콜 버전(AA 1.7), TLS 1.2 암호 스위트(`0xC02F`)의 오류가 아니다.
   - 스마트폰이 `CertificateRequest`를 보낼 때 헤드유닛이 제공하는 X.509 클라이언트 인증서가 Android Auto 앱의 신뢰 저장소(`Google Automotive Link Root CA`)에 의해 검증되지 않아 발생하는 **PKIX X.509 신뢰 앵커(Trust Anchor) 부재 오류**이다.
3. **GD13MY 기존 구현의 유효성 검증**:
   - GD13MY의 BearSSL 0.6 및 `ce_aa_*.c` 소스는 제네시스 순정 사양(TLS 1.2 `0xC02F`, AOA `18d1:2d00`, Channel 0/1/2/3/4)을 완벽히 충족하고 있으며, 가상 폰 및 DHU 2.0에서 정상 작동한다.
   - 순정 코드를 임의로 수정할 필요가 없으며, 인증서 공급 체인 형식 보강이 유일한 핵심 작업이다.

---

## 2. 생성된 산출물 맵 및 위치

작업 기본 경로: `F:\i30-gen2-android-auto\research\genesis-premium-gen2\`  
저장소 공유 문서 경로: `F:\i30-gen2-android-auto\docs\Antigravity-search\genesis-premium-gen2\`

```
genesis-premium-gen2/
├── PROGRESS.md                          # 전체 단계별 진행 상황 추적
├── 01_FIRMWARE_INVENTORY.md             # 펌웨어 식별, 파일 목록, 버전, SHA-256
├── 02_EXTRACTION_REPORT.md              # 7-Zip/LGE TER 암호 봉투 구조 분석
├── 03_PLATFORM_ANALYSIS.md              # OS(Linux MeeGo), CPU(x86), ABI, 런타임
├── 04_ANDROID_AUTO_MODULE_MAP.md        # IBOX, rootfs, keystore 연관 모듈 맵
├── 05_ANDROID_AUTO_REVERSE_ENGINEERING.md # Capstone/Ghidra 기반 어셈블리/수신기 역공학
├── 06_TLS_AUTHENTICATION_ANALYSIS.md    # TLS 1.2, 0xC02F, 신뢰 체인, 오류 07 규명
├── 07_USB_MEDIA_ANALYSIS.md             # AOA, AAP 5개 채널, H.264, ALSA/GStreamer
├── 08_GD13MY_COMPARISON.md              # GD13MY 소스 vs 제네시스 순정 비교 및 권고사항
├── FINAL_HANDOFF.md                     # 본 최종 인계 문서
├── scripts/                             # 자체 제작 정적 분석 및 디스어셈블러 도구
│   ├── disasm_decrypt.py               # LGU 암호 함수 디스어셈블러
│   ├── disasm_main.py                  # main/옵션 처리 디스어셈블러
│   ├── disasm_initdecrypt.py           # TER 푸터 검증 디스어셈블러
│   ├── disasm_pkcs1.py                 # PKCS#1 v1.5 언패딩 디스어셈블러
│   ├── hash_inventory.py               # 펌웨어 SHA-256 일괄 계산기
│   ├── search_keywords.py              # Android Auto 키워드 스캐너
│   └── test_rsa.py                     # RSA 공개키 세션키 복구 시험기
└── extracted/                           # 안전하게 추출된 유틸리티
    └── essentials/
        ├── update.tar                   # 암호화된 업데이트 컨테이너 (14.5 MB)
        └── decrypt/
            ├── DecryptToFile            # LGE 복호화 ELF 바이너리 (심볼 포함)
            └── DecryptToPIPE            # 파이프 출력용 복호화 ELF 바이너리
```

---

## 3. 후속 GPT 및 Codex 작업을 위한 가이드라인

1. **기존 GD13MY 소스 코드 보호**:
   - `src/ce/ce_aa_tls.c`, `src/ce/ce_aa_usb_client.c`, `src/ce/ce_aa_projection.c`의 구조는 이미 검증 완료되었으므로 불필요하게 리팩토링하거나 변경하지 말 것.
2. **오류 07 해결을 위한 검증 접근법**:
   - **방안 1 (Android Auto 앱 수준 우회)**:
     - 루팅 없이 순정 상태를 유지하는 것이 목표이므로, 스마트폰의 "Android Auto 개발자 설정"에서 `알 수 없는 소스 허용` 활성화 후 핸드셰이크 테스트.
   - **방안 2 (헤드유닛 인증서 체인 X.509 속성 완비)**:
     - BearSSL의 `br_x509_minimal_context` 및 인증서 체인 버퍼에 Google Automotive Link가 요구하는 표준 확장 필드(Subject Key Identifier, Authority Key Identifier, Key Usage: `digitalSignature, keyEncipherment`, Extended Key Usage: `clientAuth`)를 완벽히 충족하는 인증서 주입.
   - **방안 3 (중간 프록시 / 가상화 핸드셰이크)**:
     - 초기 AOA 연결 및 TLS 핸드셰이크를 로컬 프록시 형태로 중계하는 방안 검토.
3. **저장장치 및 보안**:
   - G 드라이브는 원본 읽기 전용 상태를 엄격히 유지하였으며, 깃허브 업로드 시에는 `docs/Antigravity-search/genesis-premium-gen2/`의 마크다운 보고서 및 자체 작성 파이썬 스크립트만 반영할 것.
