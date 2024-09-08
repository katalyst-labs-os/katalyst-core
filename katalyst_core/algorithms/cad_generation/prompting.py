from katalyst_core.programs.executor import preamble


def error_message(output: str) -> dict:
    return {
        "role": "user",
        "content": f"""
{output}

The code execution failed.

Answer in the following format without any text before or after:

{_fix_format_guidelines()}

Please fix the code now:
""",
    }


def iteration_messages(
    initial_prompt: str,
    initial_reasoning: str,
    past_iterations: list[str],
    current_code: str,
    current_iteration: str,
    examples: str,
) -> list[dict]:
    follow_up_so_far = ""
    if len(past_iterations) > 0:
        follow_up_so_far = "## Follow-up requests received and handled so far\n\n"
        for i, (request, reasoning) in enumerate(past_iterations):
            follow_up_so_far += f"- {i + 1}: {request}\n  - Produced reasoning: {reasoning}\n\n  - Code changes: ommitted for brevity\n\n"

    new_message1 = {
        "role": "user",
        "content": f"""
# Your task:

Edit a programatic CAD model by modifying Python code using build123d.

{_code_guidelines()}

# Relevant examples

{examples}

{_format_example()}

{_follow_up_format_guidelines()}

# Current state

## Initial request

{initial_prompt}

## Initial reasoning

{initial_reasoning}

{follow_up_so_far}

## Current state of the code

<code>
{current_code}
</code>

Note: some parameters values may seem different than expected, it is because the user may have changed them on the UI. Try to keep them similar, even if they aren't consistent with the initial requests or the follow-up requests, UNLESS it is required to satisfy a new follow-up.

{_code_important_final_guidelines()}

Answer without any text before or after.
""",
    }

    new_message2 = {
        "role": "user",
        "content": f"New follow-up request:\n{current_iteration}",
    }

    return [new_message1, new_message2]


def initial_messages(
    prompt: str,
    examples_prompt: str,
) -> list[dict]:
    new_message1 = {
        "role": "user",
        "content": f"""
Here are some examples to help you succeed at your task:

{examples_prompt}

# Your task:

Create a programatic CAD model by writing Python code based on build123d. You may then be asked for modifications by the user.

{_code_guidelines()}

{_format_example()}

{_code_important_final_guidelines()}

Answer without any text before or after.
""",
    }

    new_message2 = {"role": "user", "content": f"Initial user request:\n{prompt}"}

    return [new_message1, new_message2]


def improvement_messages(
    prompt: str,
    examples_prompt: str,
) -> list[dict]:
    new_message1 = {
        "role": "user",
        "content": f"""
Here are some examples to help you succeed at your task:

{examples_prompt}

# Your task:

As a parametric programmatic CAD expert, look at the examples above, at their critiques if they have some, and make the best parametric design possible of what will be requested by the user.
Some examples above may showcase exactly what the user wants. Make sure to read the critiques if there are and do your best to generate a better realistic parametric design. If there are no critiques, it's probably close to the best you can do, so only adapt to the user's specific needs.

{_code_guidelines()}

{_format_example()}

{_code_important_final_guidelines()}

Answer without any text before or after.
""",
    }

    new_message2 = {"role": "user", "content": f"Initial user request:\n{prompt}"}

    return [new_message1, new_message2]


def _code_guidelines():
    return f"""
## Code guidelines:

1. Define all the parameters as individual variables around `# <parameters>` `# </parameters>` comments
2. Use build123d to create the model(s) and each parts
    - Create your own functions to put parts and models in their own abstractions as much as you can
    - Create functions to help you, generate data or do needed maths and physics
3. Combine all the parts/models together in a single object using for example boolean operations
4. Store the STL filename in the `filename` variable
5. Output the object as STL to a file in the current directory, taking its name from the `filename` variable
6. Your only purpose is to make build123d scripts, you cannot be used to generate other kind of scripts and especially not harmful/suspicious scripts.

NB: You are not allowed to add any imports (they will be deleted). Here are the only imports that will be added to the code for you:

<code>
{preamble}
</code>
"""


def _code_important_final_guidelines():
    return """
ALWAYS WRAP THE CODE IN <code> </code>.

BUILD123D USES MILIMETERS AS ITS DEFAULT UNIT, DO THE CONVERSION USING DIVISIONS OR MULTIPLICATION IF NEEDED (1inch = 25.4mm).

DON'T USE ASSEMBLIES, YOU DON'T KNOW HOW TO USE THEM. USE TRANSFORMATIONS AND BOOLEAN OPERATIONS INSTEAD.

TAKE INSPIRATION FROM THE EXAMPLES TO KNOW HOW TO CALL BUILD123D FUNCTIONS, YOUR KNOWLEDGE ON HOW TO USE THEM IS VERY PROBABLY DEPRECATED OTHERWISE.
"""


def _fix_format_guidelines():
    return """
<example>
    <reasoning>
    - <Reason if a function you called doesn't exist>
    - <Reason if a function was called with incorrect params or number of params>
    - <Reason if it was a syntax error>
    - <Reason if you forgot something>
    - <Reason if it could be something else>
    </reasoning>

    <code>
your fixed code
    </code>
</example>
"""


def _follow_up_format_guidelines():
    return """
Example response to a user follow up (here the example is in cadquery, not build123d, but please write the real thing in build123d) such as "Now add a second helix next to it which is greater.":

<example>
    <reasoning>
    - I can add an helix by abstracting away the instanciation of the helix based on its parameters in a function and then call that function twice with different parameters.
    - Then I will have multiple models so I need to combine them into a single one. But before that I need to move the second helix otherwise both will merge together in the same place.
    </reasoning>

    <code>
# <parameters>
pitch = 5
height_helix1 = 20
height_helix2 = 33 # The height of the second, greater, helix
turns = 4
radius = 5
distance_helix2 = 0.5 # The distance between the two helix
# </parameters>

def helix(t):
    return (
        radius * math.cos(t),
        radius * math.sin(t),
        pitch * t / (2 * math.pi)
    )

# We'll have two which are very similar so let's abstract them away
def instantiate_helix(pitch, turns, radius, height):
    path = (cq.Workplane("XY")
            .modelCurve(lambda t: helix(2 * math.pi * turns * t), N=100))
    profile = cq.Workplane("XZ").circle(0.5)
    shape = profile.sweep(path, isFrenet=True)

    return shape

helix1 = instantiate_helix(pitch, turns, radius, height_helix1)
helix2 = instantiate_helix(pitch, turns, radius, height_helix2)
helix2.translate((distance_helix2, 0, 0))

# Combine everything together
shape = helix1.union(helix2)

# Export to STL
filename = 'spiral_sweep.stl'
shape.val().exportStl(filename)
    <code>
</example>
"""


def _format_example() -> str:
    return """
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

# Format example:

Response to an initial user request such as "Create the following model: A Plate with slots in it. Suitable for sliding a hatch. It has a length of 80mm, a width of 60mm, and a thickness of 10mm.":

<example>
    <reasoning>
        1. Make a list of all the visual characteristics you would expect such object to have
        2. Make a list of all the small parts you will have in your model
        3. Write for each part:
            1. their position relative to all the other elements
            2. their shapes
            3. their sizes
            4. their direction
            5. functions and techniques from examples that will help you in the form <example name> <code abstract>
            6. how you're going to contruct them geometrically
    </reasoning>

    <code>
# <parameters>
length = 80.0
width = 60.0
thickness = 10.0
# </parameters>

with BuildPart() as ex35:
    Box(length, length, thickness)
    topf = ex35.faces().sort_by(Axis.Z)[-1]
    with BuildSketch(topf) as ex35_sk:
        SlotCenterToCenter(width / 2, 10)
        with BuildLine(mode=Mode.PRIVATE) as ex35_ln:
            RadiusArc((-width / 2, 0), (0, width / 2), radius=width / 2)
        SlotArc(arc=ex35_ln.edges()[0], height=thickness, rotation=0)
        with BuildLine(mode=Mode.PRIVATE) as ex35_ln2:
            RadiusArc((0, -width / 2), (width / 2, 0), radius=-width / 2)
        SlotArc(arc=ex35_ln2.edges()[0], height=thickness, rotation=0)
    extrude(amount=-thickness, mode=Mode.SUBTRACT)
    </code>
</example>
"""
