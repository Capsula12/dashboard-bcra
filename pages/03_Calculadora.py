# pages/03_Calculadora.py
import streamlit as st
import plotly.express as px
import pandas as pd
from config import DEFAULT_DATA_DIR
from lib_data import load_all_data, list_numeric_columns, normalize_series
import unicodedata

# ---------- Estado compartido (defaults) ----------
if "data_dir" not in st.session_state:
    st.session_state["data_dir"] = DEFAULT_DATA_DIR
if "nomina_path_in" not in st.session_state:
    st.session_state["nomina_path_in"] = "Nomina.txt"
if "include_aa" not in st.session_state:
    st.session_state["include_aa"] = True
if "use_alias" not in st.session_state:
    st.session_state["use_alias"] = False

st.title("Calculadora de métricas")

with st.sidebar:
    st.header("Datos")
    st.text_input("Carpeta de datos (.csv)", key="data_dir")
    st.text_input("Archivo nomina", key="nomina_path_in")
    st.checkbox("Incluir 'AA...'", key="include_aa")
    st.checkbox("Usar alias", key="use_alias")

# ---------- Helpers para defaults ----------
def _norm_txt(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()

def pick_default_entity(entities):
    # prioriza cadenas que contengan "nacion" o alias tipicos; si no, intenta por codigo 0011
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
    # prioriza R1/ROE/Rendimiento Anual del Patrimonio
    for c in num_cols:
        if _norm_txt(c).startswith("r1"):
            return c
    for c in num_cols:
        if "roe" in _norm_txt(c):
            return c
    for c in num_cols:
        if "rendimiento anual del patrimonio" in _norm_txt(c):
            return c
    return num_cols[0] if num_cols else None

# ---------- Carga de datos ----------
df, _, _ = load_all_data(
    st.session_state["data_dir"],
    st.session_state["nomina_path_in"],
    st.session_state["include_aa"],
    st.session_state["use_alias"],
)
if df.empty:
    st.info("Cargá CSV en la carpeta indicada o usá gdrive:<FOLDER_ID>.")
    st.stop()

df["Mes"] = pd.to_datetime(df["Mes"], errors="coerce")
valid = df["Mes"].dropna()
if valid.empty:
    st.error("No hay columna 'Mes' valida en los datos.")
    st.stop()

min_mes, max_mes = valid.min().to_pydatetime(), valid.max().to_pydatetime()
rango = st.slider("Rango de meses", min_value=min_mes, max_value=max_mes, value=(min_mes, max_mes), format="YYYY-MM")
df = df[(df["Mes"] >= pd.Timestamp(rango[0])) & (df["Mes"] <= pd.Timestamp(rango[1]))]

# ---------- Seleccion de entidades ----------
entidades = sorted([e for e in df["Etiqueta"].dropna().unique()])
default_ent = pick_default_entity(entidades)
sel_ent = st.multiselect("Entidades", entidades, default=[default_ent] if default_ent else [])
df = df[df["Etiqueta"].isin(sel_ent)] if sel_ent else df

# ---------- Seleccion de metricas ----------
num_cols = list_numeric_columns(df)
if not num_cols:
    st.error("No hay columnas numericas para operar.")
    st.stop()

default_metric = pick_default_metric(num_cols)
idx_A = num_cols.index(default_metric) if default_metric in num_cols else 0
idx_B = 0 if len(num_cols) == 1 else (1 if idx_A == 0 else 0)

st.markdown("**Construir indicador**")
c1, c2, c3, c4 = st.columns([2,1,2,1])
with c1:
    A = st.selectbox("A", num_cols, index=idx_A)
with c2:
    op1_label = st.selectbox("Op1", ["+", "-", "x", "/"], index=1)
with c3:
    B = st.selectbox("B", num_cols, index=idx_B)
with c4:
    add_c = st.checkbox("Agregar C", value=False)

if add_c:
    c5, c6 = st.columns([1,2])
    with c5:
        op2_label = st.selectbox("Op2", ["+", "-", "x", "/"], index=0)
    with c6:
        C = st.selectbox("C", num_cols, index=min(2, len(num_cols)-1))
else:
    op2_label = None
    C = None

norm = st.selectbox("Normalizacion (resultado)", ["Raw", "Base 100 (primer mes)", "Min-Max (0-1)", "Z-score"], index=0)

# ---------- Operaciones (ASCII) ----------
def apply_op(s1, op_label, s2):
    if op_label == "+":
        return s1 + s2
    if op_label == "-":
        return s1 - s2
    if op_label == "x":
        return s1 * s2
    if op_label == "/":
        # evitar division por cero
        s2z = s2.replace(0, pd.NA)
        return s1 / s2z
    return pd.Series(index=s1.index, dtype="float64")

# ---------- Construccion del indicador ----------
series_list = []
label = f"{A} {op1_label} {B}" + (f" {op2_label} {C}" if op2_label and C else "")
for ent, sub in df.groupby("Etiqueta"):
    s = apply_op(sub[A], op1_label, sub[B])
    if op2_label and C:
        s = apply_op(s, op2_label, sub[C])
    s = normalize_series(s, norm)
    out = pd.DataFrame({"Mes": sub["Mes"], "Entidad": ent, "Indicador": label, "Valor": s})
    series_list.append(out)

plot_df = pd.concat(series_list, ignore_index=True)

st.subheader("Serie derivada")
fig = px.line(plot_df, x="Mes", y="Valor", color="Entidad",
              title=f"{label} ({norm})",
              labels={"Mes": "Mes", "Valor": "Valor", "Entidad": "Entidad"})
fig.update_layout(height=520)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Tabla (datos usados)")
st.dataframe(plot_df.sort_values(["Entidad","Mes"]).reset_index(drop=True),
             use_container_width=True, height=380)
