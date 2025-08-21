# pages/03_Calculadora.py
import streamlit as st
import plotly.express as px
import pandas as pd
from lib_data import load_all_data, list_numeric_columns, normalize_series

st.title("🧮 Calculadora de métricas")

with st.sidebar:
    st.header("Datos")
    data_dir = st.text_input("Carpeta de datos (.csv)", value="data", key="k_data_dir")
    nomina_path_in = st.text_input("Archivo nómina", value="Nomina.txt", key="k_nom")
    include_aa = st.checkbox("Incluir 'AA...'", value=False, key="k_aa")
    use_alias = st.checkbox("Usar alias", value=True, key="k_alias")

df, _, _ = load_all_data(data_dir, nomina_path_in, include_aa, use_alias)
if df.empty:
    st.info("Cargá CSV en la carpeta indicada.")
    st.stop()

df["Mes"] = pd.to_datetime(df["Mes"], errors="coerce")
valid = df["Mes"].dropna()
min_mes, max_mes = valid.min().to_pydatetime(), valid.max().to_pydatetime()
rango = st.slider("Rango de meses", min_mes, max_mes, (min_mes, max_mes), format="YYYY-MM")
df = df[(df["Mes"] >= pd.Timestamp(rango[0])) & (df["Mes"] <= pd.Timestamp(rango[1]))]

entidades = sorted(df["Etiqueta"].unique())
sel_ent = st.multiselect("Entidades", entidades, default=entidades[:2])
df = df[df["Etiqueta"].isin(sel_ent)] if sel_ent else df

num_cols = list_numeric_columns(df)
if not num_cols:
    st.error("No hay columnas numéricas para operar.")
    st.stop()

st.markdown("**Construí tu indicador:**")
c1, c2, c3, c4 = st.columns([2,1,2,1])
with c1:
    A = st.selectbox("A", num_cols, index=0)
with c2:
    op1 = st.selectbox("Op1", ["+", "-", "×", "÷"], index=1)
with c3:
    B = st.selectbox("B", num_cols, index=min(1, len(num_cols)-1))
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
    if op == "-": return s1 - s2
    if op == "×": return s1 * s2
    if op == "÷": return s1 / s2.replace(0, pd.NA)  # evitar división por cero
    return pd.Series(index=s1.index, dtype="float64")

series_list = []
label = f"{A} {op1} {B}" + (f" {op2} {C}" if op2 else "")
for ent, sub in df.groupby("Etiqueta"):
    s = apply_op(sub[A], op1, sub[B])
    if op2 and C:
        s = apply_op(s, op2, sub[C])
    s = normalize_series(s, norm)
    out = pd.DataFrame({"Mes": sub["Mes"], "Entidad": ent, "Indicador": label, "Valor": s})
    series_list.append(out)

plot_df = pd.concat(series_list, ignore_index=True)

st.subheader("Serie derivada")
fig = px.line(plot_df, x="Mes", y="Valor", color="Entidad",
              title=f"{label} ({norm})",
              labels={"Mes": "Mes", "Valor": norm if norm!='Raw' else "Valor", "Entidad": "Entidad"})
fig.update_layout(height=520)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Tabla (datos usados)")
st.dataframe(plot_df.sort_values(["Entidad","Mes"]).reset_index(drop=True),
             use_container_width=True, height=380)
# Helpers locales para default de entidad y métrica
import unicodedata
def _norm_txt(s: str) -> str:
    if s is None: return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()

def pick_default_entity(entities):
    # Prioridades: contiene "nacion", alias "bna", código "0011" (o variantes con ceros)
    cand = None
    for e in entities:
        se = _norm_txt(e)
        if "nacion" in se:
            return e
        if se.strip() in {"bna", "banco nacion", "banco de la nacion argentina"}:
            cand = cand or e
    # Por código
    for code in ["0011", "00011", "11"]:
        for e in entities:
            if e.strip().lstrip("0") == code.lstrip("0"):
                return e
    return cand or (entities[0] if entities else None)

def pick_default_metric(num_cols):
    # Prioridades: comienza con "r1", contiene "roe", contiene "rendimiento anual del patrimonio"
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

