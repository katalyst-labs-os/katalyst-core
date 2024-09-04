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
            
            output += """

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

Some other common errors:

- `with Locations((hub_diameter/2 - 20, 0)).rotated(...)` or `with Locations((hub_diameter/2 - 20, 0)).rotate(...)` doesn't exist. Nothing even remotely similar to that exists. If you try to do that, just give up and use translate and rotate on the individual shapes.

"""

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
