# 02_EXTRACTION_REPORT.md: 펌웨어 추출 및 컨테이너 분석 보고서

## 1. 추출 시도 내역 및 도구별 결과

| 대상 파일 | 시도 도구 | 명령 / 작업 | 결과 | 비고 |
|---|---|---|---|---|
| `G:\essentials` | 7-Zip (21.04) | `7z x essentials -o...` | **성공 (100%)** | POSIX tar 아카이브. `update.tar`, `decrypt/DecryptToFile`, `decrypt/DecryptToPIPE` 추출 완료 |
| `G:\AppUpgrade` | Git `file`, pyelftools | 바이너리 구조 검사 | **식별 성공** | ELF 32-bit x86 Linux 바이너리 (stripped). 업그레이드 총괄 프로세스 |
| `G:\HU\images\vr.img` | 7-Zip, python | `7z l vr.img` | 오류 (Headers Error) | Partclone EXTFS v0001 (Nuance Vocalizer 음성인식 데이터베이스, 1.78 GB) |
| `G:\IBOX.tar` | 7-Zip | `7z l IBOX.tar` | 실패 (Cannot open) | LGE 독자 암호화 컨테이너 ("TER" 푸터 적용, 402 MB) |
| `G:\HU\images\NP\rootfs.img` | 7-Zip, file | `file rootfs.img` | data | LGE 독자 암호화 컨테이너 ("TER" 푸터 적용, 2.56 GB) |
| `G:\HU\images\boot.img` | 7-Zip, file | `file boot.img` | data | LGE 독자 암호화 컨테이너 ("TER" 푸터 적용, 45.5 MB) |
| `extracted/essentials/update.tar` | 7-Zip | `7z l update.tar` | 실패 (Is not archive) | LGE 독자 암호화 컨테이너 ("TER" 푸터 적용, 14.5 MB) |
| `G:\BIN\*`, `G:\LIB\*` | Git `file`, pyelftools | 직접 분석 | **식별 성공** | 암호화되지 않은 ELF 실행 파일 및 공유 라이브러리 |

---

## 2. LGE 독자 패키지 ("TER" Envelope) 구조 역공학

`essentials/decrypt/DecryptToFile` 바이너리는 디버그 심볼(`DWARF`)이 완전히 보존된 상태로 배포되었으며, 이를 역공학하여 LGE 펌웨어 암호화 및 무결성 컨테이너 구조를 규명하였다.

### 2.1 파일 헤더 구조 (앞 128 KB = 0x20000 bytes)
- **난수화 인터리빙(Obfuscated Strides)**:
  - 오프셋 `0x00000`: 32비트 정수 `val0` 판독 후 `stride0 = (val0 % 0x78) + 4` 산출.
  - 오프셋 `0x10000`: 32비트 정수 `val1` 판독 후 `stride1 = (val1 % 0x73) + 4` 산출.
  - 두 개의 스트라이드 루프를 통해 헤더 전역에서 흩어진 바이트를 모아 512바이트(RSA-2048/4096 N, E)와 암호화된 세션 키 블록을 재구성한다.

### 2.2 파일 푸터 구조 (파일 끝에서 0x4024 = 16,420 bytes 위치)
`DecryptToFile`의 `LGUInitDecrypt` 함수 디컴파일을 통해 확인된 푸터 사양:
```
[Payload Data (Encrypted AES-128)]
---------------------------------------------------------------------
[Offset: FileSize - 0x4024]
  0x00 ~ 0x02 : 매직 바이트 "TER" (0x54 0x45 0x52)
  0x03        : 서브 매직 (0x53='S', 0xA7, 0x0E 등)
  0x04 ~ 0x23 : SHA-256 체크섬 (32 Bytes, 원본 페이로드 무결성 검증값)
  0x24 ~ 0x2023 : 검증 블록 1 (0x2000 Bytes)
  0x2024 ~ 0x4023: 검증 블록 2 (0x2000 Bytes)
---------------------------------------------------------------------
[EOF]
```

### 2.3 암호화 및 키 관리 메커니즘
1. **무결성 검사 (`LGUInitDecrypt`)**:
   - 푸터 오프셋 `0x00`의 "TER" 매직 확인.
   - 오프셋 `0x24`부터의 0x4000 바이트에 대해 `mbedtls_sha256` 연산을 수행하여 오프셋 `0x04`의 32바이트 해시와 일치하는지 비교.
2. **세션 키 복구 (`LGUGetKeyData`)**:
   - 128KB 헤더에서 재구성된 공개키 파라미터(N, E)를 `mbedtls_mpi_read_string`으로 파싱.
   - `mbedtls_rsa_pkcs1_decrypt`를 `MBEDTLS_RSA_PUBLIC (0)` 모드로 호출.
   - LGE 배포 서버에서 개인키로 서명/암호화한 128비트 AES 대칭키(`g_szKey`)를 헤더 공개키를 통해 복구.
3. **페이로드 복호화 (`LGUDecryptForFile` / `LGUDecryptData`)**:
   - 복구된 128비트 대칭키로 AES-128-CBC 페이로드를 복호화하여 출력 파일 생성.

---

## 3. 원본 보호 및 역공학 윤리 준수 기록

- **G 드라이브 원본 보존**: G 드라이브의 원본 파일(15.2 GB)은 1바이트도 수정, 덮어쓰기, 삭제하지 않고 읽기 전용(`ReadOnly`)으로 접근하였다.
- **추출 격리 원칙**: 필요한 도구 및 실행 파일(`essentials`)만 영구 작업 드라이브 `F:\i30-gen2-android-auto\research\genesis-premium-gen2\`로 안전하게 추출하였다.
- **비인가 키 유출 방지**: 불필요한 전체 덤프나 비공개 차량 비밀값 추출을 수행하지 않았으며, 공개 매니페스트 및 공용 검증 메커니즘만 기술적으로 기록하였다.
- **도구 실행 투명성**: 실제 성공한 7-Zip 및 Python 정적 파싱만 "성공"으로 기록하고, 지원하지 않는 도구의 실행 결과는 실패 원인과 함께 명시하였다.
