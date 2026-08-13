import io
import datetime
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from streamlit_option_menu import option_menu

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

# --- FACTORES TRANSPORTE Y BORDADO ---
FACTORES_TRANSPORTE = {
    "Auto": {"consumo": 0.10, "factor": 2.31},
    "Minivan": {"consumo": 0.12, "factor": 2.00},
    "Mototaxi": {"consumo": 0.04, "factor": 2.31},
    "Moto": {"consumo": 0.03, "factor": 2.31},
    "Camión mediano": {"consumo": 0.30, "factor": 2.68},
    "Camión grande": {"consumo": 0.40, "factor": 2.68}
}

FACTORES_BORDADO = {
    "Sin bordado / Ninguno": 0.0,
    "Simple (5 min/pieza)": 0.020,
    "Medio (9 min/pieza)": 0.037,
    "Complejo (10 min/pieza)": 0.041
}

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS MODERNOS ---
st.set_page_config(
    page_title="Gestión de Proyectos - Pequeños Detalles",
    page_icon="🧵",
    layout="wide"
)

# Inyección de estilos CSS UI/UX Modernos
st.markdown("""
    <style>
    /* Ocultar botones de incrementos en Inputs numéricos */
    div[data-testid="stNumberInput"] button { display: none !important; }
    div[data-testid="stNumberInput"] input { text-align: left; }
    
    /* Estilo para Tarjetas de Proyectos */
    .card-proyecto {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #e2e8f0;
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.03);
        margin-bottom: 15px;
        transition: all 0.2s ease-in-out;
    }
    .card-proyecto:hover {
        border-color: #cbd5e1;
        box-shadow: 0px 6px 16px rgba(0, 0, 0, 0.06);
    }
    .badge-estado {
        background-color: #fef3c7;
        color: #d97706;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.75rem;
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

# --- ESTADOS DE SESIÓN INICIALES ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "selected_menu" not in st.session_state:
    st.session_state.selected_menu = "Nuevo Reporte PDF"

if "proyecto_editar" not in st.session_state:
    st.session_state.proyecto_editar = {}

# --- LOGIN ---
USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTO = "pequenos2026"

if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center;'>🧵 Pequeños Detalles Handmade Perú</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #64748b;'>Sistema Inteligente de Informes Técnicos</h4>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
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
    # --- MENÚ LATERAL INTERACTIVO Y MODERNO ---
    with st.sidebar:
        st.markdown("### 🧵 Pequeños Detalles")
        st.caption("Admin | Sistema Interno")
        st.write("---")

        # Menú moderno con Streamlit Option Menu
        menu_actual = option_menu(
            menu_title="Menú Principal",
            options=["Nuevo Reporte PDF", "Proyectos en Proceso", "Dashboard 2026", "Historial Completo"],
            icons=["file-earmark-plus", "hourglass-split", "bar-chart-line", "journal-text"],
            menu_icon="cast",
            default_index=0 if st.session_state.selected_menu == "Nuevo Reporte PDF" else
                          1 if st.session_state.selected_menu == "Proyectos en Proceso" else
                          2 if st.session_state.selected_menu == "Dashboard 2026" else 3,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#0284c7", "font-size": "16px"}, 
                "nav-link": {"font-size": "14px", "text-align": "left", "margin": "4px", "border-radius": "8px"},
                "nav-link-selected": {"background-color": "#0284c7", "font-weight": "500"},
            }
        )
        st.session_state.selected_menu = menu_actual

        st.write("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()

    # --- CANVAS REPORTE PDF ---
    class ReporteCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.pages = []

        def showPage(self):
            self.pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            for page in self.pages:
                self.__dict__.update(page)
                self.draw_page_decorations()
                super().showPage()
            super().save()

        def draw_page_decorations(self):
            self.saveState()
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#7F8C8D"))
            self.drawString(36, 20, "Pequeños Detalles Handmade Perú S.A.C. - Trazabilidad y Sostenibilidad Textil")
            self.drawRightString(576, 20, f"Página {self._pageNumber}")
            self.restoreState()

    # --- GENERADOR PDF ---
    def generar_pdf_oficial(
        cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area,
        tipo_material, valorizacion, unidad_medida, guia_remision, origen, destino,
        lista_items, lista_trazabilidad, lista_productos,
        mat_transformado, retazos_aprovechables, perdida_no_aprovechable, total_procesado,
        pct_aprovechamiento_total, pct_perdida,
        horas_totales, cant_personas,
        co2_evitado_total, emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado
    ):
        kg_recibidos = sum([item["peso_total"] for item in lista_items])
        emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
        co2_neto = co2_evitado_total - emisiones_proceso

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)

        styles = getSampleStyleSheet()
        h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14, textColor=colors.HexColor('#1E293B'), alignment=1, spaceAfter=2)
        sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#64748B'), alignment=1, spaceAfter=12)
        h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0F172A'), spaceBefore=10, spaceAfter=6)
        cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#334155'), leading=10)
        cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#0F172A'), leading=10)
        card_title = ParagraphStyle('CardT', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#0F172A'), alignment=1)
        card_sub = ParagraphStyle('CardS', parent=styles['Normal'], fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#475569'), alignment=1)

        elements = []

        elements.append(Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style))
        elements.append(Paragraph(f"Medición de Impacto Ambiental, Trazabilidad y Gestión Social de Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>", sub_style))

        cards_data = [
            [
                Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", card_title),
                Paragraph(f"<b>{pct_aprovechamiento_total:.2f}%</b>", card_title),
                Paragraph(f"<b>{co2_neto:.2f} kg</b>", card_title),
                Paragraph(f"<b>{horas_totales:.2f} hrs</b>", card_title)
            ],
            [
                Paragraph("MATERIAL RECIBIDO", card_sub),
                Paragraph("% APROVECHAMIENTO", card_sub),
                Paragraph("CO₂e NETO EVITADO", card_sub),
                Paragraph(f"TRABAJO GENERADO ({cant_personas} PERS.)", card_sub)
            ]
        ]
        t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
        t_cards.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0,0), (-1,-1), 6),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        elements.append(t_cards)
        elements.append(Spacer(1, 8))

        elements.append(Paragraph("1. FICHA GENERAL DEL PROYECTO Y TRAZABILIDAD", h2_style))
        data_ficha = [
            [Paragraph("Cliente / Empresa", cell_bold), Paragraph(f"{cliente} (RUC: {ruc})", cell_style), Paragraph("Área / Responsable", cell_bold), Paragraph(f"{area} / {responsable}", cell_style)],
            [Paragraph("Nombre del Proyecto", cell_bold), Paragraph(proyecto_nom, cell_style), Paragraph("Periodo de Ejecución", cell_bold), Paragraph(f"{fe_inicio} al {fe_fin}", cell_style)],
            [Paragraph("Tipo de Material", cell_bold), Paragraph(tipo_material, cell_style), Paragraph("Tipo de Valorización", cell_bold), Paragraph(valorizacion, cell_style)],
            [Paragraph("Guía de Remisión", cell_bold), Paragraph(guia_remision, cell_style), Paragraph("Unidad de Medida", cell_bold), Paragraph(unidad_medida, cell_style)],
            [Paragraph("Punto de Origen", cell_bold), Paragraph(origen, cell_style), Paragraph("Punto de Destino", cell_bold), Paragraph(destino, cell_style)],
        ]
        t_ficha = Table(data_ficha, colWidths=[100, 170, 100, 170])
        t_ficha.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F8FAFC')),
            ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#F8FAFC')),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_ficha)
        elements.append(Spacer(1, 8))

        doc.build(elements, canvasmaker=ReporteCanvas)
        buffer.seek(0)
        return buffer

    # --- PESTAÑA 1: NUEVO / CONTINUAR PROYECTO ---
    if st.session_state.selected_menu == "Nuevo Reporte PDF":
        p_edit = st.session_state.proyecto_editar
        
        if p_edit:
            st.info(f"✏️ **Modo Edición Activo:** Editando proyecto de **{p_edit.get('cliente', '')}** (Código: `{p_edit.get('codigo', '')}`)")
            if st.button("❌ Salir de la edición y limpiar campos"):
                st.session_state.proyecto_editar = {}
                st.rerun()

        st.title("📋 Completa o Edita el Reporte")
        st.write("---")

        # 1. FICHA
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

        c7, c8, c9 = st.columns(3)
        responsable = c7.text_input("Responsable", value=p_edit.get("responsable", ""))
        area = c8.text_input("Área", value=p_edit.get("area", ""))
        guia_remision = c9.text_input("Nº Guía Remisión", value=p_edit.get("guia_remision", ""))

        c10, c11 = st.columns(2)
        origen = c10.text_input("Punto Origen", value=p_edit.get("origen", ""))
        destino = c11.text_input("Punto Destino", value=p_edit.get("destino", ""))

        st.write("---")

        # 2. INGRESO DE MATERIAL
        st.subheader("2. Ingreso de Material")
        if "num_items" not in st.session_state:
            st.session_state.num_items = 2

        col_btn1, col_btn2, _ = st.columns([1, 1, 4])
        if col_btn1.button("➕ Agregar Ítem"):
            st.session_state.num_items += 1
            st.rerun()
        if col_btn2.button("➖ Quitar Ítem") and st.session_state.num_items > 1:
            st.session_state.num_items -= 1
            st.rerun()

        lista_items = []
        peso_total_recibido = 0.0
        co2_evitado_total = 0.0
        opciones_prendas = sorted(list(FACTORES_CO2.keys()))

        for i in range(st.session_state.num_items):
            st.markdown(f"**Material {i+1}**")
            col_desc, col_unid, col_peso, col_tot, col_foto = st.columns([3, 1.5, 1.5, 1.5, 3])

            desc = col_desc.selectbox("Tipo de Producto / Prenda", opciones_prendas, key=f"desc_{i}")
            unid = col_unid.number_input("Ingreso (unid.)", min_value=0, value=0, key=f"unid_{i}")
            peso_u = col_peso.number_input("Peso Unit. (kg)", min_value=0.0, value=0.0, step=0.05, key=f"peso_{i}")
            p_total = unid * peso_u
            col_tot.text_input("Peso Total", value=f"{p_total:.2f} kg", disabled=True, key=f"tot_{i}")
            foto = col_foto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"foto_{i}")

            factor = FACTORES_CO2.get(desc, 6.575)
            co2_item = p_total * factor
            co2_evitado_total += co2_item

            peso_total_recibido += p_total
            lista_items.append({
                "descripcion": desc, "unidades": unid, "peso_unitario": peso_u,
                "peso_total": p_total, "foto": foto, "co2_evitado": co2_item
            })

        if peso_total_recibido == 0 and p_edit.get("peso_recibido"):
            peso_total_recibido = float(p_edit.get("peso_recibido", 0))

        st.info(f"📦 **Total Material Recibido:** {peso_total_recibido:.2f} kg | **CO₂ Evitado Calculado:** {co2_evitado_total:.2f} kg CO₂e")
        st.write("---")

        # ACCIONES DE GUARDADO
        b_col1, b_col2 = st.columns(2)

        if b_col1.button("💾 Guardar Borrador (En Proceso)", use_container_width=True):
            try:
                supabase.table("proyectos").upsert({
                    "codigo": codigo_proy if codigo_proy else "PROY-PENDIENTE",
                    "cliente": cliente if cliente else "CLIENTE POR DEFINIR",
                    "fecha": f"{fe_inicio} - {fe_fin}",
                    "peso_recibido": peso_total_recibido,
                    "ruc": ruc,
                    "estado": "EN_PROCESO"
                }).execute()
                st.success("💾 Se guardó como 'Proyecto en Proceso'.")
            except Exception as e:
                st.error(f"Error al guardar borrador: {e}")

        if b_col2.button("📑 Finalizar y Generar PDF", type="primary", use_container_width=True):
            try:
                supabase.table("proyectos").upsert({
                    "codigo": codigo_proy if codigo_proy else "SIN-CODIGO",
                    "cliente": cliente if cliente else "CLIENTE GENERAL",
                    "fecha": f"{fe_inicio} - {fe_fin}",
                    "peso_recibido": peso_total_recibido,
                    "ruc": ruc,
                    "estado": "COMPLETADO"
                }).execute()
                st.session_state.proyecto_editar = {}
                st.success("✅ Proyecto guardado como COMPLETADO.")
            except Exception as e:
                st.info("ℹ️ Registro finalizado.")

    # --- PESTAÑA 2: PROYECTOS EN PROCESO (DISEÑO MODERNO DE TARJETAS) ---
    elif st.session_state.selected_menu == "Proyectos en Proceso":
        st.title("⏳ Proyectos en Proceso")
        st.caption("Gestiona y continúa con el llenado de los borradores pendientes de envío.")
        st.write("---")

        proyectos_wip = cargar_proyectos(estado="EN_PROCESO")

        if proyectos_wip:
            st.markdown(f"#### 📁 {len(proyectos_wip)} Proyecto(s) Pendiente(s)")
            st.write("")

            for idx_p, p in enumerate(proyectos_wip):
                cod_ref = p.get('codigo', 'SIN-CÓDIGO')
                cli_ref = p.get('cliente', 'CLIENTE SIN NOMBRE')
                peso = p.get('peso_recibido', 0.0)
                fechas = p.get('fecha', 'Sin fecha definida')

                # Tarjeta Interactiva
                with st.container(border=True):
                    col_info, col_detalles, col_accion = st.columns([3, 2, 1.5])
                    
                    with col_info:
                        st.markdown(f"### 🏢 **{cli_ref}**")
                        st.markdown(f"📌 **RUC / ID:** `{p.get('ruc', 'No especificado')}`")
                    
                    with col_detalles:
                        st.caption("📊 DATOS DEL PROYECTO")
                        st.write(f"**Código:** `{cod_ref}`")
                        st.write(f"**Peso registrado:** {peso} kg")
                        st.write(f"**Fechas:** {fechas}")
                    
                    with col_accion:
                        st.write("")
                        st.write("")
                        # Botón que asigna los datos al formulario y fuerzan la redirección inmediata
                        if st.button("✏️ Continuar / Editar", key=f"btn_edit_{cod_ref}_{idx_p}", type="primary", use_container_width=True):
                            st.session_state.proyecto_editar = p
                            st.session_state.selected_menu = "Nuevo Reporte PDF"
                            st.rerun()
        else:
            st.info("🎉 ¡Excelente! No tienes ningún proyecto en proceso o pendiente por completar.")

    # --- PESTAÑAS SECUNDARIAS ---
    elif st.session_state.selected_menu == "Dashboard 2026":
        st.title("📊 Dashboard Consolidado 2026")
        lista = cargar_proyectos(estado="COMPLETADO")
        if lista:
            df = pd.DataFrame(lista)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No hay datos de proyectos completados.")

    elif st.session_state.selected_menu == "Historial Completo":
        st.title("📜 Historial General")
        lista = cargar_proyectos()
        if lista:
            st.dataframe(pd.DataFrame(lista), use_container_width=True)
        else:
            st.info("Sin registros almacenados.")
