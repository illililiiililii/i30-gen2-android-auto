# 12. 증거 색인 · 재현 · 판정 원장

작성: 2026-11-25 · 이 문서의 SHA-256은 모두 `Get-FileHash -Algorithm SHA256`(PowerShell) 기준

## 1. 인증서·키 자료

| 파일 | 크기 | SHA-256 | 출처 |
| --- | --- | --- | --- |
| `build/auth-research/certs/gal-root.pem` | 1,284 | `a611c0db298d8471b1f7254be8041faf1a29e64daa6eec25d2cfa00b32be4eb2` | `iscle/android-auto-certificates` |
| `build/auth-research/certs/phone-leaf.pem` | 1,248 | `0e70ee1cd9d7b935db5e154bd3b51809d28f99276ad3a5963c04cbca046433b5` | 동일 (AA 18.0.664264-release) |
| `build/auth-research/certs/phone-chain.pem` | 2,806 | `364a2d8afb37c8851a821102dae0c2d611466ded5cba0e7c514aa1d9f2d60196` | 동일 |
| `build/auth-research/certs/android-auto__18.0.664264-release__certificate.pem` | 2,534 | `43c05285265d83a9e1ae74da7359f07c081c711354a2c397292419169d8c360f` | 동일 |
| `build/auth-research/certs/android-auto__latest__certificate.pem` | 2,534 | `43c05285265d83a9e1ae74da7359f07c081c711354a2c397292419169d8c360f` | 동일 (바이트 동일) |
| `build/auth-research/certs/android-auto__18.0.664264-release__metadata.json` | 909 | `c13ebe9231c2229c4810401f063a2165311d7c6180deb2abc003ac087b365622` | 동일 |
| `build/auth-research/certs/dhu__2.1__certificate.pem` | 1,188 | `9c5a28e2c9bf29572f398f717c1f9731b515886de26b448b5ebf3fb063d21f2d` | 동일 |
| `build/auth-research/certs/dhu21.der` | 835 | `4eb581dcee2b84369ca87066ab6eaa73a4783aef5c7b6edc6841e066cffa7e7c` | PEM에서 변환 |
| `build/auth-research/certs/dhu__2.1__metadata.json` | 428 | `2e421dff8760e9c78ce883f72ad1492b16f53c9b8f8e0101cc3229fc8ae73540` | 동일 |
| `build/auth-research/certs/aasdk-embedded.pem` | 1,159 | `85b5043a09b1ba9464f745e6917bdbaa2bc582fe48cb727a7787c1a832a773e4` | `opencardev/aasdk` `Cryptor.cpp` |

지문:
```
GAL root      49:E5:2E:FC:13:AD:2E:D0:9F:20:4C:3B:10:69:8B:D8:4B:B7:10:5F:51:05:58:AA:14:B8:11:9A:5C:4A:D1:7F
phone leaf    46:D9:07:A7:...:54:D2:7C
DHU 2.1       4E:B5:81:DC:...:CF:FA:7E:7C
AASDK JVC     1C:0E:0E:F9:E6:72:DD:1A:63:AB:4D:61:AF:AA:89:96:A5:7C:A7:AA:96:6D:19:22:B9:7D:8F:93:85:EA:3C:35
```

---

## 2. 실측 로그

| 파일 | 크기 | SHA-256 | 내용 |
| --- | --- | --- | --- |
| `build/gd13my-native-oem-screen/live-phone-usb-trust-android.log` | 1,222 | `84e58e5d8f6d83f4684da634dff7c02f63abfab8c14f8f828f3690d513d080aa` | **결정적 폰 예외** |
| `build/gd13my-native-oem-screen/live-phone-aoa-auth-stage.json` | 403 | `29be20b664c1df5b18ab2fb8420fefdd0f7fdad5948c65e0528a2a5bb95a46db` | 서버 flight `[2,11,12,13,14]` |
| `build/gd13my-ce-projection/phone-tls-public.json` | 955 | `e11ef1872cd87ce60a4e4408db8622d6ea51271e0f11b11a8010b7084f01a325` | 폰 체인 메타데이터 |
| `build/gd13my-native-oem-screen/live-phone-usb-trust-root-cause.log` | 184 | `8879333943b2cbd61716b262160d196c69ccd93be7fe6658a0cdeb28016b4450` | 1230 B flight, USB 타임아웃 |
| `build/gd13my-native-oem-screen/live-phone-native-identity-fresh.log` | 172 | `aa30b7c3f45f83f4b05fac299124ea55a714994f90b58a138ed7077aed190373` | 개발자 터널 거부 |
| `build/gd13my-native-oem-screen/live-phone-trust-root-cause.log` | 131 | `b2eb6478f2e91dc4a3ee1e8503a74d76abb5b4baea64d6ec3a9cb0c7ab54da08` | 터널 체인 미수신 |
| `build/gd13my-aa-error07/dhu-20261123-222431/stderr.log` | 607 | `3f75f3701f450e4b16619ac39726f4c849abbb16689459d64e1fc97085f8c4f1` | **DHU 정상 기준선** |
| `build/gd13my-ce-tls-diagnostics/early-startup/arm-projection.log` | 10,612 | `40bf26be9b43effc2f32b89814cf42b1b59509486e169116ad0aa8d6cd626bed` | 의도적 alert 70 시험 |
| `build/gd13my-aa-error07/arm-usb-tls.json` | 12,176 | `43b1a4eef6d9c46f4f3fdaefc1e58fd3e5d44f754650657a2c0eac72d0953380` | ARM TLS 시험 |
| `build/gd13my-aa-error07/arm-usb-tls-dhu-cipher.json` | 12,233 | `25dc81980d2c2d843ccd304673c33b4db1d6bac5922943a87a1398b09dd8d14c` | `0xC02F` 일치 |
| `build/gd13my-phase78/boot-projection-untrusted.projection.jsonl` | 877 | `f4fbf55617bac478ad79dfc016857ac41532c64bcc8ce6d6fbd8bf1c3a0e5b0d` | 반대 방향(수신기가 폰 거부) |

---

## 3. 코드·스크립트

| 파일 | 크기 | SHA-256 |
| --- | --- | --- |
| `src/ce/ce_aa_tls.c` | 32,938 | `f2e4001ce61ebc871c53666306ea1e83e1319200d2c621f35f3549c95e153716` |
| `src/ce/ce_aa_usb_client.c` | 12,695 | `479416106718945b021706e731b0c55cc8adab8b4e0b3a42b595fd2763aa6059` |
| `build/gd13my-native-oem-screen/test-phone-debug-trust.py` | 7,252 | `529014c230b1b4e329e2e0a096562b995d0b0f9f2e3e42718cd3579c0d22fbf7` |
| `build/auth-research/scan_genesis.py` | 954 | `55b38a8741c1ed711f9277f6094bcb47b38249c6fa87f777efa33970e7ffd36d` |
| `build/auth-research/scan_genesis2.py` | 2,049 | `94d89f9480cc8ad7aaebae0d724b83b2b8ba8b052f5f8afd22a803f338013c57` |
| `build/auth-research/scan_genesis3.py` | 1,090 | `6710083ccac896fe29be1f27ff59c98469c61b8278bdaca94ee033e525301a83` |

---

## 4. 재현 명령

### 4.1 인증서 분석
```powershell
$o = 'C:\Program Files\Git\usr\bin\openssl.exe'
$d = 'build\auth-research\certs'

& $o x509 -in "$d\gal-root.pem" -noout -text
& $o x509 -in "$d\phone-leaf.pem" -noout -text -dates -fingerprint -sha256
& $o x509 -in "$d\dhu__2.1__certificate.pem" -noout -text
& $o asn1parse -inform DER -in "$d\dhu21.der" -i | Select-String 'UTCTIME'

& $o verify -CAfile "$d\gal-root.pem" "$d\phone-leaf.pem"
& $o verify -CAfile "$d\gal-root.pem" "$d\dhu__2.1__certificate.pem"          # error 13
& $o verify -no_check_time -CAfile "$d\gal-root.pem" "$d\dhu__2.1__certificate.pem"  # OK
& $o verify -no_check_time -CAfile "$d\gal-root.pem" "$d\aasdk-embedded.pem"  # OK
```

### 4.2 AASDK 임베디드 인증서 재추출
```powershell
$p = 'research\sources\opencardev__aasdk\src\Messenger\Cryptor.cpp'
$t = [IO.File]::ReadAllText($p)
$m = [regex]::Match($t, '-----BEGIN CERTIFICATE-----([\s\S]*?)-----END CERTIFICATE-----')
$b64 = ($m.Groups[1].Value -replace '\\n','' -replace '\\','' -replace '\s','')
$pem = "-----BEGIN CERTIFICATE-----`n" +
       (($b64 -split '(.{64})' | Where-Object {$_ -ne ''}) -join "`n") +
       "`n-----END CERTIFICATE-----`n"
[IO.File]::WriteAllText("$PWD\build\auth-research\certs\aasdk-embedded.pem", $pem)
```

### 4.3 펌웨어 스캔
```powershell
python build\auth-research\scan_genesis.py  "G:\BIN\APPNAVI"
python build\auth-research\scan_genesis2.py appnavi
python build\auth-research\scan_genesis2.py vr
python build\auth-research\scan_genesis3.py
```

### 4.4 BearSSL 시간 파서 확인
```powershell
Select-String -Path build\ce-tls-dependency\bearssl-0.6\src\x509\asn1.t0 -Pattern "The time zone" -Context 0,4
```

---

## 5. 판정 원장 (Ledger)

| ID | 주장 | 등급 | 근거 |
| --- | --- | --- | --- |
| L1 | 실패는 폰이 HU 인증서를 검증하는 단계 | VERIFIED | `live-phone-usb-trust-android.log` |
| L2 | 폰 원인은 `Trust anchor … not found` | VERIFIED | 동일 |
| L3 | 서버 flight는 `[2,11,12,13,14]`, client cert 요청됨 | VERIFIED | `live-phone-aoa-auth-stage.json` |
| L4 | 마지막 정상 수신 = ServerHelloDone(14) | VERIFIED | 동일 |
| L5 | 클라이언트 flight 1230 B 송신 | VERIFIED | `live-phone-usb-trust-root-cause.log` |
| L6 | 실폰에서 TLS alert 관측 안 됨 | PARTIAL | 부재 확인(계측 한계) |
| L7 | alert 48 / `BR_ERR_X509_NOT_TRUSTED`는 이 사례 근거 아님 | VERIFIED | 로그 부재 + 방향 불일치 |
| L8 | DHU는 같은 폰·같은 날 정상 | VERIFIED | `dhu-.../stderr.log` |
| L9 | 폰 leaf는 v3, SKI/AKI만 | VERIFIED | `openssl x509 -text` |
| L10 | GAL root는 v3, CA:TRUE, sha1WithRSA | VERIFIED | 동일 |
| L11 | DHU/AASDK 인증서는 GAL root로 검증됨 | VERIFIED | `openssl verify` |
| L12 | 중간 CA 없음(2장 체인) | VERIFIED | 폰 체인 캡처 |
| L13 | HU 인증서는 `Z` 대신 `-0700` UTCTime | VERIFIED | `asn1parse` (표시 GMT 값이 오프셋 적용된 실제 UTC) |
| L14 | BearSSL과 `der_time` 모두 `Z`만 허용 | VERIFIED | 소스 |
| L15 | DHU/AASDK/LIVI 성공은 공유 GAL 신원 때문 | VERIFIED | 코드·문서 |
| L16 | 독립 신원 성공 사례 없음 | VERIFIED(조사 범위) | pi-auto-headunit 등 |
| L17 | 순정 Genesis 펌웨어에 AA/GAL 신원 없음 | VERIFIED(평문) / UNKNOWN(암호문) | §07 |
| L18 | 공식 self-service 신원 없음 | VERIFIED(부재) | Google 문서 |
| L19 | AAP 2.0 인증은 3PL 경유 | VERIFIED | P3 보도자료 |
| L20 | Cinemo CE 6.0 지원·평가 신원 | UNKNOWN | 답변 없음 |
| L21 | 체인에 루트 포함 시 폰 거부 여부 | HYPOTHESIS | AARE 문서 |
| L22 | 폰이 DN/EKU/SAN을 요구하지 않음 | VERIFIED | DHU 인증서 실사용 |
| L23 | 2025년 오류 07 파동은 폰 업데이트 기인 | VERIFIED(현상) / UNKNOWN(메커니즘) | Jaycar 등 |
| L24 | GD13MY 오류 07의 주 원인은 정책 변경 아님 | VERIFIED | 같은 날 DHU 성공 |
