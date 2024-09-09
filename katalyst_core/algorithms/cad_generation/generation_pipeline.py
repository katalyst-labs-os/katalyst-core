from dataclasses import dataclass
from typing import Optional
from loguru import logger

from katalyst_core.algorithms.cad_generation.generation import (
    GenerationStep,
    GenerationResult,
)
from katalyst_core.programs.storage import program_delete


@dataclass
class GenerationPipeline:
    steps: list[GenerationStep]

    def execute(
        self, pipeline_id: int, prompt: str, llm_api_key: Optional[str] = None
    ) -> Optional[list[GenerationResult]]:
        previous = []
        final_discarded = []
        for step in self.steps:
            logger.info(f"[{pipeline_id}] Executing step: {step}")
            results, discarded = step.execute(
                pipeline_id, prompt, previous, llm_api_key
            )
            logger.info(
                f"[{pipeline_id}] Finished step with {len(results)} results: {step}"
            )
            if len(results) == 0:
                return None
            logger.info(f"[{pipeline_id}] Discarding {len(discarded)} results")
            final_discarded += discarded
            previous = results
        for result in final_discarded:
            program_delete(result.program_id)
        return previous
