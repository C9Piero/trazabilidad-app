import streamlit as st
import pandas as pd

# 1. Configuración de la página
st.set_page_config(
    page_title="Control Interno - Pequeños Detalles",
    page_icon="🌸",
    layout="wide"
)

# 2. Credenciales
USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTO = "pequenos2026"

# 3. Estado de la sesión
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center;'>🌸 Pequeños Detalles Handmade Perú</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>Sistema Interno de Trazabilidad e Impacto</h4>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔐 Iniciar Sesión")
        usuario_input = st.text_input("Usuario", placeholder="Ingresa tu usuario")
        password_input = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
        
        if st.button("Ingresar al Sistema", use_container_width=True):
            if usuario_input == USUARIO_CORRECTO and password_input == PASSWORD_CORRECTO:
                st.session_state.autenticado = True
                st.success("¡Bienvenido/a! Cargando panel...")
                st.rerun()
            else:
                st.error("⚠️ Usuario o contraseña incorrectos.")

# --- APLICACIÓN PRINCIPAL (POST-LOGIN) ---
else:
    with st.sidebar:
        st.title("Pequeños Detalles")
        st.write("👤 **Usuario:** Admin")
        st.write("---")
        
        opcion_menu = st.radio(
            "Selecciona una opción:",
            ["📊 Dashboard 2026", "➕ Nuevo Proyecto", "📁 Historial de Proyectos"]
        )
        st.write("---")
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

    # MENU 1: DASHBOARD
    if opcion_menu == "📊 Dashboard 2026":
        st.title("📊 Balance General e Indicadores 2026")
        st.markdown("Resumen de impacto ambiental y social consolidado del año.")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("CO₂e Evitado", "218.96 kg", "🌱 Impacto Ambiental")
        col2.metric("Textil Procesado", "31.25 kg", "♻️ Upcycling")
        col3.metric("Horas Sociales", "294.5 hrs", "👥 Confección + Corte")
        col4.metric("Productos Obtenidos", "14,400 unids", "📦 Producción")

    # MENU 2: NUEVO PROYECTO
    elif opcion_menu == "➕ Nuevo Proyecto":
        st.title("➕ Registro de Proyecto de Upcycling")
        st.markdown("Ingresa los datos para calcular la trazabilidad y generar el Informe Técnico.")
        
        st.subheader("1. Datos Generales del Cliente")
        c1, c2, c3 = st.columns(3)
        cliente = c1.text_input("Nombre del Cliente / Empresa", value="HILTI PERÚ S.A.")
        ruc = c2.text_input("RUC del Cliente", value="20100000001")
        codigo_proy = c3.text_input("Código del Proyecto", value="HILTI-MAR26")
        
        st.write("---")
        st.subheader("2. Ingreso de Materiales (Prendas Recibidas)")
        st.caption("Edita la tabla con las prendas, unidades y peso estimado por unidad:")
        
        # Tabla interactiva de prendas
        df_prendas_default = pd.DataFrame([
            {"Tipo de Prenda": "POLERA", "Unidades": 100, "Peso Unitario (kg)": 1.0},
            {"Tipo de Prenda": "PANTALON DRILL", "Unidades": 200, "Peso Unitario (kg)": 1.0},
            {"Tipo de Prenda": "POLO", "Unidades": 100, "Peso Unitario (kg)": 1.0}
        ])
        
        df_prendas = st.data_editor(df_prendas_default, num_rows="dynamic", key="tabla_prendas")
        df_prendas["Peso Total (kg)"] = df_prendas["Unidades"] * df_prendas["Peso Unitario (kg)"]
        
        total_kilos_recibidos = df_prendas["Peso Total (kg)"].sum()
        st.info(f"⚖️ **Total Peso Recibido:** {total_kilos_recibidos:.2f} kg")

        st.write("---")
        st.subheader("3. Registro de Horas del Equipo (Corte y Logística)")
        
        df_corte_default = pd.DataFrame([
            {"Nombre": "Maria Isabel Estrada Sandoval", "Área": "Corte", "Días Trabajados": 5, "Horas/Día": 8.5},
            {"Nombre": "Genaro Jara García", "Área": "Corte", "Días Trabajados": 4, "Horas/Día": 8.5},
            {"Nombre": "Luciana Jara Estrada", "Área": "Corte", "Días Trabajados": 3, "Horas/Día": 8.5}
        ])
        
        df_corte = st.data_editor(df_corte_default, num_rows="dynamic", key="tabla_corte")
        df_corte["Horas Totales"] = df_corte["Días Trabajados"] * df_corte["Horas/Día"]
        total_horas_corte = df_corte["Horas Totales"].sum()
        
        st.info(f"⏱️ **Total Horas de Corte/Logística:** {total_horas_corte:.1f} hrs")

        st.write("---")
        if st.button("🚀 Procesar Datos y Guardar Proyecto", type="primary", use_container_width=True):
            st.success("✅ ¡Proyecto procesado exitosamente! Los cálculos de CO₂e y aprovechamiento se han generado.")

    # MENU 3: HISTORIAL
    elif opcion_menu == "📁 Historial de Proyectos":
        st.title("📁 Proyectos Registrados")
        st.markdown("Listado de informes procesados e imprevistos de descarga.")
