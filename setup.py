import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="accounts-svc",
    version="0.0.1",
    author="Cybermaggedon",
    author_email="mark@accountsmachine.io",
    description="accountsmachine.io back-end service",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/accountsmachine/accounts-svc.git",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    download_url = "https://github.com/accountsmachine/accounts-svc.git/archive/refs/tags/v0.0.1.tar.gz",
    install_requires=[
        'py-dmidecode',
        'gnucash-uk-vat',
        'aiohttp',
        'firebase_admin',
        'jsonnet',
        'secrets',
        'stripe',
        'piecash',
        'ixbrl-parse',
        'rdflib',
        'pandas',
    ],
    scripts=[
        "scripts/am-svc"
    ]
)
