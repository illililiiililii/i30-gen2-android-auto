# Android Auto 수신기 포팅 비교

**PC 기준 구현과 CE 구현을 분리한다.** Google DHU는 폰과 케이블의 기준 동작을 확인하는 데 쓴다. 공개 수신기에서 검증할 전송·채널·미디어 경계를 정리하고, 실물에서 실행 경로와 드라이버를 확인한 뒤 CE용 경량 수신기를 구현한다. 3개 저장소는 Phase 0에 기록한 커밋을 사용해 빌드 설정 및 USB·영상·오디오·입력 소스를 다시 읽었다. [공식 DHU](https://developer.android.com/training/cars/testing/dhu)

| 항목 | f1xpl/OpenAuto | OpenCarDev/aasdk | OpenHU |
|---|---|---|---|
| 조사 커밋 | `aa90412b` | `9bf6adf9` | `49c5092a` |
| 지원 OS·CPU·ABI | README의 Linux, Raspberry Pi 3, 데스크톱 Windows. Raspberry Pi OpenMAX는 명시적 빌드 옵션이다. CE SDK나 Windows CE PE ABI 표적은 없다. | CMake의 Debian 패키지에 `amd64`, `i386`, `armhf`, `arm64`. 일부 Windows 빌드 분기가 있으며 ARM cross compile 예시는 GNU/Linux ABI를 대상으로 한다. CE 전송 계층은 없다. | Linux/Pi 프로젝트. README의 배포 대상은 x86-64/arm64. CMake의 armhf 패키지 분기는 호환 바이너리의 실제 제공이나 CE 지원의 증거가 아니다. |
| 컴파일러·의존성 | CMake ≥3.5.1, C++14, 해당 언어 표준의 호스트 컴파일러. Qt5 Multimedia/Widgets/Bluetooth, Boost, Protobuf, OpenSSL, libusb, RtAudio, aasdk. Pi 경로는 Broadcom ilclient/OpenMAX 추가. | CMake ≥3.16, C++17 필수. Boost system/log, protobuf, 선택에 따라 Abseil, libusb-1.0, OpenSSL. 일부 로깅 빌드는 nlohmann_json을 사용한다. | CMake ≥3.14, C++17, Qt 6.8/QML/Quick, FFmpeg/libavcodec, aasdk, Boost, Protobuf, Abseil 조건부, OpenSSL, libusb, GPS 및 Linux 서비스. |
| USB와 세션 | USB는 aasdk를 사용한다. 앱의 `AndroidAutoEntity` 및 서비스 클래스가 연결과 채널을 구성한다. | `AccessoryModeProtocolVersionQuery.cpp`가 AOA 질의에 필요한 control 계층을 사용한다. `USBTransport.cpp`가 libusb 비동기 bulk 전송을 제출한다. `Messenger`는 채널과 프레임, `SSLWrapper`는 보안 세션을 담당한다. | AOA 및 Android Auto는 aasdk 기반이다. UI 및 USB 상태 관리 계층을 더한다. |
| H.264 | `OMXVideoOutput.cpp`는 Pi에서 `OMX_VIDEO_CodingAVC`. `QtVideoOutput.cpp`는 Qt5 `QMediaPlayer`와 `QVideoWidget`. CE의 `VID1:` 또는 DirectDraw 전용 어댑터는 따로 필요하다. | 영상 sink와 설정/채널 메시지를 처리한다. 디코드와 화면 표시 백엔드는 사용하는 앱이 제공한다. | `FfmpegVideoOutput.cpp`의 `avcodec_send_packet` → `avcodec_receive_frame`. YUV420/NV12를 `QVideoFrame`으로 넘기며, UI가 뒤처지면 아직 표시되지 않은 프레임을 최신 것으로 교체한다. |
| 오디오·마이크 | media/system/speech 채널과 QtAudio/RtAudio 출력, QtAudioInput 기반 캡처가 분리돼 있다. CE의 WAVE API 및 OEM 음량 처리는 다시 연결해야 한다. | media sink에 미디어·안내·시스템·전화 채널과 microphone source 정의가 있다. PCM 재생과 캡처 장치는 제공하지 않는다. | `QtAudioOutput.cpp`의 Qt6 `QAudioSink`, QtAudioInput, 서비스별 음성, AudioGraph 및 덕킹 구현이 있다. Linux 오디오 포커스 방식은 CE의 OEM 장치 소유권과 별개다. |
| 입력 | `Projection/InputDevice.cpp`에서 Qt 이벤트를 터치·키로 변환해 InputService에 전달한다. | `InputSourceService.cpp` 및 메시지 정의가 채널 전송을 제공한다. OS의 터치·버튼을 받는 것은 앱 역할이다. | `Projection/InputDevice.cpp`가 Qt 터치/마우스 좌표를 프로젝션 영역으로 변환한다. 기존 CE 입력 핸들러와 연결하려면 어댑터가 필요하다. |
| 성능·메모리 | README에 명시한 Pi 성능은 이 장치와 다른 디코더 환경의 주장이다. Qt와 미디어 의존성을 포함한 CE 실측치가 없다. | 전체 앱보다 경량화 여지는 있지만, Boost/Protobuf/TLS 버퍼와 USB 전송 큐에 대한 CE RSS 또는 지연 측정값이 없다. | 코드에서 디코드 워커와 렌더 스레드 간 프레임 복사를 확인했다. CE에서는 Qt/FFmpeg 사용자 공간 메모리를 산출할 수 있는 실행 빌드가 없다. |
| 라이선스·재배포 | README GPLv3, 주요 소스는 GPLv3 이상 고지. | 문서 GPLv3, 소스 GPLv3 이상 고지. 확인한 커밋의 루트 LICENSE 부재는 [Phase 0 연구](../research/RESEARCH.md)에 기록했다. 코드 채택 전 원문 조건을 다시 확인한다. | GPL-3.0으로 표시한다. FFmpeg 빌드 옵션과 기타 종속물의 재배포 조건은 별도다. |

소스 포함 배포를 택한다면 채택한 파일의 라이선스 고지와 해당하는 소스 제공 의무를 기록한다. 공개 저장소의 프로젝트 소스와 OEM 펌웨어는 별개로 관리한다. 대상 CE의 기본 C/C++ RTL, 정확한 linker 및 SDK, ARM interworking과 import table은 작은 검증용 PE로 확인할 항목이다.

### A–D 판정

| 방안 | 난이도 및 예상 성능 | 결정 |
|---|---|---|
| A · 전체 포팅 | 매우 높음. CE에서 USB, 그래픽, 디코더, 오디오와 런타임을 교체해야 한다. Qt5의 Win32 경로와 Linux armhf 경로는 CE ABI를 해결하지 못한다. 기존 호스트 성능은 이전할 수 없다. | PC 비교 기준으로만 사용. |
| B · CE 경량 수신기 | 높음. CE ABI를 맞춘 작은 구성에 AOA 전송, 채널 프레임과 OEM 영상/오디오/입력을 별도 모듈로 개발한다. OEM H.264 DSP 경로를 재사용할 수 있다면 CPU와 복사 비용을 줄일 수 있다. | 기기 검증 통과 후 우선안. 프로토콜과 채널의 참고 구현을 사용하고, 의존성 재사용은 컴파일·메모리 결과를 본다. |
| C · 추가 런타임/시스템 구성 요소 | 높음. CE USB client나 제한된 런타임 추가를 먼저 검토할 수 있다. OS를 바꾸면 순정 카메라·미디어·MCU 연동과 복구를 다시 검증해야 한다. | B의 특정 기능에 필요한 경우에만 검토. |
| D · 기기용 구현 보류 | PC에서 테스트할 수 없는 실행 정책, full/hi speed 포트, 실제 RAM, DSP 디코딩, 카메라 점유와 복구가 남는다. | 현 상태. PC MVP는 진행할 수 있다. |

[OpenAuto 빌드](https://github.com/f1xpl/openauto/blob/aa90412bf93b5a5078495ea85ac9270c6297d369/CMakeLists.txt) · [Pi H.264 출력](https://github.com/f1xpl/openauto/blob/aa90412bf93b5a5078495ea85ac9270c6297d369/src/autoapp/Projection/OMXVideoOutput.cpp) · [aasdk 빌드](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/CMakeLists.txt) · [aasdk USB 전송](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/src/Transport/USBTransport.cpp) · [OpenHU 빌드](https://github.com/average-web-dev/openhu/blob/49c5092a8a4850814866647210faf14d54a54320/CMakeLists.txt) · [OpenHU 디코더](https://github.com/average-web-dev/openhu/blob/49c5092a8a4850814866647210faf14d54a54320/src/autoapp/Projection/FfmpegVideoOutput.cpp)
