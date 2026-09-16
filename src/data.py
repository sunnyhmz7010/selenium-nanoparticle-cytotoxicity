from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


MISSING_MARKERS = ["NA", "N/A", "--", "-", "", "None", "nan"]


BASELINE_FEATURES = [
    "Coat/Functional Group",
    "Synthesis_Method",
    "Surface_Charge",
    "Cell_Type",
    "Cell_Tissue",
    "Year",
    "size_final",
    "zeta_final",
    "abs_zeta",
    "Time (hr)",
    "Concentration (ug/ml)",
    "log_size",
    "log_concentration",
    "No_of_Cells (cells/well)",
    "zeta_missing",
    "cell_count_missing",
    "coat_missing",
    "surface_charge_missing",
]

CHEMISTRY_FEATURES = [
    "Elemental_Se_wt",
    "Stability_weeks",
    "Binding_Energy_Se3d",
    "Crystal_Code",
]


def _to_numeric(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")


def _parse_se_wt(value: object) -> float:
    if pd.isna(value):
        return np.nan
    match = re.search(r"Se\s*\(?\s*([0-9]+(?:\.[0-9]+)?)", str(value), re.IGNORECASE)
    return float(match.group(1)) if match else np.nan


def make_group_ids(frame: Mapping[str, object] | pd.DataFrame) -> pd.Series:
    """Return stable publication identifiers with an Article_ID fallback."""

    source = frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)
    doi = source["DOI"].astype("string").str.strip()
    article = source["Article_ID"].astype("string").str.strip()
    use_doi = doi.notna() & doi.ne("")
    groups = pd.Series(np.where(use_doi, "doi:" + doi.fillna(""), "article:" + article.fillna("unknown")), index=source.index)
    return groups.astype("string")


def load_senp_dataset(path: Path) -> pd.DataFrame:
    """Load the 383-row curated SeNP table used by this repository."""

    frame = pd.read_csv(path, na_values=MISSING_MARKERS, keep_default_na=True)
    material = frame["Material"].astype("string")
    is_selenium = material.notna() & material.str.contains("Se", case=False, regex=False)
    is_selenite = material.str.contains("Na₂SeO₃|Na2SeO3", case=False, regex=True, na=False)
    frame = frame.loc[is_selenium & ~is_selenite].copy()
    numeric_columns = [
        "Year",
        "Diameter (nm)",
        "Size_in_Water (nm)",
        "Size_in_Medium (nm)",
        "Zeta_in_Water (mV)",
        "Zeta_in_Medium (mV)",
        "No_of_Cells (cells/well)",
        "Time (hr)",
        "Concentration (ug/ml)",
        "Cell_Viability (%)",
        "IC50 (µM)",
        "Binding Energy Se3d (eV)",
        "Long-term Stability (weeks)",
        "Crystallinity / Fringe Spacing (Å)",
        "Size Ratio",
    ]
    _to_numeric(frame, numeric_columns)
    return frame.reset_index(drop=True)


def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic derived features without filtering rows or fitting imputers."""

    out = frame.copy()
    out["Elemental_Se_wt"] = out["Elemental Composition (wt%)"].map(_parse_se_wt)
    out["size_final"] = out["Diameter (nm)"].fillna(out["Size_in_Water (nm)"]).fillna(out["Size_in_Medium (nm)"])
    out["zeta_final"] = out["Zeta_in_Water (mV)"].fillna(out["Zeta_in_Medium (mV)"])
    out["abs_zeta"] = out["zeta_final"].abs()
    out["log_size"] = np.log1p(out["size_final"])
    out["log_concentration"] = np.log1p(out["Concentration (ug/ml)"])
    out["IC50_uM"] = out["IC50 (µM)"]
    out["Stability_weeks"] = out["Long-term Stability (weeks)"]
    out["Binding_Energy_Se3d"] = out["Binding Energy Se3d (eV)"]
    out["Crystal_Code"] = out["Crystallinity / Fringe Spacing (Å)"].notna().astype(float)
    out["zeta_missing"] = out["zeta_final"].isna().astype(int)
    out["cell_count_missing"] = out["No_of_Cells (cells/well)"].isna().astype(int)
    out["coat_missing"] = out["Coat/Functional Group"].isna().astype(int)
    out["surface_charge_missing"] = out["Surface_Charge"].isna().astype(int)
    out["group_id"] = make_group_ids(out).to_numpy()
    return out


def build_analysis_subset(frame: pd.DataFrame) -> pd.DataFrame:
    """Prepare the MTT regression subset without fitting any global imputer."""

    out = add_derived_features(frame)
    test = out["Test"].astype("string").str.upper()
    valid = test.eq("MTT") & out["Cell_Viability (%)"].notna() & out["Time (hr)"].notna() & out["Concentration (ug/ml)"].notna()
    out = out.loc[valid].copy()
    return out.reset_index(drop=True)


def feature_groups() -> dict[str, list[str]]:
    """Return the three explicitly reported feature configurations."""

    chemistry = BASELINE_FEATURES + CHEMISTRY_FEATURES
    return {
        "baseline": BASELINE_FEATURES.copy(),
        "chemistry_no_ic50": chemistry,
        "ic50_assisted": chemistry + ["IC50_uM"],
    }


def feature_coverage(frame: pd.DataFrame, groups: dict[str, list[str]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for feature_set, columns in groups.items():
        for column in columns:
            rows.append(
                {
                    "feature_set": feature_set,
                    "feature": column,
                    "available_n": int(frame[column].notna().sum()),
                    "total_n": int(len(frame)),
                    "missing_pct": round(float(frame[column].isna().mean() * 100), 3),
                }
            )
    return pd.DataFrame(rows)
