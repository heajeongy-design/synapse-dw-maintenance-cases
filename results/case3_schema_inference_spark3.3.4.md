# 케이스 3 재현 결과: pandas → Spark 변환 시 스키마 추론

- 실행 시각: 2026-09-27 05:34 UTC
- 환경: Python 3.10.21 / Linux
- 데이터: 합성 데이터 (실무 데이터 아님, 규모 비교 목적 아님)

- PySpark 3.3.4, pandas 1.5.3

| Arrow | 경우 | 결과 | 상세 |
|---|---|---|---|
| false | A 섞인 타입, 스키마 없음 | ERROR | TypeError: field ATC: Can not merge type <class 'pyspark.sql.types.StringType'> and <class 'pyspark.sql.types.LongType'> |
| false | B 섞인 타입, StringType 스키마 | OK | 3 rows, schema=struct<Ingredient:string,Product:string,Brand:string,Manufacturer:string,ATC:string> |
| false | C 문자열 정규화 + StringType 스키마 | OK | 3 rows, schema=struct<Ingredient:string,Product:string,Brand:string,Manufacturer:string,ATC:string> |
| false | D 문자열로 읽음(빈칸 NaN), 스키마 없음 | ERROR | TypeError: field Ingredient: Can not merge type <class 'pyspark.sql.types.StringType'> and <class 'pyspark.sql.types.DoubleType'> |
| false | E 문자열로 읽음(빈칸 NaN), StringType 스키마 | OK | 3 rows, schema=struct<Ingredient:string,Product:string,Brand:string,Manufacturer:string,ATC:string> |
| true | A 섞인 타입, 스키마 없음 | ERROR | TypeError: field ATC: Can not merge type <class 'pyspark.sql.types.StringType'> and <class 'pyspark.sql.types.LongType'> |
| true | B 섞인 타입, StringType 스키마 | OK | 3 rows, schema=struct<Ingredient:string,Product:string,Brand:string,Manufacturer:string,ATC:string> |
| true | C 문자열 정규화 + StringType 스키마 | OK | 3 rows, schema=struct<Ingredient:string,Product:string,Brand:string,Manufacturer:string,ATC:string> |
| true | D 문자열로 읽음(빈칸 NaN), 스키마 없음 | OK | 3 rows, schema=struct<Ingredient:string,Product:string,Brand:string,Manufacturer:string,ATC:string> |
| true | E 문자열로 읽음(빈칸 NaN), StringType 스키마 | OK | 3 rows, schema=struct<Ingredient:string,Product:string,Brand:string,Manufacturer:string,ATC:string> |

해석은 docs/case3_schema_inference.md 참고. Synapse 런타임의 기본 Arrow 설정과 버전은 이 환경과 다를 수 있다.
