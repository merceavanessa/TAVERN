from setuptools import find_packages, setup

setup(
    name='tavern',
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    version='0.1.0',
    description='TAVERN: Tool for the Analysis of various space weather datasets to study Atmospheric and geospace Variability and its Effects on geospace and Near-Earth spacecraft opeRatioN',
    author='Vanessa Mercea',
    license='MIT',
)
