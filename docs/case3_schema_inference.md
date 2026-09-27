# 케이스 3. Excel → Spark 스키마 자동 추론 실패

형식: 증상 → 원인 → 조치 → 결과 → 재현

## 증상

제품 마스터 Excel 을 읽어 Dedicated SQL Pool 의 제품 마스터 STG 로 적재하는 Spark 노트북에서, Spark DataFrame 생성 단계가 실패했다.

## 원인

```python
df_pandas = excel_to_pandas_df(excel_file)   # Excel 값을 문자열로 읽는 함수
df = spark.createDataFrame(df_pandas)        # 스키마 자동 추론
```

- 읽기 함수는 값을 문자열로 읽었지만, Excel 컬럼에 숫자·문자·빈칸이 섞여 있었다.
- 스키마를 주지 않으면 Spark 가 값을 보고 컬럼 타입을 추론한다. 한 컬럼 안에 서로 다른 타입의 값이 있으면 타입을 합치지 못하고 실패한다.
- 재현(아래)에서 확인한 형태: 숫자 셀은 `'123'` 문자열로 읽혀도 **빈칸은 NaN(실수형)으로 남는다.** 이 입력을 PySpark 3.3 에서 스키마 없이 변환하면 `StringType` 과 `DoubleType` 을 합칠 수 없다는 오류가 난다.
- 결과가 **파일 내용에 따라** 달라진다. 빈칸이 없는 달에는 성공하고 있는 달에는 실패할 수 있다.

## 조치

기대 컬럼을 명시하고 모두 `StringType` 으로 지정한 스키마로 DataFrame 을 만든다. ([`notebooks/case3_product_master_load.py`](../notebooks/case3_product_master_load.py))

```python
EXPECTED_COLS = ["Ingredient", "Product", "Brand", "Manufacturer", "ATC"]

def build_spark_schema(extra_cols=None):
    fields = [StructField(c, StringType(), True) for c in EXPECTED_COLS]
    for c in (extra_cols or []):
        fields.append(StructField(c, StringType(), True))
    return StructType(fields)

sdf = spark.createDataFrame(df_pandas, schema=build_spark_schema())
```

기준정보 컬럼(성분명, 제품명, ATC 코드)은 계산에 쓰는 값이 아니라 식별·매핑용 문자열이므로 전부 문자열로 두는 것이 맞다.

## 결과

- 스키마 자동 추론 의존을 없애 파일마다 성공·실패가 달라지는 문제를 없앴다.
- 제품 마스터 적재가 정상 수행됐다.

## 재현 (PySpark, GitHub Actions)

`make repro-spark` → [`results/case3_schema_inference_spark3.3.4.md`](../results/case3_schema_inference_spark3.3.4.md), [`results/case3_schema_inference_spark3.5.3.md`](../results/case3_schema_inference_spark3.5.3.md)

Synapse Spark 3.3 런타임과 비슷한 조합(PySpark 3.3.4, Python 3.10, pandas 1.5)과 최신 조합(PySpark 3.5.3)에서, Arrow 설정을 끄고/켜고 측정했다.

| 경우 | 입력 | 스키마 | 3.3 Arrow 끔 | 3.3 Arrow 켬 | 3.5 |
|---|---|---|---|---|---|
| A | 섞인 타입 (문자·정수·None) | 없음 | **실패** (String + Long) | **실패** | 성공 |
| B | 섞인 타입 | StringType 명시 | 성공 | 성공 | 성공 |
| C | 문자열 정규화(결측은 NULL) | StringType 명시 | 성공 | 성공 | 성공 |
| D | 문자열로 읽음, 빈칸은 NaN | 없음 | **실패** (String + Double) | 성공 | 성공 |
| E | 문자열로 읽음, 빈칸은 NaN | StringType 명시 | 성공 | 성공 | 성공 |

해석

- 실무와 같은 상황(D: 문자열로 읽었지만 빈칸이 NaN)은 **Spark 3.3 + Arrow 끔**에서 스키마 자동 추론 오류로 재현된다. 같은 입력에 **명시적 스키마를 주면(E) 성공**한다 → 실무 조치와 일치.
- 같은 입력이 **Arrow 를 켜거나 Spark 3.5 에서는 실패하지 않는다.** 자동 추론 결과가 런타임 버전·설정에 따라 달라진다는 뜻이므로, 스키마를 명시하는 것이 버전과 무관하게 결과를 고정하는 방법이다.
- 실무 Synapse 노트북의 Arrow 설정값과 당시 오류 메시지 원문은 기록이 없다. 위 표는 같은 형태의 오류를 재현한 것이며, 실무 오류와 같은 메시지였다고 단정하지 않는다.
- 결측을 `astype(str)` 로 바꾸면 `'nan'` 이라는 문자열이 생긴다. C 는 결측을 NULL 로 유지한다 (`normalize_to_str`). 테스트로 고정.

코드: [`repro/case3_schema_inference.py`](../repro/case3_schema_inference.py), 테스트: [`tests/test_case3.py`](../tests/test_case3.py)
