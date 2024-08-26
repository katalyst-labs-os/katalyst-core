import random


type ProgramId = str


def new_program_id() -> str:
    lower_bound = 1_000_000_000_000
    higher_bound = 9_000_000_000_000
    # should be enough to avoid collisions
    return str(random.randint(lower_bound, higher_bound))
