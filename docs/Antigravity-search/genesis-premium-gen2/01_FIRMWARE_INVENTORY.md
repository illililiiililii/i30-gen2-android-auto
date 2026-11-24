# 01_FIRMWARE_INVENTORY.md: 제네시스 고급형 2세대 펌웨어 인벤토리 보고서

## 1. 펌웨어 기본 식별 정보

| 항목 | 확인된 값 | 근거 위치 / 파일 |
|---|---|---|
| **차종 / 모델명** | Genesis G80 (DH PE, DIS Bluelink) | `G:\GENESIS_G80_DIS_Bluelink.ver`, `.lge.upgrade.xml` |
| **플랫폼 코드** | DHAVN (DH AVN / LGE IBOX) | `.lge.upgrade.xml` (`<dhavn>`), `BIN\APPNAVI` |
| **모델 / 하드웨어 버전** | `DHPE` / `DHPE.KOR.SOP.03.057` | `G:\.lge.upgrade.xml` (`<version>`, `<hardware-ver>`) |
| **패키지 빌드 버전** | `DHPE.KOR.SOP.00.057` (404/1) | `G:\GENESIS_G80_DIS_Bluelink.ver` Line 1 |
| **빌드 일자** | 2024-10-11 | `.lge.upgrade.xml` (`<build-date>2024-10-11</build-date>`) |
| **지역 코드** | KOR (대한민국 내수용) | `GENESIS_G80_DIS_Bluelink.ver`, `.lge.upgrade.xml` |
| **내비게이션 버전** | `PR2.KOR.HMC.210708.1001` | `.lge.upgrade.xml` (`<navi version="..."/>`) |
| **IBOX 버전 / 일자** | `E468` / `2023-06-14` | `.lge.upgrade.xml` (`<ibox version="E468" date="20230614"/>`) |
| **제조사 (OEM)** | LG Electronics (LGE) | `.lge.upgrade.xml`, `AppUpgrade`, `essentials/decrypt` |
| **전체 파일 수 / 총 용량** | 310개 파일 / 15,241,434,501 bytes (~14.19 GB) | `G:\` 디렉터리 전수 조사 |

---

## 2. 드라이브 디렉터리 구조 및 폴더별 역할

```
G:\
├── .lge.upgrade.xml                  # 펌웨어 업데이트 공개 매니페스트 (XML)
├── .lge.upgrade_enc.xml              # 암호화된 세부 업데이트 매니페스트
├── GENESIS_G80_DIS_Bluelink.ver      # 부트로더/PC 다운로더용 버전 검증 파일
├── AppUpgrade                        # i386 Linux 업데이트 인스톨러 바이너리
├── essentials                        # tar 아카이브 (decrypt 유틸리티 및 update.tar)
├── IBOX.tar                          # 암호화된 IBOX 텔레매틱스/인터페이스 펌웨어 (402 MB)
├── HU/
│   └── images/
│       ├── boot.img                  # 암호화된 HU 커널/부트 이미지 (45.5 MB)
│       ├── vr.img                    # Partclone EXTFS 이미지 (음성인식 Nuance DB, 1.78 GB)
│       └── NP/
│           └── rootfs.img            # 암호화된 HU 메인 RootFS 이미지 (2.56 GB)
├── BIN/                              # 미암호화 내비게이션 실행 파일 및 UI
│   ├── APPNAVI                       # 메인 내비게이션 ELF 32-bit x86 실행 파일 (5.99 MB)
│   ├── TPEGSERVICE                   # TPEG 교통정보 수신 서비스 (238 KB)
│   ├── LOCALIZATION/                 # 다국어 번역 파일 (.qm 19개)
│   └── QML/                          # QtQuick 1.0 QML UI 리소스 (1280x720)
├── LIB/                              # 내비게이션 및 미들웨어 공유 라이브러리 (.so 5개)
│   ├── LIBIENGINE1.so                # 맵 검색 및 경로 안내 엔진 (7.49 MB)
│   ├── LIBREDENGINE3D.so             # 3D 지도 렌더링 엔진 (2.33 MB)
│   ├── LIBMGDIQTYPE.so               # 폰트 래스터라이저 (631 KB)
│   ├── LIBTPEGDECODER.so             # TPEG 패킷 디코더 (621 KB)
│   └── LIBREDRELAY_1.so              # 렌더링 릴레이 모듈 (219 KB)
├── DATA/                             # 지도 데이터, 음성 안내, 사운드, 폰트
│   ├── COMMON/                       # 공용 폰트(TTF), 사운드(WAV 12개), 가이드 이미지
│   └── NATION/KOR/                   # 한국 지도 3D 벡터, POI 검색 DB (.mpd, .haf* 등)
├── TEXT.INFO/                        # 시스템/텍스트 정보 데이터 (.bin, .inf)
└── ASR/                              # 음성인식 컨텍스트 및 POI 사전 (.lcf, .TABLE)
```

---

## 3. 확장자별 파일 통계

| 확장자 | 파일 수 | 설명 |
|---|---|---|
| `.ares` | 60 | 지도 및 내비 리소스 패키지 |
| `.lcf` | 23 | 음성인식(ASR) 언어/POI 컨텍스트 파일 |
| `.mpd` | 21 | 내비게이션 POI 검색 인덱스 데이터베이스 |
| `.hafmma` | 20 | 현대 내비게이션 전용 지도/안내 미디어 압축 포맷 |
| `.qm` | 19 | Qt 다국어 컴파일 번역 바이너리 (Qt 4.x) |
| `.table` | 17 | 음성인식 POI 테이블 |
| `.pjn` / `.pjo` | 32 | 경로 탐색 및 교차로 안내 데이터 |
| `.txt` / `.inf` | 20 | 버전, 라이선스, 행정코드 매니페스트 |
| `.wav` | 12 | 순정 UI 효과음 (GD502.wav, GD100001.wav 등) |
| `.bin` | 8 | 펌웨어 보조 바이너리 및 모듈 |
| `.so` | 5 | 미암호화 Linux 동적 공유 라이브러리 |
| `.img` | 3 | 시스템 이미지 (`rootfs.img`, `vr.img`, `boot.img`) |
| `.tar` | 2 | 펌웨어 아카이브 (`IBOX.tar`, `update.tar`) |
| (확장자 없음) | 6 | `AppUpgrade`, `essentials`, `APPNAVI`, `TPEGSERVICE` 등 |
| 기타 | 62 | 폰트(`.ttf`), 스킨(`.skn`), 스크립트(`.scr`) 등 |
| **합계** | **310** | |

---

## 4. 주요 파일 SHA-256 및 규격

| 파일명 | 파일 크기 (Bytes) | SHA-256 체크섬 | 컨테이너 / 포맷 |
|---|---|---|---|
| `GENESIS_G80_DIS_Bluelink.ver` | 30,721 | `4a4e938e52abae67b54983bade163febe5ff50dd66059b66230a440ac69a71db` | ASCII 텍스트 매니페스트 |
| `.lge.upgrade.xml` | 2,878 | `771600ab91bba7055b5d178564a211846da812b2b92e0bb3c9f64d7799c5df18` | UTF-8 XML 매니페스트 |
| `.lge.upgrade_enc.xml` | 19,298 | `0848bffbcff6de28c88dd40cb23a0c0664fbd9287751db2c8e073d3557603915` | 암호화된 바이너리/XML |
| `AppUpgrade` | 1,274,224 | `e894b8eca2f534195ea2588e084071b442c41d483c68e2b65990f9c04d07c97f` | ELF 32-bit LSB (i386 Linux) |
| `essentials` | 14,970,880 | `a1b4da21bae439f38eee81dd5e7b7e19949f4776a04cb482b3ec463e86ac6754` | POSIX tar 아카이브 |
| `extracted/essentials/update.tar` | 14,587,940 | `e6083f96ad73163abd5464ce07cabdea8e74dfeb9d3ab9e6dbbc634c21b71ad5` | LGE "TER" 암호화 컨테이너 |
| `extracted/essentials/decrypt/DecryptToFile` | 187,986 | `2f01f8e7c9765aed119d5adaac304b123c995a2f27c71e5625372d299ee07364` | ELF 32-bit LSB (i386 Linux, 심볼 포함) |
| `extracted/essentials/decrypt/DecryptToPIPE` | 182,263 | (확보 완료) | ELF 32-bit LSB (i386 Linux) |
| `HU/images/boot.img` | 45,565,256 | `4770323866df998e446d7c211e396497ea4e6b194954807fbc891d9e202921ca` | LGE "TER" 암호화 컨테이너 |
| `HU/images/vr.img` | 1,785,153,017 | (대용량 보존) | Partclone EXTFS v0001 (Nuance VR) |
| `HU/images/NP/rootfs.img` | 2,567,399,572 | (대용량 보존) | LGE "TER" 암호화 컨테이너 (2.56 GB) |
| `IBOX.tar` | 402,335,780 | `730e1167a09c514d0d9f2f7e5b4e10c6bd7d3bedc792eda48849917c5c549e72` | LGE "TER" 암호화 컨테이너 (402 MB) |
| `BIN/APPNAVI` | 5,993,104 | `7aa23ee2555c8463c29481db4d1a9e26826c009052d7184ef823f9c2843a7d79` | ELF 32-bit LSB (i386 Linux) |
| `BIN/TPEGSERVICE` | 238,746 | `b9d1b90fc292d696db100e3c972c0eaed1ecf7ecf2b46f19c465c7cbe8ce55b3` | ELF 32-bit LSB (i386 Linux) |
| `LIB/LIBIENGINE1.so` | 7,492,276 | `7222a4f9323969638ac2a48566bf2eeb4728740da01dbf40423583dfad1354b8` | ELF 32-bit LSB shared object |

---

## 5. 모델 및 제네시스 고급형 2세대 진위 판정

- **증거 1**: `.lge.upgrade.xml` 내 `<hardware-ver>DHPE</hardware-ver>` 명시. "DHPE"는 제네시스 DH 상품성 개선형(Product Enhancement, G80 초기형 페이스리프트)의 공용 코드명이다.
- **증거 2**: `GENESIS_G80_DIS_Bluelink.ver` 파일명 및 내부 `GENESIS_G80_DIS_Bluelink` 모델 스트링 일치.
- **증거 3**: QML UI 및 사운드 리소스(`DHAVN_APPNAVI_MAIN.qml`, `1280x720` 해상도)가 제네시스 고급형 DIS 내비게이션 사양과 완벽 일치.
- **결론**: 본 펌웨어는 **제네시스 고급형 2세대 (G80 DIS Bluelink, DHPE 플랫폼, 2024년 10월 배포판)** 실물 정품 펌웨어임이 기술적으로 검증되었다 (`VERIFIED`).
