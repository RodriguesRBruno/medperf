from __future__ import annotations

from utils import read_subject_directories
from airflow.datasets import Dataset
from datetime import datetime, timedelta

_SUBJECT_SUBDIRS = read_subject_directories()

YESTERDAY = datetime.today() - timedelta(days=1)

REPORT_DATASET = Dataset("report")

SUBJECT_TIMEPOINT_LIST = [
    f"{key}/{subvalue}" for key, value in _SUBJECT_SUBDIRS.items() for subvalue in value
]

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
