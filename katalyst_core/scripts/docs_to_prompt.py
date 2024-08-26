from katalyst_core.algorithms.docs_to_desc.docs_to_prompt import docs_to_prompt


if __name__ == "__main__":
    prompt = docs_to_prompt(documents=["render.stl"], text_prompt="Generate that")

    print(prompt)
