# app.py
# Dashboard interactivo para CSVs mensuales generados con tu script.
# Ahora incluye mapeo de códigos de entidad -> nombre/alias con Nomina.txt.

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Tablero BCRA - Bancos", layout="wide")

# ---------- Helpers ----------
def find_col(cols, needle):
    """Devuelve la primera columna cuyo nombre contenga 'needle' (case-insensitive)."""
    needle = needle.lower()
    for c in cols:
        if needle in c.lower():
            return c
    return None

def parse_fecha_value(val):
    """Convierte valores tipo '202504' a datetime (primer día del mes). Acepta otros formatos."""
    if pd.isna(val):
        return pd.NaT
    s = str(val).strip().replace('"', '').replace("'", "")
    # Caso típico: yyyymm
    if len(s) >= 6 and s[:6].isdigit():
        try:
            y, m = int(s[:4]), int(s[4:6])
            return datetime(y, m, 1)
        except Exception:
            pass
    # Fallback: que intente pandas
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.NaT

def try_read_csv(path: Path, encodings=("utf-8", "latin-1"), seps=(";", ",", "\t")):
    """Intenta leer CSV probando varios encodings y separadores. Devuelve (df, sep_usado) o (None, None)."""
    for enc in encodings:
        for sep in seps:
            try:
                df = pd.read_csv(path, sep=sep, dtype=str, encoding=enc, engine="python")
                if df.shape[1] >= 3:
                    return df, sep
            except Exception:
                continue
    # último intento: sniff automático
    try:
        df = pd.read_csv(path, sep=None, engine="python", dtype=str)
        return df, None
    except Exception:
        return None, None

def normalize_codigo_entidad(x: str) -> str:
    """
    Normaliza códigos a 5 dígitos (ej. '0011' -> '00011').
    Mantiene agregados tipo 'AA000' tal cual.
    """
    if x is None:
        return ""
    s = str(x).strip().upper()
    if s.startswith("AA"):
        return s
    # Si es todo dígitos, completar a 5
    if s.isdigit():
        return s.zfill(5)
    # Si tiene mix raro, intentamos extraer dígitos
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits.zfill(5) if digits else s

@st.cache_data(show_spinner=False)
def load_nomina_map(candidates, encoding="latin-1"):
    """
    Lee Nomina.txt (TSV con 3 columnas: codigo, nombre, alias).
    candidates: lista de paths a probar en orden.
    Retorna (df_nomina[['codigo_norm','nombre','alias']], path_usado) o (df_vacio, "").
    """
    for c in candidates:
        p = Path(c)
        if p.exists():
            df = pd.read_csv(p, sep="\t", header=None, dtype=str, encoding=encoding, quotechar='"',
                             names=["codigo", "nombre", "alias"])
            df["codigo_norm"] = df["codigo"].apply(normalize_codigo_entidad)
            return df[["codigo_norm", "nombre", "alias"]], str(p)
    return pd.DataFrame(columns=["codigo_norm", "nombre", "alias"]), ""

@st.cache_data(show_spinner=False)
def load_all_data(data_dir: str):
    """Carga y concatena todos los .csv de la carpeta data_dir."""
    p = Path(data_dir)
    files = sorted(p.glob("*.csv"))
    if not files:
        return pd.DataFrame(), []

    dfs = []
    used_seps = []
    for f in files:
        df, sep_used = try_read_csv(f)
        if df is None:
            continue
        # Normalizamos columnas (quitamos espacios alrededor)
        df.columns = [c.strip() for c in df.columns]
        # Detectar columnas clave
        col_fecha = find_col(df.columns, "fecha") or "Fecha"
        col_entidad = (find_col(df.columns, "código de la entidad")
                       or find_col(df.columns, "codigo de la entidad")
                       or find_col(df.columns, "entidad")
                       or "Código de la entidad")
        # Renombrar a estándar si están presentes
        ren = {}
        if col_fecha in df.columns: ren[col_fecha] = "Fecha"
        if col_entidad in df.columns: ren[col_entidad] = "Código de la entidad"
        if ren: df = df.rename(columns=ren)

        # Validar columnas mínimas
        for must in ["Fecha", "Código de la entidad"]:
            if must not in df.columns:
                df = None
                break
        if df is None:
            continue

        # Origen del archivo (útil para debug)
        df["__archivo"] = f.name
        dfs.append(df)
        used_seps.append(sep_used or ",")

    if not dfs:
        return pd.DataFrame(), []

    full = pd.concat(dfs, ignore_index=True)

    # Parsear fecha a datetime
    full["Mes"] = full["Fecha"].apply(parse_fecha_value)
    # Orden básico
    full = full.sort_values(["Mes", "Código de la entidad"], kind="mergesort").reset_index(drop=True)

    # Convertir a numéricas todas las que no sean identificadoras
    id_cols = {"Fecha", "Mes", "Código de la entidad", "__archivo", "Nombre de entidad"}
    num_cands = [c for c in full.columns if c not in id_cols]
    for c in num_cands:
        full[c] = pd.to_numeric(full[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    return full, used_seps

# ---------- UI ----------
st.title("📊 Tablero de indicadores bancarios (CSV mensuales)")

with st.sidebar:
    st.header("⚙️ Configuración")
    data_dir = st.text_input("Carpeta de datos (.csv)", value="data")
    include_aa = st.checkbox("Incluir filas agregadas 'AA...'", value=False,
                             help="Ej.: AA000 (Sistema), AA100 (Banca privada), etc.")
    # NÓMINA
    st.markdown("**Nómina de entidades (opcional)**")
    nomina_path_in = st.text_input("Archivo nómina", value="Nomina.txt",
                                   help="Puede estar en la carpeta del app o dentro de 'data/'.")
    use_alias = st.checkbox("Usar alias corto si existe", value=True)
    st.caption("Colocá tus CSV en la carpeta indicada. Se cargan todos los archivos *.csv.")

df, seps = load_all_data(data_dir)

if df.empty:
    st.info("No encontré CSV en la carpeta indicada. Creá `data/` y poné tus archivos ahí.")
    st.stop()

# --- Filtro AA (según código crudo) ---
if not include_aa:
    df = df[~df["Código de la entidad"].astype(str).str.upper().str.startswith("AA")].copy()

# --- Mapeo de nómina ---
# Normalizar código a 5 dígitos o 'AA...' para el join
df["Codigo_norm"] = df["Código de la entidad"].apply(normalize_codigo_entidad)

# Orden de búsqueda del archivo de nómina:
nomina_df, nomina_used = load_nomina_map([
    nomina_path_in,
    Path(data_dir) / nomina_path_in,
    "Nomina.txt",
    Path(data_dir) / "Nomina.txt",
])

# Merge
df = df.merge(nomina_df, left_on="Codigo_norm", right_on="codigo_norm", how="left")

# Elegir etiqueta a mostrar (alias si hay, si no nombre, si no código)
df["Etiqueta"] = df["nombre"]
if use_alias:
    df["Etiqueta"] = np.where(df["alias"].notna() & (df["alias"].str.strip() != ""),
                              df["alias"], df["nombre"])
df["Etiqueta"] = df["Etiqueta"].fillna(df["Código de la entidad"])

# --- Fechas para widgets ---
df["Mes"] = pd.to_datetime(df["Mes"], errors="coerce")
valid_mes = df["Mes"].dropna()
if valid_mes.empty:
    st.warning("No se pudieron interpretar fechas (columna 'Fecha'). Verificá que tengan formato tipo 202504).")
    st.stop()

min_mes_py = valid_mes.min().to_pydatetime()
max_mes_py = valid_mes.max().to_pydatetime()
default_range = (min_mes_py, max_mes_py)

rango = st.slider(
    "Rango de meses",
    min_value=min_mes_py,
    max_value=max_mes_py,
    value=default_range,
    format="YYYY-MM"
)
df = df[(df["Mes"] >= pd.Timestamp(rango[0])) & (df["Mes"] <= pd.Timestamp(rango[1]))].copy()

# --- Columnas disponibles ---
all_cols = list(df.columns)
id_cols = ["Fecha", "Mes", "Código de la entidad", "Etiqueta", "Codigo_norm", "__archivo", "nombre", "alias", "codigo_norm"]
num_cols = [c for c in all_cols if c not in id_cols]

if not num_cols:
    st.error("No se encontraron columnas numéricas para graficar. Verificá que tus CSV tengan indicadores.")
    st.stop()

# --- Selección de entidades (por etiqueta) ---
entidades = sorted(df["Etiqueta"].unique().tolist())
sel_entidades = st.multiselect("Filtrar entidades (opcional)", entidades, default=[],
                               help="Si no seleccionás, se muestran todas.")
if sel_entidades:
    df = df[df["Etiqueta"].isin(sel_entidades)].copy()

# --- Métrica a graficar ---
default_metric = "R1 - Rendimiento Anual del Patrimonio ( ROE) (%)"
metric = st.selectbox(
    "Indicador / métrica",
    options=num_cols,
    index=num_cols.index(default_metric) if default_metric in num_cols else 0
)

# ---------- Visualizaciones ----------
col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader("Serie temporal")
    # Limitar series si hay demasiadas entidades
    max_series = 30
    etiquetas_plot = sorted(df["Etiqueta"].unique().tolist())[:max_series]
    df_plot = df[df["Etiqueta"].isin(etiquetas_plot)]

    fig_line = px.line(
        df_plot,
        x="Mes", y=metric, color="Etiqueta",
        title=f"Evolución de {metric}",
        labels={"Mes": "Mes", metric: metric, "Etiqueta": "Entidad"}
    )
    fig_line.update_layout(legend_title_text="Entidad", height=450)
    st.plotly_chart(fig_line, use_container_width=True)

with col2:
    st.subheader("Top-N por mes")
    meses_disponibles = sorted(df["Mes"].dropna().unique())
    meses_py = [m.to_pydatetime() for m in meses_disponibles]
    mes_sel = st.selectbox(
        "Mes",
        options=meses_py,
        index=len(meses_py) - 1,
        format_func=lambda d: d.strftime("%Y-%m")
    )
    df_mes = df[df["Mes"] == pd.Timestamp(mes_sel)].copy()

    topn = st.slider("Top N", min_value=5, max_value=50, value=15, step=1)
    df_mes = df_mes.sort_values(metric, ascending=False).head(topn)

    fig_bar = px.bar(
        df_mes,
        x=metric, y="Etiqueta",
        orientation="h",
        title=f"Top {topn} entidades en {pd.Timestamp(mes_sel).strftime('%Y-%m')} - {metric}",
        labels={"Etiqueta": "Entidad", metric: metric}
    )
    fig_bar.update_layout(height=600, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ---------- Tabla y descarga ----------
st.subheader("Tabla de datos (filtrados)")
st.dataframe(df.reset_index(drop=True), use_container_width=True, height=360)

csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Descargar CSV filtrado",
    data=csv_bytes,
    file_name="datos_filtrados.csv",
    mime="text/csv"
)

# ---------- Info técnica ----------
with st.expander("Ver detalles técnicos de los archivos cargados"):
    st.write(f"Archivos leídos (distintos): {len(set(df['__archivo'].tolist()))}")
    if seps:
        st.write("Separadores detectados (primer intento por archivo):", seps)
    st.write("Nómina usada:", nomina_used if nomina_used else "No encontrada (mostrando códigos).")
    st.write("Columnas numéricas detectadas:", [c for c in df.columns if c in num_cols])
    st.write("Rango temporal:", df['Mes'].min(), "→", df['Mes'].max())
