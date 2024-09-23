# KATALYST Core

The open-source core of KATALYST. It comprises all the algorithms needed to generate parametric CAD models, execute them, iterate on them, evaluate them and manage a dataset of designs.

It is mostly powered by the Build123D programmatic CAD Python library and by Openrouter's LLMs API endpoints. There is also some RAGging going on with the `sentence-transformers` Python library.

## Installation

Conda is mainly use to isolate the environment and dictate the python version. For the dependencies, we use pip.

```bash
conda env create -f environment.yml
conda activate katalyst-core
pip install -r requirements.txt
pip install -r requirements-dev.txt # if for development
pip install -e .
```

Download [the latest dataset](https://api.katalyst-labs.com/dataset/download) and put it under `storage/dataset` as to have:

```
- storage/dataset/
    - dataset.csv
    - steps.csv
    - files/
        - ...
```

## Usage example

Via the `run_agent` script:

```bash
python katalyst-core/scripts/run_agent.py
```

Via code:

```py
from katalyst_core.algorithms.cad_generation.agent import Agent
from katalyst_core.programs.storage import program_dir_path

PRECISION = 1
# precision goes from 0 (most inexpensive, dumbest) to 6 (most expensive, most refined)
# 0 is cheap but can at best do slight edits of what's in the dataset, otherwise it fails often (around 2cts of tokens)
# 1 can do basic things without failing most of the time (around 10cts of tokens).
# 2 is like 1 but with more details and less fails (around 50cts of tokens)
# 3+ are increasingly overkill, pretty unstable, but may give surprisingly good results (around 1 to 5$ of tokens)

prompt = input("Enter a prompt for the agent: ")
agent = Agent.initialize(prompt)
program_id = agent.generate_initial(precision=PRECISION)
while True:
    if program_id is None:
        print("It failed")
        break
    else:
        result_dir = program_dir_path(program_id)
        print(f"Result located under: {result_dir}")

    message = input("Enter an edit request for the agent: ")
    program_id = agent.generate_iteration(message)
```

For more examples, see the [examples directory](./examples/).