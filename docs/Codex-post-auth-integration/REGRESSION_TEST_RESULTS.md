# 영상·USB 및 회귀 시험

## ARM 영상·USB 측정

| 시험 | 결과 |
| --- | --- |
| 800×480 H.264 Baseline 명목 15/24/30 FPS | 각 8개 수신·응답·`StretchDIBits` 표시, 각 2개 키프레임. |
| 명목 15 FPS 1분 | 900/900 ACK 및 표시. 가상 영상 시간 60.080초, 호스트 106.003초, 호스트 CPU 103.359초. |
| 명목 15 FPS 5분 | 4,500/4,500 ACK 및 표시. 가상 시간 300.080초, 호스트 486.773초, I 프레임 300장. 최신 터치 빌드에서도 4,500/4,500 표시, 호스트 642.898초, CPU 629.156초, 종료 후 추적 할당 0. |
| 명목 15 FPS 30분 | 한 TLS 세션에서 27,000/27,000 ACK 및 표시, 1,800개 키프레임. 1/5/15/30분 시점의 추적 할당 최고치 5,231,632바이트, 종료 후 추적 할당 0건. 가상 영상 1,800.080초, 호스트 3,193.781초, CPU 3,100.844초. `final-ce`로 실행했다. |
| 고움직임 영상 15/24/30 FPS 2초씩 | `testsrc2`의 30/48/60개를 모두 표시. 압축 데이터 149,374/254,485/453,452바이트. 최대 접근 단위 22,009바이트는 여러 AAP 조각으로 전송했다. |
| 30분 수신 활동 유지 | 가상 60/300/900/1,800초 체크포인트, ping/pong 180회, 출력 프레임 5개. 간헐적 프레임을 사용한 지속 연결 시험이다. |
| 반복 연결 | 동일한 ARM 메모리 공간에서 5/10/30회 TLS·서비스·터치·영상·종료. 연결별 최고 추적 할당량 5,230,680바이트. 모든 종료 후 추적할 할당은 0. |
| 비정상 단절 및 영상 오류 | TLS 도중, AuthComplete 직후, 영상 프레임 분할 도중, 첫 DOWN 직후에 종료. USB 파이프와 전송 및 영상·TLS 할당 반환. 폭 816의 프레임 거부와 영상 STOP 뒤 다시 협상·표시 통과. |
| 수신 대기와 후방 단절 | USB 수신 대기 및 zero-length packet 중에도 올바른 터치 6건. 창 읽기 지연을 한 번 주입한 뒤에도 접촉 순서 유지. 후방 표시 이벤트 중 분리 시 출력 1장 이후 터치 0건, 추적 할당 반환. |
| Python·네이티브 빌드 | 기존 Python 84개 유지. WinCE ARM USB 전용, BearSSL/h264bsd 투사 빌드와 기존 USB·TLS·영상 회귀 통과. 실제 ARM 순정 터치 트램펄린의 전달·복귀 분기와 자동 시작 시나리오 재실행. |
| 분리된 SPS/PPS, IDR 및 재시작 | 최신 `tested-ce`에서 무타임스탬프 `CODEC_CONFIG`를 두 TLS/AAP 조각으로 보내고 사이에 제어 ping을 삽입했다. SPS/PPS ACK까지만 수신한 시점에는 표시 0장, 이후 64비트 타임스탬프가 붙은 IDR을 받아 표시 1장과 올바른 세션 ACK를 확인했다. STOP/SETUP/START 이후 동일 흐름을 반복해 설정 ACK, 영상 ACK, 표시, pong이 각각 총 2회였다. |

1분 시험의 평균·최대 프레임 ACK 시간은 각각 117.230/336.471 ms, 5분 시험은 108.038/329.586 ms이다. 실제 ARM 코드와 가상 USB·GDI API를 사용하는 5분 시험의 호스트 처리량은 약 9.24 FPS였다. 기기 시간은 시험 송신자가 정한 간격으로 증가한다. ACK 시간에는 전송·복호화·디코딩·GDI 호출이 포함된다. [1분 영상 원본](../../build/codex-post-auth-integration/arm-video-60s.json) · [5분 영상 원본](../../build/codex-post-auth-integration/arm-video-300s.json) · [고움직임 15 FPS](../../build/codex-post-auth-integration/arm-motion-15.json) · [24 FPS](../../build/codex-post-auth-integration/arm-motion-24.json) · [30 FPS](../../build/codex-post-auth-integration/arm-motion-30.json) · [ARM 반복 연결 및 예외 원본](../../build/codex-post-auth-integration/tested-arm-regression.json)

30분 시험에서는 평균 ACK 117.860 ms, 최대 507.574 ms와 약 8.45 호스트 FPS를 기록했다. 최신 빌드의 SPS/PPS 시험과 Python 84개 회귀는 세션 복구 뒤에 실행했다. [30분 체크포인트](../../build/codex-post-auth-integration/arm-video-1800s.checkpoints.jsonl) · [30분 시험 원본](../../build/codex-post-auth-integration/arm-video-1800s.json) · [SPS/PPS ARM 회귀](../../build/codex-post-auth-integration/sps-pps-arm-regression.json) · [Python 회귀](../../build/codex-post-auth-integration/resumed-unittest.stderr.log)

최신 ARM DLL과 같은 해시의 빌드를 계측해 고움직임 30 FPS 60프레임에서 `h264bsdDecode`의 프레임당 평균·최대 224.74/296.38 ms, `h264bsdNextOutputPictureBGRA`의 70.63/121.21 ms를 얻었다. 벽시계 기준의 Unicorn 호스트 수치이며, 후자는 GDI로 전달할 픽셀 변환 시간이다. 순정 GDI의 합성 지연, 실제 전송 지연, Windows CE 전체 메모리, 실제 OMAP 처리량은 별도 계측이 필요하다. [ARM 함수 계측 원본](../../build/codex-post-auth-integration/arm-video-profile.json)

상주 투사에만 마지막 양의 길이 USB 수신부터 20초 idle 제한을 적용한다. 버전·TLS 및 수동 연결 진단은 기존 시간 제한으로 유지한다. USB 파이프 소유자는 기존 `USBDeviceAttach`이며 순정 물리 호스트의 분리 통지·파이프 해제 순서는 L5에서 확인한다. [USB 전송과 자원 해제](../../src/ce/ce_aa_usb_client.c)

## 순정 통합 시험

첫 수정 이미지에서 순정 메뉴, TLS, AuthComplete, 서비스 탐색과 45개 연속 영상 응답을 관측했다. 터치 및 후진 전환을 포함한 구간은 게스트 60.895초, 호스트 749.551초, 호스트 CPU 677.094초였다. 카메라에 표시를 넘긴 구간도 영상 응답 수에 포함되어 있다. 후진을 가상 MICOM에 주입한 뒤 상대의 네이티브 영상 포커스 확인까지 가상 90.1 ms였다. 후진 중 시험 터치는 AAP로 전달되지 않았고, 같은 세션에서 투사 포커스와 영상이 복귀했다. 첫 수정 이미지 시험은 USB 분리 시작 직후 벽시계 제한에 도달했다. 반복 연결 시험은 첫 세션의 프레임 수를 줄여 별도로 진행한다. [순정 통합 결과](../../build/codex-post-auth-integration/final-integration/virtual-phone.json) · [순정 UART](../../build/codex-post-auth-integration/final-integration/virtual-phone.serial.log)

## 재현

```powershell
$out = 'build/codex-post-auth-integration'
$py = Join-Path $env:LOCALAPPDATA 'i30-phase2-venv/Scripts/python.exe'
$cc = Join-Path $env:LOCALAPPDATA 'i30-phase5-tools/arm-gnu-14.2/bin/arm-none-eabi-gcc.exe'
$ssl = Join-Path $env:ProgramFiles 'Git/usr/bin/openssl.exe'
& $py -m unittest discover -s tests
& $py tools/build_ce_usb.py "$out/final-ce" --compiler $cc `
    --bearssl-source build/ce-tls-dependency/bearssl-0.6 --h264-source build/ce-video-dependency/h264bsd
& $py tools/patch_gd13my_settings.py "$out/navigation" --compiler $cc --native-projection
& $py tools/emulate_ce_usb.py "$out/final-ce" --tls-openssl $ssl --projection --stress-rounds 30 `
    --navigation "$out/navigation/GDdNavi.exe"
& $py tools/emulate_ce_usb.py "$out/final-ce" --tls-openssl $ssl --continuous-seconds 60 --continuous-fps 15
& $py tools/emulate_ce_usb.py "$out/final-ce" --tls-openssl $ssl --continuous-seconds 2 `
    --continuous-fps 30 --motion-pattern --profile-video
& $py tools/emulate_ce_usb.py "$out/final-ce" --tls-openssl $ssl --continuous-seconds 1800 --continuous-fps 15 `
    --continuous-progress "$out/arm-video-1800s.checkpoints.jsonl"
& $py tools/emulate_gd13my_startup.py build/codex-authentication-resolution/uComH_New.exe
```

순정 통합은 기존 `.061` DiskA에 최신 `i30usb.dll`과 `i30nav.dll`, 새 `navigation`과 기존 `LibSystem/LibVideo`·부팅 패치를 넣는다. `tools/verify_gd13my_virtual_phone.py`에 `--native-menu`, `--stream-frames 12 --fps 15 --cycles 5 --camera --restore-map --seconds 2700`을 전달한다. 기존 전체 맵 매체는 C: 캐시에서 읽었고, 중요 ARM 바이너리, 시험 이미지, 로그와 스크린샷은 F:의 `build/codex-post-auth-integration/`에 저장한다. [기존 이미지 빌드 명령](../Codex-authentication-resolution/EMULATOR_VALIDATION.md#gd13my-순정-에뮬레이터-검증)
