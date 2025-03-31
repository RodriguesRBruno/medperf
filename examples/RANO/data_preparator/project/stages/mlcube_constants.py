RAW_PATH = "raw"
AUX_FILES_PATH = "auxiliary_files"
VALID_PATH = "validated"
PREP_PATH = "prepared"
BRAIN_PATH = "brain_extracted"
TUMOR_PATH = "tumor_extracted"
TUMOR_BACKUP_PATH = ".tumor_segmentation_backup"
OUT_CSV = "data.csv"
TRASH_PATH = ".trash"
INVALID_FILE = ".invalid.txt"
REPORT_FILE = "report.yaml"

# Subdirectories for manual validation
UNDER_REVIEW_PATH = "under_review"
FINALIZED_PATH = "finalized"

# JSON file (just true/false) for evaluating brain mask changes
BRAIN_MASK_CHANGED_FILE = "brain_mask_changed.json"

REPORT_STAGE_STATUS = 0
CSV_STAGE_STATUS = 1
NIFTI_STAGE_STATUS = 2
BRAIN_STAGE_STATUS = 3
TUMOR_STAGE_STATUS = 4
MANUAL_STAGE_STATUS = 5
COMPARISON_STAGE_STATUS = 6
CONFIRM_STAGE_STATUS = 7
DONE_STAGE_STATUS = 8
