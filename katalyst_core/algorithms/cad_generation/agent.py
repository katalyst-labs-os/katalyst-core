from typing import Optional
import time
from loguru import logger
from katalyst_core.algorithms.cad_generation.utils import init_client
from katalyst_core.programs.executor import execute_first_time

from katalyst_core.programs.storage import program_script_path, program_stl_path
from katalyst_core.programs.executor import preamble

from katalyst_core.algorithms.cad_generation.examples_ragging import (
    generate_examples_for_iteration_prompt,
)
from katalyst_core.algorithms.cad_generation.constants import (
    MODEL,
    MODEL_FAST,
)


class Agent:
    initial_prompt: str
    last_program_id: Optional[str]
    initial_precision: int

    def __init__(
        self,
        initial_prompt: str,
        last_program_id: Optional[str],
        initial_precision: int,
    ):
        self.initial_prompt = initial_prompt
        self.last_program_id = last_program_id
        self.initial_precision = initial_precision

    @staticmethod
    def initialize(initial_prompt: str) -> "Agent":
        return Agent(initial_prompt, None, 0)

    def generate_initial(
        self, precision: int, llm_api_key: Optional[str] = None
    ) -> Optional[str]:
        random_id = str(time.time())

        logger.trace(
            f"[{random_id}] Generating initial solution for: {self.initial_prompt}"
        )

        examples = generate_examples_for_iteration_prompt(
            self.initial_prompt, assemblies=False, top_n=10
        )

        prompt = f"""
# Prompt

<prompt>
{self.initial_prompt}
</prompt>

# Task

Taking inspiration from the up to date syntax in the examples, code a very realistic parametric CAD model using cadquery from the above prompt
"""

        main_model = MODEL
        depth = precision - 1
        if precision == 0:
            main_model = MODEL_FAST
            depth = 0

        program_id, success = generate_cad(
            examples,
            prompt,
            depth,
            main_model,
            second_model=MODEL_FAST,
            llm_api_key=llm_api_key,
        )

        if not success:
            return None

        self.last_program_id = program_id

        print(program_stl_path(program_id))

        return program_id

    def generate_iteration(
        self, iteration: str, llm_api_key: Optional[str] = None
    ) -> Optional[str]:
        assert self.last_program_id is not None

        examples_prompt = generate_examples_for_iteration_prompt(
            self.initial_prompt, top_n=6
        )

        previous_code = ""
        with open(program_script_path(self.last_program_id), "r") as f:
            previous_code = f.read()

        prompt = f"""
Answering to the prompt:

{self.initial_prompt}

And various follow-ups, you used parametric CAD to model the following:

<code>
{previous_code}
</code>

Now you are asked with doing the following change:

<request>
{iteration}
</request>

Please EDIT the above code (don't just take inspiration) to add the requested change. Really just use it entirely and then edit.
"""

        program_id, success = generate_cad(
            examples_prompt,
            prompt,
            depth=0,
            main_model=MODEL,
            second_model=MODEL_FAST,
            llm_api_key=llm_api_key,
        )

        if not success:
            return None

        self.last_program_id = program_id

        return program_id

    def to_dict(self) -> dict:
        return {
            "initial_prompt": self.initial_prompt,
            "last_program_id": self.last_program_id,
            "initial_precision": self.initial_precision,
        }

    @staticmethod
    def from_dict(d: dict) -> "Agent":
        return Agent(
            d["initial_prompt"],
            d["last_program_id"],
            d.get("initial_precision", 0),
        )


def generate_cad(
    examples: str,
    prompt: str,
    depth: int,
    main_model: str = MODEL,
    second_model: str = MODEL_FAST,
    llm_api_key: Optional[str] = None,
) -> tuple[Optional[str], bool]:
    client = init_client(llm_api_key)

    messages = [
        {
            "role": "user",
            "content": f"""
Examples:

{examples}

{prompt}

No imports can be included by you, do not write any. The following imports will be added to your code automatically:

<code>
{preamble}
</code>

First reason spatially and geometrically and then write the entire code in one text block wrapped around <code> </code> tags, without using markdown ``` and make sure the parameters are written with one `<variable> = <expression or literal>` per line (avoid dict, avoid list, avoid tuple, except if short and on one line).
Make also sure parameters are between the imports and the first modeling line and delimited by <parameters> </parameters> tags like in:

<code>
...
# <parameters>
radius = 10
height = 20
# </parameters>
...
</code>

Make also sure you export to stl in the end:

<code>
...
filename = "render.stl"
result.val().exportStl(filename) # if result is a Workplane, you must call val() before exportStl
</code>

Now think and code it:
""",
        }
    ]

    response = client.chat.completions.create(
        model=main_model, messages=messages, temperature=0.4, timeout=40
    )

    logger.trace(messages[0]["content"])
    logger.trace("Initial response: {}", response.choices[0].message.content)

    messages_improve = messages.copy()

    try:
        code = (
            response.choices[0]
            .message.content.split("<code>", 1)[1]
            .split("</code>", 1)[0]
            .strip()
        )
    except Exception as _:
        try:
            code = (
                response.choices[0]
                .message.content.replace("```python", "```")
                .split("```", 1)[1]
                .split("```", 1)[0]
                .strip()
            )
        except Exception as _:
            code = None

    d = 0
    while d < depth:
        messages_improve = [
            {
                "role": "assistant",
                "content": (
                    code if code is not None else response.choices[0].message.content
                ),
            },
            {
                "role": "user",
                "content": f"""
Make the geometry 100x more realistic, more pro, more industry-ready.

Tips:
- use standard functions/values in the industry (implement them, it's unlikely the libraries we give you have them unless it's obvious)
- make the code more modular
- use math and equations to specify positions, proportions, sizes, surfaces, points, so that you mitigate the chances of bad value guessing or bad look (you are bad at spatial reasoning)
- only touch the geometry, we DO NOT care about materials or simulation.

PS: We do not have any data file available for anything, if you see this code is using a data file, change what it does, preferably implement a function that generates the data directly in the code.

Write the entire code in one text block wrapped around <code> </code> tags, without using markdown ``` and make sure the parameters are written with one `<variable> = <expression or literal>` per line (avoid dict, avoid list, avoid tuple, except if short and on one line).
Make also sure parameters are between the imports and the first modeling line and delimited by <parameters> </parameters> tags like in:

<code>
...
# <parameters>
radius = 10
height = 20
# </parameters>
...
</code>

Make also sure you export to stl in the end:

<code>
... # __name__ == "__main__" is not allowed nor a main function
filename = "render.stl"
result.val().exportStl(filename) # if result is a Workplane, you must call val() before exportStl
</code>
""",
            },
        ]

        response = client.chat.completions.create(
            model=main_model, messages=messages_improve, temperature=0.4, timeout=40
        )

        try:
            code = (
                response.choices[0]
                .message.content.split("<code>", 1)[1]
                .split("</code>", 1)[0]
                .strip()
            )
        except Exception as e:
            code = (
                response.choices[0]
                .message.content.replace("```python", "```")
                .split("```", 1)[1]
                .split("```", 1)[0]
                .strip()
            )

        logger.trace("Precision response: {}", response.choices[0].message.content)
        d += 1

    resp_content = response.choices[0].message.content
    no_parameters = (
        "# <parameters>" not in resp_content or "# </parameters>" not in resp_content
    )
    no_code = "<code>" not in resp_content or "</code>" not in resp_content
    no_export = "result.val().exportStl(filename)" not in resp_content

    if no_parameters or no_code or no_export:
        messages_improve += [
            {
                "role": "assistant",
                "content": response.choices[0].message.content,
            },
            {
                "role": "user",
                "content": f"""
Write the entire code in one text block wrapped around <code> </code> tags, without using markdown ``` and make sure the parameters are written with one `<variable> = <expression or literal>` per line (avoid dict, avoid list, avoid tuple, except if short and on one line).
Make also sure parameters are between the imports and the first modeling line and delimited by <parameters> </parameters> tags like in:

<code>
...
# <parameters>
radius = 10
height = 20
# </parameters>
...
</code>

Make also sure you export to stl in the end:

<code>
...
filename = "render.stl"
result.val().exportStl(filename) # if result is a Workplane, you must call val() before exportStl
</code>
    """,
            },
        ]

        response = client.chat.completions.create(
            model=second_model, messages=messages_improve, temperature=0.4, timeout=40
        )

        logger.trace("Formatting response: {}", response.choices[0].message.content)

    code = (
        response.choices[0]
        .message.content.split("<code>", 1)[1]
        .split("</code>", 1)[0]
        .strip()
    )
    program_id, output, success = execute_first_time(code)

    retries = 0
    last_output = output
    repeat_error = False
    while not success and retries < 10:
        if output.strip() == "":
            output = "No bugs, but nothing was rendered, empty object. Look if you didn't substract/cut by too much."

        if repeat_error:
            messages_fix = messages.copy() + [
                {
                    "role": "assistant",
                    "content": f"""
<code>
{code}
</code>
""",
                },
                {
                    "role": "user",
                    "content": f"""
Interpreter feedback: 

{output}

This is not the first time you get this error, this means YOU DON'T KNOW HOW TO FIX IT, and probably never will. Please, just REMOVE the part of the code that causes it, despite it will simplify the result.
""",
                },
            ]
        else:
            tips = """
- if the error is like 'Workplane' object has no attribute 'xyz': DO NOT TRY TO DO IT DIFFERENTLY, JUST REMOVE WHAT YOU WERE DOING AND FORGET ABOUT IT
- if the error is cryptic and has "<OCP." codes in it: DO NOT TRY TO DO IT DIFFERENTLY, JUST REMOVE WHAT YOU WERE DOING AND FORGET ABOUT IT
- don't be afraid to remove stuff, but don't remove entire functions, just simplify small parts of the code
- find different ways, don't make something complex become "simple" just because one call fails. remove the call, find another way
"""
            if '__name__ == "__main__"' in code:
                tips += '\n- If your code contains __name__ == "__main__", DO NOT USE A main function or a __name__ == thing. Your export MUST BE at the end of the code, without indentation, so not inside a function.'
                tips += 'To export: \n\n```\nfilename = "render.stl"\nresult.val().exportStl(filename)\n```'
            if "timed out" in output:
                tips += "\n- If the code timed out, it is likely instanciating multiple objects in a loop, remove that by simplifying the code."
            if "No pending wires present" in output:
                tips += "\n- If the error is `No pending wires present`, it is likely not trival: all you can do is to remove the function call causing the error and not attempt to do in any other way what you meant to do with that call."
            if "fillet" in output or "chamfer" in output:
                tips += '\n- If the error is regarding fillet and chamfers, make sure you selected some edges with .edges(... (e.g "|Z")) before .fillet(<radius>) or .chamfer(<radius>). Notably, you can\'t pass an edge list to .chamfer() or .fillet(), it only takes a radius. You always need to select the edges with .edges. \n```\n edges(selector: Optional[Union[str, Selector]] = None, tag: Optional[str] = None)→ T\n Select the edges of objects on the stack, optionally filtering the selection. If there are multiple objects on the stack, the edges of all objects are collected and a list of all the distinct edges is returned.\nFilters must provide a single method that filters objects: filter(objectList: Sequence[Shape])→ list[Shape]\n```'
            if "one solid on the stack to union" in output:
                tips += "\n- If the error is ` Workplane object must have at least one solid on the stack to union!`, make sure you don't call .union on a workplane you just selected, but instead on a workplane with an existing object within. For instance if you created object A on a workplane and object B on another workplane, don't do `result = cq.Workplane(...).union(A).union(B)` but instead `result = A.union(B)`"
            messages_fix = messages.copy() + [
                {
                    "role": "assistant",
                    "content": f"""
<code>
{code}
</code>
""",
                },
                {
                    "role": "user",
                    "content": f"""
Interpreter feedback: 

{output}

Either: Fix the bug if it is incredibly trivial to do it (like if the error message explicitly tells you what to do), or
Remove the part of the code that is buggy and adapt the rest of the code to work without it. The goal is to simplify so we can find all the errors in this code.

Tips:

{tips}
""",
                },
            ]

        response = client.chat.completions.create(
            model=second_model, messages=messages_fix, temperature=0.4, timeout=40
        )

        logger.trace(
            "Retry response {}: {}", retries, response.choices[0].message.content
        )

        try:
            code = (
                response.choices[0]
                .message.content.split("<code>", 1)[1]
                .split("</code>", 1)[0]
                .strip()
            )
        except Exception as e:
            code = (
                response.choices[0]
                .message.content.replace("```python", "```")
                .split("```", 1)[1]
                .split("```", 1)[0]
                .strip()
            )

        program_id, output, success = execute_first_time(code)
        if output.strip().split("\n")[-1] == last_output.strip().split("\n")[-1]:
            logger.trace("Repeated error, retrying")
            repeat_error = True
        else:
            repeat_error = False

        if success:
            break
        retries += 1
        last_output = output

    return program_id, success
