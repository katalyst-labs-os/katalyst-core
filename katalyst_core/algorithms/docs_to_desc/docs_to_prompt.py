from typing import Optional, Any
from PIL import Image
import json
import concurrent.futures
import lancedb
from langchain_text_splitters import NLTKTextSplitter
from loguru import logger

from katalyst_core.algorithms.docs_to_desc.design_schema import Design
from katalyst_core.algorithms.docs_to_desc.utilities import (
    convert_image_to_base64,
    create_llm_image_format,
    get_num_tokens,
    hierarchical_summary,
    images_to_json,
    init_client,
    pdf_to_images,
    resize_image,
    sample_from_video,
    sort_files,
)
from katalyst_core.algorithms.stl_to_pics.to_pics import stl_to_pictures

VECDB_PATH = "storage/dataset/multimodal_vector_db"

db = lancedb.connect(VECDB_PATH)

if "dataset" in db:
    table = db["dataset"]
else:
    raise ValueError("dataset Table not found")

TOKEN_LIMIT = 30000
SAMPLING_RATE = 0.5  # Frames per second
CHUNK_SIZE = 1000
OVERLAP = 100
RETRIEVE_LIMIT = 5

MODEL = "openai/gpt-4o-mini"

SYSTEM_PROMPT = """
You are a CAD software assistant, you will be provided with text and image inputs,
your task is to generate a detailed desciption about the object in input,
this description should be in JSON format, with the following keys:
'name', 'description of its use, 'Rough shape description', 'dimensions', 'construction features', 'Special parameters for specific shapes', 'geometric constraints'
Where:
Construction Features: Elements defining object structure, like 3D geometric primitives, CAD operations likely to have been used. This has to be insanely detailed as to not miss any detail.
Parameters: What high-level parameters could be used to intuitively describe the current state of the object, and could be tweaked in the future to change it in a coherent way.
Geometric Constraints: Rules maintaining relationships between geometric elements, ensuring design integrity. Geometric constraints between 2D, 3D objects or points on objects. When you later edit the constrained geometry, the constraints are maintained.
"""


def docs_to_prompt(
    documents: list[str],
    text_prompt: Optional[str] = None,
    max_concurrent=4,
    llm_api_key: Optional[str] = None,
) -> str:
    messages = _docs_to_description_prompt(
        documents=documents, text_prompt=text_prompt, llm_api_key=llm_api_key
    )

    client = init_client(llm_api_key)

    if max_concurrent == 0:
        try:
            response = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=0.1
            )
            return response.choices[0].message.content
        except TypeError:
            try:
                response = client.chat.completions.create(
                    model=MODEL, messages=messages, temperature=0.1
                )
                return response.choices[0].message.content
            except TypeError:
                return "Description failed"
            except Exception as e:
                logger.error(e)
                return "Description failed"
        except Exception as e:
            logger.error(e)
            return "Description failed"

    def describe(_messages):
        response = client.chat.completions.create(
            model=MODEL, messages=_messages, temperature=0.6
        )
        return response.choices[0].message.content

    def pipeline(_messages):
        for i in range(1):
            description = describe(_messages)
            _messages = _messages + [{"role": "assistant", "content": description}]
            _messages = _messages + [
                {
                    "role": "user",
                    "content": "This is not detailed enough. Please provide below an even more detailed description of the object:",
                }
            ]

            logger.info(f"Description iteration {i}: \n{description}")

        return description

    description = pipeline(messages)
    return description


def _docs_to_description_prompt(
    documents: list[str],
    text_prompt: Optional[str] = None,
    llm_api_key: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Builds a multimodal prompt

    Args:
        documents (list[str]): list of file paths to images, PDFs, vidoes, and text files.
        text_prompt (Optional[str]): An optional text prompt to include in the message.
        api (str): The API to use for formatting the images. Defaults to "openai".

    Returns:
        list[dict[str, Any]]: A list of dictionaries representing the messages content to be sent to the API.
    """
    images, pdfs, txts, videos, stls = sort_files(documents)
    print(
        f"Found {len(images)} images, {len(pdfs)} pdfs, {len(videos)} videos, {len(txts)} txt, and {len(stls)} STL files"
    )

    num_tokens = 0
    parsed_docs = []

    def process_image(image_path):
        image = Image.open(image_path)
        img_ext = image_path.lower().split(".")[-1]
        if img_ext.upper() == "JPG":
            img_ext = "jpeg"
        image = resize_image(image)
        image_data = convert_image_to_base64(image, img_ext)
        tokens = get_num_tokens(image)
        doc = json.loads(
            create_llm_image_format(base64_image=image_data, media_type=img_ext)
        )
        if images and not pdfs and not txts and not videos:
            rs = table.search(image).limit(RETRIEVE_LIMIT).to_pydantic(Design)
            if len(rs) > 0:
                rag_docs = []
                rag_docs.append(
                    {
                        "type": "text",
                        "text": "The following is an example design that you can use to aid you in the designing of the object above",
                    }
                )
                rag_image_base64 = convert_image_to_base64(
                    resize_image(rs[0].image), "png"
                )
                rag_docs.append(
                    json.loads(
                        create_llm_image_format(
                            base64_image=rag_image_base64, media_type=img_ext
                        )
                    )
                )
                rag_docs.append({"type": "text", "text": "name: " + rs[0].name})
                rag_docs.append(
                    {"type": "text", "text": "description: " + rs[0].description}
                )
                rag_docs.append({"type": "text", "text": "code: " + rs[0].code})
                tokens += get_num_tokens(rag_docs)
                doc = [doc, *rag_docs]

        return tokens, doc

    def process_pdf(pdf_path):
        pdf_images = pdf_to_images(pdf_path)
        tokens = get_num_tokens(pdf_images)
        docs = images_to_json(pdf_images, create_llm_image_format)
        return tokens, docs

    def process_stl(stl_path):
        stl_images = stl_to_pictures(stl_path)
        stl_images = [Image.open(stl_image) for stl_image in stl_images]

        tokens = get_num_tokens(stl_images)
        docs = images_to_json(stl_images, create_llm_image_format)

        for image in stl_images:
            image.close()

        return tokens, docs

    def process_text(txt_path):
        with open(txt_path, "r") as f:
            text = f.read()
        tokens = get_num_tokens(text)
        doc = {"type": "text", "text": text}
        return tokens, doc

    def process_video(video_path):
        video_images = sample_from_video(video_path, sampling_rate=SAMPLING_RATE)
        tokens = get_num_tokens(video_images)
        docs = images_to_json(video_images, create_llm_image_format)
        return tokens, docs

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for image_path in images:
            futures.append(executor.submit(process_image, image_path))
        for pdf_path in pdfs:
            futures.append(executor.submit(process_pdf, pdf_path))
        for txt_path in txts:
            futures.append(executor.submit(process_text, txt_path))
        for video_path in videos:
            futures.append(executor.submit(process_video, video_path))
        for stl_path in stls:
            futures.append(executor.submit(process_stl, stl_path))

        for future in concurrent.futures.as_completed(futures):
            tokens, doc = future.result()
            num_tokens += tokens
            if isinstance(doc, list):
                parsed_docs.extend(doc)
            else:
                parsed_docs.append(doc)

    if num_tokens > TOKEN_LIMIT:
        text_splitter = NLTKTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4o", chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP
        )

        parsed_images = []
        all_text = ""
        for text in parsed_docs:
            if text["type"] == "text":
                all_text += text["text"]

            elif text["type"] == "image" or text["type"] == "image_url":
                parsed_images.append(text)

        if all_text != "":
            chunked_text = text_splitter.split_text(all_text)
            summary, _ = hierarchical_summary(chunked_text, llm_api_key)

        parsed_docs = [{"type": "text", "text": summary}, *parsed_images]

    if text_prompt:
        parsed_docs.append({"type": "text", "text": text_prompt})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": parsed_docs},
    ]

    return messages
