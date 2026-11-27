# 후속 연구 인계

- 기존 인증 인계의 공식 평가 신원 조사만 이어간다. 이미 재현한 오류 07과 공개 인증서 시간 파싱을 반복하지 않는다. [공식 발급 조사 범위](../Codex-authentication-resolution/FREE_AI_NEXT_TASKS.md)
- `.061` `lSoundGetSoundAuthority`와 `lSoundSetSoundAuthority` 호출 지점의 인수, 소유자 ID, 반환 값, 해제 순서를 추적한다. 순정 음악, 내비 안내, 시스템 경고, 통화, ASR에서 누가 권한을 획득하고 해제하는지 VA와 호출자로 뒷받침한다. 확인하지 못한 소유자 값이나 마이크 공유 조건은 미확인으로 둔다. [순정 오디오 분석](../VIDEO_AUDIO_ANALYSIS.md)
- OEM CDP의 볼륨·곡 이동·음소거·음성·통화·MODE의 송수신 방향, 모델 적용 범위, press/release, 순정 핸들러를 표로 정리한다. 문서화된 AAP 입력 의미와 일치하는 이벤트만 실험 후보다. 원본 차량 입력을 가로채는 패치 없이 관찰·가상 주입 근거를 전달한다.
- DSP·VideoDev 연구는 소프트웨어 디코더의 측정 결과와 분리한다. `.061`에서 실제 사용 중인 디코더·디스플레이 API, 버퍼 제약과 동시 소유권을 확인한다. 후방 우선 경로와 겹치는 요소는 별도로 기록한다.
  Web-ChatGPT의 TI WinCE SDK와 EVM 자료는 출발점으로 사용한다. 이후에는 `.061` 순정 바이너리의 실제 호출과 DSP 서버 로딩 근거를 확보한다. [DSP 후속 조사](../chatGPT-search/Web-chatGPT/GD13MY_DSP_ACCELERATION_RESEARCH.md)
