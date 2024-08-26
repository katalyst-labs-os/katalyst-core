import json
import base64
import io
import os
from PIL import Image
import pymupdf
import tiktoken
from typing import Optional, Union, Literal
import cv2
import re
import math
from openai import OpenAI

from katalyst_core.algorithms.docs_to_desc.prompts import summarization_prompt

APIType = Literal["openai"]
JSON_REGEX = r"```json(.*?)```"

MODEL = "openai/gpt-4o-mini"


def init_client(llm_api_key: Optional[str] = None) -> OpenAI:
    return OpenAI(
        api_key=(
            llm_api_key if llm_api_key is not None else os.getenv("OPENROUTER_API_KEY")
        ),
        base_url="https://openrouter.ai/api/v1",
        timeout=100,
    )


def get_completion_llm(
    prompt: Union[str, list[dict]],
    system_prompt=None,
    model=MODEL,
    llm_api_key: Optional[str] = None,
):
    client = init_client(llm_api_key)

    if isinstance(prompt, str):
        prompt = [{"role": "user", "content": prompt}]

    if system_prompt:
        prompt = [{"role": "system", "content": system_prompt}, *prompt]

    response = client.chat.completions.create(
        model=model,
        messages=prompt,
        temperature=0.4,
    )

    return response.choices[0].message.content


def summarize(text: str, llm_api_key: Optional[str] = None) -> str:
    prompt = summarization_prompt.format(doc=text)

    response = get_completion_llm(prompt, llm_api_key=llm_api_key)

    summary = None
    retries = 0
    print(response)
    while not summary and retries < 3:
        try:
            summary = json.loads(response)
        except json.JSONDecodeError as e:
            print(e)
            match = re.search(JSON_REGEX, response, re.DOTALL).group(1).strip()
            summary = json.loads(match)
        except Exception as e:
            print(e)
        finally:
            retries += 1

    return summary["summary"]


def hierarchical_summary(
    chunked_text: list[str], llm_api_key: Optional[str] = None
) -> tuple[str, list[str]]:
    summaries = [summarize(chunk, llm_api_key=llm_api_key) for chunk in chunked_text]
    summary = summarize("\n\n".join(summaries), llm_api_key=llm_api_key)
    return summary, summaries


def create_llm_image_format(base64_image: str, media_type: str) -> str:
    """
    Create a JSON representation of an image for OpenAI API.

    Args:
        base64_image (str): The base64 encoded image.
        media_type (str): The media type of the image (e.g., 'png', 'jpeg', "webp", non-animated "gif").

    Returns:
        str: JSON string representing the image.
    """
    image_data = {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/{media_type};base64,{base64_image}",
            "detail": "high",
        },
    }
    return json.dumps(image_data)


def resize_image(image: Image.Image, max_size: int = 512) -> Image.Image:
    """
    Resize the image so that its maximum width or height does not exceed max_size pixels.

    Args:
        image_path (str): The path to the image file.
        max_size (int): The maximum size for the width or height. Default is 512.

    Returns:
        Image.Image: The resized image.
    """
    original_width, original_height = image.size
    if original_width <= max_size and original_height <= max_size:
        return image

    if original_width > original_height:
        new_width = max_size
        new_height = int((max_size / original_width) * original_height)
    else:
        new_height = max_size
        new_width = int((max_size / original_height) * original_width)

    # Resize the image
    resized_img = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    return resized_img


def convert_image_to_base64(image: Image.Image, image_ext: str) -> str:
    """
    Convert an image to a base64 encoded string.

    Args:
        image (PIL.Image.Image): The image to convert.
        image_ext (str): The image file extension (e.g., 'png', 'jpeg', "webp", non-animated "gif").

    Returns:
        str: The base64 encoded image.
    """
    buffered = io.BytesIO()
    image.save(buffered, format=image_ext.upper())
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_base64


def convert_base64_to_image(base64_image: str) -> Image.Image:
    """
    Convert a base64 encoded string to a PIL Image.

    Args:
        base64_image (str): The base64 encoded image.

    Returns:
        PIL.Image.Image: The decoded image.
    """
    image_data = base64.b64decode(base64_image)
    image = Image.open(io.BytesIO(image_data))
    return image


InputDataTypes = Union[Image.Image, list[Image.Image], str, list[dict]]


def get_num_tokens(data: InputDataTypes) -> int:
    """
    Calculate the number of tokens for a given data input.

    Args:
        data (Union[PIL.Image.Image, list[PIL.Image.Image], str]): The data to calculate tokens for.

    Returns:
        int: The number of tokens.
    """

    def calculate_image_tokens(image: Image.Image) -> int:
        """
        Calculate the number of tokens for an image.

        Args:
            image (PIL.Image.Image): The image to calculate tokens for.

        Returns:
            int: The number of tokens.
        """
        # Using example in https://openai.com/api/pricing/
        width, height = image.size

        # Constants
        base_tokens = 85
        tile_tokens = 170
        price_per_token = 0.001275 / 255  # Price per token for a 512x512 image

        # Calculate the number of tiles
        tiles_x = width // 512 + (1 if width % 512 != 0 else 0)
        tiles_y = height // 512 + (1 if height % 512 != 0 else 0)
        total_tiles = tiles_x * tiles_y

        # Calculate total tokens
        total_tile_tokens = tile_tokens * total_tiles
        total_tokens = base_tokens + total_tile_tokens

        # Calculate total price
        return math.ceil(total_tokens * price_per_token)

    if isinstance(data, Image.Image):
        return calculate_image_tokens(data)

    elif isinstance(data, list) and all(isinstance(item, Image.Image) for item in data):
        total_tokens = 0
        for image in data:
            total_tokens += calculate_image_tokens(image)
        return total_tokens

    elif isinstance(data, str):
        tokenizer = tiktoken.encoding_for_model("gpt-4o")
        return len(tokenizer.encode(data))

    elif isinstance(data, list):
        num_tokens = 0
        tokenizer = tiktoken.encoding_for_model("gpt-4o")

        for content in data:
            if content["type"] == "text":
                num_tokens += len(tokenizer.encode(content["text"]))
            elif content["type"] == "image_url":
                image = convert_base64_to_image(
                    content["image_url"]["url"].split("base64,")[1]
                )
                num_tokens += calculate_image_tokens(image)
            elif content["type"] == "image":
                image = convert_base64_to_image(content["source"]["data"])
                num_tokens += calculate_image_tokens(image)

        return num_tokens


def pdf_to_images(pdf_path: str) -> list[Image.Image]:
    """
    Convert a PDF file to a list of images.

    Args:
        pdf_path (str): The path to the PDF file.

    Returns:
        list[PIL.Image.Image]: A list of images, one for each page of the PDF.
    """
    pdf = pymupdf.open(pdf_path)
    images = []

    for page_num in range(len(pdf)):
        page = pdf[page_num]

        # Convert page to a pixmap
        pix = page.get_pixmap()

        # Convert pixmap to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = resize_image(img)
        images.append(img)

    pdf.close()
    return images


def images_to_json(images: list[Image.Image], formatting_function) -> list[dict]:
    """
    Convert a list of images to a JSON representation using a formatting function.

    Args:
        images (list[PIL.Image.Image]): The list of images to convert.
        formatting_function (function): The function to format each image.

    Returns:
        list[dict]: A list of JSON objects representing the images.
    """
    contents = []
    for image in images:
        image_data = convert_image_to_base64(image, "png")
        formatted_image = formatting_function(base64_image=image_data, media_type="png")
        contents.append(json.loads(formatted_image))
    return contents


def sort_files(
    documents: list[str],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """
    Sort a list of document paths into images, PDFs, and text files.

    Args:
        documents (list[str]): The list of document paths to sort.

    Returns:
        tuple[list[str], list[str], list[str]]: Three lists containing paths to images
    """
    images = []
    pdfs = []
    txts = []
    videos = []
    stls = []

    for doc_path in documents:
        print(doc_path)
        if doc_path.lower().endswith((".png", ".jpg", ".jpeg")):
            images.append(doc_path)
        elif doc_path.lower().endswith(".pdf"):
            pdfs.append(doc_path)
        elif doc_path.lower().endswith(".txt"):
            txts.append(doc_path)
        elif doc_path.lower().endswith(
            (".avi", ".mp4", ".mov", ".mkv", ".wmv", ".flv", ".mpeg", ".ts", ".m4v")
        ):
            videos.append(doc_path)
        elif doc_path.lower().endswith(".stl"):
            stls.append(doc_path)

    return images, pdfs, txts, videos, stls


def sample_from_video(video_path: str, sampling_rate=0.5) -> list[Image.Image]:
    """
    Samples from a video according to given sampling rate and returns a list of images

    Args:
        video_path (str): path to video
        sampling_rate (float): frames per second, how many frames to take from each second

    Returns:
        list[Image.Image]: a list of PIL images
    """
    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = video.get(cv2.CAP_PROP_FPS)
    frames_to_skip = int(fps / sampling_rate)
    curr_frame = 0
    images = []

    while curr_frame < total_frames:
        video.set(cv2.CAP_PROP_POS_FRAMES, curr_frame)
        success, frame = video.read()
        if not success:
            break
        _, buffer = cv2.imencode(".png", frame)
        images.append(Image.fromarray(cv2.cvtColor(buffer, cv2.COLOR_BGR2RGB)))
        curr_frame += frames_to_skip

    video.release()

    return images
