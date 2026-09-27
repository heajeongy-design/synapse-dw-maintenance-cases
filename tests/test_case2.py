import sqlite3
import unittest

from repro import case2_master_missing as c2


class Case2Test(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        c2.build(self.conn)
        c2.rebuild_fct(self.conn)

    def test_missing_master_leaves_product_unclassified(self):
        rows = {r[0]: r for r in c2.brand_summary(self.conn)}
        self.assertIsNone(rows["제품X 정 규격D"][4])
        self.assertEqual(rows["제품X 정 규격C"][4], "복합제 시장")

    def test_orphan_query_finds_exactly_missing_product(self):
        self.assertEqual([o[0] for o in c2.orphans(self.conn)], ["제품X 정 규격D"])
        self.assertGreater(c2.unclassified_ratio(self.conn), 0)

    def test_fix_and_rebuild(self):
        total_before = self.conn.execute("SELECT SUM(filled_amt) FROM fct_market_sales").fetchone()[0]
        c2.apply_fix(self.conn)
        self.assertEqual(c2.orphans(self.conn), [])
        self.assertEqual(c2.unclassified_ratio(self.conn), 0.0)
        total_after = self.conn.execute("SELECT SUM(filled_amt) FROM fct_market_sales").fetchone()[0]
        self.assertEqual(total_before, total_after)  # 금액 합계는 그대로, 분류만 바뀐다

    def test_rebuild_is_repeatable(self):
        c2.apply_fix(self.conn)
        a = c2.brand_summary(self.conn)
        c2.rebuild_fct(self.conn)
        self.assertEqual(a, c2.brand_summary(self.conn))


if __name__ == "__main__":
    unittest.main()
