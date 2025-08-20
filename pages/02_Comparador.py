# pages/02_Comparador.py
import streamlit as st
import plotly.express as px
import pandas as pd
from lib_data import load_all_data, list_numeric_columns, normalize_series

st.title("🧭 Comparador multi-métrica")

with st.sidebar:
    st.header("Datos")
    data_dir = st.text_input("Carpeta de datos (.csv)", value="data", key="c_data_dir")
    nomina_path_in = st.text_input("Archivo nómina", value="Nomina.txt", key="c_nom")
    include_aa = st.checkbox("Incluir 'AA...'", value=False, key="c_aa")
    use_alias = st.checkbox("Usar alias", value=True, key="c_alias")

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
metrics = st.multiselect("Métricas a comparar (1–6)", num_cols, default=num_cols[:3], max_selections=6)
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
