# Windows 분석 환경

Windows 11 Pro 빌드 26300에서 Git 2.55.0.windows.5, Python 3.15.0b3, Git for Windows의 `file` 5.48, 기존 64비트 JDK 25.0.1을 사용했다. 별도 Python 의존성은 없다. Ghidra 12.2, Node.js 24.22.3 및 REA 6.10.1은 `%LOCALAPPDATA%\i30-phase0-tools`에 사용자 범위로 설치했다.

## 재현

프로젝트 루트에서 다음 명령을 실행한다. 파일을 다시 복사하려면 첫 명령의 `--verify-only`를 제거한다. 일치하지 않는 기존 분석본이 있으면 스크립트가 에러를 낸다.

```powershell
python tools/inventory.py --source F:/ --verify-only
python tools/extract_spd.py
python tools/inspect_firmware.py
python tools/inspect_ce.py
python tools/inspect_interfaces.py
python tools/check_manifests.py
python tools/check_map.py
python tools/check_rea.py
```

- [Ghidra 12.2 공식 릴리스](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.2_build) ZIP의 SHA-256 `2c2cd776db3c1f6a097ba418922378ac3649cadd5e844a6f5f088ae628a7be67`을 확인했다. JDK 25를 `JAVA_HOME`에 지정하고 `support/analyzeHeadless.bat`로 `LibUSB.dll`과 `LibVideo.dll`을 ARMv7 little-endian Windows 프로파일로 분석했다. 두 입력의 분석과 저장이 완료됐다. 최초 자동 PE 프로파일이 ARMv8로 선택되고 USB 분석이 90초에 종료되어, 펌웨어 근거에 맞는 ARMv7을 지정하고 180초 한도로 다시 실행했다. CE 시스템 DLL 일부와 PDB가 링크되지 않아 외부 함수와 예외 테이블 분석에는 제약이 있다. [로컬 Ghidra 로그](../research/evidence/ghidra/armv7.log)
- [Node.js 24.22.3](https://nodejs.org/dist/v24.22.3/) Windows x64 ZIP과 공식 `SHASUMS256.txt`를 대조했다. 해당 Node로 `npm install --prefix <도구 폴더>/rea --ignore-scripts --omit=optional --save-exact rea-agents@6.10.1`을 실행했다. npm lockfile은 설치 디렉터리에 있다.
- Codex CLI에서 `codex mcp add i30-rea`로 위 Node 및 REA 시작 스크립트를 등록했다. 환경은 `GHIDRA_INSTALL_DIR`, `JAVA_HOME`, `REA_GHIDRA_LANGUAGE_ID=ARM:LE:32:v7`, `REA_GHIDRA_COMPILER_SPEC_ID=windows`, `REA_MCP_TOOL_FAMILIES=native,direct,session`을 사용한다. REA provider 진단에서 Ghidra 12.2 및 JDK 검사를 통과했다. 등록된 프로세스에서 MCP 초기화, 도구 조회 및 업데이트 분석본에 대한 PE import/인증서 테이블 읽기 두 호출을 검증했다. Codex에서 새 설정을 반영하려면 클라이언트를 재시작한다. [REA 설치 문서](https://github.com/morluto/rea/blob/main/docs/getting-started/installation.md)
- REA의 Windows Ghidra provider에 `LibVideo.dll`을 넘기는 시험은 `architecture_unsupported`로 끝났다. 이 provider의 PE ARM 지원 범위는 ARMNT `0x01c4`와 ARM64 `0xaa64`이며 패키지는 구형 Thumb `0x01c2`다. REA는 PE 메타데이터 조사에 사용하고, 이 펌웨어의 코드 분석은 검증된 Ghidra 직접 실행을 사용한다. [REA Windows provider 범위](https://github.com/morluto/rea/blob/8bb01b514ac766c0c3ecc8f362bd38186eaec9c2/docs/providers/windows-ghidra-p0.md)
- Git 저장소는 로컬에서 초기화했다. 분석 드라이브는 파일 소유권을 기록하지 않아 Git 검사에는 `git -c safe.directory=F:/i30-gen2-android-auto status`처럼 해당 명령에만 경로를 지정한다. `git check-ignore`로 원본 및 추출 바이너리 경로가 제외되는 것을 확인했다.

이 시스템에 동작하는 WSL 배포판과 Docker가 없었다. Binwalk 및 unblob은 설치하지 않았다. 표준 zlib과 CE ROM 목차를 Windows에서 직접 파싱해 이 단계의 분석에 필요한 결과를 얻었다. 범용 추출기가 필요한 추가 이미지가 들어오면 WSL2 Ubuntu 또는 Docker 환경에서 [Binwalk v3 지침](https://github.com/ReFirmLabs/binwalk#how-do-i-get-it)과 [unblob 설치 지침](https://github.com/onekey-sec/unblob#installation)을 사용한다.

`firmware/original`과 `firmware/extracted`는 조사본이다. 프로젝트의 `src/`와 `tests/`는 향후 수신기 작업을 위한 디렉터리다.
