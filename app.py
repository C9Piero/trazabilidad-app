import io
import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Importaciones de ReportLab para réplica visual exacta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# --- CONFIGURACIÓN PÁGINA STREAMLIT ---
st.set_page_config(
    page_title="Control Interno - Pequeños Detalles",
    page_icon="🌸",
    layout="wide"
)

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception:
    st.error("Error de conexión con Supabase. Revisa las credenciales.")

# --- DIBUJADO DEL DISEÑO IDÉNTICO (HEADER + CARDS) ---
class ReporteCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_page_decorations()
            super().showPage()
        super().save()

    def draw_page_decorations(self):
        # Pie de página en todas las páginas
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#7F8C8D"))
        self.drawString(36, 20, "Pequeños Detalles Handmade Perú S.A.C. - Sistema de Trazabilidad y Sostenibilidad Textil")
        self.drawRightString(576, 20, f"Página {self._pageNumber}")
        self.restoreState()

# --- FUNCIÓN GENERADORA DEL PDF EXACTO ---
def generar_pdf_oficial(
    cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area,
    tipo_material, valorizacion, unidad_medida, guia_remision, origen, destino,
    kg_recibidos, kg_transformados, horas_totales, cant_personas, emisiones_transporte,
    emisiones_lavado, emisiones_corte, emisiones_bordado
):
    # Cálculos automáticos basados en la plantilla
    pct_aprovechamiento = (kg_transformados / kg_recibidos * 100) if kg_recibidos > 0 else 0
    co2_evitado = kg_transformados * 7.3392  # Factor derivado de plantilla (388.98 / 53)
    
    emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
    co2_neto = co2_evitado - emisiones_proceso

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Estilos exactos
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14, textColor=colors.HexColor('#1E293B'), alignment=1, spaceAfter=2)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#64748B'), alignment=1, spaceAfter=12)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0F172A'), spaceBefore=10, spaceAfter=6)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#334155'), leading=10)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#0F172A'), leading=10)
    
    # Estilo métricas
    card_title = ParagraphStyle('CardT', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#0F172A'), alignment=1)
    card_sub = ParagraphStyle('CardS', parent=styles['Normal'], fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#475569'), alignment=1)

    elements = []

    # 1. TÍTULO Y SUBTÍTULO
    elements.append(Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style))
    elements.append(Paragraph(f"Medición de Impacto Ambiental, Trazabilidad y Gestión Social de Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>", sub_style))

    # 2. CAJAS DE MÉTRICAS PRINCIPALES (TARJETAS EN CABECERA)
    cards_data = [
        [
            Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", card_title),
            Paragraph(f"<b>{pct_aprovechamiento:.2f}%</b>", card_title),
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
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 10))

    # 3. SECCIÓN 1: FICHA GENERAL DEL PROYECTO
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
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_ficha)
    elements.append(Spacer(1, 10))

    # 4. SECCIÓN 2: BALANCE DE MATERIALES Y EFICIENCIA
    elements.append(Paragraph("2. BALANCE DE MATERIALES Y APROVECHAMIENTO", h2_style))
    data_balance = [
        [Paragraph("CONCEPTO", cell_bold), Paragraph("PESO (KG)", cell_bold), Paragraph("PARTICIPACIÓN (%)", cell_bold)],
        [Paragraph("Material Recibido Total", cell_style), Paragraph(f"{kg_recibidos:.2f}", cell_style), Paragraph("100.00%", cell_style)],
        [Paragraph("Material Transformado en Productos", cell_style), Paragraph(f"{kg_transformados:.2f}", cell_style), Paragraph(f"{pct_aprovechamiento:.2f}%", cell_style)],
        [Paragraph("Pérdida / Residuo No Aprovechable", cell_style), Paragraph(f"{(kg_recibidos - kg_transformados):.2f}", cell_style), Paragraph(f"{(100 - pct_aprovechamiento):.2f}%", cell_style)],
    ]
    t_bal = Table(data_balance, colWidths=[240, 150, 150])
    t_bal.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_bal)
    
    note_text = f"<b>Nota de Eficiencia:</b> El proceso presenta un alto nivel de aprovechamiento ({pct_aprovechamiento:.2f}%). La reincorporación de sobrantes como insumo interno redujo sustancialmente la generación de residuo final."
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(note_text, cell_style))

    # SALTO A PÁGINA 2
    elements.append(PageBreak())

    # 5. SECCIÓN 3: IMPACTO AMBIENTAL (CO2)
    elements.append(Paragraph("3. BALANCE DE IMPACTO AMBIENTAL (HUELLA DE CARBONO Y CO₂ EVITADO)", h2_style))
    
    data_co2_box = [
        [Paragraph("<b>(+) CO₂ Evitado por Upcycling</b>", card_sub), Paragraph("<b>(-) Emisiones del Proceso</b>", card_sub), Paragraph("<b>(=) Impacto Neto Positivo</b>", card_sub)],
        [Paragraph(f"<b>{co2_evitado:.2f} kg CO₂e</b>", card_title), Paragraph(f"<b>{emisiones_proceso:.2f} kg CO₂e</b>", card_title), Paragraph(f"<b>{co2_neto:.2f} kg CO₂e</b>", card_title)]
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

    elements.append(Paragraph("Desglose de Emisiones Generadas durante la Operación:", cell_bold))
    data_emisiones = [
        [Paragraph("ETAPA OPERATIVA", cell_bold), Paragraph("EMISIONES (KG CO₂E)", cell_bold), Paragraph("PARTICIPACIÓN (%)", cell_bold)],
        [Paragraph("Transporte y Logística", cell_style), Paragraph(f"{emisiones_transporte:.2f}", cell_style), Paragraph(f"{(emisiones_transporte/emisiones_proceso*100):.1f}%", cell_style)],
        [Paragraph("Lavandería", cell_style), Paragraph(f"{emisiones_lavado:.2f}", cell_style), Paragraph(f"{(emisiones_lavado/emisiones_proceso*100):.1f}%", cell_style)],
        [Paragraph("Corte", cell_style), Paragraph(f"{emisiones_corte:.2f}", cell_style), Paragraph(f"{(emisiones_corte/emisiones_proceso*100):.1f}%", cell_style)],
        [Paragraph("Bordado y Acabados", cell_style), Paragraph(f"{emisiones_bordado:.2f}", cell_style), Paragraph(f"{(emisiones_bordado/emisiones_proceso*100):.1f}%", cell_style)],
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

    # 6. SECCIÓN 4: IMPACTO SOCIAL Y TRABAJO GENERADO
    elements.append(Paragraph("4. RESUMEN DE IMPACTO SOCIAL Y EMPLEO GENERADO", h2_style))
    social_txt = f"El proyecto permitió la inclusión laboral de artesanas y personal de taller, acumulando un total de <b>{horas_totales:.2f} horas de trabajo directo</b> distribuidas entre <b>{cant_personas} participantes</b> en las etapas de clasificación, corte, confección y acabados."
    elements.append(Paragraph(social_txt, cell_style))

    # CONSTRUCCIÓN DEL DOCUMENTO
    doc.build(elements, canvasmaker=ReporteCanvas)
    buffer.seek(0)
    return buffer


# --- INTERFAZ DE USUARIO STREAMLIT ---
st.title("📄 Generador Oficial de PDF de Impacto")
st.markdown("Completa los **datos clave** del proyecto para emitir automáticamente el **Informe Técnico Oficial de 2 Páginas**.")

with st.form("form_datos_clave"):
    st.subheader("1. Ficha del Proyecto")
    c1, c2, c3 = st.columns(3)
    cliente = c1.text_input("Cliente / Empresa", value="REAL PLAZA S.R.L.")
    ruc = c2.text_input("RUC", value="20511315922")
    codigo_proy = c3.text_input("Código de Proyecto", value="REAL PLAZA-JUL26")

    c4, c5, c6 = st.columns(3)
    proyecto_nom = c4.text_input("Nombre del Proyecto", value="Upcycling de uniformes corporativos")
    fe_inicio = c5.text_input("Fecha Inicio", value="27/05/2026")
    fe_fin = c6.text_input("Fecha Término", value="09/07/2026")

    c7, c8, c9 = st.columns(3)
    responsable = c7.text_input("Responsable", value="Pequeños Detalles S.A.C.")
    area = c8.text_input("Área", value="Sostenibilidad")
    guia_remision = c9.text_input("Nº Guía Remisión", value="001-0012568")

    c10, c11 = st.columns(2)
    origen = c10.text_input("Punto Origen", value="Av. Eduardo Avaroa 2403 - Jesús María")
    destino = c11.text_input("Punto Destino", value="Las Flores, SJL - Lima")

    st.write("---")
    st.subheader("2. Métricas de Peso e Impacto Social")
    m1, m2, m3, m4 = st.columns(4)
    kg_recibidos = m1.number_input("Kg Recibidos", value=59.25)
    kg_transformados = m2.number_input("Kg Transformados", value=53.00)
    horas_totales = m3.number_input("Horas Generadas", value=337.73)
    cant_personas = m4.number_input("Cantidad Personas", value=17, step=1)

    st.write("---")
    st.subheader("3. Desglose de Emisiones del Proceso (kg CO₂e)")
    e1, e2, e3, e4 = st.columns(4)
    emisiones_transporte = e1.number_input("Emisión Transporte", value=9.45)
    emisiones_lavado = e2.number_input("Emisión Lavandería", value=3.90)
    emisiones_corte = e3.number_input("Emisión Corte", value=2.96)
    emisiones_bordado = e4.number_input("Emisión Bordado", value=8.18)

    btn_generar_pdf = st.form_submit_button("🔥 Generar PDF Oficial", type="primary", use_container_width=True)

if btn_generar_pdf:
    pdf_oficial = generar_pdf_oficial(
        cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area,
        "Uniformes en desuso (operativos y administrativos)", "Upcycling", "Kilogramos (kg)",
        guia_remision, origen, destino, kg_recibidos, kg_transformados, horas_totales,
        cant_personas, emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado
    )

    # Guardar también en base de datos Supabase
    try:
        pct_aprovechamiento = (kg_transformados / kg_recibidos * 100) if kg_recibidos > 0 else 0
        co2_evitado = kg_transformados * 7.3392
        emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
        co2_neto = co2_evitado - emisiones_proceso

        supabase.table("proyectos").upsert({
            "codigo": codigo_proy,
            "cliente": cliente,
            "fecha": f"{fe_inicio} - {fe_fin}",
            "peso_recibido": kg_recibidos,
            "peso_transformado": kg_transformados,
            "aprovechamiento": pct_aprovechamiento,
            "co2_neto": co2_neto,
            "horas_totales": horas_totales,
            "ruc": ruc
        }).execute()
        st.success("✅ Datos guardados correctamente en Supabase.")
    except Exception as e:
        st.warning(f"No se pudo guardar en Supabase: {e}")

    st.download_button(
        label=f"📥 DESCARGAR PDF OFICIAL ({codigo_proy}.pdf)",
        data=pdf_oficial,
        file_name=f"Informe_Tecnico_Upcycling_{codigo_proy}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
