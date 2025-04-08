from utils.utils import read_subject_directories, create_legal_id

SUBJECT_TIMEPOINT_LIST = read_subject_directories()


def _make_dag_id_dict(id_str):
    return {
        subject: f"rano_{id_str}_{create_legal_id(subject)}"
        for subject in SUBJECT_TIMEPOINT_LIST
    }


SETUP = "rano_setup"
FINISH = "rano_end"
SUMMARIZER = "rano_summarizer"
NIFTI_CONVERSION = _make_dag_id_dict("nifti")
TUMOR_EXTRACTION = _make_dag_id_dict("tumor")
MANUAL_APPROVAL = _make_dag_id_dict("manual")
