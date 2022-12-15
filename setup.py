import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="nonebot-plugin-gachalogs",
    version="0.2.3",
    author="monsterxcn",
    author_email="monsterxcn@gmail.com",
    description="Genshin gacha history analysis plugin for NoneBot2",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/monsterxcn/nonebot-plugin-gachalogs",
    project_urls={
        "Bug Tracker": "https://github.com/monsterxcn/nonebot-plugin-gachalogs/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=["nonebot-plugin-gachalogs"],
    python_requires=">=3.7.3,<4.0",
    install_requires=[
        "nonebot2>=2.0.0a16",
        "nonebot-adapter-onebot>=2.0.0b1",
        "httpx>=0.20.0,<1.0.0",
        "matplotlib>=3.5.1",
        "xlsxWriter>=3.0.2",
        "pytz"
    ],
)
