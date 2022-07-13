from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="sparksql-helper",
    version="0.0.8",
    license="MIT",
    author="Felix Zhu",
    author_email="zhu.felix@outlook.com",
    description="SparkSQL Helper",
    long_description=long_description,
    packages=find_packages(),
    setup_requires=["setuptools_scm"],
    url="https://github.com/felixzhu17/SparkSqlHelper",
    install_requires=[
        "pandas",
        "loguru",
        "tqdm",
        "pyspark",
    ],
)
