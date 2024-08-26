import os
import shutil

from katalyst_core.programs.id import ProgramId


def program_dir_path(program_id: ProgramId) -> str:
    return os.path.join("storage/programs/", program_id)


def program_stl_path(program_id: ProgramId) -> str:
    return os.path.join(program_dir_path(program_id), "render.stl")


def program_export_path(program_id: ProgramId, format: str) -> str:
    return os.path.join(program_dir_path(program_id), f"render.{format}")


def program_params_path(program_id: ProgramId) -> str:
    return os.path.join(program_dir_path(program_id), "params.json")


def program_script_path(program_id: ProgramId) -> str:
    return os.path.join(program_dir_path(program_id), "script.py")


def program_thumbnail_path(program_id: ProgramId) -> str:
    return os.path.join(program_dir_path(program_id), "thumbnail.png")


def program_delete(program_id: ProgramId) -> str:
    shutil.rmtree(program_dir_path(program_id), ignore_errors=True)
