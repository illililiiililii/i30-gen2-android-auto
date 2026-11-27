# 브릭 예방 메모

이번 에뮬레이터 성능 작업은 로컬 실험용 이미지와 복사된 DiskA 상태만 사용했다. 원본 stock firmware, bootloader, partition table, kernel/BSP, 차량 저장장치 및 MICOM firmware는 수정하지 않았으며 차량 장치에 쓰기 작업을 하지 않았다.

현재 하드웨어 reverse engineering 중 구체적인 update/boot-chain/recovery 절차나 보호 영역 정보를 새로 확인하지 못했다. 복구, UART/JTAG, SD/USB 복구 및 eMMC 복원 절차는 검증되지 않은 상태로 남긴다.

실제 firmware build를 시작하기 전에는 별도 안전성 검증 단계가 필요하다. 그 단계는 순정 이미지 read-only 백업, 해시/모델 확인, 실험 이미지 분리, boot/recovery 검토, 복구 매체 및 복원 성공 확인, 변경 범위 승인 기록을 포함해야 한다. 현재 문서는 실제 차량에서 쓰기/업데이트하는 절차를 제시하지 않는다.
