from pathlib import Path
 
import numpy as np
from astropy.io import fits
 
 
def _flare_profile(t, peak_t=300, rise=20, decay=80, amp=100.0, base=5.0):
    profile = np.where(
        t < peak_t,
        base + amp * np.exp(-((t - peak_t) ** 2) / (2 * rise ** 2)),
        base + amp * np.exp(-(t - peak_t) / decay),
    )
    return profile
 
 
def make_solexs_sample(out_path: Path, mjdrefi=58849, mjdreff=0.0):
    """1 Hz cadence, clean (no gaps) -- represents SoLEXS soft X-ray."""
    t = np.arange(0, 600, 1.0)  # seconds since epoch, 1s cadence
    rate = _flare_profile(t, amp=150.0, base=8.0)
    rate += np.random.default_rng(1).normal(0, 0.5, size=t.shape)
    err = np.full_like(rate, 0.5)
 
    col_time = fits.Column(name="TIME", format="D", array=t)
    col_rate = fits.Column(name="RATE", format="D", array=rate)
    col_err = fits.Column(name="ERROR", format="D", array=err)
    hdu = fits.BinTableHDU.from_columns([col_time, col_rate, col_err], name="RATE")
    hdu.header["MJDREFI"] = mjdrefi
    hdu.header["MJDREFF"] = mjdreff
    hdu.header["TIMESYS"] = "UTC"
    hdu.header["TIMEUNIT"] = "s"
    hdu.header["TELESCOP"] = "ADITYA-L1"
    hdu.header["INSTRUME"] = "SoLEXS"
 
    primary = fits.PrimaryHDU()
    fits.HDUList([primary, hdu]).writeto(out_path, overwrite=True)
 
 
def make_hel1os_sample(out_path: Path, mjdrefi=58849, mjdreff=0.0):
    """
    2s cadence (different from SoLEXS) -- represents HEL1OS hard X-ray.
    Injects:
      - a 40s dropout gap (rows simply missing, t=250..290)
      - a saturation stretch where RATE is pinned at a max value (t=310..330)
    """
    t = np.arange(0, 600, 2.0)  # 2s cadence
    rate = _flare_profile(t, amp=40.0, base=2.0)
    rate += np.random.default_rng(2).normal(0, 0.3, size=t.shape)
 
    # Inject saturation: clip a stretch to a fixed ceiling value.
    sat_mask = (t >= 310) & (t <= 330)
    rate[sat_mask] = 999.0  # obviously saturated/pinned value
 
    # Inject a dropout gap: remove rows entirely (simulates missing telemetry).
    gap_mask = (t >= 250) & (t <= 290)
    t = t[~gap_mask]
    rate = rate[~gap_mask]
    err = np.full_like(rate, 0.4)
 
    col_time = fits.Column(name="TIME", format="D", array=t)
    col_rate = fits.Column(name="RATE", format="D", array=rate)
    col_err = fits.Column(name="ERROR", format="D", array=err)
    hdu = fits.BinTableHDU.from_columns([col_time, col_rate, col_err], name="RATE")
    hdu.header["MJDREFI"] = mjdrefi
    hdu.header["MJDREFF"] = mjdreff
    hdu.header["TIMESYS"] = "UTC"
    hdu.header["TIMEUNIT"] = "s"
    hdu.header["TELESCOP"] = "ADITYA-L1"
    hdu.header["INSTRUME"] = "HEL1OS"
 
    primary = fits.PrimaryHDU()
    fits.HDUList([primary, hdu]).writeto(out_path, overwrite=True)
 
 
if __name__ == "__main__":
    out_dir = Path(__file__).parent / "fixtures"
    out_dir.mkdir(exist_ok=True)
    make_solexs_sample(out_dir / "solexs_sample.fits")
    make_hel1os_sample(out_dir / "hel1os_sample.fits")
    print(f"Wrote sample fixtures to {out_dir}")
 