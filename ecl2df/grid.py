#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Extract grid information from Eclipse output files as Dataframes.

Each cell in the grid correspond to one row.

For grid cells, x, y, z for cell centre and volume is available as
geometric information. Static data (properties) can be merged from
the INIT file, and dynamic data can be merged from the Restart (UNRST)
file.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import sys
import logging
import argparse
import fnmatch
import textwrap
import datetime
import dateutil.parser

import numpy as np
import pandas as pd

from ecl2df import common, __version__

from ecl.eclfile import EclFile
from .eclfiles import EclFiles

logging.basicConfig()
logger = logging.getLogger(__name__)


def rstdates(eclfiles):
    """Return a list of datetime objects for the available dates in the RST file"""
    report_indices = EclFile.file_report_list(eclfiles.get_rstfilename())
    logger.info(
        "Restart report indices (count %s): %s",
        str(len(report_indices)),
        str(report_indices),
    )
    return [
        eclfiles.get_rstfile().iget_restart_sim_time(index).date()
        for index in range(0, len(report_indices))
    ]


def dates2rstindices(eclfiles, dates):
    """Return the restart index/indices for a given datetime or list of datetimes

      date: datetime.date or list of datetime.date, must
            correspond to an existing date. If list, it
            forces dateinheaders to be True.
            Can also be string, then the mnenomics
            'first', 'last', 'all', are supported, or ISO
            date formats. If None or empty string is supplied,
            an empty return tuple is returned.

    Raises exception if no dates are not found.

    Return: tuple, first element is
        list of integers, corresponding to restart indices. Length 1 or more.
        second element is list of corresponding datetime.date objecs, third
        is an ISO-8601 representation of the dates.
    """
    if not dates:
        return ([], [], [])

    availabledates = rstdates(eclfiles)

    supportedmnemonics = ["first", "last", "all"]

    # After this control block, chosendates is a list of dates
    # we should extract, and which exists in UNRST.
    if isinstance(dates, str):
        if dates not in supportedmnemonics:
            # Try to parse as ISO date:
            try:
                isodate = dateutil.parser.isoparse(dates).date()
            except ValueError:
                raise ValueError("date " + str(dates) + " not understood")
            if isodate not in availabledates:
                raise ValueError("date " + str(isodate) + " not found in UNRST file")
            else:
                chosendates = [isodate]
        else:
            if dates == "first":
                chosendates = [availabledates[0]]
            elif dates == "last":
                chosendates = [availabledates[-1]]
            elif dates == "all":
                chosendates = availabledates
    elif isinstance(dates, datetime.date):
        chosendates = [dates]
    elif isinstance(dates, datetime.datetime):
        chosendates = [dates.date()]
    elif isinstance(dates, list):
        chosendates = [x for x in dates if x in availabledates]
        if not chosendates:
            raise ValueError("None of the requested dates were found")
        elif len(chosendates) < len(availabledates):
            logger.warning("Not all dates found in UNRST\n")
    else:
        raise ValueError("date " + str(dates) + " not understood")

    logger.info(
        "Available dates (count %s) in RST: %s",
        str(len(availabledates)),
        str([x.isoformat() for x in availabledates]),
    )
    rstindices = [availabledates.index(x) for x in chosendates]
    isostrings = [x.isoformat() for x in chosendates]
    return (rstindices, chosendates, isostrings)


def rst2df(eclfiles, date, vectors=None, dateinheaders=False, stackdates=False):
    """Return a dataframe with dynamic data from the restart file
    for each cell, at a particular date.

    Args:
        eclfiles: EclFiles object
        date: datetime.date or list of datetime.date, must
            correspond to an existing date. If list, it
            forces dateinheaders to be True.
            Can also be string, then the mnenomics
            'first', 'last', 'all', are supported, or ISO
            date formats.
         vectors (str or list): List of vectors to include,
            glob-style wildcards supported
         dateinheaders: boolean on whether the date should
            be added to the column headers. Instead of
            SGAS as a column header, you get SGAS@YYYY-MM-DD.
         stackdates (bool): Default is false. If true, a column
            called DATE will be added and data for all restart
            dates will be added in a stacked manner. Implies
            dateinheaders False.
    """
    if not vectors:
        vectorswasdefaulted = True
        vectors = "*"  # This will include everything
    else:
        vectorswasdefaulted = False

    if not isinstance(vectors, list):
        vectors = [vectors]
    logger.info("Extracting vectors %s from RST file", str(vectors))

    # First task is to determine the restart index to extract
    # data for:
    (rstindices, chosendates, isodates) = dates2rstindices(eclfiles, date)

    logger.info("Extracting restart information at dates %s", str(isodates))

    # Determine the available restart vectors, we only include
    # those with correct length, meaning that they are defined
    # for all active cells:
    activecells = eclfiles.get_egrid().getNumActive()
    rstvectors = []
    for vec in eclfiles.get_rstfile().headers:
        if vec[1] == activecells and any(
            [fnmatch.fnmatch(vec[0], key) for key in vectors]
        ):
            rstvectors.append(vec[0])
    rstvectors = list(set(rstvectors))  # Make unique list
    # Note that all of these might not exist at all timesteps.

    if stackdates and dateinheaders:
        logger.warning("Will not put date in headers when stackdates=True")
        dateinheaders = False

    rst_dfs = {}
    for rstindex in rstindices:
        # Filter the rst vectors once more, all of them
        # might not be available at all timesteps:
        present_rstvectors = []
        for vec in rstvectors:
            try:
                if eclfiles.get_rstfile().iget_named_kw(vec, rstindex):
                    present_rstvectors.append(vec)
            except IndexError:
                pass
        logger.info(
            "Present restart vectors at index %s: %s",
            str(rstindex),
            str(present_rstvectors),
        )
        if not present_rstvectors:
            if vectorswasdefaulted:
                logger.warning(
                    "No restart vectors available at index %s", str(rstindex)
                )
            continue

        # Make the dataframe
        rst_df = pd.DataFrame(
            columns=present_rstvectors,
            data=np.hstack(
                [
                    eclfiles.get_rstfile()
                    .iget_named_kw(vec, rstindex)
                    .numpyView()
                    .reshape(-1, 1)
                    for vec in present_rstvectors
                ]
            ),
        )

        # For users convenience:
        if (
            "SWAT" in rst_df
            and "SGAS" in rst_df
            and "SOIL" not in rst_df
            and any([fnmatch.fnmatch("SOIL", key) for key in vectors])
        ):
            rst_df["SOIL"] = 1 - rst_df["SWAT"] - rst_df["SGAS"]

        # Tag the column names if requested, or if multiple rst indices
        # are asked for
        datestr = chosendates[rstindices.index(rstindex)].isoformat()
        if dateinheaders or len(rstindices) > 1 and not stackdates:
            rst_df.columns = [colname + "@" + datestr for colname in rst_df.columns]

        rst_dfs[datestr] = rst_df

    if not rst_dfs:
        return pd.DataFrame()

    if not stackdates:
        return pd.concat(rst_dfs.values(), axis=1)
    rststack = pd.concat(rst_dfs, sort=False).reset_index()
    rststack.rename(columns={"level_0": "DATE"}, inplace=True)
    del rststack["level_1"]
    return rststack


def gridgeometry2df(eclfiles):
    """Produce a Pandas Dataframe with Eclipse gridgeometry

    Order is significant, and is determined by the order from libecl, and used
    when merging with other dataframes with cell-data.

    Args:
        eclfiles (EclFiles): object holding the Eclipse output files.

    Returns:
        DataFrame: With columns I, J, K, X, Y, Z, VOLUME, one row pr. cell. The
        index of the dataframe are the global indices
    """
    if not eclfiles:
        raise ValueError
    egrid_file = eclfiles.get_egridfile()
    grid = eclfiles.get_egrid()

    if not egrid_file or not grid:
        raise ValueError("No EGRID file supplied")

    logger.info("Extracting grjd geometry from %s", str(egrid_file))
    index_frame = grid.export_index(active_only=True)
    ijk = index_frame.values[:, 0:3] + 1  # ijk from ecl.grid is off by one

    xyz = grid.export_position(index_frame)
    vol = grid.export_volume(index_frame)
    grid_df = pd.DataFrame(
        index=index_frame["active"],
        columns=["i", "j", "k", "x", "y", "z", "volume", "global_index"],
        data=np.hstack(
            (ijk, xyz, vol.reshape(-1, 1), np.array(index_frame.index).reshape(-1, 1))
        ),
    )

    # Type conversion, hstack maybe ruined the datatypes..
    grid_df["i"] = grid_df["i"].astype(int)
    grid_df["j"] = grid_df["j"].astype(int)
    grid_df["k"] = grid_df["k"].astype(int)

    # Column names should be uppercase
    grid_df.columns = [x.upper() for x in grid_df.columns]

    zonemap = eclfiles.get_zonemap()
    if zonemap:
        logger.info("Merging zonemap into grid")
        grid_df = common.merge_zones(grid_df, zonemap, kname="K")

    return grid_df


def merge_initvectors(eclfiles, dframe, initvectors, ijknames=None):
    """Merge in INIT vectors to a dataframe by I, J, K.

    Utility function for other modules to use. Normally it is sufficient
    for API users to only use the df() function.

    Args:
        eclfiles (EclFiles): Object representing the Eclipse output files
        dframe (pd.DataFrame): Table data to merge with
        initvectors (list or str): Names of INIT vectors to merge in.
        ijknames (list): Three strings that determine the I, J and K columns to use
            for merging in dframe. For compdat the 'K' is f.ex. denoted 'K1'

    Returns:
        pd.DataFrame, copy of incoming dataframe with additional columns
    """
    if not initvectors:
        # Nothing to do.
        return dframe
    if not ijknames:
        ijknames = ["I", "J", "K"]
    if len(ijknames) != 3:
        raise ValueError("ijknames must be a list of length 3")
    assert isinstance(dframe, pd.DataFrame)
    assert isinstance(eclfiles, EclFiles)

    for col in ijknames:
        assert col in dframe

    if isinstance(initvectors, str):
        initvectors = [initvectors]
    assert isinstance(initvectors, list)

    logger.info("Merging INIT data %s into dataframe", str(initvectors))
    ijkinit = df(eclfiles, vectors=initvectors)[["I", "J", "K"] + initvectors]
    return pd.merge(dframe, ijkinit, left_on=ijknames, right_on=["I", "J", "K"])


def init2df(eclfiles, vectors=None):
    """Extract information from INIT file with cell data

    Normally, you would use the df() function which will
    call this function on your behalf.

    Order is significant, as index is used for merging

    Args:
        eclfiles (EclFiles): Object that can serve the EGRID and INIT files
        vectors (str or list): List of vectors to include,
            glob-style wildcards supported.
    """
    if not vectors:
        vectors = "*"  # This will include everything
    if not isinstance(vectors, list):
        vectors = [vectors]
    logger.info("Extracting vectors %s from INIT file", str(vectors))

    init = eclfiles.get_initfile()
    egrid = eclfiles.get_egrid()

    # Build list of vector names to include:
    usevectors = []
    include_porv = False
    for vec in init.headers:
        if vec[1] == egrid.getNumActive() and any(
            [fnmatch.fnmatch(vec[0], key) for key in vectors]
        ):
            usevectors.append(vec[0])
        if vec[0] == "PORV" and any([fnmatch.fnmatch("PORV", key) for key in vectors]):
            include_porv = True

    if usevectors:
        init_df = pd.DataFrame(
            columns=usevectors,
            data=np.hstack(
                [
                    init.iget_named_kw(vec, 0).numpyView().reshape(-1, 1)
                    for vec in usevectors
                ]
            ),
        )
        # libecl emits a number around -1.0000000200408773e+20 which
        # should be considered Not-a-number
        init_df = init_df.where(init_df > -1e20 + 1e13)  # some trial and error

        # Remove columns that are all NaN:
        init_df.dropna(axis="columns", how="all", inplace=True)

    else:
        init_df = pd.DataFrame()  # empty

    # PORV is indexed by active_index, not global, needs special treatment:
    if include_porv:
        porv_numpy = init.iget_named_kw("PORV", 0).numpyView()
        glob_idxs = [
            egrid.get_global_index(active_index=ix)
            for ix in range(egrid.getNumActive())
        ]
        init_df["PORV"] = porv_numpy[glob_idxs].reshape(-1, 1)
    return init_df


def df(
    eclfiles,
    vectors="*",
    dropconstants=False,
    rstdates=None,
    dateinheaders=False,
    stackdates=False,
):
    """Produce a dataframe with grid information

    Grid information (center coordinates x, y, z), cell
    indices (i, j, k) (indices follow the Eclipse convention starting
    at 1, not zero as in libecl), properties from INIT, and optionally
    any time dependent data from Restart files.

    Args:
        eclfiles (EclFiles): Handle to an Eclipse case
        vectors (str or list): Vectors to include, wildcards
            supported. Used to match both
            INIT vectors and RESTART vectors.
        dropconstants (bool): If true, columns that are constant
            for every cell are dropped.
        rstdates (list, str or datetime): Restart dates to include in ISO-8601 format.
            Alternatively, pick from the mnenomics 'first', 'all' and 'last'.
        dateinheaders (bool): Whether columns with data from UNRST files
            should always have the ISO-date embedded in the column header.
        stackdates (bool): Default is false. If true, a column
            called DATE will be added and data for all restart
            dates will be added in a stacked manner. Implies
            dateinheaders False.
    """
    gridgeom = gridgeometry2df(eclfiles)
    initdf = init2df(eclfiles, vectors=vectors)
    rst_df = None
    if rstdates:
        rst_df = rst2df(
            eclfiles,
            rstdates,
            vectors=vectors,
            dateinheaders=dateinheaders,
            stackdates=stackdates,
        )
    grid_df = pd.concat([gridgeom, initdf, rst_df], axis=1, sort=False)
    if dropconstants:
        grid_df = drop_constant_columns(grid_df)
    return grid_df


def fill_parser(parser):
    """Set up sys.argv parser.

    Arguments:
        parser: argparse.ArgumentParser or argparse.subparser
    """
    parser.add_argument(
        "DATAFILE",
        help="Name of Eclipse DATA file. " + "INIT and EGRID file must lie alongside.",
    )
    parser.add_argument(
        "--vectors",
        "--initkeys",  # --initkeys is deprecated
        nargs="+",
        help="INIT and/or restart wildcards for vectors to include",
        default="*",
    )
    parser.add_argument(
        "--rstdates",
        "--rstdate",  # --rstdate is deprecated
        type=str,
        help="Point in time to grab restart data from, "
        + "either 'first' or 'last', 'all', or a date in "
        + "YYYY-MM-DD format",
        default="",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Name of output csv file. Use '-' for stdout.",
        default="eclgrid.csv",
    )
    parser.add_argument(
        "--stackdates",
        action="store_true",
        help=(
            "If set, the dates from restart data will not be in the column "
            "but instead there will be a DATE column with the dates. Note "
            "that the static data will be repeated for each DATE."
        ),
    )

    parser.add_argument(
        "--dropconstants",
        action="store_true",
        help="Drop constant columns from the dataset",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Be verbose")
    return parser


def drop_constant_columns(dframe, alwayskeep=None):
    """Drop/delete constant columns from a dataframe.

    Args:
        dframe: pd.DataFrame
        alwayskeep: string or list of strings of columns to keep
           anyway.
    Returns:
        pd.DataFrame with equal or less columns.
   """
    if not alwayskeep:
        alwayskeep = []
    if isinstance(alwayskeep, str):
        alwayskeep = [alwayskeep]
    if not isinstance(alwayskeep, list):
        raise TypeError("alwayskeep must be a list")
    if not isinstance(dframe, pd.DataFrame):
        raise TypeError("dropconstants() needs a dataframe")
    if dframe.empty:
        return dframe

    columnstodelete = []
    for col in set(dframe.columns) - set(alwayskeep):
        if len(dframe[col].unique()) == 1:
            columnstodelete.append(col)
    if columnstodelete:
        logging.info("Deleting constant columns %s", str(columnstodelete))
    return dframe.drop(columnstodelete, axis=1)


def df2ecl(
    grid_df, keywords, eclfiles=None, dtype=None, filename=None, nocomments=False
):
    """
    Write an include file with grid data keyword, like PERMX, PORO,
    FIPNUM etc, for the GRID section of the Eclipse deck.

    Output (returned as string and optionally written to file) will then
    contain f.ex:

        PERMX
           3.3 4.1 500.1 8543.0 1223.0 5022.0
           411.455 4433.9
        /

    if the grid contains 8 cells (inactive and active).

    Args:
        grid_df (pd.DataFrame). Dataframe with the keyword for which
            we want to export data, and also the a column with GLOBAL_INDEX.
            Without GLOBAL_INDEX, the output will likely be invalid.
            The grid can contain both active and inactive cells.
        keywords (str or list of str): The keyword(s) to export, with one value for every cell.
        eclfiles (EclFiles): If provided, the total cell count for the grid
            will be requested from this object. If not, it will be *guessed*
            from the maximum number of GLOBAL_INDEX, which can be under-estimated
            in the corner-case that the last cells are inactive.
        dtype (float or int-class): If provided, the columns which are
            outputted are converted to int or float. Dataframe columns
            read from CSV files easily gets the wrong type, while Eclipse
            might require some data to be strictly integer.
        filename (str): If provided, the string produced will also to be
            written to this filename.
        nocomments (bool): Set to True to avoid any comments being written. Defaults
            to False.
    """
    if isinstance(keywords, str):
        keywords = [keywords]

    if isinstance(dtype, str):
        if dtype.startswith("int"):
            dtype = int
        elif dtype.startswith("float"):
            dtype = float
        else:
            raise ValueError("Wrong dtype argument {}".format(dtype))

    # Figure out the total number of cells for which we need to export data for:
    global_size = None
    active_cells = None
    if eclfiles is not None:
        if eclfiles.get_egrid() is not None:
            global_size = eclfiles.get_egrid().get_global_size()
            active_cells = eclfiles.get_egrid().getNumActive()

    if "GLOBAL_INDEX" not in grid_df:
        logger.warning(
            (
                "Global index not found in grid dataframe. "
                "Assumes all cells are active"
            )
        )
        # Drop NaN rows for columns to be used (triggerd by stacked dates and no global index, unlikely)
        # Also copy dataframe to avoid side-effects on incoming data.
        grid_df = grid_df.dropna(
            axis="rows", subset=[keyword for keyword in keywords if keyword in grid_df]
        )
        grid_df["GLOBAL_INDEX"] = grid_df.index

    if global_size is None:
        global_size = int(grid_df["GLOBAL_INDEX"].max() + 1)
        active_cells = len(grid_df[grid_df.index >= 0])
        logger.warning("Global grid size estimated to %s", str(global_size))

    ecl2df_header = (
        "Output file printed by "
        + "ecl2df.grid "
        + __version__
        + "\n"
        + " at "
        + str(datetime.datetime.now())
    )

    string = ""
    if not nocomments:
        string += common.comment_formatter(ecl2df_header)
    string += "\n"

    # If we have NaNs in the dataframe, we will be more careful (costs memory)
    if grid_df.isna().any().any():
        grid_df = grid_df.dropna(
            axis="rows", subset=[keyword for keyword in keywords if keyword in grid_df]
        )

    for keyword in keywords:
        if keyword not in grid_df.columns:
            raise ValueError("Keyword {} not found in grid dataframe".format(keyword))
        vector = np.zeros(global_size)
        vector[grid_df["GLOBAL_INDEX"].astype(int).values] = grid_df[keyword]
        if dtype == int:
            vector = vector.astype(int)
        if dtype == float:
            vector = vector.astype(float)
        if len(vector) != global_size:
            logger.warning(
                "Mismatch between dumped vector length %d from df2ecl and assumed grid size %d",
                len(vector),
                global_size,
            )
            logger.warning("Data will be dumped, but may error in simulator")
        strvector = "  ".join([str(x) for x in vector])
        strvector = common.runlength_eclcompress(strvector)

        string += keyword + "\n"
        indent = " " * 5
        string += "\n".join(
            textwrap.wrap(
                strvector, initial_indent=indent, subsequent_indent=indent, width=70
            )
        )
        string += "\n/"
        if not nocomments:
            string += " -- {}: {} active cells, {} total cell count\n".format(
                keyword, active_cells, global_size
            )
        string += "\n"

    if filename is not None:
        # Make directory if not present:
        filenamedir = os.path.dirname(filename)
        if filenamedir and not os.path.exists(filenamedir):
            os.makedirs(filenamedir)
        with open(filename, "w") as file_handle:
            file_handle.write(string)

    return string


def main():
    """Entry-point for module, for command line utility. Deprecated to use
    """
    logger.warning("eclgrid2csv is deprecated, use 'ecl2csv grid <args>' instead")
    parser = argparse.ArgumentParser()
    parser = fill_parser(parser)
    args = parser.parse_args()
    grid_main(args)


def grid_main(args):
    """This is the command line API"""
    if args.verbose:
        logger.setLevel(logging.INFO)
    eclfiles = EclFiles(args.DATAFILE)
    grid_df = df(
        eclfiles,
        vectors=args.vectors,
        rstdates=args.rstdates,
        dropconstants=args.dropconstants,
        stackdates=args.stackdates,
    )
    if args.output == "-":
        # Ignore pipe errors when writing to stdout.
        from signal import signal, SIGPIPE, SIG_DFL

        signal(SIGPIPE, SIG_DFL)
        grid_df.to_csv(sys.stdout, index=False)
    else:
        grid_df.to_csv(args.output, index=False)
        print("Wrote to " + args.output)
