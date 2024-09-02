from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Optional
from loguru import logger

from katalyst_core.algorithms.cad_generation.code_generation import code_run_fix_loop
from katalyst_core.algorithms.cad_generation.comment import (
    comment_result,
    commented_results_to_examples,
)
from katalyst_core.algorithms.cad_generation.examples_ragging import (
    generate_examples_for_prompt,
)
from katalyst_core.algorithms.cad_generation.prompting import (
    improvement_messages,
    initial_messages,
)
from katalyst_core.algorithms.cad_generation.generation import (
    GenerationResult,
    GenerationStep,
)
from katalyst_core.algorithms.cad_generation.generation_pipeline import GenerationPipeline
from katalyst_core.algorithms.docs_to_desc.stl_visual_desc import compare_stl_to_prompt
from katalyst_core.programs.executor import read_program_code
from katalyst_core.programs.storage import program_stl_path


@dataclass
class GenerationStepParallel(GenerationStep):
    steps: list[GenerationPipeline]

    def execute(
        self,
        pipeline_id: int,
        prompt: str,
        previous: list[GenerationResult],
        llm_api_key: Optional[str] = None,
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        results = []
        discarded = []
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(step.execute, pipeline_id, prompt, previous, llm_api_key)
                for step in self.steps
            ]
            for future in as_completed(futures):
                maybe_results = future.result()
                if maybe_results is None:
                    continue
                new_results, new_discarded = maybe_results
                results += new_results
                discarded += new_discarded
        return results, discarded


@dataclass
class GenerationStepPipeline(GenerationStep):
    steps: list[GenerationStep]

    def execute(
        self,
        pipeline_id: int,
        prompt: str,
        previous: list[GenerationResult],
        llm_api_key: Optional[str] = None,
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        final_results = []
        discarded = []
        for step in self.steps:
            logger.info(f"[{pipeline_id}] Executing sub step: {step}")
            results, new_discarded = step.execute(
                pipeline_id,
                prompt,
                previous if len(final_results) == 0 else final_results,
                llm_api_key,
            )
            logger.info(
                f"[{pipeline_id}] Finished sub step with {len(results)} results: {step}"
            )
            if len(results) == 0:
                return final_results, discarded
            discarded += new_discarded
            final_results = results
        return final_results, discarded


@dataclass
class GenerationStepKeepComplex(GenerationStep):
    top_n: int

    def execute(
        self, pipeline_id: int, _prompt: str, previous: list[GenerationResult], llm_api_key: Optional[str] = None
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        logger.info(
            f"[{pipeline_id}] Keeping top {self.top_n} most complex solutions out of {len(previous)}"
        )
        previous.sort(key=lambda x: len(x.code), reverse=True)
        n_kept = min(len(previous), self.top_n)
        return previous[:n_kept], previous[n_kept:]


@dataclass
class GenerationStepKeepBestRated(GenerationStep):
    top_n: int

    def execute(
        self, pipeline_id: int, _prompt: str, previous: list[GenerationResult], llm_api_key: Optional[str] = None
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        logger.info(
            f"[{pipeline_id}] Keeping top {self.top_n} best rated solutions out of {len(previous)}"
        )
        previous.sort(key=lambda x: x.rating + 0.0000001 * len(x.code), reverse=True)
        n_kept = min(len(previous), self.top_n)
        return previous[:n_kept], previous[n_kept:]


@dataclass
class GenerationStepImprove(GenerationStep):
    n: int
    max_iterations: int
    model: str
    n_examples: int

    def execute(
        self, pipeline_id: int, prompt: str, previous: list[GenerationResult], llm_api_key: Optional[str] = None
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        commented_examples = commented_results_to_examples(prompt, previous)

        def _generate_improved(initial_prompt):
            examples_prompt, _ = generate_examples_for_prompt(
                initial_prompt, top_n=self.n_examples
            )

            messages = improvement_messages(
                initial_prompt,
                examples_prompt + "\n" + commented_examples,
            )

            program_id, reasoning, success = code_run_fix_loop(
                messages,
                max_iterations=self.max_iterations,
                base_temperature=0.4,
                model=self.model,
                llm_api_key=llm_api_key,
            )

            if not success:
                return None, None, None, False

            code = read_program_code(program_id)

            return program_id, code, reasoning, success

        results = []
        with ThreadPoolExecutor() as executor:
            logger.info(f"[{pipeline_id}] Improving {self.n} solutions")
            start = time.perf_counter()
            futures = [
                executor.submit(_generate_improved, prompt) for _ in range(self.n)
            ]

            for i, future in enumerate(as_completed(futures)):
                try:
                    maybe = future.result(timeout=70)
                    if maybe is None:
                        logger.info(
                            f"[{pipeline_id}] Failed to improve solution ({i}/{self.n}) due to timeout"
                        )

                    program_id, code, reasoning, success = maybe

                    if success:
                        logger.info(
                            f"[{pipeline_id}] Improved solution ({i}/{self.n}) in {time.perf_counter() - start}s"
                        )
                        results.append(
                            GenerationResult(program_id, reasoning, code, "", None, 0)
                        )
                    else:
                        logger.info(
                            f"[{pipeline_id}] Failed to improve solution ({i}/{self.n})"
                        )
                except TimeoutError:
                    logger.info(
                        f"[{pipeline_id}] Failed to improve solution ({i}/{self.n}) due to timeout"
                    )

            logger.info(
                f"[{pipeline_id}] Improved {len(results)} successful solutions in {time.perf_counter() - start}s"
            )

        if len(results) == 0:
            logger.info(
                f"[{pipeline_id}] Improving all failed. Returning first previous solution"
            )
            results = [previous[0]]
            previous = previous[1:]

        return results, previous


@dataclass
class GenerationStepComment(GenerationStep):
    model: str

    def execute(
        self, pipeline_id: int, prompt: str, previous: list[GenerationResult]
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        def _comment(result: GenerationResult):
            maybe_comment = comment_result(prompt, result, self.model)
            if maybe_comment is None:
                return None
            result.comment = maybe_comment[0]
            result.visual_critique = maybe_comment[1][0]
            result.rating = maybe_comment[1][1]
            return result

        results = []
        with ThreadPoolExecutor() as executor:
            logger.info(f"[{pipeline_id}] Auto-commenting {len(previous)} solutions")
            start = time.perf_counter()
            futures = [executor.submit(_comment, result) for result in previous]

            for i, future in enumerate(as_completed(futures)):
                commented_result = future.result(timeout=60)
                if commented_result is not None:
                    logger.info(
                        f"[{pipeline_id}] Auto-commented solution ({i}/{len(previous)}) in {time.perf_counter() - start}s"
                    )
                    results.append(commented_result)
                else:
                    logger.info(
                        f"[{pipeline_id}] Auto-commenting failed ({i}/{len(previous)})"
                    )

            logger.info(
                f"[{pipeline_id}] Auto-commented {len(results)} solutions in {time.perf_counter() - start}s"
            )

        return results, []


@dataclass
class GenerationStepVisualRate(GenerationStep):
    model: str

    def execute(
        self, pipeline_id: int, prompt: str, previous: list[GenerationResult], llm_api_key: Optional[str] = None
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        def _rate(result: GenerationResult):
            maybe = compare_stl_to_prompt(
                program_stl_path(result.program_id), prompt, self.model, llm_api_key=llm_api_key
            )
            if maybe is None:
                maybe = compare_stl_to_prompt(
                    program_stl_path(result.program_id), prompt, self.model, llm_api_key=llm_api_key
                )
                if maybe is None:
                    return None
            result.visual_critique = maybe[0]
            result.rating = maybe[1]
            return result

        results = []
        with ThreadPoolExecutor() as executor:
            logger.info(f"[{pipeline_id}] visually rating {len(previous)} solutions")
            start = time.perf_counter()
            futures = [executor.submit(_rate, result) for result in previous]

            for i, future in enumerate(as_completed(futures)):
                commented_result = future.result(timeout=60)
                if commented_result is not None:
                    logger.info(
                        f"[{pipeline_id}] visually rated solution ({i}/{len(previous)}) in {time.perf_counter() - start}s"
                    )
                    results.append(commented_result)
                else:
                    logger.info(
                        f"[{pipeline_id}] visually rating failed ({i}/{len(previous)})"
                    )

            logger.info(
                f"[{pipeline_id}] visually rated {len(results)} solutions in {time.perf_counter() - start}s"
            )

        return results, []


@dataclass
class GenerationStepInitial(GenerationStep):
    n: int
    max_iterations: int
    model: str
    n_examples: int

    def execute(
        self, pipeline_id: int, prompt: str, previous: list[GenerationResult], llm_api_key: Optional[str] = None
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        def _generate_initial(initial_prompt):
            examples_prompt, _ = generate_examples_for_prompt(
                initial_prompt, top_n=self.n_examples
            )

            messages = initial_messages(
                initial_prompt,
                examples_prompt,
            )

            program_id, reasoning, success = code_run_fix_loop(
                messages,
                max_iterations=self.max_iterations,
                base_temperature=0.4,
                model=self.model,
                llm_api_key=llm_api_key,
            )

            if not success:
                return None, None, None, False

            code = read_program_code(program_id)

            return program_id, code, reasoning, success

        results = []
        with ThreadPoolExecutor() as executor:
            logger.info(f"[{pipeline_id}] Generating {self.n} solutions")
            start = time.perf_counter()
            futures = [
                executor.submit(_generate_initial, prompt) for _ in range(self.n)
            ]

            for i, future in enumerate(as_completed(futures)):
                maybe = future.result(timeout=60)
                if maybe is None:
                    logger.info(
                        f"[{pipeline_id}] Failed to generate solution ({i}/{self.n}) due to timeout"
                    )
                    continue

                program_id, code, reasoning, success = maybe

                if success:
                    logger.info(
                        f"[{pipeline_id}] Generated solution ({i}/{self.n}) in {time.perf_counter() - start}s"
                    )
                    results.append(
                        GenerationResult(program_id, reasoning, code, "", None, 0)
                    )
                else:
                    logger.info(
                        f"[{pipeline_id}] Failed to generate solution ({i}/{self.n})"
                    )

            logger.info(
                f"[{pipeline_id}] Generated {len(results)} successful solutions in {time.perf_counter() - start}s"
            )

        return results + previous, []
