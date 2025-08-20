# lib_data.py
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

def find_col(cols, needle):
    needle = needle.lower()
    for c in cols:
        if needle in c.lower():
            return c
    return None

def parse_fecha_value(val):
    if pd.isna(val):
        return pd.NaT
    s = str(val).strip().replace('"', '').replace("'", "")
    if len(s) >= 6 and s[:6].isdigit():
        try:
            y, m = int(s[:4]), int(s[4:6])
            return datetime(y, m, 1)
        except Exception:
            pass
    return pd.to_datetime(s, errors="coerce")

def try_read_csv(path: Path, encodings=("utf-8", "latin-1"), seps=(";", ",", "\t")):
    for enc in encodings:
        for sep in seps:
            try:
                df = pd.read_csv(path, sep=sep, dtype=str, encoding=enc, engine="python")
                if df.shape[1] >= 3:
                    return df, sep
            except Exception:
                continue
    try:
        df = pd.read_csv(path, sep=None, engine="python", dtype=str)
        return df, None
    except Exception:
        return None, None

def normalize_codigo_entidad(x: str) -> str:
    if x is None:
        return ""
    s = str(x).strip().upper()
    if s.startswith("AA"):
        return s
    if s.isdigit():
        return s.zfill(5)
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits.zfill(5) if digits else s

@st.cache_data(show_spinner=False)
def load_nomina_map(candidates, encoding="latin-1"):
    for c in candidates:
        p = Path(c)
        if p.exists():
            df = pd.read_csv(p, sep="\t", header=None, dtype=str, encoding=encoding, quotechar='"',
                             names=["codigo", "nombre", "alias"])
            df["codigo_norm"] = df["codigo"].apply(normalize_codigo_entidad)
            return df[["codigo_norm", "nombre", "alias"]], str(p)
    return pd.DataFrame(columns=["codigo_norm", "nombre", "alias"]), ""

@st.cache_data(show_spinner=False)
def load_all_data(data_dir: str, nomina_path_in: str = "Nomina.txt", include_aa=False, use_alias=True):
    p = Path(data_dir)
    files = sorted(p.glob("*.csv"))
    if not files:
        return pd.DataFrame(), [], ""

    dfs, used_seps = [], []
    for f in files:
        df, sep_used = try_read_csv(f)
        if df is None:
            continue
        df.columns = [c.strip() for c in df.columns]
        col_fecha = find_col(df.columns, "fecha") or "Fecha"
        col_entidad = (find_col(df.columns, "código de la entidad")
                       or find_col(df.columns, "codigo de la entidad")
                       or find_col(df.columns, "entidad")
                       or "Código de la entidad")
        ren = {}
        if col_fecha in df.columns: ren[col_fecha] = "Fecha"
        if col_entidad in df.columns: ren[col_entidad] = "Código de la entidad"
        if ren: df = df.rename(columns=ren)

        if "Fecha" not in df.columns or "Código de la entidad" not in df.columns:
            continue

        df["__archivo"] = f.name
        dfs.append(df)
        used_seps.append(sep_used or ",")

    if not dfs:
        return pd.DataFrame(), [], ""

    full = pd.concat(dfs, ignore_index=True)
    full["Mes"] = full["Fecha"].apply(parse_fecha_value)
    full = full.sort_values(["Mes", "Código de la entidad"], kind="mergesort").reset_index(drop=True)

    id_cols = {"Fecha", "Mes", "Código de la entidad", "__archivo", "Nombre de entidad"}
    for c in [c for c in full.columns if c not in id_cols]:
        full[c] = pd.to_numeric(full[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    if not include_aa:
        full = full[~full["Código de la entidad"].astype(str).str.upper().str.startswith("AA")].copy()

    full["Codigo_norm"] = full["Código de la entidad"].apply(normalize_codigo_entidad)
    nomina_df, nomina_used = load_nomina_map([
        nomina_path_in,
        Path(data_dir) / nomina_path_in,
        "Nomina.txt",
        Path(data_dir) / "Nomina.txt",
    ])
    full = full.merge(nomina_df, left_on="Codigo_norm", right_on="codigo_norm", how="left")
    full["Etiqueta"] = full["nombre"]
    if use_alias:
        full["Etiqueta"] = np.where(full["alias"].notna() & (full["alias"].str.strip() != ""),
                                    full["alias"], full["nombre"])
    full["Etiqueta"] = full["Etiqueta"].fillna(full["Código de la entidad"])

    return full, used_seps, nomina_used

def list_numeric_columns(df: pd.DataFrame):
    id_cols = {"Fecha", "Mes", "Código de la entidad", "Etiqueta", "Codigo_norm",
               "__archivo", "nombre", "alias", "codigo_norm"}
    return [c for c in df.columns if c not in id_cols]

def normalize_series(s: pd.Series, mode: str):
    if mode == "Raw":
        return s
    if mode == "Base 100 (primer mes)":
        base = s.dropna()
        base = base.iloc[0] if not base.empty else np.nan
        return s / base * 100 if pd.notna(base) and base != 0 else s*np.nan
    if mode == "Min–Max (0–1)":
        mn, mx = s.min(skipna=True), s.max(skipna=True)
        return (s - mn) / (mx - mn) if pd.notna(mn) and pd.notna(mx) and mx != mn else s*0
    if mode == "Z-score":
        mu, sd = s.mean(skipna=True), s.std(skipna=True)
        return (s - mu) / sd if pd.notna(sd) and sd != 0 else s*0
    return s
