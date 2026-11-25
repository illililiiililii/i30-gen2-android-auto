# 실폰 시험 상태

11월 25일 초기 인증 검증 세션에서는 삼성 USB 장치가 연결되지 않았다. 같은 날 후속 통합 세션에서 사용자가 시험폰을 연결했다. 아래 표는 초기 세션까지의 기록이다. [후속 시험](#11월-25일-후속-실폰-시험)

| 단계 | 신규 ARM 빌드 실폰 | 과거 기록에서 확인한 실폰 단계 |
| --- | --- | --- |
| USB AOA | 미시험 | USB 재열거 관측 |
| AAP | 미시험 | 1.7 응답 관측 |
| ClientHello → ServerHello/Certificate/CertificateRequest | 미시험 | 폰의 전체 초기 TLS 플라이트 관측 |
| 헤드유닛 Certificate | 미시험 | 별도 PC 진단이 자체 시험 신원의 클라이언트 TLS 플라이트 전송. 폰이 신뢰 앵커를 찾지 못해 체인 거부 |
| 송신 리프 SHA-256, CertificateVerify, peer alert 번호 | 미시험 | 당시 원시 캡처 또는 상세 로그 부재로 미확인 |
| 상호 TLS Finished와 `AUTH_COMPLETE` | 미시험 | GD13MY 시험 경로에서 미확인 |
| Service Discovery, 영상, 투사 터치, USB 재연결 | 미시험 | 실제 폰과 GD13MY 경로에서 미확인 |

과거 실폰의 마지막 확인 지점은 초기 TLS 플라이트의 ServerHelloDone과 뒤이어 폰에서 발생한 클라이언트 인증서 신뢰 체인 거부다. 같은 폰의 공식 DHU 시험에서는 TLS 1.2 `ECDHE-RSA-AES128-GCM-SHA256` 협상과 800×480 표시를 관측했다. [과거 USB·Conscrypt 근거](RESEARCH_VALIDATION.md#오류-07과-과거-실폰-증거) · [공식 DHU 당시 로그](../../build/gd13my-native-oem-screen/live-phone-visible.stderr.log)

성공 시험에는 폰이 신뢰하며 프로젝트가 사용할 권한을 확보한 RSA 헤드유닛 신원이 필요하다. 저장소와 이번 시험 설정에서 그 조건을 만족하는 등록 자료를 확인하지 못했다. 사용 가능한 폰이 생기면 자기 시험 신원으로 새 진단의 송신 지문과 거부 지점을 한 번 확인할 수 있다. 평가 신원이 확보되면 같은 ARM 빌드에서 TLS Finished 이후로 진행한다. [장치 준비와 설정 경로](../ANDROID_AUTO_AUTH_STATUS.md#실폰-재시험) · [후속 발급 조사](FREE_AI_NEXT_TASKS.md)

## 11월 25일 후속 실폰 시험

SM-G996N에서 Android 15와 Android Auto 18.0.664294를 확인했다. 최신 터치 통합 ARM DLL의 USB API 시험은 ADB 서버가 실행 중일 때 Windows 접근 거부를 반환했다. 서버를 잠시 정지한 뒤 새 AOA 연결 `04e8:6860 → 18d1:2d01`과 AAP 1.7 응답을 확인했다. 이어 같은 DLL을 구동하는 격리 WinCE의 가상 USB 호스트를 실제 USB 포트에 연결해 AAP 1.7을 재현했다. [ARM 직접 USB 결과](../../build/codex-post-auth-integration/resumed-real-phone-aoa-after-adb.jsonl) · [격리 WinCE USB 원본](../../build/codex-post-auth-integration/real-phone-wince/usb.log)

첫 WinCE 이미지에서 `i30-peer-sha256.txt`에 PyFatFS가 배정한 8.3 이름은 `I30-PEER.TXT`였다. FAT에서 같은 파일이 지문 경로와 호스트명 경로 모두에 노출되어 상호 배타 등록 검사가 TLS 전에 중단했다. 시험 이미지에서 먼저 호스트명 파일 이름을 예약해 지문의 8.3 이름을 `I30-PE~1.TXT`로 배정하고, 예약 파일을 제거하자 TLS 초기화가 진행됐다. 지문 등록과 체인 검증 규칙은 기존 구현을 사용했다. [등록 실패 UART](../../build/codex-post-auth-integration/real-phone-wince/native-phone.serial.log)

| 단계 | 최신 WinCE ARM 실행 결과 |
| --- | --- |
| 실폰 응답 | AAP 1.7, ServerHello, Certificate, ServerKeyExchange, CertificateRequest, ServerHelloDone |
| TLS 협상 | TLS 1.2, `TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256` (`0xc02f`) |
| 헤드유닛 송신 | Certificate, ClientKeyExchange, CertificateVerify를 송신했다. 로컬 로딩 리프와 송신 리프 SHA-256은 모두 `27a99583a8f3f1d58873c1324e513c8e22bd4e0f44fb8f10ecf3cdcd7924ecb3`이다. 임시 자체 서명 시험 신원을 사용했다. |
| 실패 | 폰의 Conscrypt `verifyCertificateChain`이 22:11:07 KST에 `Trust anchor for certification path not found`를 기록했다. WinCE는 USB 송신 타임아웃을 기록했고 peer TLS alert 번호는 수신하지 못했다. |
| 후속 단계 | TLS Finished, `AUTH_COMPLETE`, 서비스 탐색, 영상 미도달. |

시험은 최신 `i30usb.dll` SHA-256 `6ada19e56b1d262c8a5c5f79867140233d95e75bceea7bf490858870476f3ec1`과 별칭이 분리된 임시 DiskA를 사용했다. UART 시각과 실폰 로그를 대조해 체인 거부를 확인했다. ADB 서버는 검사 뒤 다시 시작했다. 다음 실폰 시도에는 사용 권한이 있고 폰이 신뢰하는 헤드유닛 체인과 대응 키가 필요하다. [WinCE TLS UART](../../build/codex-post-auth-integration/real-phone-wince-pin-alias/native-phone.serial.log) · [USB 원본](../../build/codex-post-auth-integration/real-phone-wince-pin-alias/usb.log) · [폰 인증 오류](../../build/codex-post-auth-integration/real-phone-wince-pin-alias/adb-selected.log)
