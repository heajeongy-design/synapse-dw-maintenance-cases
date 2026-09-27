"""케이스 2 재현: 제품 마스터 1건 누락 → 성분·ATC·시장분류 매핑 실패 → 매출 집계 불일치

원 환경: 외부 처방 통계 원본 + 제품 마스터(Excel → STG) → 매핑 → 시장 매출 FCT (Synapse Dedicated SQL Pool)
재현 환경: SQLite. 제조사·제품·성분·ATC 값은 모두 더미다.

재현 가정
- 원 로직에서 매핑에 실패한 행이 "분류 없음(NULL)"으로 남았는지, 결과에서 빠졌는지는 확인하지 않았다.
  재현본은 LEFT JOIN 으로 분류가 NULL 이 되는 형태로 만든다. 어느 쪽이든 탐지 쿼리(원천에는 있고
  마스터에는 없는 제품)는 같다.
"""
from __future__ import annotations

import sqlite3

MASTER = [
    # product, brand, manufacturer, atc, ingredient
    ("제품X 정 규격A", "제품X", "제조사M", "ATC-01", "성분A, 성분B"),
    ("제품X 정 규격B", "제품X", "제조사M", "ATC-01", "성분A, 성분B"),
    ("제품X 정 규격C", "제품X", "제조사M", "ATC-01", "성분A, 성분B"),
    # ("제품X 정 규격D", ...)  <- 누락된 행
    ("제품Y 정", "제품Y", "제조사N", "ATC-02", "성분C"),
    ("제품Z 캡슐", "제품Z", "제조사K", "ATC-03", "성분D"),
]
MISSING_ROW = ("제품X 정 규격D", "제품X", "제조사M", "ATC-01", "성분A, 성분B")

ATC_GROUP = [("ATC-01", "복합제 시장"), ("ATC-02", "단일제 시장"), ("ATC-03", "기타 시장")]

RAW_SALES = [
    # datekey, product, manufacturer, filled_amt
    ("20260101", "제품X 정 규격A", "제조사M", 410_000_000),
    ("20260101", "제품X 정 규격B", "제조사M", 520_000_000),
    ("20260101", "제품X 정 규격C", "제조사M", 180_000_000),
    ("20260101", "제품X 정 규격D", "제조사M", 260_000_000),
    ("20260101", "제품Y 정", "제조사N", 900_000_000),
    ("20260101", "제품Z 캡슐", "제조사K", 300_000_000),
]


def build(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS stg_product_master;
        DROP TABLE IF EXISTS map_atc_group;
        DROP TABLE IF EXISTS raw_market_sales;
        DROP TABLE IF EXISTS fct_market_sales;
        CREATE TABLE stg_product_master (product TEXT, brand TEXT, manufacturer TEXT, atc TEXT, ingredient TEXT);
        CREATE TABLE map_atc_group (atc TEXT, item_class_group TEXT);
        CREATE TABLE raw_market_sales (datekey TEXT, product TEXT, manufacturer TEXT, filled_amt INTEGER);
        """
    )
    conn.executemany("INSERT INTO stg_product_master VALUES (?,?,?,?,?)", MASTER)
    conn.executemany("INSERT INTO map_atc_group VALUES (?,?)", ATC_GROUP)
    conn.executemany("INSERT INTO raw_market_sales VALUES (?,?,?,?)", RAW_SALES)
    conn.commit()


def rebuild_fct(conn: sqlite3.Connection) -> None:
    """Product → Ingredient/ATC → ItemClassGroup 순으로 붙여 FCT 를 다시 만든다 (전체 재생성)."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS fct_market_sales;
        CREATE TABLE fct_market_sales AS
        SELECT r.datekey, r.product, p.brand, r.manufacturer, p.atc, p.ingredient,
               g.item_class_group, r.filled_amt
        FROM raw_market_sales r
        LEFT JOIN stg_product_master p ON p.product = r.product
        LEFT JOIN map_atc_group g      ON g.atc = p.atc;
        """
    )
    conn.commit()


def brand_summary(conn: sqlite3.Connection, brand_like: str = "제품X%") -> list[tuple]:
    """실무 검증 쿼리와 같은 형태: 제품·브랜드·ATC·분류별 금액(백만)."""
    return conn.execute(
        """
        SELECT product, brand, manufacturer, atc, item_class_group,
               ROUND(SUM(filled_amt) / 1000000.0, 0) AS amt_m
        FROM fct_market_sales
        WHERE datekey = '20260101' AND product LIKE ?
        GROUP BY product, brand, manufacturer, atc, item_class_group
        ORDER BY amt_m DESC
        """,
        (brand_like,),
    ).fetchall()


# ---------------------------------------------------------------------------
# 탐지 쿼리 (재현본에서 추가한 점검 — 실무 적용 아님)
# ---------------------------------------------------------------------------

ORPHAN_SQL = """
SELECT r.product, r.manufacturer, SUM(r.filled_amt) AS amt
FROM raw_market_sales r
LEFT JOIN stg_product_master p ON p.product = r.product
WHERE p.product IS NULL
GROUP BY r.product, r.manufacturer
ORDER BY amt DESC
"""

UNCLASSIFIED_SQL = """
SELECT COALESCE(SUM(CASE WHEN item_class_group IS NULL THEN filled_amt END), 0) AS unclassified_amt,
       SUM(filled_amt) AS total_amt
FROM fct_market_sales
"""


def orphans(conn: sqlite3.Connection) -> list[tuple]:
    return conn.execute(ORPHAN_SQL).fetchall()


def unclassified_ratio(conn: sqlite3.Connection) -> float:
    u, t = conn.execute(UNCLASSIFIED_SQL).fetchone()
    return round(u / t, 4) if t else 0.0


def apply_fix(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO stg_product_master VALUES (?,?,?,?,?)", MISSING_ROW)
    conn.commit()
    rebuild_fct(conn)


if __name__ == "__main__":
    c = sqlite3.connect(":memory:")
    build(c)
    rebuild_fct(c)
    print("수정 전", brand_summary(c), orphans(c), unclassified_ratio(c))
    apply_fix(c)
    print("수정 후", brand_summary(c), orphans(c), unclassified_ratio(c))
