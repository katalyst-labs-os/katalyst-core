from typing import Optional
import time
from loguru import logger
from katalyst_core.algorithms.cad_generation.utils import init_client
from katalyst_core.programs.executor import execute_first_time, read_program_code

from katalyst_core.programs.storage import program_stl_path
from katalyst_core.programs.executor import preamble

from katalyst_core.algorithms.cad_generation.generation_pipeline import (
    GenerationPipeline,
)
from katalyst_core.algorithms.cad_generation.generation_steps import (
    GenerationStepInitial,
    GenerationStepKeepComplex,
    GenerationStepVisualRate,
    GenerationStepKeepBestRated,
    GenerationStepComment,
    GenerationStepImprove,
    GenerationStepParallel,
    GenerationStepPipeline,
)
from katalyst_core.algorithms.cad_generation.code_generation import code_run_fix_loop
from katalyst_core.algorithms.cad_generation.prompting import iteration_messages
from katalyst_core.algorithms.cad_generation.examples_ragging import (
    generate_examples_for_iteration_prompt,
)
from katalyst_core.algorithms.cad_generation.constants import (
    MODEL,
    MODEL_FAST,
    MODEL_MED,
)


class Agent:
    initial_prompt: str
    initial_reasoning: str
    iterations: list[tuple[str, str]]
    last_program_id: Optional[str]
    initial_precision: int

    def __init__(
        self,
        initial_prompt: str,
        initial_reasoning: str,
        iterations: list[tuple[str, str]],
        last_program_id: Optional[str],
        initial_precision: int,
    ):
        self.initial_prompt = initial_prompt
        self.initial_reasoning = initial_reasoning
        self.iterations = iterations
        self.last_program_id = last_program_id
        self.initial_precision = initial_precision

    @staticmethod
    def initialize(initial_prompt: str) -> "Agent":
        return Agent(initial_prompt, "", [], None, 0)

    def generate_initial(
        self, precision: int, llm_api_key: Optional[str] = None
    ) -> Optional[str]:
        random_id = str(time.time())

        logger.info(
            f"[{random_id}] Generating initial solution for: {self.initial_prompt}"
        )

        examples = generate_examples_for_iteration_prompt(self.initial_prompt, assemblies=False, top_n=10)

        messages = [
            {
                "role": "user",
                "content": f"""
Examples:

{examples}

# Build123d cheatsheet

Your knowledge on build123d's API is not up to date. Follow thoroughly the examples, they are your source of truth. Additionally, here are some functions you might need:

In build123d almost everything is a Shape, except objects created with: "with BuildPart() as ...:" which are BuildPart objects (and the same for BuildSketch). You can access the inner Shape object with "part.part".

```
with BuildPart() as part:
    ...

result = part 
export_stl(result, filename) # This will not work
result = part.part 
export_stl(result, filename) # This will work
```

```
result = part.<function_name>  # This will not work
result = part.part.<function_name>  # This will work
```

The functions below work with any object with type Shape, but not with BuildPart or BuildSketch types:

- sweep(sections: Optional[Union[Compound, Edge, Wire, Face, Solid, Iterable[Union[Compound, Edge, Wire, Face, Solid]]]] = None, path: Optional[Union[Curve, Edge, Wire, Iterable[Edge]]] = None, multisection: bool = False, is_frenet: bool = False, transition: Transition = Transition.TRANSFORMED, normal: Optional[Union[Vector, tuple[float, float], tuple[float, float, float], Iterable[float]]] = None, binormal: Optional[Union[Edge, Wire]] = None, clean: bool = True, mode: Mode = Mode.ADD)→ Union[Part, Sketch] Generic Operation: sweep. Sweep pending 1D or 2D objects along path. 

- offset(objects: Optional[Union[Edge, Face, Solid, Compound, Iterable[Union[Edge, Face, Solid, Compound]]]] = None, amount: float = 0, openings: Optional[Union[Face, list[build123d.topology.Face]]] = None, kind: Kind = Kind.ARC, side: Side = Side.BOTH, closed: bool = True, min_edge_length: Optional[float] = None, mode: Mode = Mode.REPLACE)→ Union[Curve, Sketch, Part, Compound] Generic Operation: offset. Applies to 1, 2, and 3 dimensional objects. Offset the given sequence of Edges, Faces, Compound of Faces, or Solids. The kind parameter controls the shape of the transitions. For Solid objects, the openings parameter allows selected faces to be open, like a hollow box with no lid.

- revolve(profiles: Optional[Union[Face, Iterable[Face]]] = None, axis: Axis = ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)), revolution_arc: float = 360.0, clean: bool = True, mode: Mode = Mode.ADD)→ Part. Part Operation: Revolve. Revolve the profile or pending sketches/face about the given axis. Note that the most common use case is when the axis is in the same plane as the face to be revolved but this isn’t required.

- scale(objects: Optional[Union[Shape, Iterable[Shape]]] = None, by: Union[float, tuple[float, float, float]] = 1, mode: Mode = Mode.REPLACE)→ Union[Curve, Sketch, Part, Compound]. Generic Operation: scale. Applies to 1, 2, and 3 dimensional objects. Scale a sequence of objects. Note that when scaling non-uniformly across the three axes, the type of the underlying object may change to bspline from line, circle, etc.

- split(objects: Optional[Union[Edge, Wire, Face, Solid, Iterable[Union[Edge, Wire, Face, Solid]]]] = None, bisect_by: Plane = Plane(o=(0.00, 0.00, 0.00), x=(1.00, 0.00, 0.00), z=(0.00, -1.00, 0.00)), keep: Keep = Keep.TOP, mode: Mode = Mode.REPLACE). Generic Operation: split. Applies to 1, 2, and 3 dimensional objects. Bisect object with plane and keep either top, bottom or both.

- sketch.section(obj: Optional[Part] = None, section_by: Union[Plane, Iterable[Plane]] = Plane(o=(0.00, 0.00, 0.00), x=(1.00, 0.00, 0.00), z=(0.00, -1.00, 0.00)), height: float = 0.0, clean: bool = True, mode: Mode = Mode.PRIVATE)→ Sketch. Part Operation: section. Slices current part at the given height by section_by or current workplane(s).

- rotate(axis: Axis, angle: float) -> Shape   PLEASE NOTE: THERE IS NO OTHER WAY TO ROTATE ANYTHING IN BUILD123D

- translate(vector: Vector(x: float, y: float, z: float)) -> Shape (preferred way to move objects)

Some primitives you always mis-use:

- Sphere(radius: float, arc_size1: float = -90, arc_size2: float = 90, arc_size3: float = 360, rotation: Union[tuple[float, float, float], geometry.Rotation] = (0, 0, 0), align: Union[Align, tuple[Align, Align, Align]] = (<Align.CENTER>, <Align.CENTER>, <Align.CENTER>), mode: Mode = Mode.ADD)

- Cylinder(radius: float, height: float, arc_size: float = 360, rotation: Union[tuple[float, float, float], geometry.Rotation] = (0, 0, 0), align: Union[Align, tuple[Align, Align, Align]] = (<Align.CENTER>, <Align.CENTER>, <Align.CENTER>), mode: Mode = Mode.ADD)

# Task

Taking inspiration from the up to date syntax in the examples, code a very realistic parametric CAD model using build123d from the following prompt:

<prompt>
{self.initial_prompt}
</prompt>

No imports can be included by you, do not write any. The following imports will be added to your code automatically:

<code>
{preamble}
</code>

Now think about it and code it:
"""
            }
        ]

        client = init_client(llm_api_key)
        response = client.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.4, timeout=40
        )

        logger.trace("Initial response: {}", response.choices[0].message.content)

        # messages += [
        #     {
        #         "role": "assistant",
        #         "content": response.choices[0].message.content,
        #     },
        #     {
        #         "role": "user",
        #         "content": "Make it 100x more realistic:"
        #     }
        # ]

        # response = client.chat.completions.create(
        #     model=MODEL, messages=messages, temperature=0.4, timeout=40
        # )

        # logger.trace("Second response: {}", response.choices[0].message.content)

        messages += [
            {
                "role": "assistant",
                "content": response.choices[0].message.content,
            },
            {
                "role": "user",
                "content": f"""
Write the entire code in one text block wrapped around <code> </code> tags, without using markdown ``` and make sure the parameters are written with one `<variable> = <expression or literal>` per line (avoid dict, avoid list, avoid tuple, except if short and on one line).
Make also sure parameters are between the imports and the first modeling line (first "with" for instance) and delimited by <parameters> </parameters> tags like in:

<code>
...
# <parameters>
radius = 10
height = 20
# </parameters>
...
with ...
</code>

"""
            }
        ]

        response = client.chat.completions.create(
            model=MODEL_FAST, messages=messages, temperature=0.4, timeout=40
        )

        logger.trace("Formatting response: {}", response.choices[0].message.content)

        # messages += [
        #     {
        #         "role": "assistant",
        #         "content": response.choices[0].message.content,
        #     },
        #     {
        #         "role": "user",
        #         "content": f"""Write the entire code in one text block and make sure the code has proper comments explaining the approach."""
        #     }
        # ]

        # response = client.chat.completions.create(
        #     model=MODEL_FAST, messages=messages, temperature=0.4, timeout=40
        # )

        # logger.trace("Documenting response: {}", response.choices[0].message.content)

        code = response.choices[0].message.content.split("<code>", 1)[1].split("</code>", 1)[0].strip()
        program_id, output, success = execute_first_time(code)

        retries = 0
        program_id = None
        while not success and retries < 10:
            if output.strip() == "":
                output = "No bugs, but nothing was rendered, empty object. Look if you didn't substract/cut by too much."

            messages += [
                {
                    "role": "assistant",
                    "content": f"""
<code>
{code}
</code>
"""
                },
                {
                    "role": "user",
                    "content": f"""
Interpreter feedback: 

{output}

Either: Fix the bug if it is incredibly trivial to do it (like if the error message explicitly tells you what to do), or
Remove the part of the code that is buggy and adapt the rest of the code to work without it. The goal is to simplify so we can find all the errors in this code.
"""
                }
            ]

            response = client.chat.completions.create(
                model=MODEL_FAST, messages=messages, temperature=0.4, timeout=40
            )

            logger.trace("Retry response {}: {}", retries, response.choices[0].message.content)

            try:
                code = response.choices[0].message.content.split("<code>", 1)[1].split("</code>", 1)[0].strip()
            except Exception as e:
                code = response.choices[0].message.content.replace("```python", "```").split("```", 1)[1].split("```", 1)[0].strip()

            program_id, output, success = execute_first_time(code)
            if success:
                break
            retries += 1

        self.initial_reasoning = ""

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

        messages = iteration_messages(
            self.initial_prompt,
            self.initial_reasoning,
            self.iterations,
            read_program_code(self.last_program_id),
            iteration,
            examples_prompt,
        )

        program_id, reasoning, success = code_run_fix_loop(
            messages, model=MODEL, llm_api_key=llm_api_key
        )

        if not success:
            return None

        self.initial_reasoning = reasoning
        self.last_program_id = program_id
        self.iterations.append((iteration, reasoning))

        return program_id

    def to_dict(self) -> dict:
        return {
            "initial_prompt": self.initial_prompt,
            "initial_reasoning": self.initial_reasoning,
            "iterations": self.iterations,
            "last_program_id": self.last_program_id,
            "initial_precision": self.initial_precision,
        }

    @staticmethod
    def from_dict(d: dict) -> "Agent":
        return Agent(
            d["initial_prompt"],
            d["initial_reasoning"],
            [(i[0], i[1]) for i in d["iterations"]],
            d["last_program_id"],
            d.get("initial_precision", 0),
        )
