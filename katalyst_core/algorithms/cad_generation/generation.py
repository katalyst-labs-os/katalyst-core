from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GenerationResult:
    program_id: str
    reasoning: str
    code: str
    comment: str
    visual_critique: Optional[str] = None
    rating: int = 0


class GenerationStep(ABC):
    @abstractmethod
    def execute(
        self,
        pipeline_id: int,
        prompt: str,
        previous: list[GenerationResult],
        llm_api_key: Optional[str] = None,
    ) -> tuple[list[GenerationResult], list[GenerationResult]]:
        pass
