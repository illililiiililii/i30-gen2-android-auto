# 06 — 대체 순정 AA 펌웨어 후보

작성: 2026-11-25 · 등급: **PARTIAL** (문서 기반, 직접 추출은 미수행)
전제: Genesis 펌웨어에는 평문 헤드유닛 인증서가 없다 (01 문서).
목적: 실제 양산 헤드유닛의 인증서+키를 얻을 수 있는 **공개 펌웨어** 후보를 선정한다.

출처: `mrmees/open-android-auto`의 `docs/decompiled_headunit_firmware/*`
(<https://github.com/mrmees/open-android-auto/tree/main/docs/decompiled_headunit_firmware>)

---

## 1. 후보 비교

| 후보 | 펌웨어 / 다운로드 | 크기 | 플랫폼 | 추출 가능성 | AA 스택 | 판정 |
| --- | --- | --- | --- | --- | --- | --- |
| **Sony XAV-AX100** | `XAV-AX100_v10209.zip` (2018) | - | Sunplus SPHE8388, ARM Cortex-A9, Linux 3.4.5 + eCos | **높음** — AES-128-CBC 키가 Sony 공개 GPL U-Boot 소스에 있음 | Google AAP Receiver Library, OpenSSL 1.0.2h, Qt 5.3/DirectFB | **1순위** |
| **Kenwood DNX/DDX** | `S_V1_5_0009_8000.zip` (2025-09) | `.nfu` 내 `approm_20dnx_ab_vga_hdr.ext4` 490 MB | Telechips TCC8971, Cortex-A7, Yocto Linux | **높음** — ext4 이미지, 마운트 가능 | `libreceiver-lib.so` 5.3 MB, OpenSSL full, protobuf full | **1순위** |
| Pioneer DMH-WT8600NEX | `DMH-WT8600NEX.zip` v2.08.03 | - | KM955 | **낮음** — `.avh`, 하드웨어 내장 키 AES, ECB/키스트림 약점 없음 | - | 제외 |
| Alpine Halo9 iLX-F509/F511 | `Update.zip` v6.0.000 (1.13 GB) | 1.13 GB | Telechips TCC8034, Neusoft NAGIVI Linux | **낮음** — 내부 AES 키가 기기 `/usr/bin/updatemgr`에 있음, 물리 접근 필요 | `aoa_con_server_proc` | 제외 |
| Alpine iLX-W650BT | `Alpine_SYSTEM.FIR` v1.001_0802 (2019) | - | Toshiba TMM9200, bare-metal RTOS | **중간** — strings만, FS 없음 | Google "tamul" AAP SDK 1.4.1, MatrixSSL 3.9.5 | 보류 |
| Hyundai/Kia Gen5/Gen5W | `update.hyundai.com` 공개 업데이트 | 수 GB | - | **낮음** — Genesis와 같은 암호화 컨테이너 | - | 제외 |

---

## 2. 1순위 상세

### 2.1 Sony XAV-AX100

- **선정 이유**: 펌웨어 복호화 키가 **Sony가 공개한 GPL U-Boot 소스**에 문서화되어 있다.
  `mrmees` 문서: "firmware decryption using keys derived from GPL-licensed U-Boot source
  code published by Sony, followed by strings analysis and filesystem extraction."
- 복호화 후 **완전한 AA 구현**(AAP Receiver Library + OpenSSL 1.0.2h)이 나온다.
- 헤드유닛 인증서+키는 AAP Receiver Library가 로드하는 리소스에 있을 가능성이 높다.
- 추가 후보: XAV-9500ES v3.02.00 (`.eup`, encrypted RAUC), XAV-AX5500 v2.00 (`.FIR`).

### 2.2 Kenwood DNX/DDX

- **선정 이유**: `.nfu` 안의 `approm_...ext4`(490 MB)가 **마운트 가능한 ext4**다.
  암호화 컨테이너를 풀 필요가 없다.
- `libreceiver-lib.so`(5.3 MB)가 Google AAP Receiver Library이며, OpenSSL full을 쓴다.
- 인증서는 `libreceiver-lib.so`에 임베드되었거나 `/etc`/`/data` 리소스에 있을 가능성이 높다.
- 최신 빌드(2025-09)이므로 인증서가 최신일 가능성이 있다.

---

## 3. 왜 이 후보들인가

- **평문/복호화 가능**: Sony는 GPL 키, Kenwood는 ext4. 둘 다 비밀 키 없이 접근 가능.
- **실제 양산 AA**: 두 제품 모두 Google AAP Receiver Library를 사용하는 정식 AA 헤드유닛이다.
- **인증서 존재 가능성**: AAP Receiver Library는 TLS 클라이언트 신원을 필요로 하므로,
  해당 라이브러리 또는 그 리소스에 cert+key가 있어야 한다.
- **법적/윤리적**: 공개 펌웨어 업데이트 파일을 분석하는 것은 기존 연구 관행이며,
  원본 펌웨어를 수정하지 않는다.

---

## 4. 그러나 — 우선순위는 낮다

이미 **`Google-Android-Reference` (DHU 유래, GAL 발급, `Z` 시간)** 쌍을 확보했고,
현재 펌웨어가 수정 없이 로드한다 (03/04 문서). 따라서:

1. **먼저** `Google-Android-Reference`로 라이브 시험을 한다.
2. 그것이 폰에서 거부될 경우에만 Sony/Kenwood 펌웨어에서 **다른 GAL 발급 쌍**을 추출한다.
3. 추출한 쌍도 `-0700`이면 03 문서의 파서 수정이 필요하다.

---

## 5. 판정

| 주장 | 등급 |
| --- | --- |
| Sony XAV-AX100 펌웨어가 GPL 키로 복호화 가능 | **PARTIAL** (mrmees 문서 기준) |
| Kenwood DNX app ROM이 ext4로 마운트 가능 | **PARTIAL** (mrmees 문서 기준) |
| 두 펌웨어에 헤드유닛 cert+key가 있다 | **HYPOTHESIS** |
| Pioneer/Alpine Halo9는 키 없이 복호화 불가 | **PARTIAL** (mrmees 문서 기준) |
| Genesis/Gen5W는 평문 인증서 없음 | **VERIFIED** (Genesis) / **HYPOTHESIS** (Gen5W) |

---

## 6. 후속 작업

- Sony XAV-AX100: GPL U-Boot 소스에서 AES 키/IV를 찾아 `XAV-AX100_v10209.zip` 복호화,
  `libreceiver` 리소스에서 cert+key 추출.
- Kenwood DNX: `S_V1_5_0009_8000.zip` → `.nfu` → `approm_*.ext4` 마운트,
  `libreceiver-lib.so` 및 `/etc`에서 cert+key 추출.
- 추출한 cert는 `scripts/check_hu_identity.py`로 GAL root 체인·키 일치·시간 인코딩을 검증.
