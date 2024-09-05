from dataclasses import dataclass
from typing import Iterator, Optional
import pandas as pd
from katalyst_core.dataset.generate_steps import dataset_part_to_steps
from katalyst_core.dataset.part import DatasetPart
import math

DATASET_DIR_PATH = "storage/dataset/"
DATASET_PATH = "storage/dataset/dataset.csv"
DATASET_STEPS_PATH = "storage/dataset/steps.csv"
FILES_PATH = "storage/dataset/files/"


@dataclass
class DatasetStep:
    code_before: str
    request: str
    edits: str
    parent_id: int


def dataframe_to_dataset_part(row: pd.Series) -> DatasetPart:
    files = []
    if isinstance(row["files"], str) and row["files"]:
        files = row["files"].split(";")

    return DatasetPart(
        row["id"],
        row["name"],
        row["description"],
        row["code"],
        row["backend"],
        files,
        row["author"],
        row["created_at"],
        None if math.isnan(float(row["program_id"])) else int(row["program_id"]),
    )


def read_dataset(only_backends: Optional[list[str]] = None) -> Iterator[DatasetPart]:
    df = pd.read_csv(DATASET_PATH)

    if only_backends:
        df = df[df["backend"].isin(only_backends)]

    for _, row in df.iterrows():
        yield dataframe_to_dataset_part(row)


def get_authors() -> list[str]:
    df = pd.read_csv(DATASET_PATH)
    return df["author"].unique().tolist()


def get_parts_by_author(author: str) -> list[DatasetPart]:
    df = pd.read_csv(DATASET_PATH)
    author_df = df[df["author"] == author]
    return [dataframe_to_dataset_part(row) for _, row in author_df.iterrows()]


def add_part(part: DatasetPart):
    df = pd.read_csv(DATASET_PATH)
    part_dict = vars(part)
    part_dict["files"] = ";".join(part.files)
    part_dict["id"] = df["id"].max() + 1 if not df.empty else 1
    new_row = pd.DataFrame([part_dict])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DATASET_PATH, index=False)


def delete_part(part_id: int):
    df = pd.read_csv(DATASET_PATH)
    df = df[df["id"] != part_id]
    df.to_csv(DATASET_PATH, index=False)


def edit_part(part_id: int, new_part: DatasetPart):
    df = pd.read_csv(DATASET_PATH)
    df = df[df["id"] != part_id]
    new_part_dict = vars(new_part)
    new_part_dict["files"] = ";".join(new_part.files)
    new_part_dict["id"] = part_id
    new_row = pd.DataFrame([new_part_dict])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DATASET_PATH, index=False)


def read_steps_dataset(
    only_backends: Optional[list[str]] = None,
) -> Iterator[DatasetStep]:
    steps_df = pd.read_csv(DATASET_STEPS_PATH)
    parts_df = pd.read_csv(DATASET_PATH)

    if only_backends:
        parts_df = parts_df[parts_df["backend"].isin(only_backends)]

    merged_df = pd.merge(steps_df, parts_df[["id"]], left_on="parent_id", right_on="id")

    for _, row in merged_df.iterrows():
        yield DatasetStep(
            row["code_before"], row["request"], row["edits"], row["parent_id"]
        )


def add_steps_from_part(index: int, part: DatasetPart):
    df1, df2 = dataset_part_to_steps(index, part)
    existing_steps_df = pd.read_csv(DATASET_STEPS_PATH)
    steps_df = pd.concat([existing_steps_df, df1, df2], ignore_index=True)
    steps_df.to_csv(DATASET_STEPS_PATH, index=False)


def delete_steps_from_part(index: int):
    df = pd.read_csv(DATASET_STEPS_PATH)
    df = df[df["parent_id"] != index]
    df.to_csv(DATASET_STEPS_PATH, index=False)
