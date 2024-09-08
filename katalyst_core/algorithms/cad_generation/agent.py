from typing import Optional
import time
from loguru import logger
from katalyst_core.programs.executor import read_program_code

from katalyst_core.programs.storage import program_stl_path

from katalyst_core.algorithms.cad_generation.generation_pipeline import GenerationPipeline
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
from katalyst_core.algorithms.cad_generation.examples_ragging import generate_examples_for_iteration_prompt
from katalyst_core.algorithms.cad_generation.constants import MODEL, MODEL_FAST, MODEL_MED


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

    def generate_initial(self, precision: int, llm_api_key: Optional[str] = None) -> Optional[str]:
        random_id = str(time.time())

        logger.info(
            f"[{random_id}] Generating initial solution for: {self.initial_prompt}"
        )

        pipeline = None
        if precision == 0:
            pipeline = GenerationPipeline(
                [
                    GenerationStepInitial(1, 4, MODEL_FAST, 10),
                    GenerationStepKeepComplex(1),
                ]
            )
        elif precision == 1:
            pipeline = GenerationPipeline(
                [GenerationStepInitial(3, 2, MODEL, 10), GenerationStepKeepComplex(1)]
            )
        elif precision == 2:
            pipeline = GenerationPipeline(
                [
                    GenerationStepInitial(5, 3, MODEL, 10),
                    GenerationStepVisualRate(MODEL_FAST),
                    GenerationStepKeepBestRated(3),
                    GenerationStepComment(MODEL_FAST),
                    GenerationStepImprove(3, 2, MODEL, 10),
                    GenerationStepKeepComplex(1),
                ]
            )
        elif precision == 3:
            pipeline = GenerationPipeline(
                [
                    GenerationStepInitial(6, 2, MODEL, 10),
                    GenerationStepKeepComplex(3),
                    GenerationStepComment(MODEL_FAST),
                    GenerationStepImprove(4, 2, MODEL, 10),
                    GenerationStepKeepComplex(3),
                    GenerationStepComment(MODEL_FAST),
                    GenerationStepImprove(2, 2, MODEL, 10),
                    GenerationStepKeepComplex(1),
                ]
            )
        elif precision == 4:
            pipeline = GenerationPipeline(
                [
                    GenerationStepInitial(7, 2, MODEL, 4),
                    GenerationStepKeepComplex(3),
                    GenerationStepComment(MODEL_FAST),
                    GenerationStepImprove(4, 2, MODEL, 4),
                    GenerationStepKeepComplex(3),
                    GenerationStepComment(MODEL_FAST),
                    GenerationStepImprove(3, 2, MODEL, 4),
                    GenerationStepKeepComplex(3),
                    GenerationStepComment(MODEL_FAST),
                    GenerationStepImprove(2, 2, MODEL, 4),
                    GenerationStepKeepComplex(1),
                ]
            )
        elif precision == 5:
            subpipeline = [
                GenerationStepInitial(8, 2, MODEL_MED, 4),
                GenerationStepKeepComplex(5),
                GenerationStepComment(MODEL_FAST),
                GenerationStepImprove(6, 2, MODEL_MED, 4),
                GenerationStepKeepComplex(3),
                GenerationStepComment(MODEL_FAST),
                GenerationStepImprove(3, 2, MODEL_MED, 4),
                GenerationStepKeepComplex(3),
                GenerationStepComment(MODEL_FAST),
                GenerationStepImprove(2, 2, MODEL_MED, 4),
                GenerationStepKeepComplex(1),
            ]

            pipeline = GenerationPipeline(
                [
                    GenerationStepParallel(
                        [
                            GenerationStepPipeline(subpipeline),
                            GenerationStepPipeline(subpipeline),
                            GenerationStepPipeline(subpipeline),
                            GenerationStepPipeline(subpipeline),
                        ]
                    ),
                    GenerationStepKeepComplex(4),
                    GenerationStepComment(MODEL_FAST),
                    GenerationStepImprove(2, 2, MODEL_MED, 4),
                    GenerationStepKeepComplex(1),
                ]
            )
        elif precision == 6:
            subpipeline = [
                GenerationStepComment(MODEL_FAST),
                GenerationStepImprove(5, 2, MODEL, 4),
                GenerationStepVisualRate(MODEL_FAST),
                GenerationStepKeepBestRated(5),
                GenerationStepComment(MODEL_FAST),
                GenerationStepImprove(3, 2, MODEL, 4),
                GenerationStepVisualRate(MODEL_FAST),
                GenerationStepKeepBestRated(3),
                GenerationStepComment(MODEL_FAST),
                GenerationStepImprove(3, 2, MODEL, 4),
                GenerationStepVisualRate(MODEL_FAST),
                GenerationStepKeepBestRated(3),
                GenerationStepComment(MODEL_FAST),
            ]
            pipeline = GenerationPipeline(
                [
                    GenerationStepInitial(7, 2, MODEL, 10),
                    GenerationStepVisualRate(MODEL_FAST),
                    GenerationStepKeepBestRated(6),
                    GenerationStepParallel(
                        [
                            GenerationStepPipeline(subpipeline),
                            GenerationStepPipeline(subpipeline),
                            GenerationStepPipeline(subpipeline),
                            GenerationStepPipeline(subpipeline),
                            GenerationStepPipeline(subpipeline),
                        ]
                    ),
                    GenerationStepImprove(5, 2, MODEL, 4),
                    GenerationStepVisualRate(MODEL_FAST),
                    GenerationStepKeepBestRated(3),
                    GenerationStepComment(MODEL_FAST),
                    GenerationStepImprove(2, 2, MODEL, 4),
                    GenerationStepKeepComplex(1),
                ]
            )

        self.initial_precision = precision

        results = pipeline.execute(random_id, prompt=self.initial_prompt, llm_api_key=llm_api_key)

        if results is None or len(results) == 0:
            logger.error(f"[{random_id}] Failed to generate solution")
            return None

        self.initial_reasoning = results[0].reasoning
        self.last_program_id = results[0].program_id

        print(program_stl_path(results[0].program_id))

        return results[0].program_id

    def generate_iteration(self, iteration: str, llm_api_key: Optional[str] = None) -> Optional[str]:
        assert self.last_program_id is not None

        examples_prompt = generate_examples_for_iteration_prompt(self.initial_prompt, top_n=6)

        messages = iteration_messages(
            self.initial_prompt,
            self.initial_reasoning,
            self.iterations,
            read_program_code(self.last_program_id),
            iteration,
            examples_prompt,
        )

        program_id, reasoning, success = code_run_fix_loop(messages, model=MODEL, llm_api_key=llm_api_key)

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
