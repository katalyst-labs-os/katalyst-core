from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="katalyst-core",
    version="0.1.0",
    author="Anicet Nougaret",
    author_email="",
    description="KATALYST's core library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/katalyst-labs-os",
    packages=find_packages(),
    install_requires=[
        "python-dotenv",
        "openai",
        "loguru",
        "vtk",
        "numpy==1.26.4",
        "build123d",
        "airfoils",
        "bd-warehouse @ git+https://github.com/gumyr/bd_warehouse",
        "sentence-transformers==3.0.1",
        "pymupdf",
        "tiktoken",
        "pandas",
        "lancedb==0.9.0",
        "opencv-python==4.10.0.84",
        "open_clip_torch==2.26.1",
        "langchain-community==0.2.7",
        "beautifulsoup4"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
