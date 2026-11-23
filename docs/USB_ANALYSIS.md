# USB 호스트 및 AOA 타당성

**호스트 경로는 확인됐다.** AOA는 CE USB 클라이언트 계층에서 검토할 수 있지만, 순정 USB 앱이나 현재 장치 정책에서 사용할 수 있다는 증거는 없다.

| 층 | 펌웨어 근거 |
|---|---|
| 컨트롤러 및 시작 설정 | ROM에서 푼 `default.hv`의 `Dllmusbotg.dll`(파일 `0x2f2e2`)과 `Dllmusbhcd.dll`(`0x2f4a6`), `PrefixHCD`(`0x2f4de`). XIP `musbhcd.dll`의 `HCD_Init` RVA `0xaca0`, `HCD_IOControl` RVA `0xae64`. ROM 파일 `0xc8bd13`에 OMAP3430 MUSB HCD PDB 이름, `0xc8acdb`에 bulk OUT DMA 처리 메시지가 있다. |
| 열거 및 클라이언트 | XIP `usbd.dll`의 `HcdDeviceAttached` RVA `0x1550`, `HcdSelectConfiguration` `0x12c4`, `RegisterClientDriverID` `0x1824`, `RegisterClientSettings` `0x1b48`. CE 호스트 클라이언트의 `USBDeviceAttach`가 장치 핸들과 `USB_FUNCS`를 받는 구조와 부합한다. [Microsoft USBDeviceAttach](https://learn.microsoft.com/en-us/previous-versions/windows/embedded/ms923216%28v%3Dmsdn.10%29) |
| USB 저장장치 | `usbmsc.dll`의 `USBDeviceAttach` RVA `0x39f8` 및 `UsbsDataTransfer` `0x3678`, `usbdisk6.dll`의 `UsbDiskAttach` `0x3f68`. `default.hv` 파일 `0x28332`, `0x285c2`에 USBDISK6 표기가 있다. |
| 순정 미디어 | `LibUSB.dll` VA `0x0010ece4`에서 파일 `0x1a908`과 `0x1a958`의 삽입 이벤트 문자열을 참조한다. Ghidra 함수와 ROM ordinal을 대조하면 `WaitForSingleObject`, `WaitForMultipleObjects`, `GetFileAttributesW` 호출이 있다. `GDdmedia.exe`가 `LibUSB.dll` 및 `LibMMCodec.dll`을 import한다. 이 코드에서 관찰한 동작은 마운트와 파일 기반 미디어 처리다. |
| 전원 및 분리 | `LibUSB.dll` VA `0x0010e44c`가 `USB_POWER_DOWN`(파일 `0x1a3b4`)을 참조한다. `USB OFF MsgSend micom`(`0x1ad04`)은 문자열로 확인했으며 이번 Ghidra 조회에서 호출 위치는 확인되지 않았다. |

## .061 USB 클라이언트 시험

순정 `usbd.dll`의 등록 코드 `0x1824`, `0x1b48`와 그룹 포맷 함수 `0x3ed0`에서 `HKLM\Drivers\USB\ClientDrivers`와 `HKLM\Drivers\USB\LoadClients\<Group1>\<Group2>\<Group3>\<ID>`를 확인했다. VID/PID는 10진수로 쓰고, 일치 조건을 지정하지 않은 그룹에는 `Default`를 쓴다. WinCE 사용자 프로세스의 `LoadLibraryW(L"usbd.dll")`는 0을 반환했다. 시험 앱은 순정 로더가 사용하는 레지스트리 값 `DLL`에 `\DiskA\Application\NAVI\i30usb.dll`을 쓴다. [등록 코드](../build/gd13my-aa-lab/usbd-register.asm)

`usbd.dll` RVA `0x60d0`의 `USB_FUNCS` 크기는 `0xac`이다. 사용한 테이블 오프셋은 장치 정보 `0x34`, vendor 전송 `0x38`, 파이프 열기·닫기 `0x5c/0x68`, bulk 전송 `0x74`, 완료·상태·전송 닫기 `0x80/0x84/0x90`이다. 순정 `usbmsc.dll`에서 인터페이스의 엔드포인트 포인터 `+0x14`, 구조체 간격 `0x1c`와 엔드포인트 간격 `0x14`를 대조했다. 전송 완료를 최대 3초간 폴링하고 완료 여부와 관계없이 순정 전송 닫기 API를 호출한다. [인터페이스 코드](../build/gd13my-aa-lab/ce-usbmsc-interface.asm) · [ARM 전송 시험](../build/gd13my-aa-lab/ce-usb-test-v3.json)

**AOA에 필요한 경로.** PC의 aasdk는 libusb로 장치에 control transfer를 보내고, accessory 전환에 따른 재열거 후 인터페이스를 열어 bulk IN/OUT을 사용한다. 이 플랫폼에는 libusb가 사용하는 데스크톱 드라이버 대신 CE의 USB client 및 `USB_FUNCS`에 맞는 전송층이 필요하다. 순정 앱의 파일 마운트와 별개로, 지원되는 로딩 정책에서 USB client 또는 기존 전송 API에 접근할 수 있는지 확인해야 한다. 리뷰한 GD13MY의 APP/USB ROM 근거에서 AOA 구현이나 실제 스마트폰 열거 로그는 발견되지 않았다. [AOSP AOA](https://source.android.com/docs/core/interaction/accessories/protocol) · [aasdk USB 전송](https://github.com/opencardev/aasdk/blob/9bf6adf933665dee26532201719fac14a047ccf1/src/Transport/USBTransport.cpp)

**대역폭.** OMAP3530은 데이터시트 기준 high/full/low speed 호스트를 지원한다. 실물 포트·하네스·허브·케이블의 협상 속도와 VBUS 공급은 모른다. 기준값은 링크의 명목 속도 대신 연결 후 bulk 처리량과 지연으로 잡는다. 동일 폰/케이블의 PC DHU 세션에서 1초 단위 트래픽 p95를 기록하고, 기기에서 그 값의 1.5배를 지속 처리하는지와 30분간 재열거·분리 오류가 생기는지 시험한다. 1.5배와 30분은 Phase 2의 잠정 공학 기준이다. [TI OMAP3530](https://www.ti.com/product/OMAP3530)

[ROM export](../research/evidence/phase1-rom.json) · [OEM PE import](../research/evidence/phase1-scan.json) · [Ghidra 주소](../research/evidence/phase1-xrefs.tsv)
