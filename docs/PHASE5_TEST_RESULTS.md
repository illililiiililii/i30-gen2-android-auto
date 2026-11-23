# Phase 5 검증 결과

2026-11-21 KST. Python 테스트 39개가 통과했다. Windows x64 네이티브 프로세스 시험에서 정상 종료, 크래시 감지, 재시작 대기, heartbeat 만료 후 강제 종료도 확인했다. [Python 로그](../build/phase5-evidence/unittest.log) · [네이티브 로그](../build/phase5-evidence/ce-host-test.log)

| 시험 | 관찰 결과 |
|---|---|
| PC 800×480, 30 fps, 영상과 PCM 동시 입력 | 2초에 60프레임 입력과 60프레임 디코딩·RGB 변환. 누락 0. 음악 100블록 출력, 안내를 섞은 블록 24개, 버린 PCM 샘플 0. 케이블과 TLS 이후의 수신기 경계에 합성 입력을 공급하고 PCM 출력은 메모리에서 검증했다. |
| PC 지연 및 사용량 | 기본 2.006초 실행에서 영상 ingress→RGB p95 37.85 ms, 예정 송신 시각→RGB p95 38.05 ms. Python 프로세스 CPU 0.4844초(논리 코어 하나 기준 24.2%), 샘플링한 최대 working set 48.66 MiB. 합성 영상 인코딩은 측정 구간 앞에서 수행했다. |
| PC 오디오 경합 | WinMM 장치 0에서 독립 재생 핸들 두 개가 무음 버퍼를 받았고 모두 닫혔다. 부분 획득 직후 장치 오류를 주입한 경로에서도 버퍼·장치 해제를 검증했다. [WinMM 실행 결과](../build/phase5-evidence/pc-wave.json) |
| 마이크 ACK 지연 | ACK를 보류했을 때 미확인 2개를 넘기지 않았다. 다른 세션 ID의 ACK를 무시하고 현재 세션 ACK를 받은 뒤 전송을 재개했다. 대기 PCM은 최대 40 ms였다. |
| 화면 전환과 재연결 | 모의 TLS 연결에서 카메라가 화면을 선점한 상태로 USB를 분리·재연결했다. 카메라 선점이 유지됐고, 순정 측 해제 후에만 프로젝션이 돌아왔다. USB 링크 두 개를 정리했다. |
| ARM 진단 앱 | Unicorn에서 파일·힙·실제 ARM 스레드 콜백에 대한 모의 API와 버전 왕복을 실행했다. 정상 종료 코드 0과 파일 열기 거부 코드 1을 확인했다. 두 경로에서 콜백 종료 코드는 17이다. |
| GD13MY 순정 커널 | CERF OMAP35x EVM에서 CE 6.0 이미지를 로드하고 ARM 커널 초기 코드를 실행했다. 부팅은 `0x8ff00000` 메모리 매핑 오류로 중단됐다. |

PC 수치는 합성 장면에서 측정한 짧은 실행 결과다. 실제 USB·TLS·표시 패널·오디오 장치의 종단 간 지연과 CE 사용량은 별도로 측정해야 한다. [A/V 측정 원본](../build/phase5-evidence/pc-av.json) · [재현 스크립트](../tools/check_phase5_av.py) · [CE 실행 로그](../build/phase5-evidence/cerf-gd13my.log)

```powershell
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
& $py -m unittest discover -s tests -v
& $py tools/check_phase5_av.py --seconds 2
& $py tools/check_phase5_av.py --seconds 2 --wave-device 0
& $py build/ce-host-test/i30-ce-host-test.exe
```

장시간 시험은 스크립트 인자만 준비했다. 실기기 검증 단계에서 확인할 항목은 [Phase 6 벤치 계획](PHASE6_PLAN.md)에 정리했다.
