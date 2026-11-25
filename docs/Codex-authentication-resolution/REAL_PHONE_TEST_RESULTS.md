# 실폰 시험 상태

11월 25일 기존 Platform-Tools의 `adb devices`에서 연결된 폰이 없었다. Windows PnP에도 삼성 USB 또는 AOA 장치가 없었다. 사용자가 이번 세션에서 실폰을 연결할 수 없다고 확인했다. 새 ARM DLL로 실폰 시험을 시작하지 않았다.

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
