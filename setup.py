#!/usr/bin/env python
from setuptools import setup
"""
===============
s3_storage_analyser setup
===============
"""

with open("README.rst", "rb") as f:

    setup(
        name="s3_storage_analyser",
        packages=["s3_storage_analyser"],
        entry_points={
            "console_scripts": ['s3_storage_analyser = s3_storage_analyser:main']
            },
        version="0.1",
        description="S3 Storage Analyser",
        long_description=f.read().decode("utf-8"),
        author="Hugues MALPHETTES",
        author_email="hmalphettes@gmail.com",
        url="https://github.com/hmalphettes/s3_storage_analyser",
    )
