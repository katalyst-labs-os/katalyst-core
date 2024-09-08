import sys
from katalyst_core.algorithms.cad_generation.agent import Agent
from loguru import logger


if __name__ == "__main__":
    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
        level="TRACE",
        format="<green>{time:HH:mm:ss Z}</green>|<blue>{level}</blue>| <level>{message}</level>",
        filter="katalyst_core",
    )

    prompt = input("Enter a prompt for the agent: ")
    agent = Agent.initialize(prompt)
    agent.generate_initial(precision=2)
    while True:
        message = input("Enter an edit request for the agent: ")
        agent.generate_iteration(message)
