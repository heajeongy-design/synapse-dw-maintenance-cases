# 케이스 1 재현 결과: Truncate 파라미터명 불일치 → DIM 누적

- 실행 시각: 2026-09-27 05:34 UTC
- 환경: Python 3.11.16 / Linux
- 데이터: 합성 데이터 (실무 데이터 아님, 규모 비교 목적 아님)

| 단계 | Truncate | STG 행/고유 | DIM 행/고유 | 고객당 최대 중복 | 주문 라인 | 뷰(JOIN) 행 | 배수 | DQ 키 유일성 |
|---|---|---|---|---|---|---|---|---|
| 정상 적재 (TableName1) | Succeeded | 1,000/1,000 | 1,000/1,000 | 1 | 20,000 | 20,000 | 1.0 | PASS |
| 잘못된 이름(TableName) 1회차 | Failed | 1,000/1,000 | 2,000/1,000 | 2 | 20,000 | 40,000 | 2.0 | FAIL |
| 잘못된 이름(TableName) 5회차 | Failed | 1,000/1,000 | 6,000/1,000 | 6 | 20,000 | 120,000 | 6.0 | FAIL |
| 잘못된 이름(TableName) 12회차 | Failed | 1,000/1,000 | 13,000/1,000 | 13 | 20,000 | 260,000 | 13.0 | FAIL |
| 수정 후 1회 (TableName1) | Succeeded | 1,000/1,000 | 1,000/1,000 | 1 | 20,000 | 20,000 | 1.0 | PASS |
| 수정 후 재실행 | Succeeded | 1,000/1,000 | 1,000/1,000 | 1 | 20,000 | 20,000 | 1.0 | PASS |

Truncate 실패 메시지(재현): `usp_truncate_table has no parameter named ['TableName']`

## 비교: 실패 시 다음 단계를 멈추는 경우 (재현본 가정)

- 활동 결과: Truncate=Failed, CopyDim=Skipped
- DQ: PASS (dim_customer total=1000 distinct=1000) → 누적 없음, 대신 DIM 이 갱신되지 않아 실패 알림으로 인지해야 함

## 배포 전 파라미터 이름 검사 (재현본 추가)

- 수정 전 설정: ["unknown parameter 'TableName' (procedure has ['TableName1', 'TableName2'])", "required parameter 'TableName1' not supplied"]
- 수정 후 설정: 문제 없음

해석: 실무에서 확인한 현상(STG 는 정상, DIM 만 같은 배수로 복제, 내부 뷰 행 수 폭증)과 같은 형태가 재현된다.
배수는 잘못된 설정으로 실행된 횟수 + 1 이다. 실무의 10~14배라는 값과 실행 횟수의 관계는 확인하지 않았다.
