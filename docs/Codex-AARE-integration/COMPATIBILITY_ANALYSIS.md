# AARE 및 BetterAuto 호환성

시험 기준은 AARE 공식 APK `v1.6.0`과 해당 소스 `5d726fc`다. AARE `main`은 `1aa6216`, BetterAuto `main`은 `7a55ee5`, 공식 BetterAuto 릴리스는 `0.4.0`을 확인했다. [AARE 릴리스](https://github.com/prototux/AARE/releases/tag/v1.6.0) · [BetterAuto 릴리스](https://github.com/simoneluconi/BetterAuto/releases)

| 항목 | AARE 1.6.0 | BetterAuto 0.4.0 / main | GD13MY WinCE |
| --- | --- | --- | --- |
| Android 및 USB | Android 6 이상, USB AOA. `Android Auto` 액세서리 모델에 반응. 일부 기능은 Android 8 이상 필요 | Android 10 이상, USB AOA. 무선 연결도 제공 | 순정 .061 호스트와 시험 PC의 Windows USB 전달. 일반 모드에서 AOA로 전환하는 현재 등록 대상은 시험 삼성 VID/PID |
| AAP 및 인증 완료 | 수신기가 낸 1.6에 1.7로 응답. TLS 완료 뒤 채널 0에서 `AUTH_COMPLETE`를 받고 암호화된 탐색을 시작 | 수신기 버전 요청, TLS 및 `AUTH_COMPLETE` 이후 서비스 탐색 | 1.6 요청, 1.7 수용. 검증된 TLS 세션에서만 탐색과 영상 개설 |
| TLS 역할 및 알고리즘 | 폰이 TLS 서버. TLS 1.2와 공통 알고리즘을 협상. 공식 앱은 RSA 휴대폰 인증서 및 자체 생성 인증서를 지원 | 폰이 TLS 1.2 서버. RSA 인증서가 포함된 APK를 배포. 현재 앱 소스는 수신기 인증서를 로그용으로 요청 | BearSSL TLS 1.2 클라이언트. 시험 프로필은 RSA 키, 로컬 CA와 폰 리프 SHA-256을 모두 확인 |
| 양쪽 신뢰 | 폰 인증서 PKCS#12 가져오기 지원. 유선 첫 연결에서 수신기 리프 SHA-256을 표시하고 `Trust`를 요청. 신뢰한 지문은 액세서리별로 보관 | 수신기 지문 승인 기능을 확인하지 못했다. 기본 개발 인증서는 앱에 포함 | AARE 전용 파일 및 명시적 선택 마커. 기존 Google용 파일과 진입점 유지 |
| 영상 | H.264 Baseline 지원. SPS/PPS와 키프레임으로 스트림 초기화 및 복구. 해상도는 수신기 구성에서 선택하고 30/60FPS를 해석 | H.264 Baseline MediaCodec, 영상 채널과 구성 협상 | 800×480 H.264 Baseline 30FPS 한 구성 제공. 디코더의 실제 처리 속도는 별도 측정 필요 |
| 터치 | 입력 채널을 열고 키 바인딩을 요청. 터치 화면과 좌표를 수신기 서비스 기술자에서 읽음 | 서비스에 따라 터치, 로터리, 터치패드 | 800×480 단일 포인터 입력, 누름·이동·떼기 |
| 오디오·음성 | 음악, 안내, 마이크 등은 수신기가 해당 서비스를 광고해야 함. 캡처는 Android 버전과 권한에 의존하고 시스템 오디오 라우팅은 루팅 또는 Shizuku 설정에 의존 | 음악, 내비 안내 및 차량 마이크를 활용한 음성 명령을 지원. 유선 Shizuku 사용 시 루팅 필요 | 통합 영상 프로필은 영상과 터치만 광고. 기존 순정 오디오와 분리된 오디오 시험 경로 유지 |
| 재연결 | USB 권한 재확인 및 제한된 세션 재시도. 새 연결에서 인증서 선택과 영상 재설정 | USB 연결 관리와 재시도는 추가 실기로 확인 필요 | 기존 AOA 재열거와 세션 정리 재사용. 폰 앱이 스스로 재시도하지 않으면 케이블 재연결 |
| 앱 호환성 | AARE 대시보드와 지원하는 Car App Library 앱. Maps·Waze의 다음 방향 안내와 앱 자체 UI 지원은 별개이며 후자에는 선택적 루팅 모듈이 관여 | 자체 Compose 런처, 음악·전화·알림·차량 데이터. 임의 Android 앱 화면을 지원한다고 가정할 수 없음 | 프로젝션 영상과 입력 채널에 따라 동작. 특정 내비 앱은 실기 확인 필요 |

AARE는 USB에서 수신기 인증서 승인과 독립 폰 인증서 가져오기를 모두 제공한다. 공식 APK를 그대로 사용하며 BetterAuto 구현 검토는 AARE 실폰 검증 뒤 진행한다. [AARE 인증서](https://github.com/prototux/AARE/blob/v1.6.0/docs/certificates.md) · [AARE 앱 문서](https://github.com/prototux/AARE/tree/v1.6.0#readme) · [BetterAuto 설계](https://github.com/simoneluconi/BetterAuto/blob/7a55ee5db1548c7b71377eb99fd00c61317ee27c/docs/DEVELOPMENT.md)
