-- 케이스 2 (T-SQL). 제조사·제품·ATC 값은 더미.

-- 1) 실무 검증 쿼리 형태: 특정 브랜드의 월 금액을 제품·ATC·시장 분류별로 확인
SELECT product, brand, manufacturer, atc, item_class_group,
       ROUND(SUM(filled_amt) / 1000000.0, 0) AS amt_m
FROM dbo.fct_market_sales
WHERE datekey = '20260101'
  AND manufacturer LIKE N'%제조사M%'
  AND product      LIKE N'%제품X%'
GROUP BY product, brand, manufacturer, atc, item_class_group
ORDER BY amt_m DESC;

-- 2) 기준정보(제품 마스터)에 해당 제품이 있는지 (실무: 4개 규격 중 1개 누락 확인)
SELECT *
FROM dbo.stg_product_master
WHERE product LIKE N'%제품X%'
ORDER BY product;

-- 3) 탐지 쿼리 (재현 과정에서 작성한 제안 — 실무 적용 아님)
--    원천에는 있고 마스터에는 없는 제품을 금액 순으로. 월 적재 후 결과가 0행이어야 한다.
SELECT r.product, r.manufacturer, SUM(r.filled_amt) AS amt
FROM dbo.raw_market_sales r
LEFT JOIN dbo.stg_product_master p ON p.product = r.product
WHERE p.product IS NULL
GROUP BY r.product, r.manufacturer
ORDER BY amt DESC;
