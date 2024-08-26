import os
import openai
import pandas as pd
from bs4 import BeautifulSoup

from katalyst_core.dataset.part import DatasetPart


MODEL_STEPS = "anthropic/claude-3.5-sonnet"


def dataset_part_to_steps(index, example: DatasetPart):
    """
    Generate synthetic steps examples from a given dataset part.

    Given dataset examples are faily large, they are not so suitable for prompting small edits.
    We generate two synthetic step by step examples from each dataset example:
    - low-level (small CAD edits like "add a hole" or "add a cutout" or "add a chamfer")
    - high-level (high-level edits like "add a handle" or "add a slot" or "add a pattern")
    These are then RAGged to retrieve similar edits when a new iteration is requested.

    Parameters:
    - index (int): The index of the example in the dataset.
    - example (DatasetPart): The dataset part to generate steps for.

    Returns:
    - tuple: A tuple containing two DataFrames, df1 and df2
        - df1: Low-level synthetic steps examples (small CAD edits)
        - df2: High-level synthetic steps examples (high-level edits)
    """

    low_level_steps = None
    high_level_steps = None
    try:
        result1, result2 = _generate(example)
        low_level_steps = _steps_to_dataframe(result1, index, example.name)
        high_level_steps = _steps_to_dataframe(result2, index, example.name)
    except Exception as e:
        print(f"Error processing example {index} {example.name}: {e}")
    return low_level_steps, high_level_steps


def _parse_steps(steps_text):
    soup = BeautifulSoup(steps_text, "html.parser")
    steps = soup.find_all("step")

    step_details = []

    for step_id, step in enumerate(steps):
        code_before = (
            step.find("code-before")
            .get_text(strip=True)
            .removeprefix("```\n")
            .removesuffix("\n```")
        )
        request = step.find("request").get_text(strip=True)
        edits = step.find("edits").get_text(strip=True)

        step_details.append(
            {
                "step_id": step_id,
                "code_before": code_before,
                "request": request,
                "edits": edits,
            }
        )

    return step_details


def _steps_to_dataframe(steps_text, parent_id, parent_name):
    step_details = _parse_steps(steps_text)

    df = pd.DataFrame(
        step_details,
        columns=["step_id", "code_before", "request", "edits"],
    )
    df["parent_name"] = parent_name
    df["parent_id"] = parent_id
    return df


def _generate(entry: DatasetPart):
    print(f"Generating for {entry.name}")

    client = openai.OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        timeout=100,
    )

    prompt = {
        "role": "user",
        "content": f"""
---
description: {entry.description}
code:

```
{entry.code}
```
---

Above is an example pair we give to LLMs for few shot prompting to generate cadquery code from a text description.
We have a new feature for continuous text-based user feedback and iteration, where the user might ask for any change or edit.
By using what's inside the code of this example already, construct intermediary examples of the form:
- code before
- request
- precise changes made

These examples must showcase intermediary steps for getting to exactly the code we have in the above example. Imagine how going from nothing, the user would have constructed the same thing in many many steps by asking for edits.

answer in the following format:

<steps>
<step>
<code-before>
```
some code
```
</code-before>
<request>
precise description of the edit asked for
</request>
<edits>
some substep of the edit
```
# some description of where in the code we are
some changed code snippet
```
more substeps if needed
</edits>
</step>
... more steps
</steps>

For example:

<steps>
<step>
<code-before>
```
result = cq.Workplane("XY")
```
</code-before>
<request>
Start with a blank CadQuery workplane
</request>
<edits>
Initializing a workplane
```
result = cq.Workplane("XY")
```
</edits>
</step>
<step>
<code-before>
```
result = cq.Workplane("XY")
```
</code-before>
<request>
Create a box with specific dimensions
</request>
<edits>
Define dimensions as variables
```
length = 80.0
height = 60.0
thickness = 10.0
result = cq.Workplane("XY").box(length, height, thickness)
```
</edits>
</step>
<step>
<code-before>
```
length = 80.0
height = 60.0
thickness = 10.0
result = cq.Workplane("XY").box(length, height, thickness)
```
</code-before>
<request>
Add a hole in the center of the top face
</request>
<edits>
Define the hole diameter as a variable and add the hole
```
center_hole_dia = 22.0
result = (
    cq.Workplane("XY")
    .box(length, height, thickness)
    .faces(">Z")
    .workplane()
    .hole(center_hole_dia)
)
```
</edits>
</step>
<step>
<code-before>
```
length = 80.0
height = 60.0
thickness = 10.0
center_hole_dia = 22.0
result = (
    cq.Workplane("XY")
    .box(length, height, thickness)
    .faces(">Z")
    .workplane()
    .hole(center_hole_dia)
)
```
</code-before>
<request>
Verify and ensure the hole is centered
</request>
<edits>
Ensure the hole is centered by confirming workplane alignment and hole placement
```
result = (
    cq.Workplane("XY")
    .box(length, height, thickness)
    .faces(">Z")
    .workplane(centerOption="CenterOfMass")
    .hole(center_hole_dia)
)
```
</edits>
</step>
</steps>

Steps must be small and incremental
Steps must never be "do x (involved new number)" and then next step "add variable for parameter y for x", every step should always have all its parameters defined as variable from the getgo
Steps can't be trivial, like just adding comments or changing a param, it must showcase new functions and design choices that were used to build the code to its final state
""",
    }

    response = client.chat.completions.create(
        model=MODEL_STEPS,
        messages=[prompt],
        temperature=0.1,
    )

    response1 = response.choices[0].message.content

    prompt2 = {
        "role": "user",
        "content": """
combine again every few steps (2 to 5) into one step with a very general and high-level requests in natural language for the edit happening (for instance: "add holes", "make a coin", "draw the pattern of a star", "add a stage to that furniture", "change to a sloped roof", "add a transmission and an axis"..., and certainly not using precise CAD operations and vocabulary...)
""",
    }

    response = client.chat.completions.create(
        model=MODEL_STEPS,
        messages=[prompt, {"role": "assistant", "content": response1}, prompt2],
        temperature=0.1,
    )

    response2 = response.choices[0].message.content

    return response1, response2
