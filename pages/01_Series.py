# pages/01_Series.py
import streamlit as st
import plotly.express as px
import pandas as pd
from lib_data import load_all_data, list_numeric_columns

st.title("📈 Series temporales")

with st.sidebar:
    st.header("Datos")
    data_dir = st.text_input("Carpeta de datos (.csv)", value="data", key="s_data_dir")
    nomina_path_in = st.text_input("Archivo nómina", value="Nomina.txt", key="s_nom")
    include_aa = st.checkbox("Incluir 'AA...'", value=False, key="s_aa")
    use_alias = st.checkbox("Usar alias", value=True, key="s_alias")

df, seps, _ = load_all_data(data_dir, nomina_path_in, include_aa, use_alias)
if df.empty:
    st.info("Cargá CSV en la carpeta indicada.")
    st.stop()

df["Mes"] = pd.to_datetime(df["Mes"], errors="coerce")
valid = df["Mes"].dropna()
min_mes, max_mes = valid.min().to_pydatetime(), valid.max().to_pydatetime()
rango = st.slider("Rango de meses", min_mes, max_mes, (min_mes, max_mes), format="YYYY-MM")
df = df[(df["Mes"] >= pd.Timestamp(rango[0])) & (df["Mes"] <= pd.Timestamp(rango[1]))]

entidades = sorted(df["Etiqueta"].unique())
sel_ent = st.multiselect("Entidades (opcional)", entidades, [])
if sel_ent:
    df = df[df["Etiqueta"].isin(sel_ent)]

num_cols = list_numeric_columns(df)
if not num_cols:
    st.error("No hay columnas numéricas para graficar.")
    st.stop()

metric = st.selectbox("Indicador", num_cols, index=0)

st.subheader("Serie temporal")
fig = px.line(df, x="Mes", y=metric, color="Etiqueta",
              labels={"Mes": "Mes", metric: metric, "Etiqueta": "Entidad"},
              title=f"Evolución de {metric}")
fig.update_layout(height=460, legend_title_text="Entidad")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Top-N por mes")
meses = sorted(df["Mes"].dropna().unique())
mes_sel = st.selectbox("Mes", [m.to_pydatetime() for m in meses],
                       index=len(meses)-1, format_func=lambda d: d.strftime("%Y-%m"))
df_mes = df[df["Mes"] == pd.Timestamp(mes_sel)].copy()
topn = st.slider("Top N", 5, 50, 15)
df_mes = df_mes.sort_values(metric, ascending=False).head(topn)
fig2 = px.bar(df_mes, x=metric, y="Etiqueta", orientation="h",
              labels={"Etiqueta": "Entidad", metric: metric},
              title=f"Top {topn} en {pd.Timestamp(mes_sel).strftime('%Y-%m')} – {metric}")
fig2.update_layout(height=600, yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Tabla")
st.dataframe(df.sort_values(["Etiqueta","Mes"]).reset_index(drop=True), use_container_width=True, height=380)
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

