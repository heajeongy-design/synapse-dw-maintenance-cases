"""케이스 1 재현: Truncate 파라미터명 불일치 → DIM 누적 적재 → JOIN 행 폭증

원 환경: Synapse Pipeline(Stored Procedure 활동 → Copy 활동) → Dedicated SQL Pool → AAS Refresh
재현 환경: SQLite (표준 라이브러리만 사용). 테이블·컬럼 이름은 익명화했다.

재현 가정 (원 환경에서 확인하지 못한 부분)
- 원 파이프라인에서 Truncate 가 실패한 뒤에도 DIM 적재가 수행된 "활동 연결 방식"은 확인하지 못했다.
  DIM 이 10~14배로 쌓여 있었다는 사실만 확인했다. 재현본은 이 상태를
  on_fail="continue" 로 모델링하고, 비교용으로 on_fail="stop"(성공 시에만 다음 단계)도 둔다.
- 프로시저 시그니처: @TableName1 필수, @TableName2 선택(기본값 NULL).
  실무 수정이 "TableName → TableName1" 한 곳이었으므로 TableName2 는 필수가 아니었다고 본다.
"""
from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass, field

# ----------------------------------------------------------------------------
# 합성 데이터
# ----------------------------------------------------------------------------

def build_source(conn: sqlite3.Connection, n_customers: int = 1_000, n_orders: int = 20_000, seed: int = 7) -> None:
    rnd = random.Random(seed)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS stg_customer;
        DROP TABLE IF EXISTS dim_customer;
        DROP TABLE IF EXISTS fct_order_line;
        CREATE TABLE stg_customer (cust_code TEXT, cust_name TEXT, region TEXT);
        CREATE TABLE dim_customer (cust_code TEXT, cust_name TEXT, region TEXT);
        CREATE TABLE fct_order_line (order_no TEXT, cust_code TEXT, qty INTEGER, amt INTEGER);
        """
    )
    regions = ["R1", "R2", "R3", "R4"]
    cur.executemany(
        "INSERT INTO stg_customer VALUES (?,?,?)",
        [(f"C{i:05d}", f"CUSTOMER-{i:05d}", rnd.choice(regions)) for i in range(n_customers)],
    )
    cur.executemany(
        "INSERT INTO fct_order_line VALUES (?,?,?,?)",
        [
            (f"O{i:07d}", f"C{rnd.randrange(n_customers):05d}", q := rnd.randint(1, 20), q * rnd.randint(1_000, 50_000))
            for i in range(n_orders)
        ],
    )
    # 원 구조의 내부 뷰 역할: 주문 라인에 고객 DIM 을 붙인다 (FCT 구성 쿼리가 이 뷰를 사용)
    cur.executescript(
        """
        DROP VIEW IF EXISTS v_fct_input;
        CREATE VIEW v_fct_input AS
        SELECT f.order_no, f.cust_code, d.cust_name, d.region, f.qty, f.amt
        FROM fct_order_line f
        JOIN dim_customer d ON d.cust_code = f.cust_code;
        """
    )
    conn.commit()


# ----------------------------------------------------------------------------
# "저장 프로시저"와 파이프라인 실행기
# ----------------------------------------------------------------------------

class ActivityError(Exception):
    pass


@dataclass
class Procedure:
    name: str
    required: list[str]
    optional: list[str] = field(default_factory=list)

    def bind(self, params: dict[str, str]) -> dict[str, str | None]:
        """T-SQL 처럼 이름으로 파라미터를 묶는다. 모르는 이름·필수 누락은 오류."""
        allowed = set(self.required) | set(self.optional)
        unknown = [k for k in params if k not in allowed]
        if unknown:
            raise ActivityError(f"{self.name} has no parameter named {unknown}")
        missing = [k for k in self.required if k not in params]
        if missing:
            raise ActivityError(f"{self.name} expects parameter {missing}, which was not supplied")
        return {k: params.get(k) for k in self.required + self.optional}


USP_TRUNCATE = Procedure("usp_truncate_table", required=["TableName1"], optional=["TableName2"])


def run_truncate(conn: sqlite3.Connection, params: dict[str, str]) -> None:
    bound = USP_TRUNCATE.bind(params)
    for t in (bound["TableName1"], bound["TableName2"]):
        if t:
            conn.execute(f"DELETE FROM {t}")  # SQLite 에는 TRUNCATE 가 없다


def run_copy(conn: sqlite3.Connection, src: str, sink: str) -> int:
    cur = conn.execute(f"INSERT INTO {sink} SELECT * FROM {src}")
    return cur.rowcount


def run_pipeline(conn: sqlite3.Connection, sp_params: dict[str, str], on_fail: str = "continue") -> list[tuple[str, str, str]]:
    """Truncate(Stored Procedure) → Copy(STG → DIM). 활동별 (이름, 상태, 메시지) 목록을 돌려준다."""
    log: list[tuple[str, str, str]] = []
    try:
        run_truncate(conn, sp_params)
        log.append(("Truncate", "Succeeded", ""))
    except ActivityError as e:
        log.append(("Truncate", "Failed", str(e)))
        if on_fail == "stop":
            conn.commit()
            log.append(("CopyDim", "Skipped", "upstream failed"))
            return log
    n = run_copy(conn, "stg_customer", "dim_customer")
    log.append(("CopyDim", "Succeeded", f"{n} rows"))
    conn.commit()
    return log


# ----------------------------------------------------------------------------
# 진단 쿼리 (실무에서 사용한 검증 쿼리를 익명화한 것과 같은 형태)
# ----------------------------------------------------------------------------

def measure(conn: sqlite3.Connection) -> dict[str, float]:
    q = lambda sql: conn.execute(sql).fetchone()[0]
    dim_total = q("SELECT COUNT(*) FROM dim_customer")
    dim_distinct = q("SELECT COUNT(DISTINCT cust_code) FROM dim_customer")
    stg_total = q("SELECT COUNT(*) FROM stg_customer")
    stg_distinct = q("SELECT COUNT(DISTINCT cust_code) FROM stg_customer")
    fct = q("SELECT COUNT(*) FROM fct_order_line")
    view = q("SELECT COUNT(*) FROM v_fct_input")
    max_dup = q("SELECT COALESCE(MAX(c),0) FROM (SELECT COUNT(*) c FROM dim_customer GROUP BY cust_code)")
    view_amt = q("SELECT COALESCE(SUM(amt),0) FROM v_fct_input")
    fct_amt = q("SELECT SUM(amt) FROM fct_order_line")
    return {
        "stg_total": stg_total,
        "stg_distinct": stg_distinct,
        "dim_total": dim_total,
        "dim_distinct": dim_distinct,
        "dim_max_dup": max_dup,
        "fct_rows": fct,
        "view_rows": view,
        "fanout": round(view / fct, 3) if fct else 0,
        "amt_ratio": round(view_amt / fct_amt, 3) if fct_amt else 0,
    }


# ----------------------------------------------------------------------------
# 재발 방지 장치 (재현본에서 추가한 것 — 실무 적용 아님)
# ----------------------------------------------------------------------------

def check_param_names(proc: Procedure, pipeline_params: dict[str, str]) -> list[str]:
    """배포 전 검사: 파이프라인이 넘기는 이름이 프로시저 시그니처와 맞는지.
    실제 환경에서는 sys.parameters 조회로 같은 비교를 한다 (sql/case1_03_guard_param_check.sql)."""
    problems = []
    allowed = set(proc.required) | set(proc.optional)
    for k in pipeline_params:
        if k not in allowed:
            problems.append(f"unknown parameter '{k}' (procedure has {sorted(allowed)})")
    for k in proc.required:
        if k not in pipeline_params:
            problems.append(f"required parameter '{k}' not supplied")
    return problems


def dq_dim_key_unique(conn: sqlite3.Connection) -> tuple[bool, str]:
    """DIM 적재 직후, FCT/AAS Refresh 전에 실행하는 검사."""
    total, distinct = conn.execute("SELECT COUNT(*), COUNT(DISTINCT cust_code) FROM dim_customer").fetchone()
    ok = total == distinct
    return ok, f"dim_customer total={total} distinct={distinct}"


if __name__ == "__main__":
    conn = sqlite3.connect(":memory:")
    build_source(conn)
    first = run_pipeline(conn, {"TableName1": "dim_customer"})
    print("정상 초기 적재:", first, measure(conn))
    for i in range(12):
        run_pipeline(conn, {"TableName": "dim_customer"})
    print("잘못된 파라미터로 12회 실행 후:", measure(conn))
    print("DQ:", dq_dim_key_unique(conn))
    print(run_pipeline(conn, {"TableName1": "dim_customer"}))
    print("수정 후 1회 실행:", measure(conn))
