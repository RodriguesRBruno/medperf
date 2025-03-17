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
)
from stages.constants import INTERIM_FOLDER, FINAL_FOLDER

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


if __name__ == "__main__":
    app()
