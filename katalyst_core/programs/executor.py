from __future__ import annotations

import re
import subprocess

from typing import Optional

# import traceback
import os
import json

from loguru import logger

from katalyst_core.programs.id import ProgramId, new_program_id
from katalyst_core.programs.sanitize import sanitize_code
from katalyst_core.programs.parameters_postprocessing import (
    apply_params,
    extract_params,
)
from katalyst_core.programs.storage import (
    program_dir_path,
    program_export_path,
    program_params_path,
    program_script_path,
)
from katalyst_core.programs.thumbnail import program_to_thumbnail

preamble = """
from build123d import *
import build123d as bd
from bd_warehouse.thread import *
from bd_warehouse.pipe import *
from bd_warehouse.flange import *
from bd_warehouse.bearing import *
from bd_warehouse.fastener import *
from bd_warehouse.gear import *
from bd_warehouse.open_builds import *
import math
import numpy as np
import random
"""

EXECUTION_TIMEOUT_SEC = 40


def ensure_dir_exists(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)


def read_program_code(program_id: str) -> str:
    with open(program_script_path(program_id), "r") as script_file:
        return script_file.read()


def execute(
    program_id: ProgramId, params_dict: dict | None = None, export_format: str = "stl"
) -> tuple[str, bool]:
    if os.path.exists(program_export_path(program_id, export_format)):
        os.rename(
            program_export_path(program_id, export_format),
            program_export_path(program_id, export_format) + ".old",
        )

    code = read_program_code(program_id)

    if params_dict is not None:
        # logger.trace(f"New params to be applied: \n{params_dict}")
        code = apply_params(code, params_dict)
        # logger.trace(f"Code after applying params: \n{code}")

    if export_format != "stl":
        code = replace_export_function(code, export_format)
        # logger.trace(f"Code after replacing exportStl: \n{code}")

    temp_script_path = program_script_path(program_id) + ".tmp"
    logger.trace(f"Writing script to be executed to {temp_script_path}")
    with open(temp_script_path, "w") as file:
        file.write(code)

    success = False
    try:
        process = subprocess.Popen(
            ["python", os.path.basename(temp_script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=os.path.dirname(temp_script_path),
            universal_newlines=True,
        )
        output, _ = process.communicate(timeout=EXECUTION_TIMEOUT_SEC)
        success = os.path.exists(program_export_path(program_id, export_format))

        if not success:
            logger.info("Failed to execute script")
            logger.info(output)
            output = str(output)
            success = False

        if success:
            if os.path.exists(program_export_path(program_id, export_format) + ".old"):
                os.remove(program_export_path(program_id, export_format) + ".old")
            if export_format == "stl":
                program_to_thumbnail(program_id)
        else:
            if os.path.exists(program_export_path(program_id, export_format) + ".old"):
                os.rename(
                    program_export_path(program_id, export_format) + ".old",
                    program_export_path(program_id, export_format),
                )

    except subprocess.TimeoutExpired:
        process.kill()
        output = f"Error: The script execution timed out after {EXECUTION_TIMEOUT_SEC} seconds."
        success = False
    except Exception as e:
        logger.info("Failed to execute script")
        # logger.info(e)
        # logger.trace(traceback.format_exc())
        output = str(e)
        success = False

    return output, success


def execute_first_time(script: str) -> tuple[Optional[str], str, bool]:
    program_id = new_program_id()

    ensure_dir_exists(program_dir_path(program_id))

    with open(program_script_path(program_id), "w") as f:
        script = sanitize_code(script)
        # logger.trace(f"Sanitized script:\n{script}")
        script = fix_and_replace_filename(script, "render.stl")
        script = set_tolerance(script)
        # logger.trace(f"Fixed script:\n{script}")
        params = extract_params(script)
        with open(program_params_path(program_id), "w") as params_file:
            json.dump(params, params_file, indent=4)
        script = preamble + script
        f.write(script)

    output, success = execute(program_id, params)

    if not success:
        return None, output, False

    return program_id, output, True

def set_tolerance(code: str, tolerance=5) -> str:
    if ", tolerance=" in code:
        pattern = r'(.*tolerance=)(\d+(\.\d+)?)(.*)'
        replacement = r'\g<1>{}\g<4>'.format(tolerance)
        return re.sub(pattern, replacement, code, flags=re.DOTALL)
    
    pattern = r"(export_stl\(\s*[^,]+,\s*[^)]+)(\))"
    replacement = r"\g<1>, tolerance={}\g<2>".format(tolerance)
    return re.sub(pattern, replacement, code)


def fix_and_replace_filename(code: str, by: str) -> str:
    lines = code.split("\n")
    modified_lines = []
    last_assignment = None
    replaced = False

    # First pass: look for <myvar> = "<myname>.stl"
    for line in lines:
        stripped_line = line.strip()
        var_name = None
        if "=" in stripped_line:
            parts = stripped_line.split("=")
            if len(parts) == 2:
                value_part = parts[1].strip()

                if (value_part.startswith('"') and value_part.endswith('.stl"')) or (
                    value_part.startswith("'") and value_part.endswith(".stl'")
                ):
                    var_name = parts[0].strip()
                    modified_value_part = f'"{by}"'
                    line = f"filename = {modified_value_part}"
                    replaced = True

        if var_name is not None and replaced and "export_stl(" in stripped_line:
            line = line.replace(var_name, "filename")

        modified_lines.append(line)

    # If no replacement was done, check for export_stl("<myname>.stl")
    if not replaced:
        new_modified_lines = []
        for line in modified_lines:
            stripped_line = line.strip()
            if "export_stl(" in stripped_line:
                start_quote = (
                    stripped_line.find('"')
                    if '"' in stripped_line
                    else stripped_line.find("'")
                )
                end_quote = (
                    stripped_line.rfind('"')
                    if '"' in stripped_line
                    else stripped_line.rfind("'")
                )

                if start_quote != -1 and end_quote != -1 and start_quote < end_quote:
                    filename_part = stripped_line[start_quote : end_quote + 1]
                    if filename_part.endswith('.stl"') or filename_part.endswith(
                        ".stl'"
                    ):
                        # Insert the filename line above the current line
                        new_modified_lines.append(f'filename = "{by}"')
                        line = line.replace(filename_part, "filename")
                        replaced = True

            new_modified_lines.append(line)

        if replaced:
            return "\n".join(new_modified_lines)

    # If no export_stl() case found, look for the last assignment
    if not replaced:
        new_modified_lines = modified_lines[:]
        for i in range(len(new_modified_lines) - 1, -1, -1):
            line = new_modified_lines[i].strip()
            if "=" in line:
                parts = line.split("=")
                if len(parts) == 2 and not parts[1].strip().startswith('"'):
                    var_name = parts[0].strip()
                    last_assignment = var_name
                    break

        if last_assignment:
            new_modified_lines.append(f'filename = "{by}"')
            new_modified_lines.append(f"export_stl({last_assignment}, filename)")

        return "\n".join(new_modified_lines)

    code = "\n".join(modified_lines)

    pattern = r'(\w+)\.export_stl\(([^)]+)\)'
    
    def replacer(match):
        obj = match.group(1)
        filename = match.group(2)
        return f'export_stl({obj}, {filename})'

    modified_code = re.sub(pattern, replacer, code)
    return modified_code

def replace_export_function(script, new_extension):
    if not new_extension.startswith("."):
        new_extension = "." + new_extension

    export_functions = {
        ".stl": "export_stl",
        ".brep": "export_brep",
        ".step": "export_step",
        ".gltf": "export_gltf",
        ".3mf": "Mesher",
    }

    func_name = export_functions.get(new_extension)
    if not func_name:
        return script

    lines = script.split("\n")

    for i, line in enumerate(lines):
        if new_extension == ".3mf":
            mesher_pattern = re.compile(r"export_stl\((\w+),\s*['\"](.+?)\.stl['\"]\)")
            match = mesher_pattern.search(line)
            if match:
                new_line = f"{func_name}().add_shape({match.group(1)})\n{func_name}().write('{match.group(2)}{new_extension}')"
                lines[i] = new_line
        else:
            pattern = re.compile(rf"export_stl\((\w+),\s*['\"](.+?)\.stl['\"]\)")
            match = pattern.search(line)
            if match:
                new_line = f"{func_name}({match.group(1)}, '{match.group(2)}{new_extension}')"
                lines[i] = new_line

    script = "\n".join(lines)

    return script