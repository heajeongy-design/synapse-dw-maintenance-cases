"""케이스 3 재현: Excel(pandas) → Spark DataFrame 변환 시 스키마 자동 추론 실패

원 환경: Synapse Spark 노트북, pandas 로 읽은 Excel 을 spark.createDataFrame 으로 변환 후 SQL Pool 적재
재현 환경: PySpark (requirements.txt 버전). Synapse 런타임과 Arrow 설정이 다를 수 있으므로
         Arrow 를 끈 경우와 켠 경우를 모두 측정한다.

측정하는 것 (결과는 results/case3_*.md 에 CI 가 기록)
  A. 섞인 타입 + 스키마 없음          (원래 코드)
  B. 섞인 타입 + StringType 명시 스키마 (명시 스키마만 추가)
  C. 값을 문자열로 정규화(NULL 유지) + StringType 명시 스키마
  D. 문자열로 읽었지만 빈칸은 NaN 으로 남은 경우 (숫자 셀도 '123' 문자열) — 스키마 없음
  E. D 와 같은 입력 + StringType 명시 스키마
"""
from __future__ import annotations

import math

import pandas as pd

EXPECTED_COLS = ["Ingredient", "Product", "Brand", "Manufacturer", "ATC"]


def sample_excel_like_df() -> pd.DataFrame:
    # Excel 한 컬럼에 문자열·빈칸·숫자가 섞인 상황 (값은 더미)
    return pd.DataFrame(
        {
            "Ingredient": ["성분A", None, 123],
            "Product": ["제품X 정", "제품Y 정", "제품Z 캡슐"],
            "Brand": ["제품X", "제품Y", "제품Z"],
            "Manufacturer": ["제조사M", "제조사N", float("nan")],
            "ATC": ["ATC-01", 2, "ATC-03"],
        }
    )


def sample_read_as_str_df() -> pd.DataFrame:
    """Excel 을 문자열로 읽은 경우: 숫자 셀은 '123' 같은 문자열, 빈칸은 NaN(float)."""
    nan = float("nan")
    return pd.DataFrame(
        {
            "Ingredient": pd.Series(["성분A", nan, "123"], dtype=object),
            "Product": pd.Series(["제품X 정", "제품Y 정", "제품Z 캡슐"], dtype=object),
            "Brand": pd.Series(["제품X", "제품Y", "제품Z"], dtype=object),
            "Manufacturer": pd.Series(["제조사M", "제조사N", nan], dtype=object),
            "ATC": pd.Series(["ATC-01", "2", "ATC-03"], dtype=object),
        }
    )


def build_spark_schema(extra_cols=None):
    from pyspark.sql.types import StringType, StructField, StructType

    fields = [StructField(c, StringType(), True) for c in EXPECTED_COLS]
    for c in extra_cols or []:
        fields.append(StructField(c, StringType(), True))
    return StructType(fields)


def normalize_to_str(pdf: pd.DataFrame) -> pd.DataFrame:
    """NULL/NaN 은 None 으로 두고 나머지는 str 로. (astype(str) 은 NaN 을 'nan' 문자열로 만들어 쓰지 않는다)"""

    def conv(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return str(v)

    # pandas 3 의 기본 문자열 dtype 은 결측을 NaN 으로 바꾸므로 object dtype 으로 직접 만든다
    return pd.DataFrame({c: pd.Series([conv(v) for v in pdf[c]], dtype=object) for c in pdf.columns})


def try_create(spark, pdf, schema=None) -> tuple[str, str]:
    try:
        df = spark.createDataFrame(pdf, schema=schema) if schema is not None else spark.createDataFrame(pdf)
        rows = df.collect()
        return "OK", f"{len(rows)} rows, schema={df.schema.simpleString()}"
    except Exception as e:  # 오류 종류와 첫 줄만 기록
        first = str(e).strip().splitlines()[0] if str(e).strip() else ""
        return "ERROR", f"{type(e).__name__}: {first[:200]}"


def run_matrix(spark) -> list[dict]:
    pdf = sample_excel_like_df()
    results = []
    for arrow in ("false", "true"):
        spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", arrow)
        spark.conf.set("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")
        for label, data, schema in (
            ("A 섞인 타입, 스키마 없음", pdf, None),
            ("B 섞인 타입, StringType 스키마", pdf, build_spark_schema()),
            ("C 문자열 정규화 + StringType 스키마", normalize_to_str(pdf), build_spark_schema()),
            ("D 문자열로 읽음(빈칸 NaN), 스키마 없음", sample_read_as_str_df(), None),
            ("E 문자열로 읽음(빈칸 NaN), StringType 스키마", sample_read_as_str_df(), build_spark_schema()),
        ):
            status, detail = try_create(spark, data, schema)
            results.append({"arrow": arrow, "case": label, "status": status, "detail": detail})
    return results
