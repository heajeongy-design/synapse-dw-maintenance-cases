# synapse-dw-maintenance-cases

**운영 중인 Azure Synapse 기반 영업 DW 유지보수 — 장애 원인 분석과 개선 사례**

| | |
|---|---|
| 기간 | 2025.12 ~ 2026.03 |
| 역할 | Data Engineer — 운영 중 DW 유지보수 (단독 수행) |
| 도메인 | 제약사 영업 데이터 (회사·제품·테이블·경로 이름은 익명화) |
| 스택 | Azure Synapse Analytics (Pipeline, Spark 노트북), Dedicated SQL Pool (T-SQL, 저장 프로시저), Azure Analysis Services, Power BI, Blob Storage |

> 이미 구축된 시스템(구축: 타 인력)의 유지보수 기록이다. 새로 만든 시스템이 아니라 **운영 중 발생한 문제의 원인을 찾아 고친 사례**를 정리했다.
> 실제 회사 데이터·코드·연결 정보는 들어 있지 않다. 코드는 익명화 발췌본과, 로컬에서 실행되는 재현 코드다.

## 사례

| # | 사례 | 증상 → 원인 | 결과 | 재현 |
|---|---|---|---|---|
| 1 | [DIM 누적 적재 → AAS Refresh OOM](docs/case1_dim_accumulation.md) | Refresh 메모리 부족, 내부 뷰 1억 건 이상 → 고객 DIM 10~14배 복제 → 저장 프로시저 파라미터 이름 불일치로 Truncate 미수행 | 기본 등급 S1 에서 정상 Refresh, Refresh 마다 하던 S4 수동 Scale-Up 제거 | 로컬 실행 검증 |
| 2 | [제품 마스터 누락 → 매출 분류 불일치](docs/case2_master_missing.md) | 특정 브랜드 금액·분류 불일치 → 제품 마스터 4개 규격 중 1개 누락 | 마스터 보완·재생성으로 매핑 정상화 | 로컬 실행 검증 |
| 3 | [Excel 스키마 자동 추론 실패](docs/case3_schema_inference.md) | 제품 마스터 적재 실패 → pandas → Spark 변환 시 섞인 타입 추론 | 명시적 StringType 스키마로 안정 적재 | CI 실행 후 기록 |
| 4 | [Spark 런타임 변경 대응 리팩토링](docs/case4_runtime_refactor.md) | 3.2 → 3.3 변경 시 스토리지 접근 오류 가능성, 코드 경로 ≠ 운영 경로 | SAS 인증, 파일 탐색 노트북 내부화, 경로 수정 | 문서만 |

공통점: **증상이 보인 곳과 원인이 있는 곳이 달랐다.** 결과 테이블에서 입력 쪽으로 한 단계씩 거슬러 올라가며 각 단계가 정상인지 쿼리로 확인했다. → [대상 시스템과 담당 범위](docs/00_system_overview.md)

## 상태 표시

| 내용 | 상태 |
|---|---|
| 사례 1~4 의 증상·원인·조치 | 실무 수행 |
| 사례 1·2 재현과 테스트 | 구현 및 실행 검증 완료 (로컬, 합성 데이터) |
| 사례 3 재현과 테스트 | 구현, CI 실행 후 결과 기록 |
| 재발 방지 장치 (파라미터 검사, 키 유일성 검사, 누락 탐지 쿼리) | **재현 과정에서 작성한 제안 — 실무 적용 아님** |
| 수정 후 실무 행 수·Refresh 시간, 비용 절감액 | 기록 없음 (적지 않음) |

## 실행

```bash
make test         # 사례 1·2 테스트 (Python 3.11 표준 라이브러리만), 사례 3 은 pyspark 가 있을 때만
make repro        # 사례 1·2 재현 → results/
make setup-spark  # pyspark 설치 (Java 17 필요)
make repro-spark  # 사례 3 재현 → results/
```

## 구조

```
docs/        사례 문서, 대상 시스템, 5분 설명·예상 질문
sql/         추적·탐지·점검 쿼리 (T-SQL, 익명화)
notebooks/   Synapse 노트북 수정 전/후 발췌 (익명화, Synapse 밖에서 실행 불가)
repro/       로컬 재현 코드 (SQLite, PySpark)
tests/       재현 테스트
results/     실제 실행 결과만
```
