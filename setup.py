"""Setup script for Science OS."""

from setuptools import setup, find_packages

setup(
    name="science-os",
    version="0.1.0",
    description="Science OS - A system for autonomous LLM scientific discovery",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "sqlalchemy>=2.0.23",
        "pydantic>=2.5.0",
        "python-dotenv>=1.0.0",
        "numpy>=1.24.3",
        "matplotlib>=3.8.2",
    ],
    python_requires=">=3.10",
)

