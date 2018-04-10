#!/usr/bin/env python

from setuptools import setup, find_packages

metadata = {}
with open("mrbavii_xml2html/_version.py") as handle:
    exec(handle.read(), metadata)

setup(
    name="mrbavii_xml2html",
    version=metadata["__version__"],
    description=metadata["__doc__"].strip(),
    url='',
    author=metadata["__author__"],
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "mrbavii-xml2html = mrbavii_xml2html.main:main"
        ]
    }
)
