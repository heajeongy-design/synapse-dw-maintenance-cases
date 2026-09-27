# 케이스 1. DIM 누적 적재 → JOIN 행 폭증 → Analysis Services Refresh OOM

형식: 증상 → 추적 → 근본 원인 → 조치 → 결과 → 재발 방지

## 증상

- 일배치에서 영업 주문·담당자 FCT 관련 **Analysis Services(AAS) Refresh 가 Out Of Memory 로 반복 실패**했다.
- 기본 운영 등급 **S1(메모리 25GB / 100 QPU)** 에서는 Refresh 가 완료되지 않았고, **S4(100GB / 400 QPU)** 로 올려야만 완료됐다.
- 비용 때문에 운영은 **Refresh 할 때마다 S4 로 올렸다가 끝나면 S1 으로 내리는** 방식으로 버티고 있었다.

| AAS 등급 | 메모리 / QPU | 월 정가(당시 기록) |
|---|---|---|
| S1 | 25GB / 100 QPU | 약 $1,481.90 |
| S4 | 100GB / 400 QPU | 약 $5,920.30 |

## 리소스 문제가 아니라고 의심한 이유

- 데이터 규모에 비해 메모리 사용량이 과도했다.
- 같은 테이블의 Refresh 에서만 반복됐다.
- Scale-Up 후에도 리소스 사용량이 비정상적으로 높았다.

→ 등급을 더 올리는 대신, 해당 FCT 가 어떤 데이터로 만들어지는지 거꾸로 따라갔다.

## 추적

```
FCT (영업 주문·담당자)
  └ 구성 쿼리가 쓰는 내부 뷰 v_fct_input  ── 행 수 1억 건 이상 (비정상)
      └ JOIN dim_customer (ERP 고객 DIM)
          ├ DIM: 고객 코드별 약 10~14배, 행 내용이 완전히 같은 복제   ← 여기서 부풀었다
          └ STG(stg_customer): 전체 건수 = 고유 건수                ← 원천은 정상
                → 중복은 STG → DIM 적재 단계에서 생긴다
                    └ 파이프라인: 저장 프로시저(Truncate) → Copy(STG → DIM)
                        └ 프로시저 파라미터 @TableName1, @TableName2
                          파이프라인이 넘기는 이름 'TableName'   ← 불일치
```

사용한 쿼리: [`sql/case1_01_trace_rowcount.sql`](../sql/case1_01_trace_rowcount.sql)

1. 내부 뷰 행 수 확인 → 1억 건 이상.
2. DIM 이 비즈니스 키(고객 코드) 기준 1:1 인지 `COUNT(*)` vs `COUNT(DISTINCT)` → 1:1 이 아님.
3. 키별 중복 수 → 약 10~14배. 불규칙한 중복이 아니라 **같은 행이 통째로 반복** → JOIN 오류가 아니라 적재가 반복 누적되는 형태로 판단.
4. STG 도 같은 검사 → 정상. → 문제 구간을 STG → DIM 적재로 좁힘.
5. 파이프라인 확인 → Copy 전에 Truncate 저장 프로시저가 있음 → 프로시저 정의와 활동 설정의 파라미터 이름 비교.

## 근본 원인

- 전임자가 **다른 건을 수정하면서 Stored Procedure 활동의 파라미터 이름을 바꿨고**(`TableName`), 프로시저 정의(`@TableName1`)와 맞지 않게 됐다. 이후 월별 실행에서 해당 단계 실패가 발생했다.
- 그 결과 `TRUNCATE TABLE dim_customer` 가 수행되지 않은 채 STG → DIM 적재가 반복되어 DIM 이 누적됐다.
- 누적된 DIM 과 JOIN 하는 뷰의 행 수가 배수로 늘어나 AAS Refresh 메모리 부족으로 이어졌다.

> 원 파이프라인에서 Truncate 실패 뒤에도 적재가 수행된 활동 연결 방식은 이 문서에 적지 않는다(확인한 사실이 아님).
> 확인한 것은 "파라미터 불일치로 Truncate 가 수행되지 않았다"와 "DIM 에 같은 행이 반복 적재됐다"이다.

## 조치

Stored Procedure 활동의 파라미터 이름을 프로시저 정의와 같게 수정했다. ([`sql/case1_02_procedure.sql`](../sql/case1_02_procedure.sql))

```
수정 전: Name = TableName
수정 후: Name = TableName1
```

## 결과

- 다음 실행부터 Truncate 가 정상 수행되어 DIM 의 반복 누적이 사라졌다.
- 뷰의 JOIN 행 수가 정상화되고, **기본 등급 S1 에서 Refresh 가 정상 완료**됐다.
- Refresh 때마다 하던 **S1 ↔ S4 수동 Scale-Up/Down 운영이 필요 없어졌다.** (S4 를 상시 유지한다면 월 정가 기준 약 4배 차이)
- 수정 후 행 수·Refresh 시간은 기록해 두지 않았다. 여기에는 적지 않는다.

## 재현 (로컬, 합성 데이터)

`make repro` → [`results/case1_dim_accumulation.md`](../results/case1_dim_accumulation.md)

- STG 1,000 고객 / 주문 라인 20,000 건으로, 잘못된 이름으로 12회 실행하면 DIM 13,000 행, 뷰 260,000 행(13배), 금액 합계도 13배.
- 수정 후 1회 실행으로 1:1 복귀, 재실행해도 결과 동일.
- 코드: [`repro/case1_dim_accumulation.py`](../repro/case1_dim_accumulation.py), 테스트: [`tests/test_case1.py`](../tests/test_case1.py)

## 재발 방지 (재현 과정에서 작성한 제안 — 실무 적용 아님)

| 장치 | 무엇을 막나 | 위치 |
|---|---|---|
| 배포 전 파라미터 이름 검사 (`sys.parameters` 와 활동 설정 비교) | 이번 원인 자체 | [`sql/case1_03_guard_checks.sql`](../sql/case1_03_guard_checks.sql) G1, 재현 `check_param_names` |
| DIM 적재 직후 키 유일성 검사, 위반 시 THROW | 누적이 FCT·AAS 로 번지는 것 | G2, 재현 `dq_dim_key_unique` (첫 잘못된 실행에서 FAIL) |
| 뷰 행 수 / 기준 Fact 행 수 = 1 검사 | 1:N JOIN 폭증 전반 | G3 |
| Truncate 실패 시 다음 단계 중단 + 실패 알림 | 실패가 조용히 누적으로 바뀌는 것 | 재현 `on_fail="stop"` 비교 |
| Truncate 를 Copy 활동 sink 의 pre-copy script 로 옮기는 안 | 두 활동 사이 파라미터 연결 자체 | 설계 검토만 |

## 배운 점

- 리소스 증설은 증상을 늦췄을 뿐이고 비용은 계속 나갔다. 원인은 데이터 품질(DIM 키 중복)이었다.
- "결과 테이블 → 뷰 → DIM → STG" 순으로 각 단계가 정상인지 쿼리로 확인하면 문제 구간을 좁힐 수 있다.
