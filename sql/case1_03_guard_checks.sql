-- 케이스 1 재발 방지 점검 (재현 과정에서 작성한 제안 — 실무 적용 아님)

-- G1. 프로시저 시그니처 조회: 파이프라인이 넘기는 파라미터 이름과 비교한다.
--     배포 전 체크리스트 또는 CI 에서 파이프라인 JSON 의 storedProcedureParameters 키와 대조.
SELECT p.name AS param_name, t.name AS type_name, p.max_length, p.has_default_value
FROM sys.parameters p
JOIN sys.types t ON t.user_type_id = p.user_type_id
WHERE p.object_id = OBJECT_ID('dbo.usp_truncate_table')
ORDER BY p.parameter_id;

-- G2. DIM 적재 직후, FCT·AAS Refresh 전에 키 유일성 검사. 위반 시 THROW 로 파이프라인을 실패시킨다.
IF EXISTS (
    SELECT cust_code FROM dbo.dim_customer GROUP BY cust_code HAVING COUNT(*) > 1
)
    THROW 50001, 'dim_customer business key is not unique', 1;

-- G3. JOIN 배수 검사: 내부 뷰 행 수가 기준 Fact 행 수와 같아야 한다 (1:1 조인 가정).
SELECT
    (SELECT COUNT_BIG(*) FROM dbo.v_fct_input)     AS view_rows,
    (SELECT COUNT_BIG(*) FROM dbo.fct_order_line)  AS fact_rows;
