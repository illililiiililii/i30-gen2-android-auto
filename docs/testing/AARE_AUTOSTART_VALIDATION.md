# AARE 자동 연결 기능 검증 보고서

## 1. 개요 및 시험 환경

본 문서는 GD13MY Windows CE Android Auto 수신기의 자동 연결(Autostart) 기능에 대한 체계적인 검증 결과를 기록한다.
최신 빌드 산출물인 v8 이미지(`build/gd13my-aa-autostart-v8/gd13my-aa-autostart.img`, `uComH_New.exe`)와 자동화 시험 도구(`tools/emulate_gd13my_startup.py`, `tools/emulate_ce_usb.py`, `tests/`)를 활용하여 검증을 수행했다.

- **대상 이미지**: `build/gd13my-aa-autostart-v8/gd13my-aa-autostart.img`
- **시작 컴포넌트**: `build/gd13my-aa-autostart-v8/uComH_New.exe`
- **검증 환경**: ARM 에뮬레이터 + WinCE API 더블 (가상 스마트폰 및 가상 USB 환경)

---

## 2. 세부 검증 항목 및 결과

| 검증 항목 | 시험 방법 및 명령 | 기대 결과 | 실제 결과 | 판정 |
|---|---|---|---|---|
| **1. USB 연결 시 자동 실행 옵션** | `emulate_ce_usb.py` (settings regression) | 레지스트리/옵션 파일 독립 저장 및 반영 | `\DiskA\i30-aa-usb-pending.opt` 기록 및 독립 작동 확인 | **PASS** |
| **2. 부팅 시 자동 실행 옵션** | `emulate_gd13my_startup.py` (`uComH_New.exe`) | 부팅 시 백그라운드 리시버 리스너 대기 시작 | NAVI MAIN ACK 후 USB 리스너 시작 이벤트 게시 확인 | **PASS** |
| **3. 두 옵션의 독립적인 동작** | `emulate_ce_usb.py` | 각 옵션 플래그가 상호 간섭 없이 토글됨 | "Both auto-run flags default off, persist independently" 확인 | **PASS** |
| **4. 두 옵션 동시 활성화** | `emulate_gd13my_startup.py` / `emulate_ce_usb.py` | 부팅 대기 및 USB 연결 감지가 충돌 없이 공존 | 단일 USB 소유권 유지, 중복 생성 방지 (`avoid duplicate USB owner` 성공) | **PASS** |
| **5. 설정 저장 및 재부팅 유지** | 레지스트리 / DiskA 플래그 I/O | 비휘발성 저장소에 플래그 유지 | 재부팅 시뮬레이션 후 플래그 읽기 일치 | **PASS** |
| **6. 첫 영상 프레임 표시** | `emulate_ce_usb.py --projection` | AOA -> TLS -> AAP -> 첫 프레임 GDI 렌더 | 800×480 서피스에 첫 비디오 블릿 완료 (`LCD blit begin/end`) | **PASS** |
| **7. USB 분리 후 순정 화면 복귀** | `emulate_ce_usb.py` (`resident` / `cancel` 모드) | 드라이버 안전 등록 해제 및 리소스 반환 | 등록된 4개 USB LoadClient 키 삭제 및 순정 화면 유지 확인 | **PASS** |
| **8. USB 재연결 (Replug)** | `emulate_ce_usb.py` / `native-auto-replug` | 소유권 정리 후 새로운 세션 수립 | 기존 소유권 해제 후 새로운 AOA/TLS 세션 바인딩 정상 | **PASS** |
| **9. 시동 재시작 (에뮬레이터 재실행)** | `emulate_gd13my_startup.py` 다중 사이클 | 콜드 부트 후 정상 상태 복구 | `AutoStartUp.exe` -> `AVNSysInit.exe` 순차 기동 확인 | **PASS** |

---

## 3. 시험 실행 상세 로그 요약

### 3.1 부팅 시퀀스 검증 (`tools/emulate_gd13my_startup.py`)
```json
{
  "unchanged default": [],
  "directory is not an opt-in": [],
  "legacy consent flag ignored": [],
  "start USB on stock NAVI MAIN acknowledgment": [
    "event", "start", "close 61", "close 62"
  ],
  "boot receiver launches a message wake helper": [
    "start", "close 61", "close 62"
  ],
  "boot receiver avoids duplicate USB owner": [
    "start", "close 61", "close 62"
  ],
  "start clock sync before stock startup": [
    "start", "close 61", "close 62"
  ],
  "failed launcher leaves stock running": [
    "event", "start"
  ],
  "duplicate NAVI notification": [
    "event", "close 45"
  ]
}
```
- 순정 내비게이션의 `MAIN mode ACK` 수신 시점에 안전하게 백그라운드 리스너가 기동됨.
- 이미 USB 소유자가 존재할 경우 중복 실행을 방지하는 가드가 정상 동작함.

### 3.2 USB 클라이언트 및 세션 검증 (`tools/emulate_ce_usb.py`)
- **AOA 스위치 핸드오프**: Accessory 모드 진입 성공 (`controls: [51, 52, 52, 52, 52, 53]`).
- **버전 협상**: 1.6 / 1.7 프로토콜 요청 정상 수신 및 응답 (`signals: ["Switch", "Ready"]`).
- **클라이언트 드라이버 등록/해제**:
  - 등록: `Drivers\USB\LoadClients\6353_11520`, `6353_11521`, `1256_26720`
  - 세션 종료 시 깔끔하게 역순으로 삭제됨 (`registered_then_removed` 확인).
- **화면 투사 소유권**: `owner-current: 305441741`, 중복 대체 없음.

---

## 4. 미검증 항목 및 실차/실폰 적용 전 주의사항

1. **물리 스마트폰 시험 미수행**:
   - 본 검증은 가상 스마트폰(Virtual Phone Mock) 및 WinCE API 더블 환경에서 완료된 결과다.
   - 실제 물리 스마트폰 연결 시 필요한 **최초 사용자 화면 터치 승인("이 컴퓨터/기기를 항상 신뢰")** 및 Android Auto 앱의 권한 허용 절차는 가상 환경에서 시뮬레이션할 수 없으므로, **물리 스마트폰 자동 연결 성공으로 간주하지 않는다**.
2. **USB 재연결 시 픽셀 레벨 색상 일치 검증**:
   - 케이블을 급격히 분리했다가 재연결할 때 WinCE GDI 프레임버퍼에 잔상이 남지 않는지에 대한 프레임 단위 픽셀 일치 검증은 추후 화면 캡처 장비 또는 호스트 디스플레이 테스트에서 보강이 필요함.
3. **실차 적용 보류**:
   - 실제 i30 차량 하드웨어에 대한 플래싱은 승인되지 않았으며, 실차 물리 MUSB 포트의 전원 차단/복구 동작은 검증 대상에서 제외되어 있음.
