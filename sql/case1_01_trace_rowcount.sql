-- 케이스 1 추적 쿼리 (T-SQL, Synapse Dedicated SQL Pool)
-- 실무에서 사용한 쿼리를 익명화한 것. 테이블·컬럼 이름은 더미.

-- 1) FCT 구성 쿼리가 쓰는 내부 뷰의 행 수 (실무: 1억 건 이상 확인)
SELECT COUNT_BIG(*) AS view_rows
FROM dbo.v_fct_input;

-- 2) DIM 이 비즈니스 키 기준 1:1 인지
SELECT COUNT(*)                  AS total_cnt,
       COUNT(DISTINCT cust_code) AS distinct_cnt
FROM dbo.dim_customer;

-- 3) 키별 중복 수 (실무: 고객당 약 10~14배, 완전 동일 행 복제)
SELECT cust_code, COUNT(*) AS cnt
FROM dbo.dim_customer
GROUP BY cust_code
HAVING COUNT(*) > 1
ORDER BY cnt DESC;

-- 4) 원천 STG 도 중복인지 (실무: total_cnt = distinct_cnt → STG 는 정상)
--    원천 컬럼명은 ERP 표준 필드명 대신 더미 사용
SELECT COUNT(*)                  AS total_cnt,
       COUNT(DISTINCT cust_code) AS distinct_cnt
FROM dbo.stg_customer;
-- 결론: STG → DIM 적재 단계에서 중복이 생긴다 → 파이프라인·프로시저 확인으로 이동
