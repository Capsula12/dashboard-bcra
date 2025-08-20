# app.py
import streamlit as st
from lib_data import load_all_data

st.set_page_config(page_title="Tablero BCRA - Bancos", layout="wide")

st.title("📊 Tablero BCRA – Bancos (multipágina)")
st.write(
    "Usá el menú **Pages** (arriba o en la barra lateral) para navegar: "
    "`Series`, `Comparador`, `Calculadora`."
)

with st.sidebar:
    st.header("⚙️ Configuración global")
    data_dir = st.text_input("Carpeta de datos (.csv)", value="data")
    nomina_path_in = st.text_input("Archivo nómina", value="Nomina.txt")
    include_aa = st.checkbox("Incluir filas agregadas 'AA...'", value=False)
    use_alias = st.checkbox("Usar alias corto si existe", value=True)

df, seps, nomina_used = load_all_data(
    data_dir=data_dir,
    nomina_path_in=nomina_path_in,
    include_aa=include_aa,
    use_alias=use_alias
)

if df.empty:
    st.info("No encontré CSV en la carpeta indicada. Cargá datos en `data/`.")
else:
    st.success(
        f"Datos cargados: **{df['__archivo'].nunique()} archivos** | "
        f"Entidades: **{df['Etiqueta'].nunique()}** | "
        f"Meses: **{df['Mes'].min().date() if df['Mes'].notna().any() else 'N/D'} → "
        f"{df['Mes'].max().date() if df['Mes'].notna().any() else 'N/D'}**"
    )
    with st.expander("Detalles técnicos"):
        st.write("Separadores detectados:", seps)
        st.write("Nómina usada:", nomina_used if nomina_used else "No encontrada (mostrando códigos).")
    st.write("→ Andá a **Pages** para explorar.")
