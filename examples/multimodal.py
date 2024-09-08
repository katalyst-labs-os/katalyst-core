from katalyst_core.algorithms.docs_to_desc.docs_to_prompt import docs_to_prompt
from katalyst_core.algorithms.cad_generation.agent import Agent
from katalyst_core.programs.storage import program_dir_path

PRECISION = 1

document_path = input("Enter file path (STL, PDF, png, jpeg...): ")
prompt = docs_to_prompt(documents=[document_path], text_prompt="Generate from the documents")
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


