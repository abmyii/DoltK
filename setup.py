#!/usr/bin/env python3
from distutils.core import setup

try:
    # Setuptools only needed for building the package
    import setuptools  # noqa
except ImportError:
    pass


with open('requirements.txt') as f:
    required = f.read().splitlines()


setup(
    name="doltk",
    version="0.1",
    description="Dolt repository browser",
    author="Abdurrahmaan Iqbal",
    author_email="abdurrahmaaniqbal@hotmail.com",
    url="https://github.com/abmyii/DoltK",
    download_url="https://github.com/abmyii/DoltK",
    packages=["models"],
    scripts=["doltk.py"],
    install_requires=required,
    classifiers=[
      'Development Status :: 3 - Alpha',
      'Environment :: X11 Applications :: Qt',
      'Intended Audience :: Developers',
      'Operating System :: OS Independent',
      'Programming Language :: Python',
      'Programming Language :: Python :: 3.4',
      'Programming Language :: Python :: 3.5',
      'Programming Language :: Python :: 3.6',
      'Programming Language :: Python :: 3.7',
      'Programming Language :: Python :: 3.8',
      'Topic :: Database',
      'Topic :: Database :: Front-Ends',
      'Topic :: Utilities',
    ],
    keywords=("data viewer gui dolt gitk doltk database"),
)
