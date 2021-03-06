# -*- coding: utf-8 -*-

from os import path

from setuptools import setup

try:
    from sphinx.setup_command import BuildDoc

    cmdclass = {"build_sphinx": BuildDoc}
except ImportError:
    # Skip cmdclass when sphinx is not installed (yet)

    cmdclass = {}

# Read the contents of README.md, for PyPI
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md")) as f_handle:
    LONG_DESCRIPTION = f_handle.read()

SETUP_REQUIREMENTS = ["setuptools>=28", "setuptools_scm"]
REQUIREMENTS = [
    "libecl",
    "opm; python_version >= '3.5'",
    "pandas",
    "pyyaml>=5.1",
    "treelib",
]
TEST_REQUIREMENTS = [
    "black>=20.8b0; python_version >= '3'",
    "flake8",
    "networkx",
    "pytest",
    "sphinx",
    "sphinx-argparse",
    "sphinx_rtd_theme",
]
EXTRAS_REQUIRE = {"tests": TEST_REQUIREMENTS}

setup(
    name="ecl2df",
    use_scm_version={"write_to": "ecl2df/version.py"},
    cmdclass=cmdclass,
    description="Convert Eclipse 100 input and output to DataFrames",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url="http://github.com/equinor/ecl2df",
    author="Håvard Berland",
    author_email="havb@equinor.com",
    license="GPLv3",
    packages=["ecl2df"],
    package_dir={"ecl2df": "ecl2df"},
    package_data={"ecl2df": ["opmkeywords/*"]},
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "compdat2csv=ecl2df.compdat:main",
            "csv2ecl=ecl2df.csv2ecl:main",
            "ecl2csv=ecl2df.ecl2csv:main",
            "eclgrid2csv=ecl2df.grid:main",
            "equil2csv=ecl2df.equil:main",
            "faults2csv=ecl2df.faults:main",
            "grid2csv=ecl2df.grid:main",
            "gruptree2csv=ecl2df.gruptree:main",
            "nnc2csv=ecl2df.nnc:main",
            "pvt2csv=ecl2df.pvt:main",
            "rft2csv=ecl2df.rft:main",
            "satfunc2csv=ecl2df.satfunc:main",
            "summary2csv=ecl2df.summary:main",
            "wcon2csv=ecl2df.wcon:main",
        ]
    },
    test_suite="tests",
    install_requires=REQUIREMENTS,
    setup_requires=SETUP_REQUIREMENTS,
    extras_require=EXTRAS_REQUIRE,
    python_requires=">=2.7",
)
