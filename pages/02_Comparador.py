# pages/02_Comparador.py
import streamlit as st
import plotly.express as px
import pandas as pd
from lib_data import load_all_data, list_numeric_columns, normalize_series

# Helpers para defaults (idénticos a 01)
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

st.title("🧭 Comparador multi-métrica")

with st.sidebar:
    st.header("Datos")
    for k, v in [
        ("data_dir", "data"),
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
default_metrics = [default_metric] if default_metric else num_cols[:1]
metrics = st.multiselect("Métricas a comparar (1–6)", num_cols, default=default_metrics, max_selections=6)
if not metrics:
    st.warning("Elegí al menos una métrica.")
    st.stop()

norm = st.selectbox("Normalización", ["Raw", "Base 100 (primer mes)", "Min–Max (0–1)", "Z-score"], index=0)

# Reestructurar a long con normalización por entidad y métrica
records = []
for ent, sub in df.groupby("Etiqueta"):
    for m in metrics:
        s = normalize_series(sub[m], norm)
        tmp = pd.DataFrame({"Mes": sub["Mes"], "Etiqueta": ent, "Métrica": m, "Valor": s})
        records.append(tmp)
plot_df = pd.concat(records, ignore_index=True)

st.subheader("Serie combinada")
fig = px.line(plot_df, x="Mes", y="Valor", color="Etiqueta", line_dash="Métrica",
              title=f"Comparación {'normalizada' if norm!='Raw' else ''} – {', '.join(metrics)}",
              labels={"Mes": "Mes", "Valor": norm if norm!='Raw' else "Valor", "Etiqueta": "Entidad", "Métrica": "Métrica"})
fig.update_layout(height=520, legend_title_text="Entidad / Métrica")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Tabla (datos usados)")
st.dataframe(plot_df.sort_values(["Etiqueta","Métrica","Mes"]).reset_index(drop=True),
             use_container_width=True, height=380)
