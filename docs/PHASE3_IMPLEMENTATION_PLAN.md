# Phase 3 착수 조건과 미디어·입력 계획

**독립적인 PC 미디어 개발은 준비할 수 있다.** Phase 2는 PC 빌드와 모의 통합, 실폰 USB·버전 응답을 통과했다. 실폰 연동을 전제로 하는 Phase 3에는 프로젝트 수신기의 TLS·서비스 세션 검증이 더 필요하다.

| 조건 | 상태 |
|---|---|
| 재현 가능한 PC 실행 패키지, USB·프레임·프로토콜·상태 경계 | 충족 |
| 모의 TLS/서비스/채널, 타임아웃·손상 입력, 분리 후 재연결 | 충족 |
| 실제 폰에서 AOA·bulk·버전 응답 | 첫 삼성 시험폰과 업데이트한 삼성 서브폰 모두 프로젝트 수신기에서 확인했다. [장치별 실폰 검증 수준](USB_CONNECTION_TEST.md#실폰-검증-수준) |
| 실제 TLS·서비스 세션 | 공식 DHU에서 실폰 TLS 1.2와 800×480 화면 렌더링을 확인했다. 자체 수신기에는 폰 인증서를 검증할 신뢰 자료와 예상 이름 또는 지문이 필요하다. 헤드유닛 인증서와 키는 상대가 클라이언트 인증을 요구하는 경우에만 사용한다. [DHU 화면 시험 로그](../research/evidence/phase2-dhu-display-20261120-230704.log) · [인증 자료와 통과 기준](USB_CONNECTION_TEST.md#인증-자료와-실폰-통과-기준) |
| PC의 로컬 H.264 디코딩 | 합성 Annex B 클립 800×480/30 fps의 90프레임 디코딩과 첫 프레임 PNG 출력이 통과했다. 같은 해상도에서 30분 분량인 합성 프레임 54,000개를 12.0초에 모두 디코딩했다. Windows 프로세스 피크 작업 집합은 49.5 MiB였고, 약 9천 프레임 간격의 private bytes 표본은 35.9 MiB로 유지됐다. 이 시험은 재생 속도 제어와 화면 표시를 포함하지 않았다. [미리보기](../research/evidence/pc-h264-synthetic-20261120-230901.png) · [디코딩 부하 로그](../research/evidence/phase2-h264-sustained-synthetic-20261120-232714.json) |
| PC 수신기 영상·입력 경로 | 모의 TLS에서 영상 프레임 3개, 800×480 미리보기, 암호화된 단일 탭의 두 이벤트, 서비스 탐색과 정상 종료를 확인했다. 공식 DHU에서는 첫 폰의 탭 반응과 두 폰의 화면 표시를 확인했다. 서브폰의 탭 반응은 판정 보류다. [수신기 로그](../research/evidence/phase2-pc-video-touch-mock-20261120-231851.jsonl) · [장치별 실폰 검증 수준](USB_CONNECTION_TEST.md#실폰-검증-수준) |
| 실물 CE SDK, 실행·복구, USB/영상/카메라 벤치 | 대기 |

1. [USB 연결 시험](USB_CONNECTION_TEST.md)의 실폰 `probe`와 DHU 결과를 기준으로 삼는다. 승인된 신뢰와 자격 자료가 있으면 프로젝트 수신기의 `connect`로 TLS, 광고 서비스, ping과 종료까지 기록한다.
2. PC 영상 미리보기와 별도로 연속 재생 창을 연결한다. 미리보기는 명시적으로 요청했을 때만 projection focus를 응답한다. 출력 시각과 입력 시각을 계수해 실폰에서 SPS/PPS·재연결·키프레임 처리를 기록하고, 480p 계열/30 fps 30분의 프레임 누락, p95 지연, 피크 메모리를 측정한다.
3. 연속 재생 창에서 느린 디코더와 재연결 시 패킷 큐 및 흐름 제어를 시험한다. 단일 탭 시험을 창의 좌표 변환, 5점 시험, 드래그와 연결 해제 처리로 확장한다.
4. PCM 출력과 버퍼를 추가한 뒤 안내·미디어·음량을 구분한다. 실폰 오디오 포커스와 스트림 중단·복구를 검증한 후 마이크 입출력을 추가한다.
5. CE SDK 및 실물 자료가 확보되면 PC 기능과 분리한 CE 테스트 대상으로 USB 및 디코더 어댑터를 검증한다. 후방카메라, 순정 음량·경고, USB 분리 시 순정 복귀 시험의 기준은 [벤치 계획](PHASE2_IMPLEMENTATION_PLAN.md)에 있다.

PC 단위 테스트에는 로컬 클립과 합성 입력을 쓸 수 있다. 연결·인증·카메라 전환은 각각 실제 장치에서 관찰한 결과만 통과로 기록한다.

## 로컬 H.264 시험 실행

프로젝트 루트에서 기존 PC 검증 가상환경을 사용한다. 입력은 Annex B H.264 원시 스트림이다. 진단 도구는 64 MiB까지 읽고 디코딩된 해상도와 프레임 수를 JSON으로 출력한다. `--preview`는 첫 프레임을 새 PNG로 저장한다.

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py -m pip install --only-binary=:all: av==19.0.2
& $py tools/check_pc_video.py 'C:\path\sample.h264' --preview 'C:\path\sample-preview.png'
& $py -m unittest discover -s tests -q
```

PC 시험 도구의 디코딩 시간에는 렌더링, USB 전송, 순정 내비게이션 성능이 포함되지 않는다. [PyAV 설치 문서](https://pyav.basswood.io/docs/stable/overview/installation.html)
