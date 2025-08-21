# lib_data.py
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import io

# === Google Drive ===
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ---------- helpers comunes ----------
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

def _to_num_series(col):
    # convierte inteligentemente valores con % y separadores de miles
    s = col.astype(str).str.replace('\u00a0','', regex=False).str.strip()
    s = s.str.replace('%','', regex=False)
    a = pd.to_numeric(s.str.replace('.','', regex=False).str.replace(',','.', regex=False), errors='coerce')
    b = pd.to_numeric(s.str.replace(',','', regex=False), errors='coerce')
    return a.fillna(b)

def try_read_csv_local(path: Path, encodings=("utf-8", "latin-1"), seps=(";", ",", "\t")):
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

# ---------- Normalización de códigos de entidad ----------
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

# ---------- Nómina ----------
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

# ---------- Google Drive: cliente y utilidades ----------
def _drive_credentials():
    # En Streamlit Cloud: definir en Secrets -> gdrive_service_account
    info = st.secrets.get("gdrive_service_account", None)
    if info is None:
        raise RuntimeError("Faltan credenciales en st.secrets['gdrive_service_account']")
    scopes = ['https://www.googleapis.com/auth/drive.readonly']
    return service_account.Credentials.from_service_account_info(dict(info), scopes=scopes)

@st.cache_data(show_spinner=False)
def _drive_build():
    creds = _drive_credentials()
    return build('drive', 'v3', credentials=creds, cache_discovery=False)

@st.cache_data(show_spinner=False)
def drive_list_csvs(folder_id: str):
    service = _drive_build()
    q = f"'{folder_id}' in parents and trashed=false"
    files = []
    page_token = None
    while True:
        resp = service.files().list(
            q=q,
            pageSize=1000,
            fields="nextPageToken, files(id,name,mimeType,modifiedTime)",
            pageToken=page_token
        ).execute()
        files.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    # Aceptamos CSV + TXT (por si nomina)
    csv_like = []
    for f in files:
        name_low = f["name"].lower()
        if name_low.endswith(".csv") or name_low.endswith(".txt"):
            csv_like.append(f)
    return csv_like

def drive_download_bytes(file_id: str) -> bytes:
    service = _drive_build()
    req = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue()

def _read_csv_bytes(content: bytes):
    # intenta varios separadores igual que en local
    for sep in (";", ",", "\t"):
        try:
            df = pd.read_csv(io.BytesIO(content), sep=sep, dtype=str, engine="python")
            if df.shape[1] >= 3:
                return df, sep
        except Exception:
            pass
    # sniff automático
    df = pd.read_csv(io.BytesIO(content), sep=None, engine="python", dtype=str)
    return df, None

def _read_nomina_bytes(content: bytes, encoding="latin-1"):
    return pd.read_csv(io.BytesIO(content), sep="\t", header=None, dtype=str, encoding=encoding, quotechar='"',
                       names=["codigo", "nombre", "alias"])

# ---------- Carga desde Drive o local (auto) ----------
def _load_all_data_from_drive(folder_id: str, include_aa=False, use_alias=True):
    files = drive_list_csvs(folder_id)
    if not files:
        return pd.DataFrame(), [], "", None  # df, seps, nomina_used, drive_meta

    # detectar nomina si existe
    nomina_file = None
    for f in files:
        if "nomina" in f["name"].lower() and f["name"].lower().endswith(".txt"):
            nomina_file = f
            break

    # leer CSVs
    dfs, used_seps = [], []
    for f in files:
        name_low = f["name"].lower()
        if not name_low.endswith(".csv"):
            continue
        content = drive_download_bytes(f["id"])
        try:
            df, sep_used = _read_csv_bytes(content)
        except Exception:
            continue
        df.columns = [c.strip() for c in df.columns]
        # detectar columnas clave
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
        df["__archivo"] = f["name"]
        dfs.append(df)
        used_seps.append(sep_used or ",")

    if not dfs:
        return pd.DataFrame(), [], "", {"folder_id": folder_id, "files": files}

    full = pd.concat(dfs, ignore_index=True)
    full["Mes"] = full["Fecha"].apply(parse_fecha_value)
    full = full.sort_values(["Mes", "Código de la entidad"], kind="mergesort").reset_index(drop=True)

    id_cols = {"Fecha", "Mes", "Código de la entidad", "__archivo", "Nombre de entidad"}
    for c in [c for c in full.columns if c not in id_cols]:
        full[c] = _to_num_series(full[c])

    if not include_aa:
        full = full[~full["Código de la entidad"].astype(str).str.upper().str.startswith("AA")].copy()

    # nomina
    nomina_used = ""
    if nomina_file is not None:
        try:
            nbytes = drive_download_bytes(nomina_file["id"])
            nom_df = _read_nomina_bytes(nbytes)
            nom_df["codigo_norm"] = nom_df["codigo"].apply(normalize_codigo_entidad)
            nomina_used = f"drive:{nomina_file['name']}"
        except Exception:
            nom_df = pd.DataFrame(columns=["codigo_norm", "nombre", "alias"])
    else:
        nom_df = pd.DataFrame(columns=["codigo_norm", "nombre", "alias"])

    full["Codigo_norm"] = full["Código de la entidad"].apply(normalize_codigo_entidad)
    full = full.merge(nom_df[["codigo_norm","nombre","alias"]], left_on="Codigo_norm", right_on="codigo_norm", how="left")
    full["Etiqueta"] = full["nombre"]
    if use_alias:
        full["Etiqueta"] = np.where(full["alias"].notna() & (full["alias"].str.strip() != ""),
                                    full["alias"], full["nombre"])
    full["Etiqueta"] = full["Etiqueta"].fillna(full["Código de la entidad"])

    return full, used_seps, nomina_used, {"folder_id": folder_id, "files": files}

@st.cache_data(show_spinner=False)
def load_all_data(data_dir: str, nomina_path_in: str = "Nomina.txt", include_aa=False, use_alias=True):
    """
    data_dir:
      - Modo local: ruta a carpeta (ej. 'data')
      - Modo Drive: 'gdrive:<FOLDER_ID>'
    nomina_path_in:
      - local: nombre/ruta de Nomina.txt
      - drive: 'gdrive:<FILE_ID>' (opcional). Si no se da, se intenta auto-detectar en la carpeta.
    """
    # ---- Modo DRIVE ----
    if isinstance(data_dir, str) and data_dir.lower().startswith("gdrive:"):
        folder_id = data_dir.split(":",1)[1].strip()
        df, seps, nomina_used, meta = _load_all_data_from_drive(folder_id, include_aa, use_alias)
        # si se especificó nomina gdrive:<id>, forzamos esa
        if df.empty:
            return df, seps, nomina_used
        if isinstance(nomina_path_in, str) and nomina_path_in.lower().startswith("gdrive:"):
            try:
                fid = nomina_path_in.split(":",1)[1].strip()
                nbytes = drive_download_bytes(fid)
                nom_df = _read_nomina_bytes(nbytes)
                nom_df["codigo_norm"] = nom_df["codigo"].apply(normalize_codigo_entidad)
                df = df.drop(columns=["nombre","alias","codigo_norm"], errors="ignore")\
                       .merge(nom_df[["codigo_norm","nombre","alias"]],
                              left_on="Codigo_norm", right_on="codigo_norm", how="left")
                df["Etiqueta"] = np.where(df["alias"].notna() & (df["alias"].str.strip() != ""),
                                          df["alias"], df["nombre"])
                df["Etiqueta"] = df["Etiqueta"].fillna(df["Código de la entidad"])
                nomina_used = f"drive:{fid}"
            except Exception:
                pass
        return df, seps, nomina_used

    # ---- Modo LOCAL (como siempre) ----
    p = Path(data_dir)
    files = sorted(p.glob("*.csv"))
    if not files:
        return pd.DataFrame(), [], ""

    dfs, used_seps = [], []
    for f in files:
        df, sep_used = try_read_csv_local(f)
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
        full[c] = _to_num_series(full[c])

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
