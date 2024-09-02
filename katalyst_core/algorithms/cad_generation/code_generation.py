from typing import Optional
from loguru import logger
from katalyst_core.algorithms.cad_generation.constants import MODEL

from katalyst_core.algorithms.cad_generation.utils import init_client
from katalyst_core.algorithms.cad_generation.prompting import error_message
from katalyst_core.programs.executor import execute_first_time


def code_run_fix_loop(
    messages: list[dict],
    max_iterations=4,
    model=MODEL,
    base_temperature=0.4,
    llm_api_key: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], bool]:
    iterations = 0
    program_id = None
    reasoning = None
    initial_reasoning = None
    success = False
    while iterations < max_iterations:
        temperature = base_temperature * (0.5**iterations)
        maybe = _code_from_conversation(
            messages, model=model, temperature=temperature, llm_api_key=llm_api_key
        )
        if maybe is None:
            iterations += 1
            continue
        code, reasoning = maybe
        code = code.replace(".add(", ".union(")

        if initial_reasoning is None:
            initial_reasoning = reasoning
        program_id, output, success = execute_first_time(code)
        if success:
            break

        user_message = error_message(output)
        if iterations > 0 and iterations < max_iterations - 1:
            # TODO: insert hard-coded build123d specific tips here like we did before with cadquery
            user_message = {"role": "user", "content": f"{output}\n\nTry again:"}
        elif iterations == max_iterations - 1:
            user_message = {
                "role": "user",
                "content": f"{output}\n\nThis is your LAST TRY, do whatever, simplify, try something else, BUT PLEASE, make it work at least:",
            }

        messages = messages + [
            {
                "role": "assistant",
                "content": f"""
<reasoning>
{reasoning}
</reasoning>
<code>
{code}
</code>
""",
            },
            user_message,
        ]

        iterations += 1

    return program_id, initial_reasoning, success


def _code_from_conversation(
    messages: list[dict], model=MODEL, temperature=0.4, llm_api_key: Optional[str] = None
) -> Optional[tuple[str, str]]:
    try:
        client = init_client(llm_api_key)

        try:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=temperature, timeout=40
            )

            response = response.choices[0].message.content
        except TimeoutError as e:
            raise e
        except Exception as e:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=temperature, timeout=40
            )
            response = response.choices[0].message.content

        code = ""
        if "<code>" in response:
            code = response.split("<code>", 1)[1].split("</code>", 1)[0].strip()
        elif "</reasoning>" in response:
            code = response.split("</reasoning>")[1]
        elif "```python" in response:
            code = response.split("```python", 1)[1].split("```", 1)[0].strip()
        elif "```py" in response:
            code = response.split("```py", 1)[1].split("```", 1)[0].strip()
        elif "```" in response:
            code = response.split("```", 1)[1].split("```", 1)[0].strip()
        else:
            logger.trace(f"No code found in message: {response}")

        reasoning = ""
        if "<reasoning>" in response:
            reasoning = (
                response.split("<reasoning>", 1)[1].split("</reasoning>", 1)[0].strip()
            )
        return code, reasoning
    except TimeoutError:
        logger.warning("TimeoutError in code_from_conversation")
        return None
    except Exception as e:
        logger.warning(f"Exception in code_from_conversation: {e}")
        return None
