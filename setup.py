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
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
