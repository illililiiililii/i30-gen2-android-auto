# 순정 펌웨어 패키징 감사

대상은 `i30_2013` / `HM` / `GD13MY.KOR.SOP.00.061`이다. Phase 5의 감사 도구는 원본을 읽고 JSON을 출력한다. 설치용 파일이나 매니페스트를 생성하는 기능은 없다. [기존 형식과 저장 경로 근거](FIRMWARE.md)

## Android Auto 메뉴 변경본

한국형 `.061`의 `GDdNavi.exe`와 `nfdNaviGui_lit.gcf`에서 원본 SHA-256을 확인한 뒤에만 패치한다. `내비설정 → 기타`의 `IDC_SHOT_NMN09`에 31번 항목을 추가하고, 해당 화면의 버튼 좌표에서 순정 `WM_LBUTTONUP`이 발생하면 `\DiskA\Application\NAVI\i30aa.exe`를 실행한다. 기존 119개 화면의 기존 컨트롤 레코드가 모두 일치했다. ARM 시험에서 다른 화면과 버튼 밖 좌표, 실행 파일 누락, 이미 열린 대화상자 경로를 확인했다. [바이너리 검증](../build/gd13my-aa-lab/patched-files.json) · [ARM 실행 시험](../build/gd13my-aa-lab/patched-arm-smoke.json)

시험용 `APP.hdr`와 `APP.spd.000`을 재구성하고 전체 파일을 다시 풀어 예상 경로 및 바이트와 비교했다. BSP, MICOM, ACC와 실제 설치 프로그램은 이 변경본의 구성에 포함되지 않는다. 에뮬레이터 가상 디스크도 따로 만들었고, MBR·지도·설정 영역과 수정 대상 외 순정 파일 117개가 원본 가상 디스크와 일치했다. [APP 파일](../build/gd13my-aa-lab/app-archive) · [재구성 결과](../build/gd13my-aa-lab/patched-archive.json) · [가상 디스크 비교](../build/gd13my-aa-lab/native-image-audit.json)

순정 `install.ini`는 APP 설치 전에 `DiskA`를 포맷하도록 설정한다. 에뮬레이터는 설치 후 배치된 파일을 실행하므로 OEM 설치기의 전원 차단 대응이나 실제 차량의 순정 복구는 이 부팅 검증의 범위 밖이다. 원본 APP과 기존 디스크를 보존했다.

USB 연결 시험용 APP은 위 두 순정 메뉴 파일 변경에 `/Application/NAVI/i30aa.exe`와 `/Application/NAVI/i30usb.dll`을 포함한다. 원본 APP 대상 119개 파일을 읽어 변경 대상 SHA-256을 확인한 뒤, 재구성한 APP을 다시 풀어 파일 바이트를 대조했다. 지도 포함 가상 디스크의 MBR, 파티션 배치, 지도·설정 영역 전체 및 변경 대상 외 순정 APP 파일 117개가 원본과 일치했다. 차량 업데이트에 필요한 매니페스트나 설치 프로그램은 생성하지 않았다. [USB 시험용 APP](../build/gd13my-aa-lab/app-archive-usb-v3) · [APP 해시](../build/gd13my-aa-lab/ce-usb-archive-v3.json) · [가상 디스크 비교](../build/gd13my-aa-lab/ce-usb-full-audit.json)

### v5 시작 설정 시험용 APP

한국형 GD13MY `.061`의 시스템 관리자 `uComH_New.exe`에 ARM 시작 설정 경로를 추가했다. `내비설정 → 기타 → Android Auto`의 두 체크박스는 사용자가 저장하면 `\DiskA\i30agree.opt` 및 `\DiskA\i30auto.opt`로 기록된다. 기본 파일은 두 옵션이 꺼진 상태다. 시스템 관리자는 순정 내비 시작 알림에서 선택된 옵션을 읽고 기존 동의 경로 또는 USB 시험 실행 파일을 부팅당 한 번 호출한다. [ARM 시작 경로 시험](../build/gd13my-aa-lab/startup-arm-test-v5.json) · [체크박스와 USB ARM 시험](../build/gd13my-aa-lab/ce-usb-test-v5.json)

v5 APP을 다시 풀어 예상 파일과 바이트를 대조했다. 적용 대상은 `nfdNaviGui_lit.gcf`, `GDdNavi.exe`, `uComH_New.exe` 및 두 시험용 ARM PE 파일이다. 차량 설치와 복구, 폰 자동 연결 및 인증·화면 투사는 미검증이다. [v5 APP 검사 폴더](../build/gd13my-aa-lab/app-archive-startup-v5) · [v5 APP 해시](../build/gd13my-aa-lab/startup-app-archive-v5.json)

두 옵션을 켠 APP 전용 시험 이미지에서 가상 MICOM 기동 이벤트를 한 번 보조했다. 순정 WinCE는 시스템 관리자 패치를 실행했고, 순정 동의 처리 함수와 `CreateProcessW`를 거쳐 `i30aa.exe`의 USB 연결 대기에 들어갔다. 설정 실행 파일을 별도로 시작했을 때 순정 WinCE가 새 대화상자를 생성하고 `WM_INITDIALOG`를 전달했다. [네이티브 시작 호출](../build/gd13my-boot/gd13my-window-20261122-125050-022637.startup-native.log) · [설정 초기화](../build/gd13my-boot/gd13my-window-20261122-125050-022637.dialog-native.log) · [실제 WinCE UART](../build/gd13my-boot/gd13my-window-20261122-125050-022637.serial.log)

v6 시험 이미지는 v5에 들어 있던 USB 클라이언트 DLL의 CE 이벤트 처리만 교체했다. 두 로컬 이미지의 6,144바이트 DLL 범위 밖 전체 바이트가 동일함을 확인했다. 검사용 APP 아카이브를 생성해 기존 순정 파일과 패치 파일을 비교했다. [v6 이미지 비교](../build/gd13my-aa-lab/startup-compact-v6.json) · [v6 APP 아카이브 해시](../build/gd13my-aa-lab/startup-app-archive-v6.json)

| 영역 | 관찰 결과 |
|---|---|
| 배포 및 모델 | 루트 `i30_2013.ver`는 모델·지역 버전·구성 파일 크기·CRC32를 기록한다. Phase 5에서는 루트와 GD13MY의 항목 15개를 실제 바이트에서 재확인했다. 공용 지도는 기존 Phase 0의 전체 볼륨 검증 결과를 재사용했다. |
| 헤더와 압축 | `HACO STDAVN UPGRADE IMAGE` 헤더, 헤더 길이와 MD5, 각 파일의 압축 경계·크기·MD5를 확인했다. APP 119개 파일과 zlib 122개, BSP 3개 파일과 zlib 3개, MICOM 1개 파일과 zlib 1개였다. ACC 압축 볼륨은 비어 있다. |
| 부트 및 OS | BSP의 `raw`에 TI X-Loader와 Hyundai Autonet EBOOT 흔적이 있고, `kernel`의 CE BIN 레코드 160개 및 ROM TOC를 재검사했다. MICOM과 커널은 별도 구성 파일이다. |
| 적용과 복구 | `install.ini`에서 BSP·APP·ACC·MAP·MICOM 활성 플래그와 Bluetooth 비활성 플래그를 확인했다. APP·ACC 백업 항목, 지도 경로를 확인했다. 설정의 섹션 나열과 실제 적용 순서·재부팅·장애 복구 동작은 각각 별개의 근거가 필요하다. ROM `AutoStartUp.exe`에는 `AVNRecovery.exe` 후보 경로가 있다. |
| 무결성 및 서명 | 루트 `install.md5` 일치와 두 PE의 보안 디렉터리 값 0을 확인했다. REA에서도 내장 PE 인증서 테이블 항목을 찾지 못했다. 외부 서명, 보안 부팅, 기기별 코드 허용 및 업데이트 신뢰 정책은 확인되지 않았다. MD5와 CRC32는 패키지에서 관찰한 오류 검출 값이다. |

변경 구성 요소의 첫 통합 지점은 OEM이 지원하는 독립 진단 앱 실행 경로다. 정식 패키지 통합의 판단은 실제 설치 순서, 코드 실행 정책 및 같은 버전 순정 복구가 확인된 뒤에 가능하다. [Phase 6 시험 순서](PHASE6_PLAN.md) · [읽기 전용 감사 보고서](../build/phase5-evidence/firmware-audit.json)
