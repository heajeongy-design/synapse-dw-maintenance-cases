"""PySpark 가 설치된 환경(CI)에서만 실행된다."""
import unittest

try:
    from pyspark.sql import SparkSession

    HAS_SPARK = True
except ImportError:  # 로컬에 pyspark 가 없으면 건너뛴다
    HAS_SPARK = False

from repro import case3_schema_inference as c3


class NormalizeTest(unittest.TestCase):
    def test_normalize_keeps_null_and_stringifies(self):
        out = c3.normalize_to_str(c3.sample_excel_like_df())
        self.assertIsNone(out.loc[1, "Ingredient"])
        self.assertEqual(out.loc[2, "Ingredient"], "123")
        self.assertIsNone(out.loc[2, "Manufacturer"])  # NaN -> None, 'nan' 문자열이 아님
        self.assertEqual(out.loc[1, "ATC"], "2")


@unittest.skipUnless(HAS_SPARK, "pyspark not installed")
class SparkMatrixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = SparkSession.builder.master("local[1]").appName("case3").getOrCreate()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_normalized_with_schema_succeeds_both_arrow_modes(self):
        res = c3.run_matrix(self.spark)
        for r in res:
            if r["case"].startswith("C"):
                self.assertEqual(r["status"], "OK", r)

    def test_matrix_records_every_case(self):
        # A·B·D·E 의 성공/실패는 버전·설정에 따라 다르므로 단정하지 않고 기록만 한다 (results/)
        res = c3.run_matrix(self.spark)
        self.assertEqual(len(res), 10)

if __name__ == "__main__":
    unittest.main()
