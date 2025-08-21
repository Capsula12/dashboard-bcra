# app.py
import streamlit as st
from lib_data import load_all_data

st.set_page_config(page_title="Tablero BCRA - Bancos", layout="wide")
st.title("📊 Tablero BCRA – Bancos (multipágina)")

with st.sidebar:
    st.header("⚙️ Configuración global")

    # Estado compartido (valores por defecto)
    if "data_dir" not in st.session_state:
        st.session_state["data_dir"] = "data"
    if "nomina_path_in" not in st.session_state:
        st.session_state["nomina_path_in"] = "Nomina.txt"
    if "include_aa" not in st.session_state:
        st.session_state["include_aa"] = True   # ← ahora tildado por defecto
    if "use_alias" not in st.session_state:
        st.session_state["use_alias"] = False   # ← ahora destildado por defecto

    # Sincronizar data_dir con la URL (para compartir enlaces)
    def _sync_qp():
        try:
            st.query_params["data_dir"] = st.session_state["data_dir"]
        except Exception:
            st.experimental_set_query_params(data_dir=st.session_state["data_dir"])

    try:
        qp = st.query_params
        if "data_dir" in qp and qp["data_dir"]:
            st.session_state["data_dir"] = qp["data_dir"]
    except Exception:
        qp = st.experimental_get_query_params()
        if "data_dir" in qp and qp["data_dir"]:
            st.session_state["data_dir"] = qp["data_dir"][0]

    st.text_input("Carpeta de datos (.csv)", key="data_dir", on_change=_sync_qp)
    st.text_input("Archivo nómina", key="nomina_path_in")
    st.checkbox("Incluir filas agregadas 'AA...'", key="include_aa")
    st.checkbox("Usar alias corto si existe", key="use_alias")

st.write("Usá el menú **Pages** (arriba o en la barra lateral) para navegar: `Series`, `Comparador`, `Calculadora`.")

# Carga (usa los valores actuales del estado)
df, seps, nomina_used = load_all_data(
    data_dir=st.session_state["data_dir"],
    nomina_path_in=st.session_state["nomina_path_in"],
    include_aa=st.session_state["include_aa"],
    use_alias=st.session_state["use_alias"],
)

if df.empty:
    st.info("No encontré CSV en la carpeta indicada. Cargá datos en `data/` o apuntá a `gdrive:<FOLDER_ID>`.")
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

st.markdown("### Navegación")
st.page_link("app.py", label="🏠 Inicio")
st.page_link("pages/01_Series.py", label="📈 Series")
st.page_link("pages/02_Comparador.py", label="🧭 Comparador")
st.page_link("pages/03_Calculadora.py", label="🧮 Calculadora")
st.divider()
