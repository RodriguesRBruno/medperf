import os
from collections import defaultdict


def create_legal_id(subject_slash_timepoint, restrictive=False):
    import re

    if restrictive:
        legal_chars = "A-Za-z0-9_-"
    else:
        legal_chars = "A-Za-z0-9_.~:+-"
    legal_id = re.sub(rf"[^{legal_chars}]", "_", subject_slash_timepoint)
    return legal_id


def read_subject_directories():
    INPUT_DATA_DIR = os.getenv("AIRFLOW_INPUT_DATA_DIR")

    subject_id_to_timepoints = defaultdict(lambda: [])

    for subject_id_dir in os.listdir(INPUT_DATA_DIR):
        subject_complete_dir = os.path.join(INPUT_DATA_DIR, subject_id_dir)

        for timepoint_dir in os.listdir(subject_complete_dir):
            subject_id_timepoint_dir = os.path.join(subject_id_dir, timepoint_dir)
            subject_id_to_timepoints[subject_id_dir].append(timepoint_dir)

    return subject_id_to_timepoints
