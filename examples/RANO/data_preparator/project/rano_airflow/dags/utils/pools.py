from airflow.models import Pool
import os

NIFTI_POOL = Pool.create_or_update_pool(
    name="NIfTI Conversion Pool",
    slots=os.getenv("NIFTI_POOL_SLOTS") or 10,
    description="Limits the execution of NIfTI Conversion tasks to the number assigned to the NIFTI_POOL_SLOTS environment variable. "
    "If the variable is not set, the default limit is 10.",
    include_deferred=False,
)

EXTRACTION_POOL = Pool.create_or_update_pool(
    name="Brain/Tumor Extraction Pool",
    slots=os.getenv("EXTRACTION_POOL_SLOTS") or 5,
    description="Limits the execution of Brain Extraction and Tumor Extraction tasks to the number assigned to the EXTRACTION_POOL_SLOTS environment variable. "
    "If the variable is not set, the default limit is 5.",
    include_deferred=False,
)
