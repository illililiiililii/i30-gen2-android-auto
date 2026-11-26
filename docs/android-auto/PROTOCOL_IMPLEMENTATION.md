# Phase 2 · 프로토콜 구현 범위

aasdk의 `9bf6adf9`를 기준으로 삼았다. `tools/build_phase2.py`는 공개 `.proto`와 import를 protoc로 컴파일해 디스크립터를 생성한다. 컨트롤 메시지, Media ID, 채널 및 서비스 필드를 Python에서 재정의하지 않고 공식 protobuf 런타임이 해석한다. 전체 C++ 라이브러리 링크는 이 빌드에 포함되지 않는다. [aasdk 소스](https://github.com/opencardev/aasdk/tree/9bf6adf933665dee26532201719fac14a047ccf1)

| 단계 | PC 코드의 동작 |
|---|---|
| 프레임 | 디스크립터 이전 전송층은 aasdk의 채널(1 B), 플래그(1 B), big-endian 길이(2 B), 첫 조각의 총 길이(4 B)를 따른다. 메시지 ID는 big-endian 16비트다. USB 읽기 경계와 메시지 경계를 별도로 처리하고 TLS 암호화된 조각은 복호화 후 원문 길이를 검사한다. [FrameHeader](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/src/Messenger/FrameHeader.cpp) · [MessageOutStream](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/src/Messenger/MessageOutStream.cpp) |
| 버전 | 채널 0에 로컬 1.6 요청을 보낸다. 성공 상태와 호환 주 버전을 확인하고 폰의 버전을 로그에 남긴다. 고정 여섯 바이트 응답을 지원하며 형식이 다르거나 거부되면 종료한다. [Version과 컨트롤 채널](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/src/Channel/Control/ControlServiceChannel.cpp) |
| TLS | OpenSSL 기반 TLS 1.2 클라이언트의 handshake 바이트를 `ENCAPSULATED_SSL` 메시지 안에서 송수신한다. 신뢰 체인을 검증하고 예상 이름 또는 인증서 SHA-256 지문을 확인한 뒤 `AuthResponse`를 보낸다. 이후 제어/미디어는 보호된 프레임으로 처리한다. 검증이 실패하면 활성 상태로 진입하지 않는다. [aasdk TLS의 클라이언트 연결 방향](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/src/Transport/SSLWrapper.cpp) |
| 서비스 탐색 | 확인된 메시지에 H.264 800×480/30 fps 영상과 48 kHz/16-bit/stereo PCM 미디어 오디오 진단 sink를 알린다. 이 값은 PC 테스트용 제안값이다. 실물 패널 사양이나 오디오 연결성을 의미하지 않는다. |
| 채널 | 보호된 채널 open 요청에서 서비스 ID와 채널 일치를 확인한다. Setup·Config·Start·Stop 및 채널 close 상태를 정리한다. 샘플은 동기 sink에 넘기고 세션 ID로 ACK한다. PC 미리보기 모드에서는 프로젝션 focus 요청을 받아 H.264를 디코딩하고 첫 프레임을 저장한다. [영상 채널 프로토콜](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/src/Channel/MediaSink/Video/VideoMediaSinkService.cpp) |
| 터치 | `--tap`이 지정된 경우 채널 1에 800×480 터치 표면을 광고한다. 보호된 Open과 키 바인딩 뒤 단일 포인터의 누름·뗌을 `InputReport`로 보낸다. 키 코드가 포함된 바인딩은 거절한다. 재연결이 같은 탭을 재전송하지 않는다. [입력 채널 구현 근거](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/src/Channel/InputSource/InputSourceService.cpp) |
| 유지·종료 | 상대 ping을 응답하며 주기 ping의 timestamp를 추적한다. 일치 응답이 기한 내 없으면 실패 처리한다. 사용자 정지와 정상 종료에는 ByeBye 교환, 비정상 분리에는 기존 링크를 닫고 선택적으로 재연결한다. |

길이 상한은 개별 프레임 16.5 KiB, 단일 조립 메시지 2 MiB, 전체 예약 4 MiB 및 진행 중인 채널 8개다. 조각의 암호화·제어 플래그가 다르거나 선언된 전체 길이와 불일치하면 해당 세션을 닫는다. 시작 단계의 예상 밖 메시지, 실패한 TLS, 필수 protobuf 필드 누락을 처리한다. 활성 세션에서 지원하지 않는 선택 메시지는 코드만 제한적으로 기록한다. 로그에 TLS 인증서·키·폰 이름·비디오/오디오 원문을 쓰지 않는다.

모의 통합 시험은 임시 자체 서명 테스트 인증서를 양쪽에 신뢰시키는 로컬 TLS 1.2 교환을 수행한다. 테스트 키는 임시 폴더에 생성돼 후처리로 제거된다. 실제 폰에서 신뢰하는 헤드유닛 인증서, 폰의 인증 체인과 Android Auto 버전은 별도 검증이 필요하다. 저장소나 패키지에 기존 시스템의 키를 넣지 않았다.

[수신기 소스](../src/i30_receiver/protocol.py) · [프레임 소스](../src/i30_receiver/wire.py) · [모의 세션 로그](../research/evidence/phase2-release-normal.jsonl)
