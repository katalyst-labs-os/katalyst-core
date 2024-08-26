import tempfile
import os
import glob

from katalyst_core.algorithms.stl_to_pics.render import render


def stl_to_pictures(stl_path: str) -> list[str]:
    temp_dir = tempfile.mkdtemp()
    stl_name = os.path.basename(stl_path).split(".")[0]
    render(
        [stl_path],
        [(0, 0, 0)],
        [(0.5, 0.5, 1.0)],
        [
            (
                (1, 0, 0),
                (0, 0.3, 1),
                "top",
            ),
            (
                (1, 0, 0),
                (0, 0.3, -1),
                "bottom",
            ),
            (
                (0, 0, 1),
                (0.3, 1, 0),
                "front",
            ),
            ((0, 0, 1), (-1, 0.3, 0), "left"),
        ],
        temp_dir,
        prefix=stl_name,
    )
    paths = glob.glob(os.path.join(temp_dir, f"{stl_name}_*.jpg"))
    return paths
