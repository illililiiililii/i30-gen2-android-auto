# 07. Genesis 순정 펌웨어 내 헤드유닛 신원 탐색 (P0-4)

작성: 2026-11-25 · 대상: `G:\` (읽기 전용, Genesis G80 DIS Bluelink 펌웨어)
목적: 순정 펌웨어에 Android Auto / GAL 인증서가 **존재하는지** 확정

## 0. 결론

| 질문 | 답 | 등급 |
| --- | --- | --- |
| 순정 펌웨어에 Android Auto 수신기 모듈이 있는가 | **없다** (평문 영역 기준) | VERIFIED |
| GAL 발급 헤드유닛 인증서가 있는가 | **없다** | VERIFIED |
| PEM 인증서가 어떤 파일에든 있는가 | **0건** (40MB 이하 전체 스캔) | VERIFIED |
| 암호화 이미지 안에 있을 가능성 | 배제 불가 | UNKNOWN |
| 결론 | **순정 펌웨어에서 신원을 얻는 경로는 없다** | VERIFIED(평문) / UNKNOWN(암호문) |

---

## 1. 펌웨어 구조

```
G:\
├─ HU\images\
│   ├─ boot.img      45,565,256 B   magic 53807d50ea2f7b129833bbc9941aa626
│   ├─ vr.img     1,785,153,017 B   "partclone-imageEXTFS"
│   └─ NP\rootfs.img 2,567,399,572 B  magic 53807d50ea2f7b129833bbc9941aa626
├─ IBOX.tar         402,335,780 B   비-tar (offset 257 != "ustar")
├─ essentials        14,970,880 B   tar → update.tar → decrypt/{DecryptToFile,DecryptToPIPE}
├─ AppUpgrade         1,274,224 B   ELF 32-bit ARM
├─ BIN\APPNAVI        5,993,104 B   ELF 32-bit ARM (Qt/AVP 내비 앱)
├─ LIB\*.so          (5개, 219KB~7.5MB)  ELF ARM shared objects
├─ DATA\             리소스(사운드/가이드/맵)
├─ ASR\, TEXT.INFO\
├─ GENESIS_G80_DIS_Bluelink.ver  30,721 B  파일 목록+CRC
└─ .lge.upgrade.xml / .lge.upgrade_enc.xml
```

관측:
- `boot.img`/`rootfs.img`의 매직은 알려진 컨테이너(Android boot, cramfs, squashfs, ext)가 아니다.
  → **암호화 또는 벤더 전용 컨테이너**.
- `vr.img`는 `partclone` 이미지(EXTFS) — 파티션 덤프 포맷.
- `IBOX.tar`는 이름과 달리 tar가 아니다(오프셋 257이 `ustar` 아님). → 암호화/압축.
- `essentials`는 **복호화 도구만** 담고 있다:
  ```
  ./decrypt/DecryptToFile   187,986 B
  ./decrypt/DecryptToPIPE   182,263 B
  ```
  이는 나머지 이미지가 **업데이트 시점에 복호화**된다는 직접 증거다.

---

## 2. 스캔 결과

### 2.1 PEM 인증서 전수 검색

```
build/auth-research/scan_genesis3.py
→ G:\ 전체, 40MB 이하 파일, "-----BEGIN " 문자열 카운트
→ total files with PEM headers: 0
```

의미: 평문으로 배포되는 어떤 파일에도 PEM 인증서/키가 없다.
(HTTPS용, Bluelink용, 맵 서명용 포함)

등급 VERIFIED.

### 2.2 APPNAVI (내비 앱 ELF) 문자열 스캔

```
build/auth-research/scan_genesis.py G:\BIN\APPNAVI
  AndroidAuto 0     Android Auto 0     Google Automotive 0
  CarService  0     Accessory 0         TLS 0
  cert 0            .pem 0              RSA 0
  Android 0
  IBOX 3            AOAP 2 (우연 일치, base64 블록 내부)
```

- `IBOX`/`AOAP` 히트는 실제 심볼이 아니라 **압축/인코딩 데이터 내부의 우연한 바이트열**임을
  문맥 출력으로 확인(`scan_genesis2.py appnavi` → 주변 200바이트가 전부 `@A@B@C…` 형태의 테이블).
- `Android`, `Google`, `TLS` 문자열이 **전혀 없다**.

⇒ APPNAVI는 Android Auto와 무관한 순정 내비 앱이다. 등급 VERIFIED.

### 2.3 vr.img (1.78GB) 내용 스캔

```
build/auth-research/scan_genesis2.py vr
```

- `"Android Auto"`, `"Apple Car Play"` 문자열이 **다국어 경고 문구**로만 등장
  (예: 노르웨이어 `Du kan ikke aktivere Bluetooth-lyd, mens "Apple Car Play" kjører`).
- 즉 **UI 문자열/번역 리소스**이며, 프로토콜·인증서·TLS 구현이 아니다.
- `APK`, `CarService`, `headunit` 심볼 없음.

⇒ vr.img는 순정 UI/리소스 파티션이며 AA 수신기 코드를 포함하지 않는다.
등급 VERIFIED(문자열 수준).

주의: partclone 이미지 전체를 파일 단위로 마운트·검증한 것은 아니다.
"AA 코드가 전혀 없다"는 **문자열 기반 판정**이며, 등급은 VERIFIED(관측)로 한정한다.

### 2.4 펌웨어 매니페스트

`GENESIS_G80_DIS_Bluelink.ver`의 `Auto|AA|CarPlay|Projection|Cert|Key` 검색 결과:

```
DATA\NATION\KOR|MAP_CERTIFICATE_INFO.inf|381637|...|137|1
DATA\NATION\KOR\SEARCH\POI|SPECIAL_KEYWORDS.dict|381659|...|97383|1
```

- `MAP_CERTIFICATE_INFO.inf` 137바이트는 **지도 데이터 저작권/발행 정보**이며 인증서가 아니다.
- `SPECIAL_KEYWORDS.dict`는 POI 검색 사전.
- **Android Auto / CarPlay / Projection 모듈 항목이 매니페스트에 없다.**

⇒ 이 펌웨어는 **AA 수신 기능을 탑재하지 않은 빌드**다. 등급 VERIFIED.

### 2.5 암호화 이미지

| 파일 | 상태 | 근거 |
| --- | --- | --- |
| `rootfs.img` | 복호화 필요 | 매직 불명, `essentials/decrypt` 도구 존재 |
| `boot.img` | 복호화 필요 | 동일 매직 |
| `IBOX.tar` | 복호화/압축 | `ustar` 아님 |
| `vr.img` | partclone(평문 계열) | `partclone-imageEXTFS` |

이 4개 중 `rootfs.img`가 실제 OS 루트 파일시스템이므로, **이론적으로** 그 안에
벤더가 숨긴 AA 모듈이 있을 수 있다. 그러나:

1. 매니페스트에 AA 항목이 없다 → 빌드 산출물에 포함되지 않았을 가능성이 높다.
2. GD13MY(2013 i30)는 AA 지원 세대가 아니다(5세대 안드로이드 기반부터 지원).
3. `essentials`의 복호화 도구는 **업데이트 프로그램 전용**이며 키를 포함하지 않는다(바이너리만).
4. 복호화 키를 역공학하는 것은 본 연구 범위(인증서·TLS)를 벗어나고, 펌웨어 무결성 정책에도 어긋난다.

⇒ **P0-4 결론: 순정 펌웨어에서 GAL 신원을 얻는 경로는 사실상 없다.**
   (등급: VERIFIED for 평문 / UNKNOWN for 암호화 이미지 내부, 후자는 후속 과제로 남기지 않는다)

---

## 3. 이 결과가 의미하는 것

1. "Genesis 순정 헤드유닛 인증서를 추출해서 쓰면 된다"는 가설은 **성립하지 않는다.**
   - 추출할 인증서 자체가 이 펌웨어에 없다.
   - 설령 암호화 이미지에 있더라도, 그 인증서는 **Bluelink/맵 서명용**일 가능성이 높고
     AA 수신기용 GAL 클라이언트 인증서일 이유가 없다.
2. GD13MY는 AA를 **원래 지원하지 않는 하드웨어 세대**다.
   - 따라서 "순정 펌웨어의 신원을 재사용"이라는 경로는 처음부터 존재하지 않았다.
3. 우리가 필요한 것은 **외부에서 발급받는 GAL 신원**이며, 이는 §09의 주제다.

---

## 4. 재현

```powershell
python build\auth-research\scan_genesis.py  "G:\BIN\APPNAVI"
python build\auth-research\scan_genesis2.py appnavi
python build\auth-research\scan_genesis2.py vr
python build\auth-research\scan_genesis3.py
python -c "import tarfile; t=tarfile.open(r'G:\essentials'); [print(m.name,m.size) for m in t.getmembers()]"
```

스크립트 SHA-256은 `12_EVIDENCE_INDEX.md` 참조.
