summarization_prompt = """Document: {doc}

You are a professional at summarizing text.

<<< Task >>>
Your task will be to generate concise, entity-dense summaries of the above document. The documents provided are about specifications for a CAD of some compnents.

<<< Guidelines >>>
Guidelines for summarization:
- The summary should be concise (4-5 sentences, ~80 words).
- Make every word count. Do not fill with additional words which are not critical to summarize the original document.
- Do not provide introduction words like "here is a summary", or "here is a concise summary". Only provide the summary itself.
- Make space with fusion, compression, and removal of uninformative phrases like "the article discusses" and "There is no other relevant information about the component specifications.".
- The summaries should become highly dense and concise yet self-contained, i.e., easily understood without the article.
- Output the summaries in a JSON format with the following keys:
    - "summary": the summary of the document
- The summary should not contain any information not related to the compnent being designed
- Do not discuss the guidelines for summarization in your response.

<<< OUTPUT >>>
"""

questions_prompt = """You are tasked with designing a component on a CAD software.
Check the Image provided, if you need extra information about the document ask a maximum of 5 questions so that you can construct the 3D component shown in the image, the questions should help you understand the 3D object purpose, shape, parts, subparts and parameters (size, count)

<<< Guidelines >>>
- The answer to the questions should not be available in the image
- Keep the questions consice and straight to the point
- Keep the questions about important specifications and properties of the component (eg. color is not important to reconstruct the shape)
- Output the questions in a JSON format with the following keys:
    - "questions": a list of questions
"""
