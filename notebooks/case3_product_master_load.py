# Synapse Spark 노트북 — 제품 마스터 Excel 적재 (케이스 3)
# 익명화·발췌본. 연결 정보·경로는 더미이며 이 파일은 Synapse 밖에서 실행되지 않는다.
# 로컬에서 실행 가능한 재현은 repro/case3_schema_inference.py 참고.

# ---------------------------------------------------------------------------
# 수정 전
# ---------------------------------------------------------------------------
# with fsspec_handle.open() as excel_file:
#     df_pandas = excel_to_pandas_df(excel_file)
# df = spark.createDataFrame(df_pandas)          # <- 스키마 자동 추론: 컬럼에 문자·숫자·빈칸이 섞이면 실패
# df = df.withColumn("Create_Date", lit(int(yymmdd)))

# ---------------------------------------------------------------------------
# 수정 후
# ---------------------------------------------------------------------------
from pyspark.sql.functions import lit
from pyspark.sql.types import StringType, StructField, StructType

EXPECTED_COLS = ["Ingredient", "Product", "Brand", "Manufacturer", "ATC"]


def build_spark_schema(extra_cols=None):
    fields = [StructField(c, StringType(), True) for c in EXPECTED_COLS]
    for c in extra_cols or []:
        fields.append(StructField(c, StringType(), True))
    return StructType(fields)


with fsspec_handle.open() as excel_file:  # noqa: F821  (Synapse 노트북 앞 셀에서 생성)
    df_pandas = excel_to_pandas_df(excel_file)  # noqa: F821

schema = build_spark_schema()
sdf = spark.createDataFrame(df_pandas, schema=schema)  # noqa: F821
sdf = sdf.withColumn("Create_Date", lit(int(yymmdd)))  # noqa: F821
