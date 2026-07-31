import streamlit as st

# 1. Configuración de la página (Título e icono corporativo)
st.set_page_config(
    page_title="Control Interno - Pequeños Detalles",
    page_icon="🌸",
    layout="wide"
)

# 2. Credenciales del usuario único (Puedes cambiar la contraseña aquí)
USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTO = "pequenos2026"

# 3. Inicializar el estado de la sesión si no existe
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# --- PANTALLA 1: FORMULARIO DE LOGIN ---
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
                st.rerun()  # Recarga la página para mostrar la app
            else:
                st.error("⚠️ Usuario o contraseña incorrectos.")

# --- PANTALLA 2: APLICACIÓN PRINCIPAL (POST-LOGIN) ---
else:
    # Barra lateral (Sidebar) para navegación y salir
    with st.sidebar:
        st.image("https://via.placeholder.com/150", width=120) # Aquí irá el logo oficial
        st.title("Pequeños Detalles")
        st.write("👤 **Usuario:** Admin")
        st.write("---")
        
        # Opciones del Menú Principal
        opcion_menu = st.radio(
            "Selecciona una opción:",
            ["📊 Dashboard 2026", "➕ Nuevo Proyecto", "📁 Historial de Proyectos"]
        )
        
        st.write("---")
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

    # Contenido de la pantalla según la opción elegida
    if opcion_menu == "📊 Dashboard 2026":
        st.title("📊 Balance General e Indicadores 2026")
        st.info("Aquí verás los indicadores consolidados de todos los proyectos del año.")
        
    elif opcion_menu == "➕ Nuevo Proyecto":
        st.title("➕ Registro y Trazabilidad de Proyecto")
        st.info("Aquí ingresaremos los datos de las prendas, horas del equipo e impacto.")
        
    elif opcion_menu == "📁 Historial de Proyectos":
        st.title("📁 Proyectos Registrados")
        st.info("Aquí podrás ver la lista de proyectos y descargar los PDFs de la Constancia e Informe Técnico.")
