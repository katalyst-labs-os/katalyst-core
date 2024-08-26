import math
import os
import pickle
import threading
from sentence_transformers import SentenceTransformer
import numpy as np

from katalyst_core.dataset.manage_parts import (
    DatasetStep,
    read_dataset,
    read_steps_dataset,
)
from katalyst_core.dataset.part import DatasetPart

model = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1")

CACHE_FILE_PATH = "storage/embeddings-cache.pickle"

embeddings_cache = {}
cache_lock = threading.Lock()

if os.path.exists(CACHE_FILE_PATH):
    with open(CACHE_FILE_PATH, "rb") as f:
        embeddings_cache = pickle.load(f)


def generate_examples_for_iteration_prompt(
    prompt: str, assemblies: bool = False, top_n: int = 3
):
    backends = ["cadquery:noassembly"]
    if assemblies:
        backends.append("cadquery:assembly")
    examples: list[DatasetStep] = list(
        read_steps_dataset(only_backends=backends)
    )

    prompt_embedding = model.encode(prompt)

    relevant_examples: list[tuple[DatasetStep, float]] = []
    for example in examples:
        label = example.request + " including ".join(example.edits.split("```")[::2])
        label_embedding = _get_or_compute_embedding(label)
        similarity: float = np.dot(prompt_embedding, label_embedding) / (
            np.linalg.norm(prompt_embedding) * np.linalg.norm(label_embedding)
        )
        relevant_examples.append((example, similarity))

    relevant_examples.sort(key=lambda x: x[1], reverse=True)
    top_examples = relevant_examples[:top_n]

    examples_prompt = "Here are some examples of how edit cadquery in response to similar follow-up requests:\n\n"
    for example, similarity in top_examples:
        examples_prompt += f"""
<example>
    <code-before>
    {example.code_before}
    </code-before>
    <request>
    {example.request}
    </request>
    <edits>
    {example.edits}
    </edits>
</example>
"""

    return examples_prompt


def generate_examples_for_prompt(prompt: str, assemblies: bool = False, top_n: int = 7):
    backends = ["cadquery:noassembly"]
    if assemblies:
        backends.append("cadquery:assembly")
    examples = list(read_dataset(only_backends=backends))

    prompt_embedding = _get_or_compute_embedding(prompt)

    relevant_examples: list[tuple[DatasetPart, float]] = []
    for example in examples:
        label = example.description
        # Compute or retrieve embedding for the label
        label_embedding = _get_or_compute_embedding(label)
        # Calculate cosine similarity between label_embedding and prompt_embedding
        similarity: float = np.dot(prompt_embedding, label_embedding) / (
            np.linalg.norm(prompt_embedding) * np.linalg.norm(label_embedding)
        )
        relevant_examples.append((example, similarity))

    # Sort examples by similarity and pick top top_n
    relevant_examples.sort(key=lambda x: x[1], reverse=True)
    top_examples = relevant_examples[: math.ceil(top_n * 0.7)]

    highest_similarity = top_examples[0][1]

    relevant_examples.sort(key=lambda x: x[1], reverse=False)
    out_of_scope_examples = relevant_examples[: top_n - len(top_examples)]
    mixed_examples = top_examples + out_of_scope_examples

    examples_prompt = ""
    for example, similarity in mixed_examples:
        examples_prompt += f"""<example>
<prompt>{example.description}</prompt>
<code>
{example.code}
</code>
<critique>This is perfect</critique>
</example>

"""

    return examples_prompt, highest_similarity


def _save_embeddings_cache():
    with open(CACHE_FILE_PATH, "wb") as f:
        pickle.dump(embeddings_cache, f)


def _get_or_compute_embedding(label):
    with cache_lock:
        if label not in embeddings_cache:
            embeddings_cache[label] = model.encode(label)
            _save_embeddings_cache()  # Save cache after adding new entry
        return embeddings_cache[label]
