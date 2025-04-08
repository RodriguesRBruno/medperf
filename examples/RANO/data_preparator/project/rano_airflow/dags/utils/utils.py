import os
import yaml
from typing import Literal, Any

AIRFLOW_DATA_DIR = os.getenv("AIRFLOW_DATA_DIR")
INPUT_DATA_DIR = os.getenv("AIRFLOW_INPUT_DATA_DIR")


class ReportSummary:

    _REPORT_SUMMARY_FAILE = os.path.join(
        AIRFLOW_DATA_DIR, "report_summary.yaml"
    )  # TODO maybe use Workspace dir?

    def __init__(
        self,
        execution_status: Literal["running", "failure", "done"],
        progress_dict: dict[str, Any] = None,
    ):
        self.execution_status = execution_status
        self.progress_dict = progress_dict if progress_dict is not None else {}

    def to_dict(self):
        report_dict = {
            "execution_status": self.execution_status,
            "progress": self.progress_dict,
        }
        return report_dict

    def write_yaml(self):
        report_dict = self.to_dict()
        with open(self._REPORT_SUMMARY_FAILE, "w") as f:
            yaml.dump(
                report_dict,
                f,
                sort_keys=False,
            )


def create_legal_id(subject_slash_timepoint, restrictive=False):
    import re

    if restrictive:
        legal_chars = "A-Za-z0-9_-"
    else:
        legal_chars = "A-Za-z0-9_.~:+-"
    legal_id = re.sub(rf"[^{legal_chars}]", "_", subject_slash_timepoint)
    return legal_id


def read_subject_directories():

    subject_slash_timepoint_list = []

    for subject_id_dir in os.listdir(INPUT_DATA_DIR):
        subject_complete_dir = os.path.join(INPUT_DATA_DIR, subject_id_dir)

        for timepoint_dir in os.listdir(subject_complete_dir):
            subject_slash_timepoint_list.append(
                os.path.join(subject_id_dir, timepoint_dir)
            )

    return subject_slash_timepoint_list


def get_manual_review_directory(
    subject_slash_timepoint: str,
    review_type: Literal["tumor_extraction", "brain_mask"],
    review_state: Literal["under_review", "finalized"],
    include_host_path: bool = False,
):

    if review_type == "tumor_extraction":
        FILE_NAME = f"{'_'.join(subject_slash_timepoint.split(os.sep))}_tumorMask_model_0.nii.gz"
    elif review_type == "brain_mask":
        FILE_NAME = "brainMask_fused.nii.gz"
    else:
        raise ValueError(
            f'review_type must be either "tumor_extraction" or "brain_mask"!'
        )

    if include_host_path:
        # TODO proper way to get whole path in there
        BASE_DIR = os.path.join("/path/to/workspace", AIRFLOW_DATA_DIR[1:])
    else:
        BASE_DIR = AIRFLOW_DATA_DIR

    BASE_REVIEW_DIR = os.path.join(
        BASE_DIR,
        "manual_review",
        subject_slash_timepoint,
    )

    final_path = os.path.join(BASE_REVIEW_DIR, review_type, review_state, FILE_NAME)
    return final_path


def create_documentation_for_manual_steps(subject_slash_timepoint):
    TO_BE_REVIEWED_TUMOR_EXTRACTION_FILE = get_manual_review_directory(
        subject_slash_timepoint,
        "tumor_extraction",
        "under_review",
        include_host_path=True,
    )
    CONFIRMED_TUMOR_EXTRACTION_FILE = get_manual_review_directory(
        subject_slash_timepoint, "tumor_extraction", "finalized", include_host_path=True
    )

    TO_BE_REVIEWED_BRAIN_MASK_FILE = get_manual_review_directory(
        subject_slash_timepoint, "brain_mask", "under_review", include_host_path=True
    )
    CORRECTED_BRAIN_MASK_FILE = get_manual_review_directory(
        subject_slash_timepoint, "brain_mask", "finalized", include_host_path=True
    )

    brain_mask_review_doc = f"""
    #### BRAIN MASK REVIEW
    The automatic Brain Mask is located at **{TO_BE_REVIEWED_BRAIN_MASK_FILE}**. Please review it with the software of your preference.
    If the automatic Brain Mask is correct, no further action is required; please proceed to the Tumor Segmentation review below.
    If the automatic Brain Mask must be adjusted, please make the necessary corrections and save the corrected Brain Mask to **{CORRECTED_BRAIN_MASK_FILE}**.
    Note that this path is in the **finalized** directory, while the original (automatic) Brain Mask was in the **under_review** sub-directory. The pipeline
    will automatically detect the corrected file and proceed accordingly. Note that changing the Brain Mask will cause the pipeline to re-run the Brain
    Extraction and Tumor Extraction stages. The new tumor extraction will need to be manually approved in this DAG once it is ready."""

    tumor_segmentation_review_doc = f"""
    #### TUMOR SEGMENTATION REVIEW
    The automatic Tumor Segmentation is located at **{TO_BE_REVIEWED_TUMOR_EXTRACTION_FILE}**. Please review it with the software of your preference.
    If the automatic Tumor Segmentation must be adjusted, please make the necessary corrections and save the corrected Tumor Segmentation to **{CONFIRMED_TUMOR_EXTRACTION_FILE}**.
    Note that this path is in the **finalized** directory, while the original (automatic) Brain Mask was in the **under_review** sub-directory.
    If the automatic Tumor Segmentation does not need any corrections, it may simply be copied to the **finalized** subdirectory (that is, having a final
    path of **{CONFIRMED_TUMOR_EXTRACTION_FILE}**). Once the finalized Tumor Segmentation is detected, the pipeline will automatically proceed to the next stage.
    Note that the final stages in the pipeline, located in the FINISH DAG, will only run once all subjects are manually approved (that is, all the Manual Approval DAGs
    have completed)."""

    dag_doc = f"""
    This DAG requires manual intervention to be run to completion.
    Please review the automatic Brain Mask and automatic Tumor Segmentation generated by the Pipeline.

    {brain_mask_review_doc}

    {tumor_segmentation_review_doc}"""

    return brain_mask_review_doc, tumor_segmentation_review_doc, dag_doc
