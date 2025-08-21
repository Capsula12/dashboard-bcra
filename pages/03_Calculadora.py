# pages/03_Calculadora.py
import streamlit as st
import plotly.express as px
import pandas as pd
from config import DEFAULT_DATA_DIR
from lib_data import load_all_data, list_numeric_columns, normalize_series

# Helpers para defaults (idénticos)
import unicodedata
def _norm_txt(s: str) -> str:
    if s is None: return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()
def pick_default_entity(entities):
    cand = None
    for e in entities:
        se = _norm_txt(e)
        if "nacion" in se:
            return e
        if se.strip() in {"bna", "banco nacion", "banco de la nacion argentina"}:
            cand = cand or e
    for code in ["0011", "00011", "11"]:
        for e in entities:
            if e.strip().lstrip("0") == code.lstrip("0"):
                return e
    return cand or (entities[0] if entities else None)
def pick_default_metric(num_cols):
    for c in num_cols:
        if _norm_txt(c).startswith("r1"): return c
    for c in num_cols:
        if "roe" in _norm_txt(c): return c
    for c in num_cols:
        if "rendimiento anual del patrimonio" in _norm_txt(c): return c
    return num_cols[0] if num_cols else None

st.title("🧮 Calculadora de métricas")

with st.sidebar:
    st.header("Datos")
    for k, v in [
        ("data_dir", DEFAULT_DATA_DIR),
        ("nomina_path_in", "Nomina.txt"),
        ("include_aa", True),
        ("use_alias", False),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v
    st.text_input("Carpeta de datos (.csv)", key="data_dir")
    st.text_input("Archivo nómina", key="nomina_path_in")
    st.checkbox("Incluir 'AA...'", key="include_aa")
    st.checkbox("Usar alias", key="use_alias")

df, _, _ = load_all_data(
    st.session_state["data_dir"],
    st.session_state["nomina_path_in"],
    st.session_state["include_aa"],
    st.session_state["use_alias"],
)
if df.empty:
    st.info("Cargá CSV en la carpeta indicada.")
    st.stop()

df["Mes"] = pd.to_datetime(df["Mes"], errors="coerce")
valid = df["Mes"].dropna()
min_mes, max_mes = valid.min().to_pydatetime(), valid.max().to_pydatetime()
rango = st.slider("Rango de meses", min_mes, max_mes, (min_mes, max_mes), format="YYYY-MM")
df = df[(df["Mes"] >= pd.Timestamp(rango[0])) & (df["Mes"] <= pd.Timestamp(rango[1]))]

entidades = sorted(df["Etiqueta"].unique())
default_ent = pick_default_entity(entidades)
sel_ent = st.multiselect("Entidades", entidades, default=[default_ent] if default_ent else [])
df = df[df["Etiqueta"].isin(sel_ent)] if sel_ent else df

num_cols = list_numeric_columns(df)
if not num_cols:
    st.error("No hay columnas numéricas para operar.")
    st.stop()

default_metric = pick_default_metric(num_cols)
idx_A = num_cols.index(default_metric) if default_metric in num_cols else 0
idx_B = 0 if len(num_cols) == 1 else (1 if idx_A == 0 else 0)

st.markdown("**Construí tu indicador:**")
c1, c2, c3, c4 = st.columns([2,1,2,1])
with c1:
    A = st.selectbox("A", num_cols, index=idx_A)
with c2:
    op1 = st.selectbox("Op1", ["+", "-", "×", "÷"], index=1)
with c3:
    B = st.selectbox("B", num_cols, index=idx_B)
with c4:
    add_c = st.checkbox("Agregar C", value=False)

if add_c:
    c5, c6 = st.columns([1,2])
    with c5:
        op2 = st.selectbox("Op2", ["+", "-", "×", "÷"], index=0)
    with c6:
        C = st.selectbox("C", num_cols, index=min(2, len(num_cols)-1))
else:
    op2 = None
    C = None

norm = st.selectbox("Normalización (resultado)", ["Raw", "Base 100 (primer mes)", "Min–Max (0–1)", "Z-score"], index=0)

def apply_op(s1, op, s2):
    if op == "+": return s1 + s2
    if op ==

