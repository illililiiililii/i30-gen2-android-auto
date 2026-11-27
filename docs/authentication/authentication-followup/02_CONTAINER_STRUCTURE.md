# 02 — IBOX / rootfs 컨테이너 구조

작성: 2026-11-25 · 등급: **VERIFIED** (구조), **UNKNOWN** (내용)
원칙: 실패한 복호화 시도는 반복하지 않는다. 구조와 공식 도구만 기록한다.

---

## 1. 인벤토리

| 경로 | 크기 (B) | 성격 |
| --- | --- | --- |
| `G:\HU\images\boot.img` | 45,565,256 | 암호화 이미지 |
| `G:\HU\images\NP\rootfs.img` | 2,567,399,572 | 암호화 이미지 |
| `G:\HU\images\vr.img` | 1,785,153,017 | `partclone-imageEXTFS` (비암호화 FS 이미지) |
| `G:\IBOX.tar` | 402,335,780 | 이름과 달리 tar 아님, 암호화 컨테이너 |
| `G:\essentials` | 14,970,880 | tar: `update.tar` + `decrypt/DecryptToFile` + `decrypt/DecryptToPIPE` |

> 이전 보고서의 `G:\HU\images\rootfs.img` 경로는 존재하지 않는다.
> 실제 경로는 **`G:\HU\images\NP\rootfs.img`** 이다.

---

## 2. 헤더

```
boot.img   : 53807d50ea2f7b129833bbc9941aa626 8e63888e9aa5007866616e83899bc8d4 ...
rootfs.img : 53807d50ea2f7b129833bbc9941aa626 8e63888e9aa5007866616e83899bc8d4 ...
IBOX.tar   : 0dce4666c61b3b7cfd1ed2a4f57dc363 d637cedd9aa5007866616e83899bf8e4 ...
```

- `boot.img`와 `rootfs.img`는 **16바이트 magic이 완전히 동일**하다.
- `IBOX.tar`는 첫 16바이트만 다르고, 그 뒤 구조는 같은 계열이다.
- 세 파일 모두 첫 4 MB 엔트로피 **8.000** → 암호화 또는 압축.

`vr.img`:

```
70617274636c6f6e652d696d6167654558544653  "partclone-imageEXTFS"
```

비암호화 파일시스템 이미지다. `fsck`/`debugfs`/`partclone` 계열로 마운트할 수 있으나,
AA 인증서는 없다 (01 문서).

---

## 3. 새 발견 — 결정적 키스트림 재사용

`IBOX.tar`와 `boot.img`를 같은 오프에서 비교했다.

```
비교 구간            8,388,608 B
동일 바이트          307,287 (3.663%)   ← 무작위 기대값 0.391%
동일 16B 블록        12,913 / 524,288 (2.463%)
최장 동일 연속 구간  7,938 B at offset 20,799
```

7,938바이트 연속 동일 암호문은 우연이 아니다. 또한:

- 16바이트 블록 주기성 없음 (`shared_run_period = None`)
- 각 파일의 16B 블록은 모두 고유 (ECB의 반복 블록 없음)
- XOR 스트림 엔트로피 6.45 (구조적 편향)

### 해석 (HYPOTHESIS, 강한 정황)

- **고정 키 + 고정 IV/논스의 스트림 암호**(AES-CTR/OFB 계열)이거나,
- **고정 키 AES-ECB**에서 두 파일의 평문이 같은 구간을 공유하는 경우.

어느 쪽이든 **파일별 랜덤 IV가 없다**. 즉 암호화가 결정적(deterministic)이다.
이것은 컨테이너 설계의 암호학적 약점이지만, **알려진 평문이 없으면 즉시 복호화로
이어지지 않는다.** 이번 세션은 복호화를 시도하지 않는다.

### 왜 중요한가

- `boot.img`/`rootfs.img`가 같은 키스트림을 쓰므로, 한쪽의 평문을 확보하면
  다른 쪽의 같은 오프 구간을 XOR로 복원할 수 있다.
- `essentials/decrypt/DecryptToFile`이 공식 복호화 도구이므로, 평문 확보 경로는
  "도구 + 올바른 키"이다.
- 그러나 03/04 문서의 신원 경로가 확보되어 **이 컨테이너를 열 필요가 없어졌다.**

---

## 4. 공식 추출 도구

`G:\essentials`는 tar이며 다음을 포함한다.

```
update.tar
./decrypt/DecryptToFile
./decrypt/DecryptToPIPE
```

이전 Antigravity 분석에서 확인된 함수:

- `LGUInitDecrypt`
- `LGUGetKeyData`
- `mbedtls_rsa_pkcs1_decrypt` (`0x08049c90`)
- `mbedtls_rsa_rsaes_pkcs1_v15_decrypt` (`0x080484b0`)

즉 복호화는 **RSA PKCS#1 v1.5**로 키를 푸는 구조다. 키는 기기/라이선스에 묶여 있을
가능성이 높고, `essentials` 자체에는 평문 키가 없다 (01 문서: `rsaEncryption` OID 0건).

---

## 5. 판정

| 주장 | 등급 |
| --- | --- |
| `boot.img`/`rootfs.img`는 동일 magic의 암호화 컨테이너 | **VERIFIED** |
| `IBOX.tar`는 tar가 아니며 같은 계열 컨테이너 | **VERIFIED** |
| `vr.img`는 `partclone-imageEXTFS` | **VERIFIED** |
| 컨테이너 암호화는 결정적(고정 IV/키스트림 재사용) | **VERIFIED (통계)** / 원인 **HYPOTHESIS** |
| 컨테이너 내부에 AA 인증서가 없다 | **UNKNOWN** |
| 컨테이너를 키 없이 복호화할 수 있다 | **FAILED / 근거 없음** |

---

## 6. 재현

```powershell
python build\auth-followup\container_probe.py
python build\auth-followup\keystream_probe.py
python build\auth-followup\block_probe.py
python build\auth-followup\rootfs_probe.py
```

스크립트는 `scripts/`에도 복사되어 있다.
