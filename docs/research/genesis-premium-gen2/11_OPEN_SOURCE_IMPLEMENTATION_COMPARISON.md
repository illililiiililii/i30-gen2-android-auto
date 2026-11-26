# 11. 오픈소스 구현 비교 (실제 소스 기준)

작성일: 2026-11-24
방법: 저장소 22개를 GitHub API로 접근성 확인 후, 인증서/TLS와 직접 관련된 프로젝트만 소스와 문서를 내려받아 확인했다. README 요약만으로 판단하지 않았다. 다운로드/검사 파일은 저장소에 커밋하지 않고 `%TEMP%\opencode\aa-research`에서만 사용했다.

---

## 0. 먼저 답할 것: `pi-auto-headunit`의 세 문서는 존재하는가?

**존재한다.** `blakereuben/pi-auto-headunit`(기본 브랜치, 2026-11-24 기준)에서 아래 파일을 직접 내려받아 확인했다.

| 파일 | 크기 | SHA-256 |
| --- | --- | --- |
| `docs/protocol/tls-credential-policy.md` | 7,632 | `b649b93468f4fad85da463f9772f8d0ca8204a8cf80fd4ed46022df40f05b246` |
| `docs/protocol/receiver-provisioning-options.md` | 7,450 | `c1fb8d8df88d6b0db5070a17cdc9ef09206bdee17709ed72ce45b36e2c8cd578` |
| `docs/protocol/livi-adoption.md` | 15,047 | `290646fd48ac743bc594d7e0087376ee4eca51d3398cf37f98b19eb84b9d7d86` |

핵심 원문:

- `tls-credential-policy.md`: "The project will not copy, embed, present, or redistribute credentials, certificates, private keys, authentication material, or security bypasses from OpenAuto, OpenAuto Pro, AASDK, or another head-unit implementation." … AASDK `Cryptor.cpp`가 고정 인증서/개인키를 로드하고 `SSLWrapper.cpp`가 peer 검증을 끈다는 사실을 명시.
- `receiver-provisioning-options.md`: "Android Auto rejects the project's independent identity with error 7." … "Google … does not publish a self-service receiver SDK, test identity, hobbyist provisioning process, or public head-unit partner application." … 상용 후보(Cinemo, ART SDK, ECORE KOREA, NXP)는 "no vendor is selected, contacted, endorsed".
- `livi-adoption.md`: LIVI가 "canonical OpenAuto head-unit certificate and matching private key"를 내장하고 "phones accept that shared identity"라고 기록. 즉 **기술적으로는 공유 OEM 신원이 여전히 통과한다**는 증거다(합법성과 별개).

이 세 문서는 "독립 신원은 거부되고, 합법적 provisioning 경로는 아직 없다"는 이 프로젝트의 결론과 정확히 일치한다.

---

## 1. 비교표

| 프로젝트 | 역할/스택 | 라이선스 | TLS 처리 | peer 검증 | HU 신원 | 실제 phone 연결 | 이 프로젝트 관련성 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Google DHU | 공식 데스크톱 HU (Linux/macOS/Win) | 비공개 배포 | TLS 1.2, mutual TLS | phone 체인 검증 | `Android-Auto-Internal` leaf (GAL 발급) | 정상 | **동작 기준선** |
| opencardev/aasdk | C++ AAP 라이브러리 | GPL-3.0 | OpenSSL, `TLSv1_2_client_method` | `SSL_VERIFY_NONE` | JVC Kenwood leaf + 공개 개인키 | 대체로 정상 | 프로토콜 참조, 신원 재사용 금지 |
| opencardev/OpenAuto | C++ HU 앱 | GPL-3.0 | aasdk 사용 | 없음 | aasdk와 동일 | 대체로 정상 | 구조 참조 |
| andreknieriem/open-headunit (구 headunit-revived) | Android HU 앱 (Kotlin) | AGPL-3.0 | Android `SSLEngine`, 선택적 Conscrypt | **trust-all** | 앱 내 `SingleKeyKeyManager` | 기기별 편차, error 7 다수 | TLS 운용/에러 분류 참조 |
| blakereuben/pi-auto-headunit | Rust 네이티브 HU | GPL-3.0 | Rust TLS + AAP 프레이밍 | **미확인**(`TlsClient` 트레이트로 교체 가능) | 독립 신원(거부됨) | error 7 (미해결) | **정책/한계의 가장 정직한 사례** |
| f-io/LIVI | Electron/TS HU | GPL-3.0 | OpenAuto 파생 | - | OpenAuto 공개 인증서 내장 | 정상 보고 | 신원 공유의 증거, 채택 금지 |
| AARE 문서 (오픈소스 HU 리서치) | 리서치/데스크톱 HU | 오픈소스 | TLS 1.2 in AAP | 문서화 | 자체/공개 자료 | DHU 대조 | 인증서 요구사항 문서 |
| JanRi3D/OpenAuto | 포크 | GPL-3.0 | aasdk | 없음 | aasdk와 동일 | - | 낮음 |
| 기타 14개 저장소 | 프로토콜 파서/도구/포크 | 다양 | 대부분 라이브러리 재사용 | - | - | - | 낮음 |

---

## 2. 소스 근거

### 2.1 aasdk — TLS 1.2 고정 + 검증 비활성화

`aasdk/src/Transport/SSLWrapper.cpp` (newdev, 2026-11-24 확인):

```cpp
// line 99
return TLSv1_2_client_method();
// line 101
return TLS_client_method();
// line 139
SSL_set_verify(ssl, SSL_VERIFY_NONE, nullptr);
```

- `SSL_CTX_use_certificate`/`use_PrivateKey`로 고정 인증서를 넣는다(`readCertificate`, `readPrivateKey`).
- `BIO_new(BIO_s_mem())` 두 개로 메모리 BIO 위에 TLS를 올린다(AAP 메시지 안에 TLS 레코드를 캡슐화).
- 핵심: **HU는 TLS client, phone은 TLS server**이며, HU는 phone 인증서를 검증하지 않는다. phone만 HU를 검증한다. 따라서 에러 07은 "HU가 phone을 못 믿어서"가 아니라 "phone이 HU를 못 믿어서" 발생한다.

### 2.2 open-headunit — trust-all + Conscrypt

`app/src/main/java/com/andrerinas/openheadunit/ssl/SslContextFactory.kt`:

```kotlin
override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
```

- HU 쪽은 모든 phone 인증서를 신뢰한다. 즉 HU는 phone 검증에서 실패할 수 없다.
- `SingleKeyKeyManager`가 HU 신원을 제공한다.
- PR #66 "Add Conscrypt (Fixes Error 7 on lower Android Versions)" (2026-01-23): Conscrypt provider로 `SSLContext`를 만들자 Android 4.4 계열에서 error 7이 사라졌다는 보고. 이는 **체인이 아니라 TLS 스택 호환성**으로 발생한 error 7 사례다.
- `TlsUnwrapLoop.kt`: AAP 프레임 바디 안의 TLS 레코드를 여러 번 unwrap하고, 바이트/태스크 진행이 없으면 spin하지 않도록 방어한다. AAP-over-TLS 프레이밍 참조 구현으로 유용.

### 2.3 AARE — 요구사항 문서

`certificates.md`:

- "After the version exchange, phone and head unit run **TLS 1.2** inside AAP messages (channel 0, message type 3, `ENCAPSULATED_SSL`)."
- "**The phone is the TLS server; the head unit is the TLS client.** It is **mutual TLS**."
- HU는 핸드셰이크 후 `AUTH_COMPLETE`(message type 4, `AuthResponse`)를 보내고, status `0`이면 수락.
- 문서 스스로 "What isn't verified is marked as such"라고 명시한다. 즉 이 문서도 1차 관측과 추론을 구분한다.

### 2.4 pi-auto-headunit — 독립 신원의 한계

`receiver-provisioning-options.md`:

- Pi 5에서 AAP 1.6, USB/AOA 및 Google 개발자 transport로 TLS 데이터 교환까지 도달.
- "Android Auto rejects the project's independent identity with error 7."
- "A synthetic mutual-TLS verifier confirms that the project presents its configured client certificate and completes the handshake when that identity is trusted."
- "The remaining release gate is legitimate Android Auto receiver provisioning."

이 문장은 이 프로젝트의 진단과 동일한 구조다. **프로토콜/전송은 되고, 신원만 막힌다.**

### 2.5 LIVI — 공유 신원이 통과한다는 증거

`livi-adoption.md` + `receiver-provisioning-options.md`:

- LIVI의 AA crypto 소스가 "canonical OpenAuto head-unit certificate and matching private key"를 내장.
- "phones accept that shared identity."
- pi-auto는 이 파일/신원을 "prohibited by this project's credential policy"로 배제.

기술적 결론: phone은 차량별 고유성을 요구하지 않고 **GAL 체인**만 본다. 합법적 결론: 공유 키를 쓰는 것은 신원 위조/자격 증명 재배포이므로 이 프로젝트는 하지 않는다.

### 2.6 DHU — 동작 기준선

- 공식 도구이며 자체 `Android-Auto-Internal` 인증서를 사용한다.
- 이 인증서는 OEM 파트너 leaf가 아님에도 phone이 수락한다. 이는 "GAL 발급 leaf면 충분하다"는 강한 증거다.
- 동시에 DHU는 Google이 배포하는 테스트 도구이므로, 개인키가 공개되어 있어도 **제품 HU 신원으로 사용할 라이선스가 없다.**

---

## 3. 구현 패턴 비교

| 항목 | aasdk/OpenAuto | open-headunit | pi-auto | DHU |
| --- | --- | --- | --- | --- |
| TLS 라이브러리 | OpenSSL | Android SSLEngine(+Conscrypt) | Rust TLS | 미공개 |
| TLS 버전 | 1.2 고정(조건부) | 기본 협상 | 1.2 | 1.2 |
| phone 검증 | 안 함 | 안 함(trust-all) | 미확인(교체 가능 경계) | 함 |
| AAP 캡슐화 | memory BIO | SSLEngine unwrap 루프 | 자체 프레이밍 | 자체 |
| 인증서 출처 | 공개 OEM leaf | 앱키 | 독립(거부) | 내부 테스트 |
| 에러 07 | 드묾(공유 신원) | 기기별 | 항상 | 없음 |
| 라이선스 | GPL-3.0 | AGPL-3.0 | GPL-3.0 | 비공개 |

**해석:** "TLS를 잘 구현하는 것"과 "phone이 신뢰하는 신원을 갖는 것"은 별개다. OSS 프로젝트들이 동작하는 이유는 TLS 구현이 뛰어나서가 아니라 **GAL 체인 신원을 재사용**하기 때문이다. 이 프로젝트는 그 선택지를 윤리/법적으로 배제했으므로, 남은 길은 provisioning뿐이다.

---

## 4. GD13MY(WinCE/ARM)에 직접 적용할 것

`[GD13MY 적용 가능]`

1. **TLS 1.2 + `0xC02F` 유지**: BearSSL 0.6으로 이미 동작. wolfSSL/mbedTLS 교체는 근거 없음.
2. **HU=client, phone=server**: 인증서 검증 방향을 코드에 명시. HU는 phone 체인을 검증하고(선택), phone은 HU 체인을 검증한다(필수).
3. **AAP-over-TLS 프레이밍**: `TlsUnwrapLoop.kt`의 "프레임 바디 = 하나 이상의 TLS 레코드" 모델을 C++로 이식할 때 참조. 단, 코드 복사는 라이선스(AGPL) 확인 필요.
4. **AUTH_COMPLETE status 처리**: `0` 수락, 음수 거부. 거부 사유를 TLS alert와 분리해 로깅.
5. **Conscrypt 사례**: GD13MY는 Android가 아니므로 직접 적용은 아니지만, "TLS 스택이 다르면 같은 에러 7이 발생할 수 있다"는 테스트 축으로 반영.

---

## 5. 하지 말아야 할 것

- DHU/AASDK/LIVI의 인증서+개인키를 제품/배포물에 넣지 않는다. 공개되어 있어도 신원 위조다.
- `SSL_VERIFY_NONE`을 "phone 검증"에 적용하지 않는다. phone 쪽은 우리가 제어할 수 없다.
- "인증서 무시" 플래그를 찾지 않는다. phone 앱에는 그런 스위치가 없다.
- AGPL 코드를 GPL-3.0 프로젝트에 그대로 복사하지 않는다. 특히 open-headunit은 AGPL-3.0이다.
