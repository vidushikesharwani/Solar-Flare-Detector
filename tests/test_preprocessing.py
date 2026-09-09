"""
tests/test_preprocessing.py
 
Unit tests for pipeline/preprocessing.py.
Uses synthetic FITS fixtures (see make_synthetic_fits.py) so these tests
run without needing real ISRO mission data.
 
Run with:  pytest tests/test_preprocessing.py -v
"""
 
from pathlib import Path
 
import numpy as np
import pandas as pd
import pytest
 
from pipeline.preprocessing import (
    OUTPUT_COLUMNS,
    align_lightcurves,
    apply_quality_flags,
    load_and_align,
    parse_hel1os_fits,
    parse_solexs_fits,
)
 
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SOLEXS_SAMPLE = FIXTURES_DIR / "solexs_sample.fits"
HEL1OS_SAMPLE = FIXTURES_DIR / "hel1os_sample.fits"
 
 
@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures_exist():
    """Generate the synthetic fixtures once before this test module runs,
    so `pytest` works standalone without a manual setup step."""
    if not SOLEXS_SAMPLE.exists() or not HEL1OS_SAMPLE.exists():
        from tests.make_synthetic_fits import make_hel1os_sample, make_solexs_sample
        FIXTURES_DIR.mkdir(exist_ok=True)
        make_solexs_sample(SOLEXS_SAMPLE)
        make_hel1os_sample(HEL1OS_SAMPLE)
 
 
# --------------------------------------------------------------------------
# Parsing tests
# --------------------------------------------------------------------------
 
def test_parse_solexs_returns_expected_row_count():
    lc = parse_solexs_fits(SOLEXS_SAMPLE)
    assert lc.instrument == "solexs"
    assert len(lc.timestamp) == 600  # 600s span, 1s cadence
    assert len(lc.flux) == len(lc.timestamp)
 
 
def test_parse_hel1os_returns_expected_row_count():
    lc = parse_hel1os_fits(HEL1OS_SAMPLE)
    assert lc.instrument == "hel1os"
    # 600s span at 2s cadence minus a 40s (20-row) injected gap
    assert len(lc.timestamp) < 300
 
 
def test_parsed_timestamps_are_monotonic_increasing():
    lc = parse_solexs_fits(SOLEXS_SAMPLE)
    assert lc.timestamp.is_monotonic_increasing
 
 
def test_parsed_flux_has_no_nans_from_source():
    """Raw parsed flux (before alignment) shouldn't introduce NaNs itself --
    any NaNs in the final output should come from quality-flag logic, not
    from a parsing bug."""
    lc = parse_solexs_fits(SOLEXS_SAMPLE)
    assert not lc.flux.isna().any()
 
 
def test_parse_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_solexs_fits(FIXTURES_DIR / "does_not_exist.fits")
 
 
# --------------------------------------------------------------------------
# Alignment tests
# --------------------------------------------------------------------------
 
def test_align_produces_one_second_grid():
    s = parse_solexs_fits(SOLEXS_SAMPLE)
    h = parse_hel1os_fits(HEL1OS_SAMPLE)
    df = align_lightcurves(s, h)
 
    diffs = df["timestamp"].diff().dropna()
    assert (diffs == pd.Timedelta(seconds=1)).all()
 
 
def test_align_has_both_flux_columns():
    s = parse_solexs_fits(SOLEXS_SAMPLE)
    h = parse_hel1os_fits(HEL1OS_SAMPLE)
    df = align_lightcurves(s, h)
 
    assert "solexs_flux" in df.columns
    assert "hel1os_flux" in df.columns
    # SoLEXS is native at 1s, so it should have essentially no NaNs pre-quality-flagging
    assert df["solexs_flux"].isna().sum() == 0
 
 
def test_align_hel1os_values_are_interpolated_not_just_copied():
    """HEL1OS is 2s cadence; on the 1s grid, the 'odd' seconds should be
    genuinely interpolated (not equal to the previous or next real value)."""
    s = parse_solexs_fits(SOLEXS_SAMPLE)
    h = parse_hel1os_fits(HEL1OS_SAMPLE)
    df = align_lightcurves(s, h)
 
    odd_second_value = df.loc[1, "hel1os_flux"]  # t=1s, between real samples at t=0 and t=2
    real_at_0 = df.loc[0, "hel1os_flux"]
    real_at_2 = df.loc[2, "hel1os_flux"]
    assert odd_second_value != real_at_0
    assert odd_second_value != real_at_2
    # should sit between the two neighbors for a smooth flare-like signal
    assert min(real_at_0, real_at_2) <= odd_second_value <= max(real_at_0, real_at_2)
 
 
def test_align_raises_on_non_overlapping_ranges():
    s = parse_solexs_fits(SOLEXS_SAMPLE)
    h = parse_hel1os_fits(HEL1OS_SAMPLE)
    # Shift hel1os timestamps far into the future so ranges don't overlap.
    h.timestamp = h.timestamp + pd.Timedelta(days=10)
    with pytest.raises(ValueError):
        align_lightcurves(s, h)
 
 
# --------------------------------------------------------------------------
# Quality flag tests -- the core "don't fake large gaps" requirement
# --------------------------------------------------------------------------
 
def test_short_gap_is_not_flagged():
    """The injected 40s HEL1OS gap is shorter than MAX_GAP_MINUTES (2 min),
    so it should be trusted/interpolated, not flagged 'gap'."""
    s = parse_solexs_fits(SOLEXS_SAMPLE)
    h = parse_hel1os_fits(HEL1OS_SAMPLE)
    df = align_lightcurves(s, h)
    df = apply_quality_flags(df, s, h)
 
    window = df[
        (df["timestamp"] >= "2020-01-01 00:04:10")
        & (df["timestamp"] <= "2020-01-01 00:04:50")
    ]
    assert (window["quality_flag"] != "gap").all()
    assert not window["hel1os_flux"].isna().any()
 
 
def test_long_gap_center_is_flagged_and_nan():
    """A gap well beyond MAX_GAP_MINUTES must leave the far-from-real-data
    center as NaN with quality_flag == 'gap' -- never a guessed value."""
    from astropy.io import fits
    import tempfile
    from tests.make_synthetic_fits import _flare_profile
 
    t = np.arange(0, 900, 2.0)
    rate = _flare_profile(t, amp=40.0, base=2.0)
    gap_mask = (t >= 400) & (t <= 700)  # 300s gap, >> 2 min threshold
    t2, rate2 = t[~gap_mask], rate[~gap_mask]
    err = np.full_like(rate2, 0.4)
 
    col_time = fits.Column(name="TIME", format="D", array=t2)
    col_rate = fits.Column(name="RATE", format="D", array=rate2)
    col_err = fits.Column(name="ERROR", format="D", array=err)
    hdu = fits.BinTableHDU.from_columns([col_time, col_rate, col_err], name="RATE")
    hdu.header["MJDREFI"] = 58849
    hdu.header["MJDREFF"] = 0.0
    hdu.header["TIMESYS"] = "UTC"
 
    with tempfile.NamedTemporaryFile(suffix=".fits", delete=False) as tmp:
        fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(tmp.name, overwrite=True)
        h_biggap = parse_hel1os_fits(tmp.name)
 
    s = parse_solexs_fits(SOLEXS_SAMPLE)
    df = align_lightcurves(s, h_biggap)
    df = apply_quality_flags(df, s, h_biggap)
 
    # true center: >120s from real data on both sides of the 300s gap
    center = df[
        (df["timestamp"] >= "2020-01-01 00:08:40")
        & (df["timestamp"] <= "2020-01-01 00:09:40")
    ]
    assert len(center) > 0
    assert (center["quality_flag"] == "gap").all()
    assert center["hel1os_flux"].isna().all()
 
 
def test_saturated_values_are_flagged():
    s = parse_solexs_fits(SOLEXS_SAMPLE)
    h = parse_hel1os_fits(HEL1OS_SAMPLE)
    df = align_lightcurves(s, h)
    df = apply_quality_flags(df, s, h)
 
    window = df[
        (df["timestamp"] >= "2020-01-01 00:05:10")
        & (df["timestamp"] <= "2020-01-01 00:05:30")
    ]
    assert (window["quality_flag"] == "saturated").all()
 
 
def test_quality_flag_only_uses_allowed_values():
    s = parse_solexs_fits(SOLEXS_SAMPLE)
    h = parse_hel1os_fits(HEL1OS_SAMPLE)
    df = load_and_align(SOLEXS_SAMPLE, HEL1OS_SAMPLE)
    assert set(df["quality_flag"].unique()) <= {"good", "gap", "saturated"}
 
 
# --------------------------------------------------------------------------
# Full pipeline / output contract tests
# --------------------------------------------------------------------------
 
def test_load_and_align_output_contract():
    """The output columns are a fixed contract with the rest of the team --
    this test should fail loudly if that contract is ever broken."""
    df = load_and_align(SOLEXS_SAMPLE, HEL1OS_SAMPLE)
    assert list(df.columns) == OUTPUT_COLUMNS
 
 
def test_load_and_align_no_duplicate_timestamps():
    df = load_and_align(SOLEXS_SAMPLE, HEL1OS_SAMPLE)
    assert not df["timestamp"].duplicated().any()
 
 
def test_load_and_align_returns_nonempty():
    df = load_and_align(SOLEXS_SAMPLE, HEL1OS_SAMPLE)
    assert len(df) > 0
