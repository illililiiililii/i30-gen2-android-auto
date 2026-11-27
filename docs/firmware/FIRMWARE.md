# 펌웨어 구조

2026-11-20에 `F:\`의 업데이트 파일 44개와 프로젝트 내 분석본을 SHA-256으로 대조했다. 파일별 이름, 확장자, 크기, UTC 수정 시각, SHA-256을 [inventory.csv](../research/evidence/inventory.csv)에 기록했다. 분석 대상은 주로 `GD13MY`이며, 지도는 세 모델이 공유한다.

| 패키지 | 소프트웨어 | 내부 식별자 |
|---|---|---|
| GD | `GD.KOR.SOP.00.071` | `GD.KOR.SOP.001.250304` |
| GD13MY | `GD13MY.KOR.SOP.00.061` | `GD13MY.KOR.SOP.001.250304` |
| GD14MY | `GD14MY.KOR.SOP.00.053` | `GD14MY.KOR.SOP.001.250304` |

`i30_2013.ver` 1행은 `HM`, `i30_2013`, `GD13MY.KOR.SOP.00.061`을 포함한다. `GD13MY/model.bin`의 처음 두 행과 APP 첫 멤버의 동일한 데이터에서 버전을 재확인했다. APP의 `systemCfg.xml`은 `GD`, `KOR`, `HMC`, `GEN 2.0`을 명시한다. 현대자동차 공식 홈페이지도 이 버전을 i30 2013 표준형 2세대로 분류하며 지도 버전 `KOR.18.42.62`를 표시한다. 탈거 기기에 설치된 버전과 부품 번호는 미확인이다. [현대자동차 소프트웨어 목록](https://update.hyundai.com/KR/KO/updateNoticeView/GVgVE4)

| 구성 | 실제 파일과 관찰 결과 |
|---|---|
| APP | `GD13MY/APP.spd.000` 23,456,390 B. zlib 스트림 122개를 헤더와 대조해 파일 119개 복원. `0x0` 모델 정보, `0x15465` 설정, `0x1565b` `uComH_New.exe`, `0x315905` `LibUSB.dll`. 큰 GCF 리소스 2개는 여러 스트림을 이어 붙여 복원했다. |
| BSP | `GD13MY/BSP.spd.000` 13,246,777 B. `0x0` `raw` 393,216 B, `0x109a5` `logo` 768,072 B, `0x2dfc7` `kernel` 21,599,691 B. `GD`와 `GD13MY` BSP의 SHA-256은 동일하다. `GD14MY` BSP는 다르다. |
| MICOM | `GD13MY/MICOM.spd.000` 138,993 B. zlib 한 개를 풀면 1 MiB MCU 이미지가 나온다. 세 모델의 MICOM 데이터가 다르다. MCU 보드 모델과 실제 장치의 칩은 미확인이다. |
| ACC | `ACC.spd.000` 0 B. `ACC.hdr`의 UTF-16LE `/DiskA3` 및 `/DiskA3/TPEG_CH` 엔트리가 있다. |
| 공통 지도 | `COMMON/MAP.hdr` 75,008 B, `MAP.spd.000–002` 2,527,564,100 B. 헤더 `0x130`에 `/DiskA2`, `0x150`에 `/DiskA2/ASR_DB`. zlib 조각 996개를 스트리밍으로 풀어 길이·볼륨·오프셋·MD5를 모두 헤더와 대조했다. |
| 복구 및 업데이트 | `install.exe` 및 `AVNRecovery.exe`는 ARM Thumb Windows CE PE32. 각각 PE 시그니처가 파일 `0x108`, `0xd8`에 있고 COFF Machine은 `0x1c2`, Subsystem은 9다. |

## 형식과 무결성

- `.hdr` 시작에 `HACO STDAVN UPGRADE IMAGE`가 있다. `0x24`의 little-endian 32비트 길이가 헤더 크기와 일치한다. `0x28–0x37`은 `0x38` 이후 바이트의 MD5와 일치한다.
- APP·BSP·MICOM의 모든 126개 zlib 스트림을 복호화 없이 풀었다. 각 조각의 MD5 및 경계를 헤더와 비교했다. 헤더는 이름과 볼륨 번호·압축 오프셋·압축 전후 길이를 저장한다. 패키지 전체를 암호화한 흔적은 이 세 볼륨에서 발견되지 않았다. 내부 일부 리소스의 별도 보호 여부는 미확인이다.
- 루트 `install.md5` 16바이트는 `install.exe`의 MD5 `bfc1bc95fa72ff12d47f94b4faa1bf02`와 일치한다. 두 루트 PE의 인증서 테이블 값은 모두 0이다. `.ver`에 나열된 43개 파일의 크기와 CRC32가 모두 일치했다. 지도 3개 볼륨도 압축 파일의 32 MiB 블록 기준으로 `install.crc`의 76개 CRC32와 모두 일치했다. 각 볼륨은 zlib 헤더로 시작한다. 기기의 공개키 기반 검증, 보안 부팅 및 사용자 코드 허용 여부는 미확인이다.
- BSP `raw` `0x14`의 `CHSETTINGS`, `0x13a4`의 TI iNAND X-Loader 및 `0x216ec`의 Hyundai Autonet EBOOT 문자열에서 두 부트 단계의 코드를 확인했다. 실물 플래시 배치와 부트 설정은 미확인이다. `kernel`은 `B000FF\n`으로 시작하는 Windows CE BIN이고 160개 레코드의 바이트 합 체크섬을 검증했다. ROMHDR은 `0x149758b`, 주소 `0x854f47ec`에 있다. `nk.exe`, `kernel.dll`, `coredll.dll`, `udevice.exe`, `boot.hv`, `default.hv`, `user.hv`를 ROM 목차에서 확인했다.
- `APP.hdr` 및 `install.ini`에서 `/DiskA`의 앱, `/DiskA2`의 지도, `/DiskA3`의 설정 및 사용자 데이터가 확인된다. `install.ini`는 `partitioning=0`을 명시한다. ROM에는 `exfat.dll`, `mspart.dll`, `sdmemory.dll`이 있다. 현재 제공된 패키지는 실물 매체의 파티션 덤프를 포함하지 않으므로 물리 매체 종류, 파일시스템, 섹터 경계는 미확인이다.

[조각별 파일 오프셋과 해시](../research/evidence/gd13my-streams.json) · [지도 볼륨 검증](../research/evidence/map-streams.json) · [매니페스트 검증](../research/evidence/manifest-checks.json) · [ROMHDR과 ROM 목차](../research/evidence/ce-rom.json) · [Microsoft PE 헤더 명세](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)
