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