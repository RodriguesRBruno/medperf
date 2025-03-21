"""MLCube handler file"""

import typer
import os
from stages.mlcube_constants import (
    OUT_CSV,
    VALID_PATH,
    PREP_PATH,
    BRAIN_PATH,
    TUMOR_PATH,
    BRAIN_STAGE_STATUS,
    TUMOR_STAGE_STATUS,
    TUMOR_BACKUP_PATH,
)
from stages.constants import INTERIM_FOLDER

app = typer.Typer()

WORKSPACE_DIR = os.getenv("WORKSPACE_DIRECTORY")
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
INPUT_DIR = os.path.join(WORKSPACE_DIR, "input_data")


def _get_data_csv_dir(subject_subdir):
    return os.path.join(DATA_DIR, "csv", subject_subdir)


def _get_data_csv_filepath(subject_subdir):
    csv_dir = _get_data_csv_dir(subject_subdir)
    return os.path.join(csv_dir, OUT_CSV)


@app.command("make_csv")
def prepare(
    subject_subdir: str = typer.Option(..., "--subject-subdir"),
):
    from stages.get_csv import (
        AddToCSV,
    )

    output_csv_dir = _get_data_csv_dir(subject_subdir)
    os.makedirs(output_csv_dir, exist_ok=True)
    output_csv = _get_data_csv_filepath(subject_subdir)
    out_dir = os.path.join(DATA_DIR, VALID_PATH)
    csv_creator = AddToCSV(
        input_dir=INPUT_DIR,
        output_csv=output_csv,
        out_dir=out_dir,
        prev_stage_path=INPUT_DIR,  # TODO validate this
    )
    csv_creator.execute(subject_subdir)
    print(output_csv)


@app.command("convert_nifti")
def convert_nifti(
    subject_subdir: str = typer.Option(..., "--subject-subdir"),
):
    from stages.nifti_transform import NIfTITransform

    csv_path = _get_data_csv_filepath(subject_subdir)
    output_path = os.path.join(DATA_DIR, PREP_PATH)
    metadata_path = os.path.join(DATA_DIR, "metadata")
    os.makedirs(output_path, exist_ok=True)
    os.makedirs(metadata_path, exist_ok=True)

    nifti_transform = NIfTITransform(
        data_csv=csv_path,
        out_path=output_path,
        prev_stage_path=INPUT_DIR,  # TODO validate this
        metadata_path=metadata_path,
        data_out=DATA_DIR,
    )
    nifti_transform.execute(subject_subdir)
    print(output_path)


@app.command("extract_brain")
def extract_brain(
    subject_subdir: str = typer.Option(..., "--subject-subdir"),
):
    from stages.extract import Extract

    csv_path = _get_data_csv_filepath(subject_subdir)
    output_path = os.path.join(DATA_DIR, BRAIN_PATH)
    prev_path = os.path.join(DATA_DIR, PREP_PATH)
    os.makedirs(output_path, exist_ok=True)

    brain_extract = Extract(
        data_csv=csv_path,
        out_path=output_path,
        subpath=INTERIM_FOLDER,
        prev_stage_path=prev_path,
        prev_subpath=INTERIM_FOLDER,
        func_name="extract_brain",
        status_code=BRAIN_STAGE_STATUS,
    )
    brain_extract.execute(subject_subdir)
    print(output_path)


@app.command("extract_tumor")
def extract_tumor(
    subject_subdir: str = typer.Option(..., "--subject-subdir"),
):
    from stages.extract_nnunet import ExtractNnUNet

    csv_path = _get_data_csv_filepath(subject_subdir)
    output_path = os.path.join(DATA_DIR, TUMOR_PATH)
    prev_path = os.path.join(DATA_DIR, BRAIN_PATH)
    os.makedirs(output_path, exist_ok=True)

    models_path = os.path.join(WORKSPACE_DIR, "additional_files", "models")
    tmpfolder = os.path.join(WORKSPACE_DIR, ".tmp")
    cbica_tmpfolder = os.path.join(tmpfolder, ".cbicaTemp")
    os.environ["TMPDIR"] = tmpfolder
    os.environ["CBICA_TEMP_DIR"] = cbica_tmpfolder
    os.makedirs(tmpfolder, exist_ok=True)
    os.makedirs(cbica_tmpfolder, exist_ok=True)
    os.environ["RESULTS_FOLDER"] = os.path.join(models_path, "nnUNet_trained_models")
    os.environ["nnUNet_raw_data_base"] = os.path.join(tmpfolder, "nnUNet_raw_data_base")
    os.environ["nnUNet_preprocessed"] = os.path.join(tmpfolder, "nnUNet_preprocessed")
    tumor_extract = ExtractNnUNet(
        data_csv=csv_path,
        out_path=output_path,
        subpath=INTERIM_FOLDER,
        prev_stage_path=prev_path,
        prev_subpath=INTERIM_FOLDER,
        status_code=TUMOR_STAGE_STATUS,
    )
    tumor_extract.execute(subject_subdir)
    print(output_path)


@app.command("manual_annotation")
def manual_annotation(
    subject_subdir: str = typer.Option(..., "--subject-subdir"),
):
    # TODO formally implement/integrate with existing RANO tool! Currently just moves existing masks into finalized dir
    import shutil
    from stages.utils import copy_files

    prev_stage_segmentation_dir = os.path.join(
        DATA_DIR, TUMOR_PATH, "DataForQC", subject_subdir, "TumorMasksForQC"
    )
    finalized_dir = os.path.join(prev_stage_segmentation_dir, "finalized")
    print(f"{prev_stage_segmentation_dir=}")
    print(f"{finalized_dir=}")
    if os.path.exists(finalized_dir):
        print("finalized dir exists, deleting...")
        shutil.rmtree(finalized_dir, ignore_errors=True)
    copy_files(prev_stage_segmentation_dir, finalized_dir)

    from stages.manual import ManualStage

    csv_path = _get_data_csv_filepath(subject_subdir)
    prev_stage_path = os.path.join(DATA_DIR, TUMOR_PATH)
    backup_out = os.path.join(
        DATA_DIR, "labels", TUMOR_BACKUP_PATH
    )  # TODO validate this path

    manual_validation = ManualStage(
        data_csv=csv_path,
        out_path=prev_stage_path,
        prev_stage_path=prev_stage_path,
        backup_path=backup_out,
    )
    manual_validation.execute(subject_subdir)


@app.command("consolidation_stage")
def consolidation_stage(keep_files: bool = typer.Option(False, "--keep-files")):
    from stages.split import SplitStage
    from stages.utils import get_subdirectories

    labels_out = os.path.join(DATA_DIR, "labels")
    params_path = os.path.join(WORKSPACE_DIR, "parameters.yaml")
    base_finalized_dir = os.path.join(DATA_DIR, TUMOR_PATH, INTERIM_FOLDER)

    print(f"{keep_files=}")
    if keep_files:
        dirs_to_remove = []
    else:
        dirs_to_keep = {"metadata", "labels"}
        dirs_to_remove = [
            os.path.join(DATA_DIR, subdir)
            for subdir in get_subdirectories(DATA_DIR)
            if subdir not in dirs_to_keep
        ]

    split = SplitStage(
        params=params_path,
        data_path=DATA_DIR,
        labels_path=labels_out,
        staging_folders=dirs_to_remove,
        base_finalized_dir=base_finalized_dir,
    )
    split.execute()


if __name__ == "__main__":
    app()
