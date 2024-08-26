import re

from katalyst_core.programs.sanitize import (
    sanitize_param_value_string,
)


def extract_params(code: str) -> dict[str, str]:
    params_dict = {}

    pattern = r"#\s*<parameters>\s*(.*?)\s*#\s*</parameters>"
    matches = re.findall(pattern, code, re.DOTALL)

    for match in matches:
        lines = match.strip().split("\n")
        for line in lines:
            if "=" not in line.strip():
                continue
            if len(line.strip().split("=")) != 2:
                continue

            param, value = line.strip().split("=")
            param = param.strip()
            value = value.strip()

            if "#" in value:
                value = value[: value.index("#")].strip()

            params_dict[param] = value

    code = re.sub(pattern, r"", code, flags=re.DOTALL)

    return params_dict


def apply_params(code: str, params_dict: dict):
    def replace_params(match):
        lines = match.group(1).strip().split("\n")
        updated_lines = []
        for line in lines:
            if "=" not in line.strip():
                continue
            if len(line.strip().split("=")) != 2:
                continue

            param, _ = line.strip().split("=")
            param = param.strip()
            value = params_dict[param]

            value = sanitize_param_value_string(value)

            updated_line = f"{param} = {value}"
            updated_lines.append(updated_line)

        updated_params_block = "\n".join(updated_lines)

        return f"# <parameters>\n{updated_params_block}\n# </parameters>"

    pattern = r"#\s*<parameters>\s*(.*?)\s*#\s*</parameters>"
    code = re.sub(pattern, replace_params, code, flags=re.DOTALL)

    return code
