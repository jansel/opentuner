#!/usr/bin/env python

from setuptools import setup

try:
    from pypandoc import convert
    read_md = lambda f: convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")
    read_md = lambda f: open(f, 'r', encoding='utf-8').read()

with open('requirements.txt', 'r', encoding='utf-8') as f:
    required = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

setup(
    name='opentuner',
    version='0.8.8',
    url='http://opentuner.org/',
    license='MIT',
    author='Jason Ansel',
    author_email='jansel@jansel.net',
    description='An extensible framework for program autotuning',
    long_description=read_md('README.md'),
    long_description_content_type='text/markdown',
    packages=['opentuner', 'opentuner.resultsdb', 'opentuner.utils',
              'opentuner.measurement', 'opentuner.search'],
    install_requires=required,
)
