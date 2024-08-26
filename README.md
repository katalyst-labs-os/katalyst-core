# KATALYST Core

The open-source core of KATALYST. It comprises all the algorithms needed to generate parametric CAD models, execute them, iterate on them, evaluate them and manage a dataset of designs.

It is mostly powered by the Build123D programmatic CAD Python library and by Openrouter's LLMs API endpoints. There is also some RAGging going on with the `sentence-transformers` Python library.

## User Installation

```bash
pip install -e .
```

## Dev Installation

Conda is mainly use to isolate the environment and dictate the python version. For the dependencies, we use pip.

```bash
conda env create -f environment.yml
conda activate katalyst-core
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Run scripts in `katalyst/scripts/`

```bash
pip install -e . # if not done already
python -m katalyst_core.scripts.<script_name>
```
