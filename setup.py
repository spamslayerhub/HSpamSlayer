from setuptools import setup, find_packages

setup(
    name="HSpamSlayer",
    version="4.0.0-dev",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    tests_require=["pytest"],
)
