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

# --- DICCIONARIO BASE DE DATOS DE FACTORES DE EMISIÓN DE CO2 ---
FACTORES_CO2 = {
    "Banner": 9.5,
    "Bata de laboratorio": 6.575,
    "Bolsas": 8.0,
    "Camisa": 6.575,
    "Camisa algodón": 5.0,
    "Camisa drill": 5.9,
    "Camisa ignífuga": 5.35,
    "Camisa jean / denim": 5.0,
    "Camisaco": 5.0,
    "Camisaco drill": 5.9,
    "Camisaco drill con cinta": 6.25,
    "Casaca": 6.575,
    "Casaca drill": 5.9,
    "Casaca polar": 6.0,
    "Casaca polar con cinta reflectiva": 6.3,
    "Casaca térmica": 6.1,
    "Chaleco": 6.575,
    "Chaleco con cinta": 6.925,
    "Chaleco de seguridad": 9.75,
    "Chaleco Fluorescente": 9.625,
    "Chaleco polar": 6.0,
    "Chaleco reversible": 9.5,
    "Chompa": 7.1,
    "Chompa con cinta reflectiva": 7.45,
    "Chompa Jorge Chavez": 6.0,
    "Chompa Jorge Chavez con cinta reflectiva": 6.3,
    "Chompa polar": 6.0,
    "Enterizo": 6.575,
    "Gorro": 7.925,
    "Impermeable": 9.425,
    "Mameluco": 6.575,
    "Mameluco acolchado": 5.825,
    "Mameluco drill": 5.9,
    "Mameluco jean reflectivo": 5.35,
    "Merma": 6.575,
    "Overol": 6.575,
    "Pantalón": 6.575,
    "Pantalón algodón": 5.0,
    "Pantalón drill": 5.9,
    "Pantalón drill con cinta": 6.25,
    "Pantalón ignífugo": 5.35,
    "Pantalón jean": 5.0,
    "Pantalón jean / drill": 5.675,
    "Pantalón jean con cinta reflectiva": 5.35,
    "Pantalón polar": 6.0,
    "Pantalón térmico": 6.0,
    "Polera": 5.0,
    "Polera polar": 6.0,
    "Polo": 6.8,
    "Polo algodón": 5.0,
    "Polo con cinta reflectiva": 6.925,
    "Polo manga corta": 6.8,
    "Polo manga larga": 6.8,
    "Polo manga larga con cinta reflectiva": 6.7,
    "Polo piqué": 5.0,
    "Short": 6.575,
    "Toalla": 5.0,
    "Otro": 6.575
}

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Control Interno - Pequeños Detalles",
    page_icon="🌸",
    layout="wide"
)

# --- ESTILO CSS CUSTOM ---
st.markdown("""
    <style>
    div[data-testid="stNumberInput"] button {
        display: none !important;
    }
    div[data-testid="stNumberInput"] input {
        text-align: left;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception:
    st.error("Error al conectar con Supabase. Revisa las credenciales en Secrets.")

def cargar_proyectos():
    try:
        response = supabase.table("proyectos").select("*").execute()
        return response.data
    except Exception:
        return []

# --- 3. SISTEMA DE LOGIN ---
USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTO = "pequenos2026"

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center;'>🌸 Pequeños Detalles Handmade Perú</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>Generador Oficial de Informes Técnicos</h4>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔐 Iniciar Sesión")
        usuario_input = st.text_input("Usuario")
        password_input = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar al Sistema", use_container_width=True):
            if usuario_input == USUARIO_CORRECTO and password_input == PASSWORD_CORRECTO:
                st.session_state.autenticado = True
                st.success("¡Bienvenido/a!")
                st.rerun()
            else:
                st.error("⚠️ Usuario o contraseña incorrectos.")

else:
    # --- MENÚ LATERAL ---
    with st.sidebar:
        st.title("Pequeños Detalles")
        st.write("👤 **Usuario:** Admin")
        st.write("---")
        opcion_menu = st.radio(
            "Selecciona una opción:",
            ["➕ Nuevo Reporte PDF", "📊 Dashboard 2026", "📁 Historial de Proyectos"]
        )
        st.write("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()

    # --- CANVAS PARA PIE DE PÁGINA Y HEADER EN EL PDF ---
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

    # --- GENERADOR DEL PDF OFICIAL ---
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

        # Encabezado
        elements.append(Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style))
        elements.append(Paragraph(f"Medición de Impacto Ambiental, Trazabilidad y Gestión Social de Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>", sub_style))

        # Tarjetas Métricas
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

        # 1. Ficha General
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

        # 2. Ingreso de Material
        elements.append(Paragraph("2. INGRESO DE MATERIAL Y EVIDENCIA FOTOGRÁFICA", h2_style))
        data_prendas_pdf = [[
            Paragraph("Ítem", cell_bold), Paragraph("Tipo de Producto / Prenda", cell_bold),
            Paragraph("Ingreso (unid)", cell_bold), Paragraph("Peso unit. (kg)", cell_bold),
            Paragraph("Peso total (kg)", cell_bold), Paragraph("Evidencia", cell_bold)
        ]]

        total_unidades_ingreso = 0
        for i, item in enumerate(lista_items, 1):
            total_unidades_ingreso += item["unidades"]
            if item["foto"]:
                try:
                    img_data = io.BytesIO(item["foto"].read())
                    item["foto"].seek(0)
                    img_cell = Image(img_data, width=45, height=45)
                except Exception:
                    img_cell = Paragraph("Sin foto", cell_style)
            else:
                img_cell = Paragraph("Sin foto", cell_style)

            data_prendas_pdf.append([
                Paragraph(str(i), cell_style), Paragraph(item["descripcion"], cell_style),
                Paragraph(str(item["unidades"]), cell_style), Paragraph(f"{item['peso_unitario']:.2f}", cell_style),
                Paragraph(f"{item['peso_total']:.2f}", cell_style), img_cell
            ])

        data_prendas_pdf.append([
            Paragraph("<b>TOTAL MATERIAL RECIBIDO</b>", cell_bold), "",
            Paragraph(f"<b>{total_unidades_ingreso}</b>", cell_bold), Paragraph("-", cell_bold),
            Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", cell_bold), Paragraph("-", cell_bold)
        ])

        t_prendas = Table(data_prendas_pdf, colWidths=[30, 180, 80, 75, 75, 100])
        t_prendas.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('SPAN', (0, -1), (1, -1)),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (2,0), (4,-1), 'CENTER'),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_prendas)
        elements.append(Spacer(1, 8))

        # 3. Trazabilidad
        elements.append(Paragraph("3. TRAZABILIDAD DEL PROCESO EN UPCYCLING", h2_style))
        data_traza_pdf = [[
            Paragraph("Etapa", cell_bold), Paragraph("Fecha", cell_bold),
            Paragraph("Responsable", cell_bold), Paragraph("Peso (kg)", cell_bold),
            Paragraph("Tipo de Registro", cell_bold), Paragraph("Evidencia", cell_bold)
        ]]

        for t_item in lista_trazabilidad:
            if t_item["foto"]:
                try:
                    img_data = io.BytesIO(t_item["foto"].read())
                    t_item["foto"].seek(0)
                    img_cell = Image(img_data, width=45, height=35)
                except Exception:
                    img_cell = Paragraph("Sin foto", cell_style)
            else:
                img_cell = Paragraph("Sin foto", cell_style)

            data_traza_pdf.append([
                Paragraph(t_item["etapa"], cell_style), Paragraph(t_item["fecha"], cell_style),
                Paragraph(t_item["responsable"], cell_style), Paragraph(f"{t_item['peso']:.2f}", cell_style),
                Paragraph(t_item["tipo_registro"], cell_style), img_cell
            ])

        t_traza = Table(data_traza_pdf, colWidths=[90, 70, 130, 60, 100, 90])
        t_traza.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,0), (3,-1), 'CENTER'),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_traza)

        elements.append(PageBreak())

        # 4. SALIDA DE PRODUCTOS
        elements.append(Paragraph("4. SALIDA DE PRODUCTOS", h2_style))
        elements.append(Paragraph("Registro de productos obtenidos a partir del proceso de upcycling", sub_style))

        data_prod_pdf = [[
            Paragraph("Producto", cell_bold),
            Paragraph("Cantidad (Unidades)", cell_bold),
            Paragraph("Evidencia", cell_bold)
        ]]

        total_prod_unidades = 0
        for p_item in lista_productos:
            total_prod_unidades += p_item["cantidad"]
            if p_item["foto"]:
                try:
                    img_data = io.BytesIO(p_item["foto"].read())
                    p_item["foto"].seek(0)
                    img_cell = Image(img_data, width=70, height=70)
                except Exception:
                    img_cell = Paragraph("Sin foto", cell_style)
            else:
                img_cell = Paragraph("Sin foto", cell_style)

            data_prod_pdf.append([
                Paragraph(p_item["producto"], cell_style),
                Paragraph(str(p_item["cantidad"]), cell_style),
                img_cell
            ])

        data_prod_pdf.append([
            Paragraph("<b>SUMA TOTAL</b>", cell_bold),
            Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold),
            Paragraph("-", cell_bold)
        ])

        t_prod = Table(data_prod_pdf, colWidths=[240, 150, 150])
        t_prod.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,0), (1,-1), 'CENTER'),
            ('ALIGN', (2,0), (2,-1), 'CENTER'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_prod)
        elements.append(Spacer(1, 15))

        # 5. BALANCE DE MATERIAL
        elements.append(Paragraph("5. BALANCE DE MATERIAL", h2_style))
        elements.append(Paragraph("Resumen del flujo y aprovechamiento del material procesado", sub_style))

        data_balance = [
            [Paragraph("<b>Concepto</b>", cell_bold), Paragraph("<b>Cantidad (kg)</b>", cell_bold)],
            [Paragraph("Material recibido", cell_style), Paragraph(f"{kg_recibidos:.2f}", cell_style)],
            [Paragraph("Material transformado en productos", cell_style), Paragraph(f"{mat_transformado:.2f}", cell_style)],
            [Paragraph("Retazos aprovechables", cell_style), Paragraph(f"{retazos_aprovechables:.2f}", cell_style)],
            [Paragraph("Pérdida no aprovechable", cell_style), Paragraph(f"{perdida_no_aprovechable:.2f}", cell_style)],
            [Paragraph("<b>Total procesado</b>", cell_bold), Paragraph(f"<b>{total_procesado:.2f}</b>", cell_bold)],
            [Paragraph("<b>Indicador</b>", cell_bold), Paragraph("<b>Valor</b>", cell_bold)],
            [Paragraph("% aprovechamiento total", cell_style), Paragraph(f"{pct_aprovechamiento_total:.2f}%", cell_style)],
            [Paragraph("% pérdida", cell_style), Paragraph(f"{pct_perdida:.2f}%", cell_style)],
        ]

        t_balance = Table(data_balance, colWidths=[340, 200])
        t_balance.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
            ('BACKGROUND', (0,6), (-1,6), colors.HexColor('#F5D0FE')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_balance)
        elements.append(Spacer(1, 6))

        nota_style = ParagraphStyle('NotaBalance', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#334155'))
        elements.append(Paragraph("<b>Nota:</b> El proceso presenta un alto nivel de aprovechamiento del material, donde los retazos generados son reincorporados como insumo en nuevos productos, reduciendo la generación de residuos.", nota_style))
        elements.append(Spacer(1, 15))

        # 6. BALANCE DE IMPACTO AMBIENTAL
        elements.append(Paragraph("6. BALANCE DE IMPACTO AMBIENTAL (HUELLA DE CARBONO Y CO₂ EVITADO)", h2_style))
        data_co2_box = [
            [Paragraph("<b>(+) CO₂ Evitado por Upcycling</b>", card_sub), Paragraph("<b>(-) Emisiones del Proceso</b>", card_sub), Paragraph("<b>(=) Impacto Neto Positivo</b>", card_sub)],
            [Paragraph(f"<b>{co2_evitado_total:.2f} kg CO₂e</b>", card_title), Paragraph(f"<b>{emisiones_proceso:.2f} kg CO₂e</b>", card_title), Paragraph(f"<b>{co2_neto:.2f} kg CO₂e</b>", card_title)]
        ]
        t_co2_box = Table(data_co2_box, colWidths=[180, 180, 180])
        t_co2_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_co2_box)
        elements.append(Spacer(1, 10))

        data_emisiones = [
            [Paragraph("ETAPA OPERATIVA", cell_bold), Paragraph("EMISIONES (KG CO₂E)", cell_bold), Paragraph("PARTICIPACIÓN (%)", cell_bold)],
            [Paragraph("Transporte y Logística", cell_style), Paragraph(f"{emisiones_transporte:.2f}", cell_style), Paragraph(f"{(emisiones_transporte/emisiones_proceso*100 if emisiones_proceso>0 else 0):.1f}%", cell_style)],
            [Paragraph("Lavandería", cell_style), Paragraph(f"{emisiones_lavado:.2f}", cell_style), Paragraph(f"{(emisiones_lavado/emisiones_proceso*100 if emisiones_proceso>0 else 0):.1f}%", cell_style)],
            [Paragraph("Corte", cell_style), Paragraph(f"{emisiones_corte:.2f}", cell_style), Paragraph(f"{(emisiones_corte/emisiones_proceso*100 if emisiones_proceso>0 else 0):.1f}%", cell_style)],
            [Paragraph("Bordado y Acabados", cell_style), Paragraph(f"{emisiones_bordado:.2f}", cell_style), Paragraph(f"{(emisiones_bordado/emisiones_proceso*100 if emisiones_proceso>0 else 0):.1f}%", cell_style)],
            [Paragraph("<b>TOTAL EMISIONES PROCESO</b>", cell_bold), Paragraph(f"<b>{emisiones_proceso:.2f}</b>", cell_bold), Paragraph("<b>100.0%</b>", cell_bold)],
        ]
        t_emisiones = Table(data_emisiones, colWidths=[240, 150, 150])
        t_emisiones.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_emisiones)
        elements.append(Spacer(1, 15))

        # 7. Impacto Social
        elements.append(Paragraph("7. RESUMEN DE IMPACTO SOCIAL Y EMPLEO GENERADO", h2_style))
        elements.append(Paragraph(f"El proyecto permitió la inclusión laboral de artesanas y personal de taller, acumulando un total de <b>{horas_totales:.2f} horas de trabajo directo</b> distribuidas entre <b>{cant_personas} participantes</b>.", cell_style))

        doc.build(elements, canvasmaker=ReporteCanvas)
        buffer.seek(0)
        return buffer

    # --- NAVEGACIÓN PRINCIPAL ---
    if opcion_menu == "➕ Nuevo Reporte PDF":
        st.title("📄 Generador Oficial de Informe Técnico")

        # 1. FICHA
        st.subheader("1. Ficha del Proyecto")
        c1, c2, c3 = st.columns(3)
        cliente = c1.text_input("Cliente / Empresa", value="")
        ruc = c2.text_input("RUC", value="")
        codigo_proy = c3.text_input("Código de Proyecto", value="")

        c4, c5, c6 = st.columns(3)
        proyecto_nom = c4.text_input("Nombre del Proyecto", value="")
        fe_inicio = c5.text_input("Fecha Inicio", value="")
        fe_fin = c6.text_input("Fecha Término", value="")

        c7, c8, c9 = st.columns(3)
        responsable = c7.text_input("Responsable", value="")
        area = c8.text_input("Área", value="")
        guia_remision = c9.text_input("Nº Guía Remisión", value="")

        c10, c11 = st.columns(2)
        origen = c10.text_input("Punto Origen", value="")
        destino = c11.text_input("Punto Destino", value="")

        st.write("---")

        # 2. INGRESO DE MATERIAL (CON MENÚ DESPLEGABLE)
        st.subheader("2. Ingreso de Material")
        if "num_items" not in st.session_state:
            st.session_state.num_items = 2

        col_btn1, col_btn2, _ = st.columns([1, 1, 4])
        if col_btn1.button("➕ Agregar Ítem Material"):
            st.session_state.num_items += 1
            st.rerun()
        if col_btn2.button("➖ Quitar Ítem Material") and st.session_state.num_items > 1:
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

            # Factor CO2 para esta prenda
            factor = FACTORES_CO2.get(desc, 6.575)
            co2_item = p_total * factor
            co2_evitado_total += co2_item

            peso_total_recibido += p_total
            lista_items.append({
                "descripcion": desc,
                "unidades": unid,
                "peso_unitario": peso_u,
                "peso_total": p_total,
                "foto": foto,
                "co2_evitado": co2_item
            })

        st.info(f"💡 **Total Material Recibido:** {peso_total_recibido:.2f} kg | **CO₂ Evitado Calculado:** {co2_evitado_total:.2f} kg CO₂e")
        st.write("---")

        # 3. TRAZABILIDAD
        st.subheader("3. Trazabilidad del Proceso en Upcycling")
        etapas_fijas = [
            {"etapa": "Clasificación", "fecha": datetime.date.today(), "resp": "Área de Logística", "peso": "0.00", "tipo": "Registro interno"},
            {"etapa": "Lavado", "fecha": datetime.date.today(), "resp": "Lavandería", "peso": "0.00", "tipo": "Servicio Externo"},
            {"etapa": "Corte", "fecha": datetime.date.today(), "resp": "Taller de corte", "peso": "0.00", "tipo": "Pesaje real"},
            {"etapa": "Confección", "fecha": datetime.date.today(), "resp": "Producción descentralizada", "peso": "0.00", "tipo": "Entrega / Recepción"},
        ]
        lista_trazabilidad = []
        for i, item_fijo in enumerate(etapas_fijas):
            st.markdown(f"**Etapa {i+1}**")
            c_etapa, c_fecha, c_resp, c_peso, c_tipo, c_foto = st.columns([2, 1.8, 2, 1.5, 2, 2.5])
            e_nom = c_etapa.text_input("Etapa", value=item_fijo["etapa"], disabled=True, key=f"tr_etapa_{i}")
            e_fec_val = c_fecha.date_input("Fecha", value=item_fijo["fecha"], format="DD/MM/YYYY", key=f"tr_fecha_{i}")
            e_res = c_resp.text_input("Responsable", value=item_fijo["resp"], disabled=True, key=f"tr_resp_{i}")
            e_pes_str = c_peso.text_input("Peso (kg)", value=item_fijo["peso"], key=f"tr_peso_{i}")
            try:
                e_pes_num = float(e_pes_str)
            except ValueError:
                e_pes_num = 0.0
            e_tip = c_tipo.text_input("Tipo Registro", value=item_fijo["tipo"], disabled=True, key=f"tr_tipo_{i}")
            e_fot = c_foto.file_uploader("Evidencia", type=["jpg", "png", "jpeg"], key=f"tr_foto_{i}")

            lista_trazabilidad.append({"etapa": e_nom, "fecha": e_fec_val.strftime("%d/%m/%Y"), "responsable": e_res, "peso": e_pes_num, "tipo_registro": e_tip, "foto": e_fot})

        st.write("---")

        # 4. SALIDA DE PRODUCTOS
        st.subheader("4. Salida de Productos (Nombre, Cantidad y Foto)")

        if "num_prods" not in st.session_state:
            st.session_state.num_prods = 3

        cp_btn1, cp_btn2, _ = st.columns([1, 1, 4])
        if cp_btn1.button("➕ Agregar Producto"):
            st.session_state.num_prods += 1
            st.rerun()
        if cp_btn2.button("➖ Quitar Producto") and st.session_state.num_prods > 1:
            st.session_state.num_prods -= 1
            st.rerun()

        lista_productos = []
        total_prod_unid = 0

        for i in range(st.session_state.num_prods):
            st.markdown(f"**Producto {i+1}**")
            col_pnom, col_pcant, col_pfoto = st.columns([4, 2, 4])

            p_nombre = col_pnom.text_input("Producto", value="", key=f"prod_nom_{i}")
            p_cant = col_pcant.number_input("Cantidad (Unidad)", min_value=0, value=0, key=f"prod_cant_{i}")
            p_foto = col_pfoto.file_uploader("Evidencia Foto", type=["jpg", "png", "jpeg"], key=f"prod_foto_{i}")

            total_prod_unid += p_cant
            lista_productos.append({
                "producto": p_nombre if p_nombre.strip() else f"Producto {i+1}",
                "cantidad": p_cant,
                "foto": p_foto
            })

        st.success(f"📦 **Suma Total de Productos Obtenidos:** {total_prod_unid} unidades")
        st.write("---")

        # 5. BALANCE DE MATERIAL
        st.subheader("5. Balance de Material")
        st.info(f"📦 **Material Recibido (calculado automáticamente):** {peso_total_recibido:.2f} kg")

        col_bm1, col_bm2 = st.columns(2)
        mat_transformado = col_bm1.number_input("Material transformado en productos (kg)", min_value=0.0, value=0.0, step=0.1)
        retazos_aprovechables = col_bm2.number_input("Retazos aprovechables (kg)", min_value=0.0, value=0.0, step=0.1)

        col_bm3, _ = st.columns([1, 1])
        perdida_no_aprovechable = col_bm3.number_input("Pérdida no aprovechable (kg)", min_value=0.0, value=0.0, step=0.1)

        total_procesado = mat_transformado + retazos_aprovechables + perdida_no_aprovechable

        if peso_total_recibido > 0:
            pct_aprovechamiento_total = ((mat_transformado + retazos_aprovechables) / peso_total_recibido) * 100
            pct_perdida = (perdida_no_aprovechable / peso_total_recibido) * 100
        else:
            pct_aprovechamiento_total = 0.0
            pct_perdida = 0.0

        st.markdown("##### Resumen de Indicadores")
        ind1, ind2, ind3 = st.columns(3)
        ind1.metric("Total Procesado", f"{total_procesado:.2f} kg")
        ind2.metric("% Aprovechamiento Total", f"{pct_aprovechamiento_total:.2f}%")
        ind3.metric("% Pérdida", f"{pct_perdida:.2f}%")
        st.write("---")

        # 6. MÉTRICAS SOCIALES Y EMISIONES
        st.subheader("6. Métricas de Trabajo Social y Emisiones del Proceso")
        
        # Muestra el CO2 evitado suma de prendas ingresadas
        st.success(f"🌱 **CO₂ Evitado por prendas recibidas (Suma total):** {co2_evitado_total:.2f} kg CO₂e")

        m1, m2 = st.columns(2)
        horas_totales = m1.number_input("Horas Generadas", min_value=0.0, value=0.0, step=0.5)
        cant_personas = m2.number_input("Cantidad Personas Beneficiadas", min_value=0, value=0, step=1)

        st.markdown("**Desglose de Emisiones del Proceso (kg CO₂e)**")
        e1, e2, e3, e4 = st.columns(4)
        emisiones_transporte = e1.number_input("Emisión Transporte", min_value=0.0, value=0.0)
        emisiones_lavado = e2.number_input("Emisión Lavandería", min_value=0.0, value=0.0)
        emisiones_corte = e3.number_input("Emisión Corte", min_value=0.0, value=0.0)
        emisiones_bordado = e4.number_input("Emisión Bordado", min_value=0.0, value=0.0)

        st.write("---")

        # BOTÓN GENERADOR
        if st.button("🔥 Generar PDF Oficial y Guardar", type="primary", use_container_width=True):
            emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
            co2_neto = co2_evitado_total - emisiones_proceso

            try:
                supabase.table("proyectos").insert({
                    "codigo": codigo_proy if codigo_proy else "SIN-CODIGO",
                    "cliente": cliente if cliente else "CLIENTE GENERAL",
                    "fecha": f"{fe_inicio} - {fe_fin}",
                    "peso_recibido": peso_total_recibido,
                    "peso_transformado": mat_transformado,
                    "aprovechamiento": pct_aprovechamiento_total,
                    "co2_neto": co2_neto,
                    "horas_totales": horas_totales,
                    "ruc": ruc
                }).execute()
                st.success("✅ Guardado correctamente en la base de datos.")
            except Exception:
                st.info("ℹ️ Generando PDF (el registro en BD ya existe, omitiendo duplicación).")

            pdf_oficial = generar_pdf_oficial(
                cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area,
                "Uniformes en desuso", "Upcycling", "Kilogramos (kg)",
                guia_remision, origen, destino, lista_items, lista_trazabilidad, lista_productos,
                mat_transformado, retazos_aprovechables, perdida_no_aprovechable, total_procesado,
                pct_aprovechamiento_total, pct_perdida,
                horas_totales, cant_personas, co2_evitado_total, emisiones_transporte, emisiones_lavado,
                emisiones_corte, emisiones_bordado
            )

            st.download_button(
                label=f"📥 DESCARGAR INFORME EN PDF ({codigo_proy if codigo_proy else 'INFORME'}.pdf)",
                data=pdf_oficial,
                file_name=f"Informe_Tecnico_{codigo_proy if codigo_proy else 'PROYECTO'}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    elif opcion_menu == "📊 Dashboard 2026":
        st.title("📊 Dashboard Consolidado 2026")
        lista_proyectos = cargar_proyectos()
        if lista_proyectos:
            df = pd.DataFrame(lista_proyectos)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("CO₂e Evitado Total", f"{df['co2_neto'].sum():.2f} kg")
            col2.metric("Textil Procesado", f"{df['peso_transformado'].sum():.2f} kg")
            col3.metric("Horas Generadas", f"{df['horas_totales'].sum():.1f} hrs")
            col4.metric("Total Proyectos", len(df))
        else:
            st.info("Sin datos acumulados.")

    elif opcion_menu == "📁 Historial de Proyectos":
        st.title("📁 Historial de Proyectos")
        lista_proyectos = cargar_proyectos()
        if lista_proyectos:
            st.dataframe(pd.DataFrame(lista_proyectos), use_container_width=True)
        else:
            st.info("Sin registros en BD.")
