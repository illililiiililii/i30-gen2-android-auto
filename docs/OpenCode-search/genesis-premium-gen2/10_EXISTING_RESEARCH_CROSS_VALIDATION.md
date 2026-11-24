# 10. 기존 연구 교차검증 (DeepSeek / ChatGPT / Antigravity)

작성일: 2026-11-24
범위: `docs/DeepSeek-search/`, `docs/chatGPT-search/`, `docs/Antigravity-search/`의 결론을 1차 자료(공개 인증서, 공개 저장소 소스, 이 저장소의 실측 로그, 펌웨어 바이너리)와 대조.
원칙: 이전 결론과 확률을 신뢰하지 않고 재검증했다. 모든 항목은 아래 7개 등급 중 하나로 분류한다.

| 등급 | 의미 |
| --- | --- |
| `[확인됨]` | 공개 1차 자료 또는 이 저장소의 실측으로 재현 가능 |
| `[미검증 가설]` | 그럴듯하지만 증거가 없거나, 이번 조사에서 확인하지 못함 |
| `[외부 신규 검증]` | 이번 조사에서 새로 확보한 외부 증거 |
| `[제네시스 펌웨어 직접 증거]` | G80/DHPE 펌웨어(또는 그 컨테이너)에서 직접 확인 |
| `[GD13MY 적용 가능]` | i30 GD13MY(WinCE/ARM)에 그대로 적용 가능한 결론 |
| `[GPT 분석 필요]` | 모델/프로토콜 추론이 더 필요한 항목 |
| `[Codex 구현 필요]` | 코드/테스트 작업이 필요한 항목 |

---

## 1. 한 줄 결론

**에러 07의 이 프로젝트 원인은 "HU 클라이언트 인증서 체인이 phone의 신뢰 앵커(`O=Google Automotive Link`)로 이어지지 않음"으로 확정적이며, TLS 1.2/`0xC02F` 협상 실패나 인증서 만료가 아니다.** 다만 외부 사례에서는 같은 "error 7" 표시가 TLS 스택 호환성, Google 정책 변경, 단순 설정 오류에서도 나타나므로, 에러 코드만으로 원인을 단정하면 안 된다.

---

## 2. DeepSeek 연구 검증

### 2.1 DHU 2.1 인증서 "만료" 혼동

- 주장: DHU 2.1 `metadata.json`의 `notBefore`/`notAfter`가 비어 있어 날짜 계산이 틀렸고, 실제 인증서는 2048년까지 유효하다.
- 검증: 공개 DHU 2.1과 `dhu/latest` 인증서를 직접 디코드했다.
  - SHA-256: `4eb581dcee2b84369ca87066ab6eaa73a4783aef5c7b6edc6841e066cffa7e7c`
  - Subject: `C=US, ST=California, L=Mountain View, O=Android-Auto-Internal, OU=01`
  - Issuer: `O=Google Automotive Link`
  - Serial: `0x0111`, X.509 v1, RSA 2048, `sha256WithRSAEncryption`
  - Validity: `2014-07-04 07:00:00Z` ~ `2048-08-01 17:21:23Z`
  - `metadata.json`: `"version": "2.1"`, `"notBefore": null`, `"notAfter": null`
- 판정: `[확인됨]` 날짜 혼동의 원인은 metadata의 null 필드다. **DHU 인증서 만료는 에러 07의 원인이 아니다.**
- 보정: DHU 2.1과 latest 인증서는 바이트 단위로 동일하다(다운로드 파일 SHA-256 동일). "버전이 다르니 인증서도 다르다"는 가정은 틀렸다.

### 2.2 phone leaf 만료 2027-02-17

- 주장: phone이 보내는 leaf 인증서는 2027-02-17에 만료되며, 이는 프로젝트가 관측한 값과 일치한다.
- 검증:
  - 실측 캡처 `build/gd13my-ce-projection/phone-tls-public.json`: `notAfter = Feb 17 19:01:30 2027 GMT`, SHA-256 `46d907a7482d0abd5d0ca26c0f14784808cc0e614945a2f3921c53099754d27c`
  - Android Auto `18.0.664264-release` 패키지에서 추출한 인증서와 동일 지문/만료.
  - 체인: `O=CarService` leaf ← `O=Google Automotive Link` root(self-signed, 2044-06-05까지, SHA-256 `49e52efc13ad2ed09f204c3b10698bd84bb7105f510558aa14b8119a5c4ad17f`).
- 판정: `[확인됨]` **2027-02-17은 실제 미래 절벽이다.** 다만 Google이 phone 앱 업데이트로 교체할 수 있으므로 "프로젝트가 해결해야 할 문제"는 아니다. HU 쪽 만료(DHU 2048, JVC 2045)는 당장 문제가 아니다.

### 2.3 "에러 07 = 인증서 체인 거부"

- 주장: GD13MY에서 phone이 HU의 self-signed/사설 CA 인증서를 거부해 에러 07이 발생한다.
- 검증: 이 저장소의 BearSSL 로그에서 `BR_ERR_X509_NOT_TRUSTED`(TLS alert 48, `bad certificate`)가 확인된다. TLS 1.2와 cipher `0xC02F`는 정상 협상된다. 자체 서명 인증서를 신뢰 앵커에 추가한 합성 검증기에서는 핸드셰이크가 완료된다.
- 판정: `[확인됨]` 이 프로젝트의 현재 실패 지점은 **체인/신뢰 앵커**다.
- 단서: "에러 07 = 항상 체인"은 아니다. 13번 문서의 외부 사례 참조.

### 2.4 "wolfSSL 교체 필요"

- 주장(초기): TLS 구현 교체가 필요할 수 있다. 후속 보정: TLS 1.2가 이미 동작하므로 불필요.
- 검증: `0xC02F`(TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256) 협상 성공, 인증서 교환/검증 단계까지 도달. 실패는 `X509_NOT_TRUSTED`.
- 판정: `[확인됨]` **wolfSSL 교체는 불필요하다.** BearSSL 0.6 유지가 맞다. 단, 외부 사례 중 Conscrypt 교체로 에러 07이 사라진 사례(11번/13번)는 "HU 쪽 TLS 스택 버그"라는 별도 축이다.

### 2.5 성공 확률 수치

- 주장: 단계별 성공 확률/가중치.
- 검증: 확률의 근거가 된 표본 수, 조건, 측정 방법이 문서에 없다.
- 판정: `[미검증 가설]` **확률 수치는 의사결정 근거로 쓰지 말 것.** 대신 "차단 요인 1개(신뢰 앵커)"와 "미해결 구현 난이도(비디오 디코드, 입력, USB)"로 분해한다.

---

## 3. ChatGPT 연구 검증

### 3.1 Genesis G80(DHPE) vs GD13MY 비교 대상

- 주장: G80은 Linux/MeeGo 계열, GD13MY는 WinCE/ARM으로 바이너리 비호환이며, 프로토콜/인증 설계만 재사용 가능하다.
- 검증:
  - G80 HU userspace는 **i386 ELF가 확인됐다.** `G:\LIB\LIBIENGINE1.so`, `LIBREDENGINE3D.so`, `LIBTPEGDECODER.so`, `LIBMGDIQTYPE.so`는 모두 ELF32, `e_machine=0x03`(Intel 80386)이다. `G:\BIN\APPNAVI`도 동일하다.
  - `.lge.upgrade.xml`: `version=DHPE.KOR.SOP.03.057`, `build-date=2024-10-11`, `hardware-ver=DHPE`, BIOS/FPGA/SSD(Micron/SuperTalent) 펌웨어 항목, `ibox version="E468" (2023-06-14)`. BIOS+SSD 구성은 x86 플랫폼과 일치한다.
  - `APPNAVI`에 `SetModeStatusIBOX`, `IBOXKeyBoardChange`, `com.dhavn.mostmanager.qtdbus`, `NaviMostComm` 문자열이 있다. IBOX는 MOST로 연결된 외부 모듈로 HU 내비 앱에서 제어된다.
  - 반면 `IBOX.tar`, `HU/images/NP/rootfs.img`, `boot.img`는 암호화 컨테이너이고, 평문 AA 리시버 바이너리는 얻지 못했다. `HU/images/vr.img`만 `partclone-imageEXTFS` 헤더를 가진다.
- 판정: **i386 사용자공간은 `[제네시스 펌웨어 직접 증거]`로 확인됐다.** "MeeGo"라는 특정 배포판명은 `[미검증 가설]`로 남긴다. AA 리시버 바이너리 미확인은 유지한다.
- `[GD13MY 적용 가능]` G80에서 얻을 수 있는 것은 **프로토콜/인증서 취급/채널 순서**이지 바이너리가 아니다.

### 3.2 OMAP3530 부록

- 주장: GD13MY가 OMAP3530 계열이며, 하드웨어 디코드/DSP 활용 여지가 있다.
- 검증: GD13MY BSP 커널에서 `omap3430_dma.pdb`, `omap3430_spi.pdb`, `omap3430_rtc.pdb`, `omap3430_mcbsp.pdb`, `omap3430_uart.pdb`, `omap3430_quart.pdb`, `omap3430_musbotg.pdb`, `omap3430_musbhcd.pdb`, `evm3530_bus.pdb` 문자열을 직접 확인했다. 앱 계층 `LibMMCodec.dll`은 `IOCTL_VDEV_VID_DECODE`, `IOCTL_VDEV_VID_DECINIT`, `IOCTL_VDEV_AUD_DECINIT`, `DSP Version`, `MAF` 큐, DDraw overlay를 사용한다.
- 판정: `[제네시스 펌웨어 직접 증거]`는 아니고 `[GD13MY 적용 가능]` + `[확인됨]`이다. **GD13MY는 OMAP3430/3530 계열 BSP를 쓰며, 별도 DSP/VideoDev 디코드 경로가 존재한다.**
- 단, 실제 AA 비디오를 그 경로로 디코드할 수 있는지는 `[GPT 분석 필요]` + `[Codex 구현 필요]`.

---

## 4. Antigravity 연구 검증 (중요 보정)

Antigravity의 `EVIDENCE_VERIFICATION.md`가 스스로 "미확인"으로 표시한 항목은 그대로 미확인으로 취급한다. 아래는 문서 간 불일치를 정리한 것이다.

| # | Antigravity 주장 | 이번 검증 | 판정 |
| --- | --- | --- | --- |
| A1 | `genesis.keystore`에 GAL 서명 OEM 체인이 들어 있다 | keystore를 복호화/디코드한 증거가 없다. 파일 존재와 추정만 있다 | `[미검증 가설]` |
| A2 | IBOX가 USB AOA/AAP를 처리한다 | Genesis rootfs 미복호화. GD13MY `LibUSB.dll`은 미디어 파일 브라우징(`lUSBFB*`, `lUSBmm*`)만이고 AOA 문자열이 없다 | `[미검증 가설]` (근거 없는 단정) |
| A3 | Genesis AA가 OpenSSL 1.0.x 또는 mbedtls 2.x를 쓴다 | 바이너리 미확보. `DecryptToFile`에 mbedtls 심볼이 있는 것은 **복호화 도구**이지 AA 리시버가 아니다 | `[미검증 가설]` (도구와 리시버 혼동) |
| A4 | Intel GMA 하드웨어 디코드를 쓴다 | G80 커널/드라이버 미확인. i386 사용자공간은 확인했지만 GPU/디코드 경로는 확인 못함 | `[미검증 가설]` |
| A5 | h264bsd 30fps로 충분하다 | 측정 없음. GD13MY에는 DSP/VideoDev 경로가 있어 "소프트웨어만" 전제가 틀릴 수 있다 | `[미검증 가설]` |
| A6 | "unknown sources" 허용/인증서 무시 플래그로 우회 | phone은 HU 인증서를 검증하며, 우회 플래그는 phone 쪽에 없다. Antigravity도 후속 문서에서 철회 | **기각** (기술적으로 불가) |
| A7 | Genesis AA 리시버 바이너리/TLS 함수 주소를 특정했다 | `EVIDENCE_VERIFICATION.md`가 "미확인"으로 표시. 이번에도 컨테이너 복호화 실패 | `[미검증 가설]` |

### 4.1 Antigravity "복호화 성공" 주장에 대한 경고

`research/genesis-premium-gen2/scripts/`의 기존 스크립트는 128KB 헤더에서 RSA modulus/exponent를 뽑는다고 가정한다. 이번에 동일 로직을 `update.tar`와 `G:\IBOX.tar`에 적용한 결과:

- 헤더 엔트로피 ≈ 8.0 bit/byte, 출력 바이트가 ASCII hex가 아님.
- 추출한 "E"가 `0x16271d3b829a` 같은 비정상 값.
- 복호화 결과가 PKCS#1 `00 01`/`00 02`로 시작하지 않음.

즉 **128KB 헤더는 평문 RSA 키 블록이 아니라 암호화/압축된 영역**이다. `DecryptToFile`의 `LGUGetKeyForFile`은 0x20000 바이트를 읽은 뒤 `Cryptor_CbcPadDecrypt` 계열로 처리하므로, 키는 헤더 안에 평문으로 있지 않다. 따라서 "RSA 키를 추출했다"는 과거 서술은 `[미검증 가설]`이며, 이번 조사에서도 **복호화는 달성하지 못했다**.

---

## 5. 이 저장소 자체 실측과의 정합성

| 항목 | 근거 | 판정 |
| --- | --- | --- |
| phone이 client certificate를 요청함 | `phone-tls-public.json`의 `server_requested_client_certificate: true` | `[확인됨]` |
| TLS 1.2, `0xC02F` | BearSSL 로그/프로젝트 문서 | `[확인됨]` |
| 실패 지점 `BR_ERR_X509_NOT_TRUSTED` | BearSSL stderr 로그 | `[확인됨]` |
| AAP version 1.7 협상 | `phone-tls-public.json` | `[확인됨]` |
| DHU는 phone과 정상 연결 | DHU 공식 도구, 공개 인증서 | `[확인됨]` |
| AASDK/JVC 인증서가 실제 차량에서 동작 | 다수 OSS 프로젝트 보고 + pi-auto 문서의 "phones accept that shared identity" | `[외부 신규 검증]` |

**핵심 해석:** phone은 "차량별 고유 신원"을 요구하지 않는다. `GAL`로 체인이 이어지는 leaf면 통과한다. DHU의 `Android-Auto-Internal` 인증서도 통과한다. 따라서 문제는 "우리 차의 인증서가 아님"이 아니라 **"GAL 체인 밖의 인증서"**다.

---

## 6. 문서별 신뢰도 요약

| 문서 | 유지되는 결론 | 폐기/수정할 결론 |
| --- | --- | --- |
| DeepSeek error07 | 체인/신뢰 앵커 중심 분석, OSS 매트릭스 | "error 7 = 항상 체인" 단정 |
| DeepSeek phase2 | DHU 날짜 혼동 원인, TLS 1.2 동작, wolfSSL 불필요 | DHU 버전별 인증서 차이 가정 |
| DeepSeek success probability | 단계 분해 자체는 유용 | 확률 수치 |
| ChatGPT handoff | G80/GD13MY 역할 분리, 우선순위 | G80 i386 단정, OMAP 세부 미확인 |
| Antigravity 06 TLS | "GAL 서명 체인이 필요" 방향 | Genesis keystore 체인, OpenSSL 버전, 함수 주소 |
| Antigravity 04 모듈맵 | IBOX/rootfs 후보 지점 | IBOX=AOA, keystore GAL 체인 |
| Antigravity EVIDENCE_VERIFICATION | 미확인 목록은 정확 | (유지) |

---

## 7. 이번 조사에서 새로 확정한 사실

1. `pi-auto-headunit`의 세 문서 `docs/protocol/tls-credential-policy.md`, `receiver-provisioning-options.md`, `livi-adoption.md`는 **실제로 존재한다**(11번 문서에 원문 근거).
2. DHU 2.1과 latest 인증서는 동일하고, metadata 날짜만 null이다.
3. AASDK 공개 인증서는 `O=JVC Kenwood` leaf, serial `0x1B`, 2045-04-29 만료, SHA-256 `1c0e0ef9…`이며 개인키도 공개 저장소에 있다.
4. GD13MY BSP는 OMAP3430/3530 계열이며, `LibMMCodec.dll`이 VideoDev/DSP IOCTL을 사용한다.
5. Genesis `IBOX.tar`/`rootfs.img`/`update.tar`는 동일한 LGE 컨테이너 형식이고 헤더는 고엔트로피(암호화)다.
6. Genesis G80 HU 사용자공간은 i386 ELF이며(BIOS/SSD 구성과 일치), `APPNAVI`가 MOST 기반 IBOX 모듈을 제어한다. IBOX가 phone projection 모듈일 가능성은 높지만, 바이너리 미확보로 AA 리시버라는 직접 증거는 아직 없다.
7. OpenCode 조사 시점(2026-11-24) 기준 22개 저장소는 모두 접근 가능하며, `headunit-revived`는 `open-headunit`으로 이름이 바뀌었다.

---

## 8. 남은 검증 과제

- `[GPT 분석 필요]` LGE 컨테이너의 키 유도 경로(`LGUInitDecrypt` → `LGUDecryptData` → `Cryptor_CbcPadDecrypt`)를 의사코드로 복원하고, 키가 기기 고유값인지 빌드 상수인지 판별.
- `[Codex 구현 필요]` `DecryptToFile`의 x86 로직을 Python으로 재구현해 `IBOX.tar` 복호화 시도(읽기 전용, 임시 디렉터리).
- `[GPT 분석 필요]` GD13MY `LibMMCodec.dll`의 `VideoDev` 디바이스 이름/IOCTL 번호와 H.264 지원 여부.
- `[Codex 구현 필요]` 에러 07 분류기(체인/정책/만료/TLS 스택/오진)를 로그에서 자동 판별하는 진단 코드.
