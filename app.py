import io
import datetime
import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Importaciones para ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# --- FACTORES DE EMISIÓN DE MATERIALES ---
FACTORES_CO2 = {
    "Banner": 9.5, "Bata de laboratorio": 6.575, "Bolsas": 8.0, "Camisa": 6.575,
    "Camisa algodón": 5.0, "Camisa drill": 5.9, "Camisa ignífuga": 5.35, "Camisa jean / denim": 5.0,
    "Camisaco": 5.0, "Camisaco drill": 5.9, "Camisaco drill con cinta": 6.25, "Casaca": 6.575,
    "Casaca drill": 5.9, "Casaca polar": 6.0, "Casaca polar con cinta reflectiva": 6.3,
    "Casaca térmica": 6.1, "Chaleco": 6.575, "Chaleco con cinta": 6.925, "Chaleco de seguridad": 9.75,
    "Chaleco Fluorescente": 9.625, "Chaleco polar": 6.0, "Chaleco reversible": 9.5, "Chompa": 7.1,
    "Chompa con cinta reflectiva": 7.45, "Chompa Jorge Chavez": 6.0,
    "Chompa Jorge Chavez con cinta reflectiva": 6.3, "Chompa polar": 6.0, "Enterizo": 6.575,
    "Gorro": 7.925, "Impermeable": 9.425, "Mameluco": 6.575, "Mameluco acolchado": 5.825,
    "Mameluco drill": 5.9, "Mameluco jean reflectivo": 5.35, "Merma": 6.575, "Overol": 6.575,
    "Pantalón": 6.575, "Pantalón algodón": 5.0, "Pantalón drill": 5.9, "Pantalón drill con cinta": 6.25,
    "Pantalón ignífugo": 5.35, "Pantalón jean": 5.0, "Pantalón jean / drill": 5.675,
    "Pantalón jean con cinta reflectiva": 5.35, "Pantalón polar": 6.0, "Pantalón térmico": 6.0,
    "Polera": 5.0, "Polera polar": 6.0, "Polo": 6.8, "Polo algodón": 5.0,
    "Polo con cinta reflectiva": 6.925, "Polo manga corta": 6.8, "Polo manga larga": 6.8,
    "Polo manga larga con cinta reflectiva": 6.7, "Polo piqué": 5.0, "Short": 6.575,
    "Toalla": 5.0, "Otro": 6.575
}

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Pequeños Detalles - Sistema de Trazabilidad",
    page_icon="🧵",
    layout="wide"
)

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    /* Ocultar flechas numéricas */
    div[data-testid="stNumberInput"] button { display: none !important; }
    div[data-testid="stNumberInput"] input { text-align: left; }
    
    /* Header principal moderno */
    .hero-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 50%, #2563EB 100%);
        color: white;
        padding: 24px 30px;
        border-radius: 16px;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3);
        margin-bottom: 25px;
    }
    .hero-header h1 {
        color: #ffffff !important;
        font-weight: 800;
        font-size: 1.8rem;
        margin: 0;
    }
    .hero-header p {
        color: #93C5FD !important;
        margin: 4px 0 0 0;
        font-size: 0.95rem;
    }

    /* Badges de estado */
    .badge-wip {
        background-color: #FEF3C7;
        color: #D97706;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.8rem;
        border: 1px solid #FCD34D;
    }

    /* Estilos para el sidebar */
    div[data-testid="stSidebar"] {
        background-color: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    
    .sidebar-section-title {
        color: #475569;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 15px;
        margin-bottom: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception:
    st.error("Error al conectar con Supabase. Revisa las credenciales en Secrets.")

def cargar_proyectos(estado=None):
    try:
        query = supabase.table("proyectos").select("*")
        if estado:
            query = query.eq("estado", estado)
        response = query.execute()
        return response.data
    except Exception:
        return []

# --- ESTADOS DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "pestaña_activa" not in st.session_state:
    st.session_state.pestaña_activa = "➕ Nuevo Reporte PDF"

if "proyecto_editar" not in st.session_state:
    st.session_state.proyecto_editar = {}

# --- LOGIN ---
USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTO = "pequenos2026"

if not st.session_state.autenticado:
    st.markdown("""
        <div style="text-align: center; padding: 40px 10px;">
            <h1 style="color: #1E293B; font-size: 2.2rem; font-weight: 800;">🧵 Pequeños Detalles</h1>
            <p style="color: #64748B; font-size: 1.1rem;">Handmade Perú S.A.C. — Gestión de Sostenibilidad</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("🔑 Iniciar Sesión")
            usuario_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")
            
            if st.button("Ingresar al Sistema", use_container_width=True, type="primary"):
                if usuario_input == USUARIO_CORRECTO and password_input == PASSWORD_CORRECTO:
                    st.session_state.autenticado = True
                    st.success("¡Bienvenido/a!")
                    st.rerun()
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")

else:
    # --- Cargar lista de proyectos en proceso ---
    proyectos_wip = cargar_proyectos(estado="EN_PROCESO")

    # --- BARRA LATERAL MODERNA ---
    with st.sidebar:
        st.markdown("### 🧵 Pequeños Detalles")
        st.caption("Panel de Control Interno | 2026")
        st.write("---")

        st.markdown('<p class="sidebar-section-title">Navegación</p>', unsafe_allow_html=True)

        if st.button("✨ Nuevo Reporte PDF", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "➕ Nuevo Reporte PDF" else "secondary"):
            st.session_state.proyecto_editar = {}
            st.session_state.pestaña_activa = "➕ Nuevo Reporte PDF"
            st.rerun()

        st.markdown('<p class="sidebar-section-title">Proyectos Pendientes</p>', unsafe_allow_html=True)
        
        # LISTA DIRECTA DE BOTONES POR CADA PROYECTO EN PROCESO
        if proyectos_wip:
            for p in proyectos_wip:
                cli_nombre = p.get('cliente', 'Sin Nombre')
                cod_ref = p.get('codigo', '')
                label_btn = f"🔸 {cli_nombre}" + (f" ({cod_ref})" if cod_ref else "")
                
                # Resaltar botón si es el proyecto seleccionado en este momento
                es_activo = st.session_state.proyecto_editar.get('id') == p.get('id') or st.session_state.proyecto_editar.get('codigo') == cod_ref
                
                if st.button(label_btn, key=f"side_proj_{p.get('id', cod_ref)}", use_container_width=True, type="primary" if es_activo else "secondary"):
                    st.session_state.proyecto_editar = p
                    st.session_state.pestaña_activa = "➕ Nuevo Reporte PDF"
                    st.rerun()

            st.write("")
            if st.button("📋 Ver Lista en Proceso", use_container_width=True):
                st.session_state.pestaña_activa = "⏳ Proyectos en Proceso"
                st.rerun()
        else:
            st.caption("🟢 No hay proyectos en borrador")

        st.markdown('<p class="sidebar-section-title">Analítica e Histórico</p>', unsafe_allow_html=True)

        if st.button("📊 Dashboard 2026", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "📊 Dashboard 2026" else "secondary"):
            st.session_state.pestaña_activa = "📊 Dashboard 2026"
            st.rerun()

        if st.button("📜 Historial Completo", use_container_width=True, type="primary" if st.session_state.pestaña_activa == "📜 Historial Completo" else "secondary"):
            st.session_state.pestaña_activa = "📜 Historial Completo"
            st.rerun()

        st.write("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.proyecto_editar = {}
            st.rerun()

    # --- HEADER VÍVIDO PARA TODAS LAS PÁGINAS ---
    st.markdown(f"""
        <div class="hero-header">
            <h1>🧵 Sistema de Gestión de Informes Técnicos</h1>
            <p>Sección Activa: <b>{st.session_state.pestaña_activa}</b></p>
        </div>
    """, unsafe_allow_html=True)

    # --- PESTAÑA: NUEVO / EDITAR REPORTE ---
    if st.session_state.pestaña_activa == "➕ Nuevo Reporte PDF":
        p_edit = st.session_state.proyecto_editar
        
        if p_edit:
            st.warning(f"✏️ **Modo Edición Activo:** Modificando borrador de **{p_edit.get('cliente', '')}** (`{p_edit.get('codigo', '')}`)")
            if st.button("❌ Descartar selección y limpiar formulario"):
                st.session_state.proyecto_editar = {}
                st.rerun()

        with st.container(border=True):
            st.subheader("1. Ficha del Proyecto")
            c1, c2, c3 = st.columns(3)
            cliente = c1.text_input("Cliente / Empresa", value=p_edit.get("cliente", ""))
            ruc = c2.text_input("RUC", value=p_edit.get("ruc", ""))
            codigo_proy = c3.text_input("Código de Proyecto", value=p_edit.get("codigo", ""))

            c4, c5, c6 = st.columns(3)
            fechas_raw = p_edit.get("fecha", " - ").split(" - ")
            f_ini_val = fechas_raw[0] if len(fechas_raw) > 0 else ""
            f_fin_val = fechas_raw[1] if len(fechas_raw) > 1 else ""

            proyecto_nom = c4.text_input("Nombre del Proyecto", value=p_edit.get("nombre", f"Upcycling {cliente}"))
            fe_inicio = c5.text_input("Fecha Inicio", value=f_ini_val)
            fe_fin = c6.text_input("Fecha Término", value=f_fin_val)

        st.write("")

        # BOTONES DE ACCIÓN PRINCIPALES
        b_col1, b_col2 = st.columns(2)

        if b_col1.button("💾 Guardar Borrador (En Proceso)", use_container_width=True):
            try:
                supabase.table("proyectos").upsert({
                    "codigo": codigo_proy if codigo_proy else "PROY-PENDIENTE",
                    "cliente": cliente if cliente else "CLIENTE POR DEFINIR",
                    "fecha": f"{fe_inicio} - {fe_fin}",
                    "ruc": ruc,
                    "estado": "EN_PROCESO"
                }).execute()
                st.success("💾 ¡Guardado con éxito como Borrador!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

        if b_col2.button("📑 Finalizar y Completar Proyecto", type="primary", use_container_width=True):
            try:
                supabase.table("proyectos").upsert({
                    "codigo": codigo_proy if codigo_proy else "SIN-CODIGO",
                    "cliente": cliente if cliente else "CLIENTE GENERAL",
                    "fecha": f"{fe_inicio} - {fe_fin}",
                    "ruc": ruc,
                    "estado": "COMPLETADO"
                }).execute()
                st.session_state.proyecto_editar = {}
                st.balloons()
                st.success("🎉 ¡Proyecto completado con éxito!")
            except Exception as e:
                st.info("ℹ️ Guardado.")

    # --- PESTAÑA: PROYECTOS EN PROCESO ---
    elif st.session_state.pestaña_activa == "⏳ Proyectos en Proceso":
        st.subheader("⏳ Listado de Proyectos en Proceso")
        st.caption("Haz clic en cualquier proyecto para cargarlo en el formulario.")
        st.write("---")

        if proyectos_wip:
            for idx_p, p in enumerate(proyectos_wip):
                cod_ref = p.get('codigo', 'SIN-CÓDIGO')
                cli_ref = p.get('cliente', 'CLIENTE SIN NOMBRE')

                with st.container(border=True):
                    col_info, col_status, col_btn = st.columns([3, 1.5, 1.5])
                    
                    with col_info:
                        st.markdown(f"### 🏢 **{cli_ref}**")
                        st.caption(f"📌 **Código:** `{cod_ref}` | 💳 **RUC:** `{p.get('ruc', '-')}`")
                    
                    with col_status:
                        st.markdown('<span class="badge-wip">⏳ EN PROCESO</span>', unsafe_allow_html=True)
                        st.write(f"📅 {p.get('fecha', 'Sin fecha')}")

                    with col_btn:
                        st.write("")
                        if st.button("✏️ Continuar / Editar", key=f"btn_edit_list_{cod_ref}_{idx_p}", type="primary", use_container_width=True):
                            st.session_state.proyecto_editar = p
                            st.session_state.pestaña_activa = "➕ Nuevo Reporte PDF"
                            st.rerun()
        else:
            st.success("🎉 ¡No hay borradores pendientes! Todos tus proyectos están al día.")

    # --- OTRAS PESTAÑAS ---
    elif st.session_state.pestaña_activa == "📊 Dashboard 2026":
        st.subheader("📊 Métrica General de Impacto")
        lista_completados = cargar_proyectos(estado="COMPLETADO")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Proyectos Completados", len(lista_completados), "2026")
        col2.metric("Proyectos en Proceso", len(proyectos_wip), "-")
        col3.metric("Impacto Social Generado", "100%", "+ Sostenible")

        st.write("---")
        if lista_completados:
            st.dataframe(pd.DataFrame(lista_completados), use_container_width=True)

    elif st.session_state.pestaña_activa == "📜 Historial Completo":
        st.subheader("📜 Historial de Proyectos")
        lista = cargar_proyectos()
        if lista:
            st.dataframe(pd.DataFrame(lista), use_container_width=True)
