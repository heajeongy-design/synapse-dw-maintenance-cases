# 케이스 3. Excel → Spark 스키마 자동 추론 실패

형식: 증상 → 원인 → 조치 → 결과 → 재현

## 증상

제품 마스터 Excel 을 읽어 Dedicated SQL Pool 의 제품 마스터 STG 로 적재하는 Spark 노트북에서, Spark DataFrame 생성 단계가 실패했다.

## 원인

```python
df_pandas = excel_to_pandas_df(excel_file)
df = spark.createDataFrame(df_pandas)   # 스키마 자동 추론
```

- `createDataFrame` 에 스키마를 주지 않으면 Spark 가 값을 보고 컬럼 타입을 추론한다.
- Excel 한 컬럼에 문자열·빈칸·숫자가 섞여 있으면(예: 성분 컬럼에 `성분A` / 빈칸 / `123`) 어떤 타입으로 만들지 결정하지 못하고 실패한다.
- 결과가 **파일 내용에 따라** 달라진다. 같은 코드가 어떤 달에는 성공하고 어떤 달에는 실패할 수 있다.

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

## 재현 (PySpark, CI 에서 실행)

`make repro-spark` → [`results/case3_schema_inference.md`](../results/case3_schema_inference.md)

Arrow 설정을 끄고/켜고, 다음 세 경우를 측정한다.

| 경우 | 내용 |
|---|---|
| A | 섞인 타입 + 스키마 없음 (수정 전 코드) |
| B | 섞인 타입 + StringType 스키마 (스키마만 추가) |
| C | 값을 문자열로 정규화(결측은 NULL 유지) + StringType 스키마 |

- B 가 통과하는지는 **pandas 단계에서 값이 이미 문자열인지**에 달려 있다. Spark 는 스키마를 줘도 숫자 객체를 `StringType` 으로 자동 변환하지 않고 검증 오류를 낼 수 있다.
- 결측을 `astype(str)` 로 바꾸면 `'nan'` 이라는 문자열이 생긴다. C 는 결측을 NULL 로 유지한다 (`normalize_to_str`).
- 측정 결과는 CI 실행 후 `results/` 에 기록한다. 실무 노트북의 `excel_to_pandas_df` 가 값을 어떻게 읽는지는 이 문서에서 단정하지 않는다.

코드: [`repro/case3_schema_inference.py`](../repro/case3_schema_inference.py), 테스트: [`tests/test_case3.py`](../tests/test_case3.py)
