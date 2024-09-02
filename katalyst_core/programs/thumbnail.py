from typing import Optional
from loguru import logger
from katalyst_core.algorithms.stl_to_pics.render import render
from katalyst_core.programs.id import ProgramId
from katalyst_core.programs.storage import program_stl_path, program_thumbnail_path


def program_to_thumbnail(program_id: ProgramId) -> Optional[str]:
    stl_path = program_stl_path(program_id)
    thumbnail_path = program_thumbnail_path(program_id)
    try:
        render(
            [stl_path],
            [(0, 0, 0)],
            [(0.97, 0.94, 1.0)],
            [
                ((0, 0, 1), (0.7, 0.7, 0.7), "thumbnail"),
            ],
            thumbnail_path,
            prefix="",
            transparent_background=True,
        )
    except Exception as e:
        logger.error(f"Error generating thumbnail for {program_id}: {e}")
        return None
    logger.info(f"Generated thumbnail for {program_id} at {thumbnail_path}")
    return thumbnail_path
