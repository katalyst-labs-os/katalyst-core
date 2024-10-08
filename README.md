# KATALYST Core

The open-source core of KATALYST. It comprises all the algorithms needed to generate parametric CAD models, execute them, iterate on them, evaluate them and manage a dataset of designs.

It is mostly powered by the Cadquery programmatic CAD Python library and by Openrouter's LLMs API endpoints. There is also some RAGging going on with the `sentence-transformers` Python library.

We are looking for contributors to help us grow our community's open dataset. If you'd like to contribute Cadquery or Build123d code, please [do so here](https://discord.gg/8BuBk8yuvw).

The simplest way to use KATALYST is through the [web UI](https://katalyst-labs.com).

## Installation

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
# 1 can do basic designs (around 10cts of tokens).
# 2 is like 1 but with more details (around 15cts of tokens)
# 3+ are increasingly overkill, pretty unstable, but may give surprisingly good results (around 20cts to 1$ of tokens)

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

## Goals

- Grow our Cadquery dataset to make the approach more effective (we know we can scale the quality of the approach with more data via RAG or fine-tuning)
- Update with new LLMs, if useful and as cheap as before
- Make prompting increasingly simpler/cheaper if performance can be conserved
- As RAG doesn't help much with Build123d, grow a large Build123d dataset (at least 500 examples) to fine-tune for the community one day and finally not be bad with it
- Add small changes to the generation logic that allow better UX on the KATALYST app (Node-based editing? Light UI based editing? Let us know what you'd like!)

To help us reach our goals, please join our community on [Discord](https://discord.gg/8BuBk8yuvw) or open issues.
