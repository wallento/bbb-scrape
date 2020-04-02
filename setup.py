import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="bbb-scrape",
    author="Stefan Wallentowitz",
    author_email="stefan.wallentowitz@hm.edu",
    description="Scrape BBB meeting",
    url="https://github.com/wallento/bbb-scrape",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    install_requires=["requests"],
    setup_requires=[
        'setuptools_scm',
    ],
    use_scm_version={
        "relative_to": __file__,
        "write_to": "bbbscrape/version.py",
    },
    entry_points={
        "console_scripts": [
            "bbb-scrape = bbbscrape.main:main"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
)
