from typing import Optional

from loguru import logger
from katalyst_core.algorithms.cad_generation.generation import GenerationResult

from katalyst_core.algorithms.cad_generation.utils import init_client
from katalyst_core.algorithms.docs_to_desc.stl_visual_desc import compare_stl_to_prompt, describe_stl
from katalyst_core.programs.storage import program_stl_path


def commented_results_to_examples(
    initial_prompt: str, results: list[GenerationResult]
) -> str:
    total = f"""
<example>
<prompt>
{initial_prompt}
</prompt>
<solutions>
"""
    for result in results:
        total += f"""
<AI-solution>
<reasoning>
{result.reasoning}
</reasoning>
<code>
{result.code}
</code>
<critique>
{result.comment}
</critique>
</AI-solution>
"""

    total += "\n<solutions>\n</example>"
    return total


def comment_result(
    initial_prompt: str, result: GenerationResult, model: str
) -> Optional[tuple[str, tuple[str, int]]]:
    stl_path = program_stl_path(result.program_id)
    description = describe_stl(stl_path, model)
    if description is None:
        description = "No description available"

    visual_critique, rating = (None, 0)
    if result.visual_critique is None:
        maybe = compare_stl_to_prompt(stl_path, initial_prompt, model)
        if maybe is not None:
            visual_critique, rating = maybe
    else:
        visual_critique = result.visual_critique
        rating = result.rating

    prompt = f"""
The following prompt was given to a parametric CAD programmer AI agent:

<prompt>
{initial_prompt}
</prompt>

It then generated the following reasoning:

<reasoning>
{result.reasoning}
</reasoning>

And then the following code:

<code>
{result.code}
</code>

And it gave a 3D model, which an AI described visually as:

<visual-description>
{description}
</visual-description>

And a expert human CAD designer critiqued with regards to the prompt:

<visual-critique>
{visual_critique}
</visual-critique>

And rated the quality of the model as:

<rating>
{rating}/10
</rating>

You will now impersonate a parametric and code CAD experts, tasked with honestly and coldly critiquing the solution designed by the AI agent.

Answer in the following format:

<final-summary>
    Should be of the form

    < code or reasoning excerpt >
    < actionable change described in high details >

    Repeated for each change that should be done to improve the realism, coherence, shape of the solution.
</final-summary>

WE DO NOT CARE ABOUT: benchmarks, materials, exports. Don't critique these aspects.
"""
    client = init_client()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            timeout=40,
        )

        response = response.choices[0].message.content

        final_summary = response.split("<final-summary>")[-1].split("</final-summary>")[
            0
        ]
        # print(response)
        return final_summary, (visual_critique, rating)
    except TimeoutError:
        logger.info("Timeout in comment_result")
        return None
    except Exception as e:
        logger.warning(f"Exception in comment_result: {e}")
        return None
