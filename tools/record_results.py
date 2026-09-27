"""재현 결과를 results/ 에 기록한다. 실행한 결과만 적는다 (합성 데이터).

  python -m tools.record_results            # 케이스 1, 2 (표준 라이브러리만)
  python -m tools.record_results --spark    # 케이스 3 추가 (pyspark 필요)
"""
from __future__ import annotations

import argparse
import datetime as dt
import platform
import sqlite3
import sys
from pathlib import Path

from repro import case1_dim_accumulation as c1
from repro import case2_master_missing as c2

OUT = Path(__file__).resolve().parents[1] / "results"


def header(title: str) -> list[str]:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return [
        f"# {title}",
        "",
        f"- 실행 시각: {now}",
        f"- 환경: Python {platform.python_version()} / {platform.system()}",
        "- 데이터: 합성 데이터 (실무 데이터 아님, 규모 비교 목적 아님)",
        "",
    ]


def case1() -> Path:
    conn = sqlite3.connect(":memory:")
    c1.build_source(conn)
    lines = header("케이스 1 재현 결과: Truncate 파라미터명 불일치 → DIM 누적")
    lines += ["| 단계 | Truncate | STG 행/고유 | DIM 행/고유 | 고객당 최대 중복 | 주문 라인 | 뷰(JOIN) 행 | 배수 | DQ 키 유일성 |", "|---|---|---|---|---|---|---|---|---|"]

    def row(label, log):
        m = c1.measure(conn)
        ok, _ = c1.dq_dim_key_unique(conn)
        lines.append(
            f"| {label} | {log[0][1]} | {m['stg_total']:,}/{m['stg_distinct']:,} | {m['dim_total']:,}/{m['dim_distinct']:,} | "
            f"{m['dim_max_dup']} | {m['fct_rows']:,} | {m['view_rows']:,} | {m['fanout']} | {'PASS' if ok else 'FAIL'} |"
        )

    row("정상 적재 (TableName1)", c1.run_pipeline(conn, {"TableName1": "dim_customer"}))
    bad = None
    for i in range(1, 13):
        bad = c1.run_pipeline(conn, {"TableName": "dim_customer"})
        if i in (1, 5, 12):
            row(f"잘못된 이름(TableName) {i}회차", bad)
    row("수정 후 1회 (TableName1)", c1.run_pipeline(conn, {"TableName1": "dim_customer"}))
    row("수정 후 재실행", c1.run_pipeline(conn, {"TableName1": "dim_customer"}))

    conn2 = sqlite3.connect(":memory:")
    c1.build_source(conn2)
    c1.run_pipeline(conn2, {"TableName1": "dim_customer"})
    stop_log = c1.run_pipeline(conn2, {"TableName": "dim_customer"}, on_fail="stop")
    ok2, msg2 = c1.dq_dim_key_unique(conn2)

    lines += [
        "",
        f"Truncate 실패 메시지(재현): `{bad[0][2]}`",
        "",
        "## 비교: 실패 시 다음 단계를 멈추는 경우 (재현본 가정)",
        "",
        f"- 활동 결과: {', '.join(f'{a}={s}' for a, s, _ in stop_log)}",
        f"- DQ: {'PASS' if ok2 else 'FAIL'} ({msg2}) → 누적 없음, 대신 DIM 이 갱신되지 않아 실패 알림으로 인지해야 함",
        "",
        "## 배포 전 파라미터 이름 검사 (재현본 추가)",
        "",
        f"- 수정 전 설정: {c1.check_param_names(c1.USP_TRUNCATE, {'TableName': 'dim_customer'})}",
        f"- 수정 후 설정: {c1.check_param_names(c1.USP_TRUNCATE, {'TableName1': 'dim_customer'}) or '문제 없음'}",
        "",
        "해석: 실무에서 확인한 현상(STG 는 정상, DIM 만 같은 배수로 복제, 내부 뷰 행 수 폭증)과 같은 형태가 재현된다.",
        "배수는 잘못된 설정으로 실행된 횟수 + 1 이다. 실무의 10~14배라는 값과 실행 횟수의 관계는 확인하지 않았다.",
    ]
    p = OUT / "case1_dim_accumulation.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def case2() -> Path:
    conn = sqlite3.connect(":memory:")
    c2.build(conn)
    c2.rebuild_fct(conn)
    lines = header("케이스 2 재현 결과: 제품 마스터 누락 → 분류 불일치")

    def table(title):
        nonlocal lines
        lines += [f"## {title}", "", "| 제품 | 브랜드 | ATC | 시장 분류 | 금액(백만) |", "|---|---|---|---|---:|"]
        for p, b, _m, a, g, amt in c2.brand_summary(conn):
            lines.append(f"| {p} | {b or '(없음)'} | {a or '(없음)'} | {g or '(없음)'} | {amt:,.0f} |")
        o = c2.orphans(conn)
        lines += ["", f"- 마스터에 없는 제품(탐지 쿼리): {[x[0] for x in o] or '없음'}", f"- 분류 없음 금액 비율: {c2.unclassified_ratio(conn):.2%}", ""]

    table("수정 전")
    c2.apply_fix(conn)
    table("마스터 보완 + FCT 재생성 후")
    p = OUT / "case2_master_missing.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def case3() -> Path:
    import pyspark
    from pyspark.sql import SparkSession

    from repro import case3_schema_inference as c3

    spark = SparkSession.builder.master("local[1]").appName("case3").getOrCreate()
    try:
        res = c3.run_matrix(spark)
    finally:
        spark.stop()
    import pandas as pd

    lines = header("케이스 3 재현 결과: pandas → Spark 변환 시 스키마 추론")
    lines += [f"- PySpark {pyspark.__version__}, pandas {pd.__version__}", "", "| Arrow | 경우 | 결과 | 상세 |", "|---|---|---|---|"]
    for r in res:
        detail = r["detail"].replace("|", "\\|")
        lines.append(f"| {r['arrow']} | {r['case']} | {r['status']} | {detail} |")
    lines += ["", "해석은 docs/case3_schema_inference.md 참고. Synapse 런타임의 기본 Arrow 설정과 버전은 이 환경과 다를 수 있다."]
    p = OUT / f"case3_schema_inference_spark{pyspark.__version__}.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spark", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    for f in (case1, case2) + ((case3,) if a.spark else ()):
        print("wrote", f())
    sys.exit(0)
