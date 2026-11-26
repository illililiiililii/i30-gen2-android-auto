# Phase 2 · PC Android Auto 수신기

**실폰 AOA와 Android Auto 1.7 응답을 검증했다.** Windows x64용 PC 진단 앱은 로컬 모의 스마트폰과 TLS·서비스 탐색·두 미디어 채널·재연결을 검증했다. 같은 삼성 테스트폰으로 공식 DHU의 TLS·영상·터치 시험도 통과했다. 프로젝트 수신기는 암호화된 자체 실폰 영상·입력 세션 검증을 남겨 두었다. [USB 연결 시험](USB_CONNECTION_TEST.md)

| 계층 | 구현과 경계 |
|---|---|
| USB 전송 | `src/i30_receiver/transport.py`의 `AoaTransport`가 선택 포트 확인, AOA 정보 교환, 재열거, 인터페이스 개방을 수행한다. `usb_pc.py`는 PyUSB/libusb, `mock.py`는 같은 `UsbBackend`와 `BulkLink` 계약을 구현한다. |
| 프레임 | `wire.py`가 USB 읽기 경계를 넘어 프레임을 읽고 채널별 조각을 재조립한다. 큰 메시지 및 무한 대기를 방지하는 크기 예산과 세션 제한이 있다. |
| 프로토콜 | `schema.py`가 aasdk의 고정 protobuf 디스크립터를 사용한다. `protocol.py`가 버전·TLS·서비스 탐색, 영상·오디오 채널 및 ping/종료를 관리한다. `tls.py`는 표준 Python SSL과 OpenSSL에 암호 처리를 맡긴다. |
| 연결 상태 | `session.py` 순서는 Disconnected → DeviceDetected → Negotiating → Connected(TLS 인증) → SessionActive(서비스 탐색 응답). 오류가 나면 Error → Disconnected로 자원을 반환한다. 다시 시도하도록 선택했으면 Reconnecting에서 새 링크와 세션을 만든다. |
| 플랫폼 경계 | `platform.py`에서 시간·대기·로그·정지 플래그와 할당 함수를 주입한다. 프로토콜과 USB 링크의 소유권은 동기식 루프 하나에 있다. PC 정지 신호는 CLI의 `threading.Event`이며 핵심 코드에 Windows 동기화 API가 들어가지 않는다. |
| 미디어·입력 | `MediaSink`가 채널 상태와 검증된 미디어 패킷을 받는다. `--video-preview`는 PyAV로 디코딩하고 첫 영상 프레임을 PNG로 저장한다. `--tap X Y`는 입력 채널을 광고하고 바인딩 후 누름·뗌을 한 번 전송한다. 기본 진단 모드에서는 미디어 통계를 기록한다. |
| PC 앱 | `list`(열거), `probe`(AOA와 평문 버전), `connect`(승인받은 TLS 신뢰 정보로 실제 연결), `mock`(로컬 합성). 콘솔에 JSON Lines로 연결, 재시도, 오류, 채널 상태를 표시하고 선택한 파일에 저장한다. |

## 빌드와 테스트

이 PC에서 CPython 3.15.0b3 x64, OpenSSL 3.5.7, protoc 36.2, protobuf 7.36.2, PyUSB 1.3.1, libusb 1.0.30으로 검증했다. protoc와 libusb는 공식 릴리스 ZIP/7z의 SHA-256을 확인했다. 대표 Hash는 protoc `f0c128dc0d8492eceece83bb459a4c0e316764b929ffbf1aa416357fd644edd3`, libusb `7fb1dfec805b97983763d7d0ae244320da12add1003d4249c96cc4d586398c79`다. PC 산출물은 Python 환경이 필요한 ZIP 실행 패키지다.

현재 환경에서 프로젝트 루트로 이동한 뒤 실행한다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$protoc = Join-Path $env:LOCALAPPDATA 'i30-phase2-tools/protoc/bin/protoc.exe'
& $py tools/build_phase2.py --protoc $protoc
& $py -m unittest discover -s tests -v
& $py build/i30-receiver.pyz mock
& $py build/i30-receiver.pyz mock --scenario unplug --reconnect
& $py build/i30-receiver.pyz mock --tap 44 440 --video-preview 'C:\path\new-preview.png'
& $py build/i30-receiver.pyz list
```

다른 PC에서는 가상환경에 `requirements-phase2.txt`를 `pip install -r`로 설치한 다음 Host용 protoc를 준비한다. 빌드 도구에 aasdk 커밋 `9bf6adf933665dee26532201719fac14a047ccf1`의 `protobuf` 폴더를 `--schemas`로 지정한다. 이 작업공간의 기본 경로는 `research/sources/opencardev__aasdk/protobuf`다. 모의 인증서 생성에는 OpenSSL CLI가 필요하며 `mock --openssl`로 경로를 지정할 수 있다. libusb 경로는 `list/probe/connect --libusb`로 지정한다. [protoc 릴리스](https://github.com/protocolbuffers/protobuf/releases/tag/v36.2) · [libusb 릴리스](https://github.com/libusb/libusb/releases/tag/v1.0.30) · [aasdk 스키마 소스](https://github.com/opencardev/aasdk/tree/9bf6adf933665dee26532201719fac14a047ccf1/protobuf)

**자동 테스트 30개가 통과했다.** 기존 오류·재연결·메모리 시험에 인증 전 터치 차단, 좌표 범위와 가운데·네 모서리의 5점 탭, 재연결 시 탭 중복 방지, 모의 TLS 세션의 영상·터치 통합 시험을 추가했다. 미리보기 기능과 해당 자동 시험에는 `av==19.0.2`가 필요하다. 기존 라이브러리 반복 시험은 Python 할당과 링크 반환을 비교하며 ASan/UBSan 측정은 남아 있다. [자동 시험 로그](../research/evidence/phase2-windows-touch-tests-20261120-232550.log) · [영상·터치 통합 로그](../research/evidence/phase2-pc-video-touch-mock-20261120-231851.jsonl)

[실행 산출물](../build/i30-receiver.pyz) · [소스 진입점](../src/i30_receiver/cli.py) · [테스트 코드](../tests/test_phase2.py) · [프로토콜 세부 구현](PROTOCOL_IMPLEMENTATION.md)
