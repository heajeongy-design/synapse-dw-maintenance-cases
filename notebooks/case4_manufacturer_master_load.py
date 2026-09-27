# Synapse Spark 노트북 — 제조사 마스터 Excel 적재 (케이스 4)
# 익명화·발췌본. 스토리지 계정·컨테이너·연결 서비스 이름은 더미이며 비밀값은 코드에 두지 않는다.
# 이 파일은 Synapse 밖에서 실행되지 않는다 (TokenLibrary, mssparkutils 는 Synapse 전용).

# ---------------------------------------------------------------------------
# 수정 전
# ---------------------------------------------------------------------------
# 파이프라인: Get Metadata(폴더) → FilterFiles(.xlsx) → Notebook(FILE_NAME = @activity('FilterFiles').output.value[0].name)
#
# FILE_PATH = "<upload-container>/01_Master/04_Manufacturer"     # 실제 폴더는 11_Master 였다
# FILE_PATH = 'abfss://{}/'.format(FILE_PATH)                   # abfss 축약 경로를 pandas 로 직접 읽음
# df = pd.read_excel(FILE_PATH + FILE_NAME)

# ---------------------------------------------------------------------------
# 수정 후
# ---------------------------------------------------------------------------
import fsspec
import pandas as pd
from notebookutils import mssparkutils  # Synapse 전용
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# 파라미터 셀 (값은 더미)
FILE_PATH = "<upload-container>/11_Master/04_Manufacturer"
account_name = "<storage-account>"
linked_service_name = "<linked-service>"

upload_container_name, _, rel_path = FILE_PATH.partition("/")  # 컨테이너 / 상대 경로 분리

# 1) SAS 는 연결 서비스에서 받아온다 (코드·파라미터에 비밀값을 두지 않음)
sas_key = TokenLibrary.getConnectionString(linked_service_name)  # noqa: F821  (Synapse 전용)
blob_sas_token = "<blob-sas-token>"  # 폴더 조회용 SAS. 획득 방식은 이 발췌에 포함하지 않음

# 2) 폴더 조회: wasbs 경로 + Spark 설정에 SAS 등록
spark.conf.set(
    f"fs.azure.sas.{upload_container_name}.{account_name}.blob.core.windows.net",
    blob_sas_token,
)
folder_path = f"wasbs://{upload_container_name}@{account_name}.blob.core.windows.net/{rel_path}/"

# 3) 파일 선택을 노트북 안으로: .xlsx 중 Excel 임시 파일(~$)은 제외
file_list = mssparkutils.fs.ls(folder_path)
excel_files = [f.name for f in file_list if f.name.endswith(".xlsx") and not f.name.startswith("~$")]
file_name = excel_files[0]

# 4) 파일 읽기: fsspec + SAS
file_url = f"abfss://{upload_container_name}/{rel_path}/{file_name}"
fsspec_handle = fsspec.open(file_url, account_name=account_name, sas_token=sas_key)
with fsspec_handle.open() as excel_file:
    df_pandas = pd.read_excel(excel_file)  # 이후 변환·적재 셀은 발췌에서 생략
