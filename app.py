import streamlit as st
from config import DEFAULT_DATA_DIR
from lib_data import load_all_data

st.set_page_config(page_title="Tablero BCRA - Bancos", layout="wide")
st.title("📊 Tablero BCRA – Bancos (multipágina)")

# ---------- Estado compartido (defaults únicos en toda la app) ----------
if "data_dir" not in st.session_state:
    st.session_state["data_dir"] = DEFAULT_DATA_DIR
if "nomina_path_in" not in st.session_state:
    st.session_state["nomina_path_in"] = "Nomina.txt"
if "include_aa" not in st.session_state:
    st.session_state["include_aa"] = True     # por defecto: tildado
if "use_alias" not in st.session_state:
    st.session_state["use_alias"] = False     # por defecto: destildado

# ---------- Sidebar (sincroniza data_dir con la URL) ----------
with st.sidebar:
    st.header("⚙️ Configuración global")

    # leer query param al cargar por primera vez
    try:
        qp = st.query_params
        if "data_dir" in qp and qp["data_dir"]:
            st.session_state["data_dir"] = qp["data_dir"]
        def _sync_qp():
            st.query_params["data_dir"] = st.session_state["data_dir"]
    except Exception:
        qp = st.experimental_get_query_params()
        if "data_dir" in qp and qp["data_dir"]:
            st.session_state["data_dir"] = qp["data_dir"][0]
        def _sync_qp():
            st.experimental_set_query_params(data_dir=st.session_state["data_dir"])

    st.text_input("Carpeta de datos (.csv)", key="data_dir", on_change=_sync_qp)
    st.text_input("Archivo nómina", key="nomina_path_in")
    st.checkbox("Incluir filas agregadas 'AA...'", key="include_aa")
    st.checkbox("Usar alias corto si existe", key="use_alias")

    st.divider()
    if st.button("Limpiar caché de datos"):
        st.cache_data.clear()
        st.success("Caché limpiada. Volvé a ejecutar o cambiá un control.")

st.write("Usá el menú **Pages** para navegar: Series, Comparador y Calculadora.")

# ---------- Carga de datos ----------
df, seps, nomina_used = load_all_data(
    data_dir=st.session_state["data_dir"],
    nomina_path_in=st.session_state["nomina_path_in"],
    include_aa=st.session_state["include_aa"],
    use_alias=st.session_state["use_alias"],
)

if df.empty:
    st.info("No encontré CSV en la carpeta indicada. Cargá datos en 'data/' o usá 'gdrive:<FOLDER_ID>'.")
else:
    # resumen
    try:
        min_mes = df["Mes"].min()
        max_mes = df["Mes"].max()
        rango_txt = f"{min_mes.date()} → {max_mes.date()}" if pd.notna(min_mes) and pd.notna(max_mes) else "N/D"
    except Exception:
        rango_txt = "N/D"

    st.success(
        f"Archivos: {df['__archivo'].nunique()} | "
        f"Entidades: {df['Etiqueta'].nunique()} | "
        f"Rango de meses: {rango_txt}"
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
