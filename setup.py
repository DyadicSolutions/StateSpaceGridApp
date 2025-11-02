from setuptools import setup, find_packages

setup(
    name="StateSpaceGridApp",
    version="0.0.1",
    packages=find_packages(),
    description="GUI for 2D state space grid diagrams and measures for dynamic systems",
    install_requires=[
        "StateSpaceGridLib @ git+https://github.com/DyadicSolutions/StateSpaceGridLib",
        "pandas",
        "matplotlib",
        "PySide6"
    ],
)