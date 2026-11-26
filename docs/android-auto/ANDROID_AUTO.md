# 유선 Android Auto 요구사항

스마트폰이 Android Auto 앱을 실행한다. 헤드유닛은 USB 호스트로 연결을 관리하고 화면, 음성 및 입력을 중계한다. Google의 Desktop Head Unit(DHU)은 개발 PC에서 이 역할을 검증할 기준이 된다. AOA는 USB 전송 단계의 일부이며 화면·오디오·입력 서비스를 개설하려면 Android Auto 프로토콜 협상이 별도로 필요하다. [Google DHU](https://developer.android.com/training/cars/testing/dhu) · [AOSP AOA](https://source.android.com/docs/core/interaction/accessories/protocol)

| 요구사항 | 관찰 결과와 통과 조건 |
|---|---|
| 1. USB 호스트/AOA | MUSB 호스트와 저장장치 경로 확인. USB 제어 요청, 재열거 후 bulk IN/OUT, 권한, 충전 및 안정적인 분리를 실제 CE 드라이버에서 검증한다. |
| 2. 연결과 프로토콜 | 순정 패키지에서 Android Auto 수신 스택은 확인되지 않았다. 공개 수신기의 초기 협상, 보안 채널, 서비스 탐색 및 재연결을 PC에서 기준으로 삼고 기기 쪽 ABI와 인증 호환성을 별도로 검증한다. |
| 3. H.264 | OEM 파서와 영상 장치 후보가 있다. `LibMMCodec.dll`은 `lmmCodecPlay`(RVA `0x165ec`) 및 `lmmCodecSetVideoSize`(RVA `0x16748`)를 내보낸다. 원시 스트림 투입 경로, 해상도/프로파일, 프레임 유실 및 지연을 확인한다. 800×480은 로고 리소스의 크기다. |
| 4. 디스플레이 | DirectDraw·DDI·GLES와 800×480 리소스가 있다. 프로젝션을 그리는 표면과 화면 전환 주체를 식별하고 후진 영상의 우선순위를 검증한다. |
| 5. 터치 | OEM 터치 드라이버와 좌표 로그 확인. 화면 비율 보정, 터치 좌표 및 누름/뗌 전달, OEM 포커스 복귀 검증. |
| 6. 버튼 | MICOM 및 통신 핸들러 확인. 음악·음성 등 허용할 사용자 입력을 OEM 이벤트 계층에서 식별하고 순정 동작과의 우선순위를 정한다. |
| 7. 오디오 출력 | CE wave API, SAF7730 드라이버, OEM 음량 라이브러리 확인. 음악·안내·전화의 경로와 샘플레이트, 덕킹, 믹싱, 순정 음량 및 음소거 동작 검증. |
| 8. 마이크 | OEM ASR 프로그램과 음성 리소스가 있다. 마이크 PCM 접근과 통화/순정 음성 기능 간 자원 경쟁, 음성 명령 종료 후 반환 경로를 확인한다. |
| 9. 분리와 복구 | USB 분리 이벤트 흔적을 확인했다. 케이블 분리·재장착, 타임아웃, 프로세스 종료 시 오디오·화면·입력을 원상 복구해야 한다. |
| 10. 순정 기능 | Bluetooth, 내비, 미디어, 후방카메라의 구성 요소 확인. 카메라 선점 및 복귀, 경고음, 통화, 볼륨과 버튼의 충돌을 벤치에서 테스트한다. |

## 코드 재사용 비교

| 후보 | 사용할 수 있는 부분 | CE에서의 비용 |
|---|---|---|
| [f1xpl/OpenAuto](https://github.com/f1xpl/openauto) / [opencardev/OpenAuto](https://github.com/opencardev/openauto) | 수신기 서비스, 미디어·안내·시스템 오디오 구분, 터치/키 입력, Qt 및 Raspberry Pi OpenMAX 영상 경로의 참고 구현. USB는 aasdk 쪽이다. | GPLv3 계열. Qt·Boost·aasdk와 각 디코더/오디오 백엔드가 필요하다. Raspberry Pi OpenMAX를 CE OMAP 영상 드라이버에서 쓸 수 있다는 증거가 없다. |
| [opencardev/aasdk](https://github.com/opencardev/aasdk) | AOA, USB/TCP 전송, SSL, 메시지 스키마와 영상·오디오·마이크·입력 채널. 호스트 기준과 메시지 모델에 적합하다. | GPLv3 계열. libusb·OpenSSL·Boost·protobuf 및 빌드 옵션에 따른 Abseil 필요. CE 호스트 드라이버와 미디어 I/O를 대체할 구현이 필요하다. |
| [OpenHU](https://github.com/average-web-dev/openhu) | OpenAuto 계열 수신기, FFmpeg 영상, Qt 입력·오디오 및 포커스 전환 설계 참고. | GPL-3.0. Qt 6.8/QML·FFmpeg·Linux 기반. 이 CE 시스템에 그대로 빌드할 근거가 없다. |
| [mretallack/AndroidAuto](https://github.com/mretallack/AndroidAuto) | Android 송신기 쪽 AOA 동작, 영상 송출 및 입력 수신 방향의 참고. | GPL-3.0. Kotlin·Android SDK·MediaCodec 기반으로 수신기가 아니다. |

CE용 경량 수신기에는 USB/AOA, 메시지 프레이밍 및 채널, 영상, 오디오, 입력, 순정 상태 전환을 독립 경계로 둔다. PC에서 상호 운용성을 먼저 재현하고, CE에서 기존 드라이버를 사용하는 작은 검증 프로그램으로 각 경계를 시험한다. 재사용과 배포 방식은 채택한 소스와 종속 라이선스를 함께 검토한다.
