"""
pipeline/preprocessing.py
 
Data ingestion & preprocessing for the Solar Flare Detector project.
Owner: Prakriti (Data Ingestion & Preprocessing)
 
Reads raw FITS light curves from:
    - SoLEXS  (soft X-ray, 1-15 keV)   -> data/raw/
    - HEL1OS  (hard X-ray, 12-200 keV) -> data/raw/hel1os/
 
Produces a single aligned time series consumed by the rest of the team:
    columns: timestamp, solexs_flux, hel1os_flux, quality_flag
    written to: data/processed/
 
STATUS NOTE (read before trusting column names):
Aditya-L1 light curve FITS files are OGIP-compliant. That standard defines
a TIME column (seconds since a reference epoch given in the header, e.g.
MJDREF/TIMESYS/TSTART) and a RATE column (+ optional ERROR). This module
assumes that convention but does NOT hard-code exact header keywords --
`inspect_fits` (below) should be run against a real sample file first to
confirm names before this is trusted on real mission data.
"""
 
from __future__ import annotations
 
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
 
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.time import Time
from astropy import units as u
 
logger = logging.getLogger(__name__)
 
# --------------------------------------------------------------------------
# Config: candidate column/keyword names, in priority order.
# If a real file uses something else, add it here rather than editing the
# parsing logic itself.
# --------------------------------------------------------------------------
 
TIME_COL_CANDIDATES = ["TIME", "Time", "time"]
FLUX_COL_CANDIDATES = ["RATE", "COUNT_RATE", "COUNTS", "FLUX", "Rate"]
ERROR_COL_CANDIDATES = ["ERROR", "STAT_ERR", "RATE_ERR"]
 
# OGIP time-reference keywords, checked in this order.
MJDREF_KEYS = [("MJDREFI", "MJDREFF"), ("MJDREF", None)]
TIMESYS_KEY = "TIMESYS"
TIMEUNIT_KEY = "TIMEUNIT"
TSTART_KEY = "TSTART"
 
 
@dataclass
class RawLightCurve:
    """Container for a single instrument's parsed light curve, pre-alignment."""
 
    instrument: str  # "solexs" or "hel1os"
    timestamp: pd.Series  # tz-aware pandas Timestamps (UTC)
    flux: pd.Series
    error: Optional[pd.Series]
    source_path: Path
    header_meta: dict
 
 
def inspect_fits(path: str | Path) -> None:
    """
    Print the HDU structure, column names, and relevant time keywords for a
    FITS file. Run this against a real sample file BEFORE trusting the
    parser on mission data -- it tells you whether TIME_COL_CANDIDATES /
    FLUX_COL_CANDIDATES need to be extended.
    """
    path = Path(path)
    with fits.open(path) as hdul:
        print(f"\n=== {path.name} ===")
        hdul.info()
        for i, hdu in enumerate(hdul):
            if hasattr(hdu, "columns") and hdu.columns is not None:
                print(f"\n-- HDU[{i}] '{hdu.name}' columns --")
                for col in hdu.columns:
                    print(f"   {col.name!r:20s} format={col.format}")
                print(f"-- HDU[{i}] relevant header keywords --")
                for key in ("MJDREFI", "MJDREFF", "MJDREF", "TIMESYS",
                            "TIMEUNIT", "TSTART", "TSTOP", "TIMEPIXR",
                            "TELESCOP", "INSTRUME", "TIMEDEL"):
                    if key in hdu.header:
                        print(f"   {key} = {hdu.header[key]}")
 
 
def _find_column(colnames: list[str], candidates: list[str], label: str) -> str:
    for cand in candidates:
        if cand in colnames:
            return cand
    raise KeyError(
        f"Could not find a {label} column. Looked for {candidates}, "
        f"found columns: {colnames}. Run inspect_fits() on this file and "
        f"add the real column name to the *_COL_CANDIDATES list."
    )
 
 
def _resolve_time_epoch(header: fits.Header) -> Time:
    """
    Determine the reference epoch (as an astropy Time) for a TIME column,
    following the OGIP convention: TIME is seconds since MJDREF (or
    MJDREFI + MJDREFF), interpreted in TIMESYS (default UTC).
    """
    timesys = header.get(TIMESYS_KEY, "UTC")
 
    for int_key, frac_key in MJDREF_KEYS:
        if int_key in header:
            mjd = header[int_key] + (header[frac_key] if frac_key and frac_key in header else 0.0)
            return Time(mjd, format="mjd", scale=timesys.lower() if timesys.lower() in ("utc", "tt", "tai") else "utc")
 
    if TSTART_KEY in header:
        # Fallback: some products give TSTART directly in MJD.
        return Time(header[TSTART_KEY], format="mjd", scale="utc")
 
    raise KeyError(
        "No MJDREF/MJDREFI+MJDREFF/TSTART keyword found in header -- cannot "
        "convert TIME column to absolute timestamps. Run inspect_fits() to "
        "see what time keywords this file actually has."
    )
 
 
def _parse_lightcurve_fits(path: str | Path, instrument: str) -> RawLightCurve:
    """
    Shared parsing logic for OGIP-style light curve FITS files.
    Picks the first binary table HDU that has both a time-like and a
    flux-like column.
    """
    path = Path(path)
    with fits.open(path) as hdul:
        table_hdu = None
        for hdu in hdul:
            if hasattr(hdu, "columns") and hdu.columns is not None:
                names = hdu.columns.names
                if any(c in names for c in TIME_COL_CANDIDATES) and \
                   any(c in names for c in FLUX_COL_CANDIDATES):
                    table_hdu = hdu
                    break
 
        if table_hdu is None:
            raise ValueError(
                f"{path.name}: no HDU found with both a time and flux "
                f"column. Run inspect_fits('{path}') to see what's in it."
            )
 
        colnames = table_hdu.columns.names
        time_col = _find_column(colnames, TIME_COL_CANDIDATES, "time")
        flux_col = _find_column(colnames, FLUX_COL_CANDIDATES, "flux")
 
        data = table_hdu.data
        raw_time = np.asarray(data[time_col], dtype="float64")
        raw_flux = np.asarray(data[flux_col], dtype="float64")
 
        error_col = None
        for cand in ERROR_COL_CANDIDATES:
            if cand in colnames:
                error_col = cand
                break
        raw_error = np.asarray(data[error_col], dtype="float64") if error_col else None
 
        # Convert TIME (seconds offset) -> absolute UTC timestamps.
        header = table_hdu.header
        epoch = _resolve_time_epoch(header)
        abs_time = epoch + raw_time * u.s
        timestamps = pd.to_datetime(abs_time.utc.isot)
 
        meta = {
            "telescope": header.get("TELESCOP"),
            "instrument_hdr": header.get("INSTRUME"),
            "time_col": time_col,
            "flux_col": flux_col,
            "error_col": error_col,
            "n_rows": len(raw_time),
        }
 
        logger.info(
            "Parsed %s (%s): %d rows, time_col=%s flux_col=%s",
            path.name, instrument, len(raw_time), time_col, flux_col,
        )
 
        return RawLightCurve(
            instrument=instrument,
            timestamp=pd.Series(timestamps, name="timestamp"),
            flux=pd.Series(raw_flux, name="flux"),
            error=pd.Series(raw_error, name="error") if raw_error is not None else None,
            source_path=path,
            header_meta=meta,
        )
 
 
def parse_solexs_fits(path: str | Path) -> RawLightCurve:
    """Parse a SoLEXS (soft X-ray, 1-15 keV) light curve FITS file."""
    return _parse_lightcurve_fits(path, instrument="solexs")
 
 
def parse_hel1os_fits(path: str | Path) -> RawLightCurve:
    """Parse a HEL1OS (hard X-ray, 12-200 keV) light curve FITS file."""
    return _parse_lightcurve_fits(path, instrument="hel1os")
 
 
# --------------------------------------------------------------------------
# Step 2: Time alignment / resampling onto a common grid.
#
# Grid choice: 1-second steps, matching SoLEXS's native cadence (the finer
# of the two instruments). SoLEXS values are used as-is at each grid point
# (or lightly interpolated if a sample is missing); HEL1OS values (coarser,
# e.g. 2s cadence) are interpolated up onto the 1s grid.
# --------------------------------------------------------------------------
 
# How far (in seconds) either instrument's nearest real sample may be from
# a grid point before we refuse to interpolate and leave NaN instead.
# This is a *default* wired to gap-handling in step 3; alignment itself
# just needs a coarse safety cap so we never interpolate across an absurd
# distance (e.g. across a multi-hour data outage).
_MAX_INTERP_GAP_SECONDS = 300  # 5 minutes; step 3 will refine this per-column
 
 
def _to_grid(series_time: pd.Series, series_value: pd.Series, grid: pd.DatetimeIndex) -> pd.Series:
    """
    Linearly interpolate one instrument's (time, value) samples onto `grid`.
    Points on `grid` that fall outside the instrument's own observed time
    range, or further than _MAX_INTERP_GAP_SECONDS from the nearest real
    sample on either side, are left as NaN rather than extrapolated/faked.
    """
    s = pd.Series(series_value.values, index=pd.DatetimeIndex(series_time.values)).sort_index()
    s = s[~s.index.duplicated(keep="first")]
 
    # Reindex onto the union of the instrument's own timestamps + the grid,
    # interpolate, then select just the grid points.
    combined_index = s.index.union(grid)
    interpolated = s.reindex(combined_index).interpolate(method="time", limit_area="inside")
    on_grid = interpolated.reindex(grid)
 
    # Mask out grid points too far from any real sample (avoid extrapolation
    # far beyond what step 3's gap logic would allow).
    nearest_before = s.index.searchsorted(grid, side="right") - 1
    nearest_after = s.index.searchsorted(grid, side="left")
    n = len(s.index)
 
    dist_seconds = np.full(len(grid), np.inf)
    for i, g in enumerate(grid):
        candidates = []
        if 0 <= nearest_before[i] < n:
            candidates.append(abs((g - s.index[nearest_before[i]]).total_seconds()))
        if 0 <= nearest_after[i] < n:
            candidates.append(abs((s.index[nearest_after[i]] - g).total_seconds()))
        if candidates:
            dist_seconds[i] = min(candidates)
 
    too_far = dist_seconds > _MAX_INTERP_GAP_SECONDS
    on_grid = on_grid.mask(too_far)
 
    return on_grid.reset_index(drop=True)
 
 
def align_lightcurves(solexs: RawLightCurve, hel1os: RawLightCurve) -> pd.DataFrame:
    """
    Resample both instruments' light curves onto a common 1-second grid
    (SoLEXS's native cadence). Returns a DataFrame with columns:
        timestamp, solexs_flux, hel1os_flux
    Grid spans the overlap of both instruments' observed time ranges.
    quality_flag is added separately in step 3.
    """
    start = max(solexs.timestamp.min(), hel1os.timestamp.min())
    end = min(solexs.timestamp.max(), hel1os.timestamp.max())
 
    if start >= end:
        raise ValueError(
            "SoLEXS and HEL1OS time ranges do not overlap -- nothing to align. "
            f"SoLEXS: [{solexs.timestamp.min()}, {solexs.timestamp.max()}], "
            f"HEL1OS: [{hel1os.timestamp.min()}, {hel1os.timestamp.max()}]"
        )
 
    grid = pd.date_range(start=start, end=end, freq="1s")
 
    solexs_on_grid = _to_grid(solexs.timestamp, solexs.flux, grid)
    hel1os_on_grid = _to_grid(hel1os.timestamp, hel1os.flux, grid)
 
    df = pd.DataFrame({
        "timestamp": grid,
        "solexs_flux": solexs_on_grid.values,
        "hel1os_flux": hel1os_on_grid.values,
    })
 
    logger.info(
        "Aligned %d rows onto 1s grid, span %s to %s",
        len(df), start, end,
    )
    return df
 
 
# --------------------------------------------------------------------------
# Step 3: Gap and quality handling.
#
# quality_flag values (per row):
#   "good"        - both instruments have trustworthy data
#   "gap"         - one or both fluxes are NaN because the real gap in the
#                   source data exceeded MAX_GAP_MINUTES (no guessing allowed)
#   "saturated"   - a raw flux value looked pinned at/near an instrument's
#                   maximum plausible reading (sensor saturation)
# --------------------------------------------------------------------------
 
MAX_GAP_MINUTES = 2  # gaps longer than this are left as NaN, never interpolated
 
# Values at or above this are treated as "saturated" (sensor pinned at max).
# These are placeholder thresholds -- update once real instrument dynamic
# range / saturation limits are confirmed from mission documentation.
SOLEXS_SATURATION_THRESHOLD = 500.0
HEL1OS_SATURATION_THRESHOLD = 500.0
 
 
def _real_sample_gap_seconds(series_time: pd.Series, grid: pd.DatetimeIndex) -> np.ndarray:
    """
    For each point on `grid`, return the distance (seconds) to the nearest
    REAL sample in `series_time` on either side (i.e. how big is the actual
    gap in the source data around this grid point) -- not the grid spacing.
    """
    idx = pd.DatetimeIndex(series_time.values).sort_values()
    n = len(idx)
    dist = np.full(len(grid), np.inf)
 
    pos_after = idx.searchsorted(grid, side="left")
    for i, g in enumerate(grid):
        candidates = []
        pa = pos_after[i]
        if 0 <= pa < n:
            candidates.append(abs((idx[pa] - g).total_seconds()))
        if 0 <= pa - 1 < n:
            candidates.append(abs((g - idx[pa - 1]).total_seconds()))
        if candidates:
            dist[i] = min(candidates)
    return dist
 
 
def apply_quality_flags(
    df: pd.DataFrame,
    solexs: RawLightCurve,
    hel1os: RawLightCurve,
) -> pd.DataFrame:
    """
    Adds a `quality_flag` column to an already-aligned DataFrame (from
    align_lightcurves). Enforces the "real gaps stay NaN" rule: any grid
    point further than MAX_GAP_MINUTES from a real sample of either
    instrument has that instrument's flux forced to NaN (even if the
    earlier linear interpolation guessed a value), and is flagged "gap".
    Also flags saturated readings.
    """
    df = df.copy()
    grid = pd.DatetimeIndex(df["timestamp"])
    max_gap_seconds = MAX_GAP_MINUTES * 60
 
    solexs_gap = _real_sample_gap_seconds(solexs.timestamp, grid) > max_gap_seconds
    hel1os_gap = _real_sample_gap_seconds(hel1os.timestamp, grid) > max_gap_seconds
 
    # Enforce: no guessed values survive across a real gap larger than the
    # threshold, regardless of what align_lightcurves() interpolated.
    df.loc[solexs_gap, "solexs_flux"] = np.nan
    df.loc[hel1os_gap, "hel1os_flux"] = np.nan
 
    solexs_saturated = df["solexs_flux"] >= SOLEXS_SATURATION_THRESHOLD
    hel1os_saturated = df["hel1os_flux"] >= HEL1OS_SATURATION_THRESHOLD
 
    is_gap = solexs_gap | hel1os_gap
    is_saturated = (solexs_saturated | hel1os_saturated) & ~is_gap
 
    flags = np.full(len(df), "good", dtype=object)
    flags[is_saturated] = "saturated"
    flags[is_gap] = "gap"  # gap takes priority if somehow both conditions overlap
    df["quality_flag"] = flags
 
    n_gap = int(is_gap.sum())
    n_sat = int(is_saturated.sum())
    logger.info(
        "Quality flags: %d good, %d gap, %d saturated (of %d rows)",
        len(df) - n_gap - n_sat, n_gap, n_sat, len(df),
    )
    return df
 
 
# --------------------------------------------------------------------------
# Step 4/5: Public entry point + output contract.
#
# This is the function the rest of the team imports. Output columns are a
# fixed contract: timestamp, solexs_flux, hel1os_flux, quality_flag.
# Do not change this contract without raising it as a GitHub issue first.
# --------------------------------------------------------------------------
 
OUTPUT_COLUMNS = ["timestamp", "solexs_flux", "hel1os_flux", "quality_flag"]
 
 
def load_and_align(solexs_path: str | Path, hel1os_path: str | Path) -> pd.DataFrame:
    """
    Full pipeline: parse both instruments' FITS files, align them onto a
    common 1-second grid, and apply gap/saturation quality flags.
 
    Returns a DataFrame with exactly these columns, in this order:
        timestamp, solexs_flux, hel1os_flux, quality_flag
    This is the fixed output contract consumed by the detection/ML modules.
    """
    solexs = parse_solexs_fits(solexs_path)
    hel1os = parse_hel1os_fits(hel1os_path)
    df = align_lightcurves(solexs, hel1os)
    df = apply_quality_flags(df, solexs, hel1os)
    return df[OUTPUT_COLUMNS]
 
 
def process_to_parquet(
    solexs_path: str | Path,
    hel1os_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """Run load_and_align() and write the result to a parquet file."""
    df = load_and_align(solexs_path, hel1os_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info("Wrote %d rows to %s", len(df), output_path)
    return df
 
 
def _cli():
    import argparse
 
    parser = argparse.ArgumentParser(
        description="Parse, align, and quality-flag SoLEXS + HEL1OS FITS light curves."
    )
    parser.add_argument("solexs_path", help="Path to a SoLEXS FITS file")
    parser.add_argument("hel1os_path", help="Path to a HEL1OS FITS file")
    parser.add_argument(
        "-o", "--output",
        default="data/processed/aligned_lightcurve.parquet",
        help="Output parquet path (default: data/processed/aligned_lightcurve.parquet)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
 
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    process_to_parquet(args.solexs_path, args.hel1os_path, args.output)
 
 
if __name__ == "__main__":
    _cli()
 