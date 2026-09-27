# 케이스 4. Spark 런타임 변경 대응 — 레거시 적재 노트북 리팩토링

형식: 배경 → 수정 전 구조 → 수정 내용(무엇을, 왜) → 효과

## 배경

- 2023년에 구축된 제조사 마스터 적재 파이프라인은 오랫동안 실행 이력이 없었다.
- Spark 풀의 런타임이 **Spark 3.2 → 3.3** 으로 바뀌면 기존 `abfss://` 경로 직접 읽기 방식에서 스토리지 접근 오류가 날 수 있었다.
- 2026.03 유지보수 중 이 사실을 인지했고, 이후 추가 유지보수 요청으로 **오류가 발생하기 전에** 수정했다. (실제 오류가 난 뒤 고친 것이 아님)

## 수정 전 구조

```
파이프라인: 스토리지 폴더 조회 → FilterFiles(.xlsx) → 첫 번째 파일명 → Notebook(FILE_NAME)
노트북:     pd.read_excel('abfss://<컨테이너>/01_Master/04_Manufacturer/' + FILE_NAME)
```

- 매월 바뀌는 파일명을 하드코딩하지 않는 장점은 있었지만, 파일을 고르는 책임이 파이프라인 활동에 있어 노트북만 단독으로 실행할 수 없었다.

## 수정 내용

코드: [`notebooks/case4_manufacturer_master_load.py`](../notebooks/case4_manufacturer_master_load.py) (연결 정보는 더미)

| # | 수정 전 | 수정 후 | 이유 |
|---|---|---|---|
| 1 | `pd.read_excel(abfss://...)` 직접 읽기 | `fsspec.open()` + 연결 서비스에서 받은 SAS 로 인증 후 읽기 | 3.3 런타임에서 스토리지 인증 오류(`invalid authority`, `invalid container name`) 방지 |
| 2 | 파이프라인 FilterFiles 가 파일명을 노트북에 전달 | 노트북이 `mssparkutils.fs.ls()` 로 폴더를 조회해 `.xlsx` 선택 (Excel 임시 파일 `~$` 제외) | 파일을 찾는 **책임을 노트북으로 이동** → 노트북 단독 실행·재사용 가능. 기능을 새로 만든 것이 아님 |
| 3 | `abfss://` 경로로 폴더 조회 | `wasbs://<컨테이너>@<계정>.blob.core.windows.net` + `spark.conf.set()` 으로 SAS 등록 | 3.3 런타임에서 폴더 조회 안정성 |
| 4 | `.../01_Master/04_Manufacturer` | `.../11_Master/04_Manufacturer` | 코드 경로가 **실제 운영 스토리지 경로와 달랐다** |
| - | 전체 경로 문자열 | `FILE_PATH.partition("/")` 로 컨테이너와 상대 경로 분리 | 두 경로 형식(abfss, wasbs)에서 재사용 |

## 효과

1. 3.3 런타임에서 스토리지 접근 호환성 확보
2. SAS 인증으로 `invalid authority` / `container name` 오류 예방
3. 파일 탐색을 노트북 안으로 옮겨 파이프라인 의존도 감소, 노트북 단독 실행 가능
4. 매월 바뀌는 파일명에 수동 수정 불필요
5. 코드 경로와 실제 운영 경로 일치
6. 같은 방식을 쓰는 다른 마스터 적재 노트북(ATC 마스터)과 스토리지 접근 패턴 통일

## 재현

Synapse 전용 API(`TokenLibrary`, `mssparkutils`)에 의존하므로 로컬 재현은 하지 않았다. 문서와 익명화 코드만 둔다.
