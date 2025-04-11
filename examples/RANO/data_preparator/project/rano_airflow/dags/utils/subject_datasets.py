from __future__ import annotations

from utils.utils import read_subject_directories
from airflow.datasets import Dataset

SUBJECT_TIMEPOINT_LIST = read_subject_directories()

SETUP_DATASET = Dataset("setup")
SUBJECT_NIFTI_DATASETS = {
    subject_slash_timepoint: Dataset(f"nifti/{subject_slash_timepoint}")
    for subject_slash_timepoint in SUBJECT_TIMEPOINT_LIST
}
SUBJECT_TUMOR_EXTRACT_DATASETS = {
    subject_slash_timepoint: Dataset(f"tumor_extract/{subject_slash_timepoint}")
    for subject_slash_timepoint in SUBJECT_TIMEPOINT_LIST
}
SUBJECT_DONE_DATASETS = {
    subject_slash_timepoint: Dataset(f"done/{subject_slash_timepoint}")
    for subject_slash_timepoint in SUBJECT_TIMEPOINT_LIST
}
ALL_DONE_DATASETS = list(SUBJECT_DONE_DATASETS.values())
