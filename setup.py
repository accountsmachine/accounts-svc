import setuptools
import os

with open("README.md", "r") as fh:
    long_description = fh.read()

version = os.getenv("PACKAGE_VERSION")

setuptools.setup(
    name="accounts-svc",
    version=version,
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
    download_url = "https://github.com/accountsmachine/accounts-svc.git/archive/refs/tags/v" + version + ".tar.gz",
    install_requires=[
        'py-dmidecode',
        'gnucash-uk-vat',

        # Workaround - cachecontrol is not compatible with firebase_admin
        # https://github.com/ionrock/cachecontrol/issues/292
        'urllib3<2.0.0',

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
