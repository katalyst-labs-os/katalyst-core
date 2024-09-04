from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DatasetPart:
    id: int
    name: str
    description: str
    code: str
    backend: str
    files: list[str]
    author: str
    created_at: datetime
    program_id: Optional[str]

