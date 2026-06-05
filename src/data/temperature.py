"""Temperature loader and panel alignment (Task A, Phase 1).

External source: Open-Meteo historical archive API (ERA5 reanalysis), free,
no key for academic volumes. Endpoint:

    https://archive-api.open-meteo.com/v1/archive

We pull hourly 2 m air temperature for ONE representative load-center point
per balancing-authority zone, on the SAME UTC hourly grid as the carbon panel,
then align it through the identical ``build_daily_panel`` machinery so the
temperature panel is shape-for-shape and date-for-date identical to the carbon
panel (1815, 4, 24).

Station mapping -- one representative load-weighted point per zone
-----------------------------------------------------------------
Rationale: a single load-center point matches the fidelity of the assumed
PUE curve (a smooth function of one temperature). Multi-station spatial
averaging is noted as a refinement, NOT implemented here.

  US-CAL-CISO -> Central Valley (Fresno). CISO is the large CA balancing
                 authority; its load-weighted centre is warm and inland, NOT
                 coastal San Francisco. Fresno is chosen over the LA basin so
                 the point does not collide geographically with LDWP (= the
                 City of Los Angeles). 36.74 N, 119.77 W.
  US-CAL-BANC -> Sacramento (SMUD territory). 38.58 N, 121.49 W.
  US-CAL-LDWP -> Los Angeles (City of LA / LADWP). 34.05 N, 118.24 W.
  US-NW-NEVP  -> Las Vegas (NV Energy south). 36.17 N, 115.14 W.

Timezone note (IMPORTANT)
-------------------------
The carbon ``wide`` DataFrame is indexed in UTC, but ``build_daily_panel``
converts to ``America/Los_Angeles`` local time and indexes hours by LOCAL
hour-of-day. So the carbon panel's hour axis t is LA-LOCAL hour, not UTC hour.
To guarantee identical alignment we (a) pull temperature in UTC, (b) reindex it
onto the EXACT carbon UTC index, then (c) pass it through the same
``build_daily_panel`` with the same tz. The result is provably the same set of
days and the same local-hour indexing as the carbon panel.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from src.models.covariance import (
    DEFAULT_TZ,
    REGION_ORDER,
    T_HOURS,
    build_daily_panel,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMP_DIR = PROJECT_ROOT / "data" / "raw" / "temperature"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# One representative load-center point per zone: (latitude, longitude, label).
# Two region sets share this dict (keys are disjoint): the Task A US zones and
# the Task B Iberian zones. Consumers pass the relevant zone list explicitly.
STATION_COORDS: dict[str, tuple[float, float, str]] = {
    # --- Task A (US, California/Nevada) ---
    "US-CAL-CISO": (36.7378, -119.7871, "Fresno / Central Valley"),
    "US-CAL-BANC": (38.5816, -121.4944, "Sacramento"),
    "US-CAL-LDWP": (34.0522, -118.2437, "Los Angeles"),
    "US-NW-NEVP": (36.1716, -115.1391, "Las Vegas"),
    # --- Task B (Iberia + France) ---
    # ES/PT: national load centres (Madrid, Lisbon). FR: France is large and
    # spatially heterogeneous; Paris (Ile-de-France) is the dominant load centre
    # and the load-weighted single-point choice (multi-station noted as a
    # refinement, not implemented -- same fidelity rationale as Task A).
    "ES": (40.4168, -3.7038, "Madrid"),
    "PT": (38.7223, -9.1393, "Lisbon"),
    "FR": (48.8566, 2.3522, "Paris"),
}

# Default pull window. End is inclusive in the Open-Meteo API; we request the
# full year 2025 and trim/reindex against the carbon panel downstream.
DEFAULT_START = "2021-01-01"
DEFAULT_END = "2025-12-31"


# ----------------------------------------------------------------------
# Fetch + cache
# ----------------------------------------------------------------------

def _cache_path(zone: str, start: str, end: str, cache_dir: Path) -> Path:
    return cache_dir / f"openmeteo_{zone}_{start}_{end}_2m_temp_utc.csv"


def fetch_zone_temperature(
    zone: str,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    cache_dir: Path = DEFAULT_TEMP_DIR,
    force: bool = False,
    max_retries: int = 4,
) -> pd.DataFrame:
    """Fetch (or load from cache) hourly 2 m temperature for one zone's point.

    Returns a DataFrame with columns ['timestamp_utc', 'temperature_c'],
    tz-aware UTC timestamps, sorted and de-duplicated. Results are cached to
    a CSV under ``cache_dir`` so re-runs do not re-hit the API.

    Args:
        zone: Electricity Maps zone id; must be a key of STATION_COORDS.
        start, end: ISO dates (inclusive) for the Open-Meteo request.
        cache_dir: directory for the CSV cache.
        force: if True, re-pull even if a cache file exists.
        max_retries: simple exponential-backoff retry count for transient
            HTTP / network errors.
    """
    if zone not in STATION_COORDS:
        raise ValueError(f"Unknown zone {zone!r}; known: {list(STATION_COORDS)}")
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(zone, start, end, cache_dir)

    if path.exists() and not force:
        df = pd.read_csv(path)
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        return df

    import requests  # local import so the module imports without the dep present

    lat, lon, _label = STATION_COORDS[zone]
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": "temperature_2m",
        "timezone": "UTC",  # return times on the UTC grid
    }

    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(ARCHIVE_URL, params=params, timeout=120)
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception as exc:  # noqa: BLE001 -- retry on any transient error
            last_err = exc
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"Open-Meteo fetch failed for {zone} after {max_retries} "
                    f"attempts: {exc}"
                ) from exc
            time.sleep(2.0 * (2 ** attempt))

    hourly = payload["hourly"]
    times = pd.to_datetime(pd.Series(hourly["time"]), utc=True)
    temps = pd.to_numeric(pd.Series(hourly["temperature_2m"]), errors="coerce")
    df = pd.DataFrame({"timestamp_utc": times, "temperature_c": temps})
    df = df.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")
    df = df.reset_index(drop=True)

    df.to_csv(path, index=False)
    return df


def fetch_all_zones(
    zones: Sequence[str] = REGION_ORDER,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    cache_dir: Path = DEFAULT_TEMP_DIR,
    force: bool = False,
) -> dict[str, pd.DataFrame]:
    """Fetch/cache every zone; returns {zone: per-zone DataFrame}."""
    return {
        z: fetch_zone_temperature(z, start, end, cache_dir, force)
        for z in zones
    }


# ----------------------------------------------------------------------
# Wide assembly + alignment
# ----------------------------------------------------------------------

def load_temperature_wide(
    zones: Sequence[str] = REGION_ORDER,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    cache_dir: Path = DEFAULT_TEMP_DIR,
    force: bool = False,
) -> pd.DataFrame:
    """Return a wide temperature DataFrame: UTC index, one column per zone.

    Mirrors the shape of ``electricitymaps.to_wide`` so it can flow through the
    same ``build_daily_panel``.
    """
    per_zone = fetch_all_zones(zones, start, end, cache_dir, force)
    cols = {}
    for z in zones:
        s = per_zone[z].set_index("timestamp_utc")["temperature_c"]
        cols[z] = s
    wide = pd.DataFrame(cols)
    wide = wide[list(zones)]  # enforce column order == zones
    wide.index.name = "timestamp_utc"
    return wide.sort_index()


def align_temperature_to_panel(
    temp_wide: pd.DataFrame,
    carbon_wide: pd.DataFrame,
    region_order: Sequence[str] = REGION_ORDER,
    tz: str = DEFAULT_TZ,
    expected_T: int = T_HOURS,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """Align a wide temperature frame to the carbon panel's exact grid.

    Reindexes temperature onto the carbon UTC index (so day-keeping is
    identical), interpolates short gaps, then runs the SAME build_daily_panel
    used for carbon. Returns (temp_panel, dates) with temp_panel shape
    (N, R, T) and the same `dates` the carbon panel would produce.

    Any residual missing values after a short-gap interpolation are filled by
    nearest-hour so build_daily_panel does not silently drop days that the
    carbon panel keeps; the % filled is reported by `temperature_summary`.
    """
    # Reindex onto the carbon UTC index so the kept-day set is identical.
    idx = carbon_wide.index
    temp = temp_wide.reindex(idx)
    # Short-gap handling: linear interpolation up to 6 h, then ffill/bfill.
    temp = temp.interpolate(method="time", limit=6, limit_direction="both")
    temp = temp.ffill().bfill()
    panel, dates = build_daily_panel(
        temp, region_order=region_order, tz=tz, expected_T=expected_T
    )
    return panel, dates


def pue_from_temperature(
    temperature: np.ndarray,
    pue0: float = 1.10,
    kappa: float = 0.015,
    t_set: float = 20.0,
) -> np.ndarray:
    """Temperature-coupled PUE field: PUE(T) = pue0 + kappa * max(T - t_set, 0).

    A piecewise-linear ("hockey-stick") cooling model: below the economizer
    set-point t_set the facility runs at its floor PUE pue0; above it,
    mechanical cooling adds kappa per degree C. Defaults sit in typical
    industry ranges (modern efficient floor PUE ~1.1; ~0.015 PUE/C above an
    ~20 C economizer threshold) and are EXPOSED for sensitivity analysis.

    This is a pure function of the (given) temperature, so when used inside the
    optimizer it yields a per-cell CONSTANT multiplier and the effective-power
    cap PUE(T)*x <= bar_P stays linear (the program remains an SOCP/LP).
    """
    T = np.asarray(temperature, dtype=float)
    return pue0 + kappa * np.maximum(T - t_set, 0.0)


def temperature_field(
    temp_panel: np.ndarray,
    dates: pd.DatetimeIndex,
    years: Optional[Iterable[int]] = None,
) -> np.ndarray:
    """Per-cell mean temperature field (R, T) over the given years.

    This is the representative thermal field used as a fixed parameter of the
    feasible set (analogous to ceiling / rho_bar). Defaults to all years.
    """
    if years is None:
        sel = np.ones(len(dates), dtype=bool)
    else:
        yrs = set(years)
        sel = np.array([d.year in yrs for d in dates])
    if not sel.any():
        raise ValueError(f"No panel days in years={years}")
    return temp_panel[sel].mean(axis=0)


def temperature_summary(
    temp_panel: np.ndarray,
    temp_wide: pd.DataFrame,
    carbon_wide: pd.DataFrame,
    region_order: Sequence[str] = REGION_ORDER,
) -> pd.DataFrame:
    """Per-zone sanity stats: min/mean/max temperature and % missing.

    % missing is computed on the raw temperature reindexed to the carbon UTC
    index, BEFORE interpolation, so it reflects true data availability.
    """
    raw = temp_wide.reindex(carbon_wide.index)
    rows = []
    for r, z in enumerate(region_order):
        col = raw[z]
        rows.append({
            "zone": z,
            "station": STATION_COORDS[z][2],
            "lat": STATION_COORDS[z][0],
            "lon": STATION_COORDS[z][1],
            "min_C": float(np.nanmin(temp_panel[:, r, :])),
            "mean_C": float(np.nanmean(temp_panel[:, r, :])),
            "max_C": float(np.nanmax(temp_panel[:, r, :])),
            "pct_missing_raw": float(col.isna().mean() * 100.0),
        })
    return pd.DataFrame(rows)
