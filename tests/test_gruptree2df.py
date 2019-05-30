# -*- coding: utf-8 -*-
"""Test module for nnc2df"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import sys
import pytest

import pandas as pd

from ecl.eclfile import EclFile
from ecl.grid import EclGrid

from ecl2df import gruptree2df
from ecl2df.eclfiles import EclFiles

TESTDIR = os.path.dirname(os.path.abspath(__file__))
DATAFILE = os.path.join(TESTDIR, "data/reek/eclipse/model/2_R001_REEK-0.DATA")


def test_gruptree2df():
    """Test that dataframes are produced"""
    eclfiles = EclFiles(DATAFILE)
    grupdf = gruptree2df.gruptree2df(eclfiles.get_ecldeck())

    assert not grupdf.empty
    assert len(grupdf["DATE"].unique()) == 5
    assert len(grupdf["CHILD"].unique()) == 10
    assert len(grupdf["PARENT"].unique()) == 3
    assert set(grupdf["TYPE"].unique()) == set(["GRUPTREE", "WELSPECS"])

    grupdfnowells = gruptree2df.gruptree2df(eclfiles.get_ecldeck(), welspecs=False)

    assert len(grupdfnowells["TYPE"].unique()) == 1
    assert grupdf["PARENT"].unique()[0] == "FIELD"
    assert grupdf["TYPE"].unique()[0] == "GRUPTREE"


def test_str2df():
    schstr = """
GRUPTREE
 'OPWEST' 'OP' /
 'OP' 'FIELD' /
 'FIELD' 'AREA' /
 'AREA' 'NORTHSEA' /
/

WELSPECS
 'OP1' 'OPWEST' 41 125 1759.74 'OIL' 0.0 'STD' 'SHUT' 'YES'  0  'SEG' /
/

"""
    deck = EclFiles.str2deck(schstr)
    grupdf = gruptree2df.gruptree2df(deck)
    assert grupdf.dropna().empty  # the DATE is empty

    withstart = gruptree2df.gruptree2df(deck, startdate="2019-01-01")
    assert not withstart.dropna().empty
    assert len(withstart) == 5


def test_main():
    """Test command line interface"""
    tmpcsvfile = ".TMP-gruptree.csv"
    sys.argv = ["gruptree2csv", DATAFILE, "-o", tmpcsvfile]
    gruptree2df.main()

    assert os.path.exists(tmpcsvfile)
    disk_df = pd.read_csv(tmpcsvfile)
    assert not disk_df.empty
    os.remove(tmpcsvfile)