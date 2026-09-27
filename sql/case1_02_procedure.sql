-- 케이스 1: Truncate 프로시저 형태 (익명화·단순화한 예시, 원본 코드 아님)
-- 실무에서 확인한 사실: 프로시저 파라미터는 @TableName1, @TableName2 였고
--                     파이프라인 Stored Procedure 활동은 이름을 'TableName' 으로 넘기고 있었다.
-- 아래 본문(동적 SQL, 기본값)은 설명을 위한 예시다.

CREATE PROCEDURE dbo.usp_truncate_table
    @TableName1 NVARCHAR(100),
    @TableName2 NVARCHAR(100) = NULL
AS
BEGIN
    DECLARE @sql NVARCHAR(400);

    SET @sql = N'TRUNCATE TABLE dbo.' + QUOTENAME(@TableName1) + N';';
    EXEC sp_executesql @sql;

    IF @TableName2 IS NOT NULL
    BEGIN
        SET @sql = N'TRUNCATE TABLE dbo.' + QUOTENAME(@TableName2) + N';';
        EXEC sp_executesql @sql;
    END
END;

-- 파이프라인 Stored Procedure 활동의 파라미터 (JSON 일부, 익명화)
--   수정 전: "storedProcedureParameters": { "TableName":  { "value": "dim_customer", "type": "String" } }
--   수정 후: "storedProcedureParameters": { "TableName1": { "value": "dim_customer", "type": "String" } }
