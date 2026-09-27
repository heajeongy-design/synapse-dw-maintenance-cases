import sqlite3
import unittest

from repro import case1_dim_accumulation as c1


class Case1Test(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        c1.build_source(self.conn, n_customers=200, n_orders=2_000)
        c1.run_pipeline(self.conn, {"TableName1": "dim_customer"})

    def test_wrong_param_name_fails_truncate(self):
        log = c1.run_pipeline(self.conn, {"TableName": "dim_customer"})
        self.assertEqual(log[0][1], "Failed")
        self.assertIn("no parameter named", log[0][2])

    def test_accumulation_multiplies_join_rows(self):
        for _ in range(9):
            c1.run_pipeline(self.conn, {"TableName": "dim_customer"})
        m = c1.measure(self.conn)
        self.assertEqual(m["stg_total"], m["stg_distinct"])  # STG 는 정상
        self.assertEqual(m["dim_total"], 10 * m["dim_distinct"])  # DIM 은 10배
        self.assertEqual(m["fanout"], 10.0)  # JOIN 결과도 10배
        self.assertEqual(m["amt_ratio"], 10.0)  # 금액 합계도 10배

    def test_dq_detects_after_first_bad_run(self):
        self.assertTrue(c1.dq_dim_key_unique(self.conn)[0])
        c1.run_pipeline(self.conn, {"TableName": "dim_customer"})
        self.assertFalse(c1.dq_dim_key_unique(self.conn)[0])

    def test_fix_restores_one_to_one(self):
        for _ in range(5):
            c1.run_pipeline(self.conn, {"TableName": "dim_customer"})
        c1.run_pipeline(self.conn, {"TableName1": "dim_customer"})
        m = c1.measure(self.conn)
        self.assertEqual(m["dim_total"], m["dim_distinct"])
        self.assertEqual(m["fanout"], 1.0)

    def test_rerun_after_fix_is_idempotent(self):
        c1.run_pipeline(self.conn, {"TableName1": "dim_customer"})
        a = c1.measure(self.conn)
        c1.run_pipeline(self.conn, {"TableName1": "dim_customer"})
        self.assertEqual(a, c1.measure(self.conn))

    def test_stop_on_failure_prevents_accumulation(self):
        c1.run_pipeline(self.conn, {"TableName": "dim_customer"}, on_fail="stop")
        self.assertTrue(c1.dq_dim_key_unique(self.conn)[0])

    def test_param_check_catches_mismatch_before_run(self):
        self.assertTrue(c1.check_param_names(c1.USP_TRUNCATE, {"TableName": "dim_customer"}))
        self.assertEqual(c1.check_param_names(c1.USP_TRUNCATE, {"TableName1": "dim_customer"}), [])


if __name__ == "__main__":
    unittest.main()
