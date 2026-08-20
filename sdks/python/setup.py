from setuptools import setup, find_packages

setup(
    name="chatbot-platform-sdk",
    version="1.0.0",
    description="Canonical Python SDK for Multi-Tenant Chatbot Platform",
    author="Chatbot Team",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.25.0",
        "pydantic>=2.0.0"
    ],
    python_requires=">=3.8"
)
