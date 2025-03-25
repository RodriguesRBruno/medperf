import os
import yaml
import pandas as pd
from typing import List
import math

from .dset_stage import DatasetStage
from .utils import get_id_tp, cleanup_storage, get_subdirectories
from .mlcube_constants import DONE_STAGE_STATUS
from .constants import INTERIM_FOLDER, TUMOR_MASK_FOLDER


def row_to_path(row: pd.Series) -> str:
    id = row["SubjectID"]
    tp = row["Timepoint"]
    return os.path.join(id, tp)


class SplitStage(DatasetStage):
    def __init__(
        self,
        params: str,
        data_path: str,
        labels_path: str,
        staging_folders: List[str],
        base_finalized_dir: str,
    ):
        self.params = params
        self.data_path = data_path
        self.labels_path = labels_path
        self.split_csv_path = os.path.join(data_path, "splits.csv")
        self.train_csv_path = os.path.join(data_path, "train.csv")
        self.val_csv_path = os.path.join(data_path, "val.csv")
        self.staging_folders = staging_folders
        self.base_finalized_dir = base_finalized_dir

    @property
    def name(self) -> str:
        return "Generate splits"

    @property
    def status_code(self) -> int:
        return DONE_STAGE_STATUS

    def could_run(self, report: pd.DataFrame) -> bool:
        split_exists = os.path.exists(self.split_csv_path)
        if split_exists:
            # This stage already ran
            return False

        for index in report.index:
            id, tp = get_id_tp(index)
            case_data_path = os.path.join(self.data_path, id, tp)
            case_labels_path = os.path.join(self.labels_path, id, tp)
            data_exists = os.path.exists(case_data_path)
            labels_exist = os.path.exists(case_labels_path)

            if not data_exists or not labels_exist:
                # Some subjects are not ready
                return False

        return True

    def __report_success(self, report: pd.DataFrame) -> pd.DataFrame:
        from filelock import SoftFileLock
        from .env_vars import REPORT_LOCK
        from .utils import load_report, write_report

        with SoftFileLock(REPORT_LOCK, timeout=-1) as lock:
            if report is None:
                report = load_report()

            report["status"] = self.status_code
            write_report(report)

        return report

    def _find_finalized_subjects(self):
        subject_and_timepoint_list = []

        candidate_subjects = get_subdirectories(self.base_finalized_dir)
        for candidate_subject in candidate_subjects:
            subject_path = os.path.join(self.base_finalized_dir, candidate_subject)
            timepoint_dirs = get_subdirectories(subject_path)

            for timepoint in timepoint_dirs:
                timepoint_complete_path = os.path.join(subject_path, timepoint)
                finalized_path = os.path.join(
                    timepoint_complete_path, TUMOR_MASK_FOLDER, "finalized"
                )
                try:
                    path_exists = os.path.exists(finalized_path)
                    path_is_dir = os.path.isdir(finalized_path)
                    only_one_case = len(os.listdir(finalized_path)) == 1
                    if path_exists and path_is_dir and only_one_case:
                        subject_timepoint_dict = {
                            "SubjectID": candidate_subject,
                            "Timepoint": timepoint,
                        }
                        subject_and_timepoint_list.append(subject_timepoint_dict)
                except (FileNotFoundError, OSError):
                    pass
        return subject_and_timepoint_list

    def execute(self, report: pd.DataFrame = None) -> pd.DataFrame:
        with open(self.params, "r") as f:
            params = yaml.safe_load(f)

        seed = params["seed"]
        train_pct = params["train_percent"]

        finalized_subjects = self._find_finalized_subjects()
        print(f"{finalized_subjects=}")
        split_df = pd.DataFrame(finalized_subjects)
        print(split_df)
        subjects = split_df["SubjectID"].drop_duplicates()
        subjects = subjects.sample(frac=1, random_state=seed)
        train_size = math.floor(len(subjects) * train_pct)

        train_subjects = subjects.iloc[:train_size]
        val_subjects = subjects.iloc[train_size:]

        train_mask = split_df["SubjectID"].isin(train_subjects)
        val_mask = split_df["SubjectID"].isin(val_subjects)

        split_df.loc[train_mask, "Split"] = "Train"
        split_df.loc[val_mask, "Split"] = "Val"

        split_df.to_csv(self.split_csv_path, index=False)

        # Generate separate splits files with relative path
        split_df["path"] = split_df.apply(row_to_path, axis=1)

        split_df.loc[train_mask].to_csv(self.train_csv_path, index=False)
        split_df.loc[val_mask].to_csv(self.val_csv_path, index=False)

        report = self.__report_success(report)
        cleanup_storage(self.staging_folders)

        return report, True
