import os
import sys

from katalyst_core.algorithms.stl_to_pics.render import render


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python script.py <stl_path (single stl file or directory of stl files)> <output_path (directory)> [prefix]"
        )
        sys.exit(1)

    stl_path = sys.argv[1]
    output_path = sys.argv[2]

    if os.path.isdir(stl_path):
        # Render all STL files in the input directory
        stl_files = [
            os.path.join(stl_path, f)
            for f in os.listdir(stl_path)
            if f.endswith(".stl")
        ]
        for stl_program_path in stl_files:
            stl_out_dirname = os.path.join(
                output_path, os.path.splitext(os.path.basename(stl_program_path))[0]
            )
            if not os.path.exists(stl_out_dirname):
                os.makedirs(stl_out_dirname)
            render(
                [stl_program_path],
                [(0, 0, 0)],
                [(0.5, 0.5, 1.0)],
                [
                    (
                        (1, 0, 0),
                        (
                            0.1,
                            0.1,
                            1,
                        ),
                        "top",
                    ),
                    (
                        (1, 0, 0),
                        (
                            0.1,
                            0.1,
                            -1,
                        ),
                        "bottom",
                    ),
                    (
                        (0, 0, 1),
                        (0.15, 1, 0),
                        "front",
                    ),
                    ((0, 0, 1), (-1, 0, 0), "left"),
                ],
                stl_out_dirname,
                prefix="",
            )
    else:
        # Render a single STL file to the output directory
        stl_out_dirname = os.path.join(
            output_path, os.path.splitext(os.path.basename(stl_path))[0]
        )
        if not os.path.exists(stl_out_dirname):
            os.makedirs(stl_out_dirname)
        render(
            [stl_path],
            [(0, 0, 0)],
            [(0.83, 0.7, 1.0)],
            [
                ((0, 0, 1), (0.7, 0.7, 0.3), "thumbnail"),
            ],
            stl_out_dirname,
            prefix="",
            transparent_background=True,
        )
