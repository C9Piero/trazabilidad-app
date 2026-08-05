import io
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA (¡SIEMPRE DEBE SER LA PRIMERA LÍNEA DE STREAMLIT!)
# ==============================================================================
st.set_page_config(page_title="Generador de Informes", layout="wide")


# ==============================================================================
# 2. CLASE CANVAS PARA PIE DE PÁGINA Y NUMERACIÓN
# ==============================================================================
class ReporteCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(612 - 36, 20, page_text)
        self.drawString(36, 20, "Informe Técnico de Valorización Textil — Confidencial")
        
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 32, 612 - 36, 32)
        
        self.restoreState()


# ==============================================================================
# 3. FUNCIÓN GENERADORA DEL PDF (EN MEMORIA)
# ==============================================================================
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
    
    # Reducimos márgenes superior e inferior para evitar saltos de página fantasma
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        leftMargin=36, 
        rightMargin=36, 
        topMargin=25, 
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14, textColor=colors.HexColor('#1E293B'), alignment=1, spaceAfter=2)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#64748B'), alignment=1, spaceAfter=10)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=4)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#334155'), leading=10)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#0F172A'), leading=10)
    card_title = ParagraphStyle('CardT', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0F172A'), alignment=1)
    card_sub = ParagraphStyle('CardS', parent=styles['Normal'], fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#475569'), alignment=1)

    elements = []

    # ENCABEZADO
    elements.append(Paragraph("INFORME TÉCNICO DE VALORIZACIÓN TEXTIL", h1_style))
    elements.append(Paragraph(f"Medición de Impacto Ambiental, Trazabilidad y Gestión Social de Upcycling<br/><b>CÓDIGO: {codigo_proy}</b>", sub_style))

    # METRICAS
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
            Paragraph("CO<sub>2</sub>e NETO EVITADO", card_sub),
            Paragraph(f"TRABAJO GENERADO ({cant_personas} PERS.)", card_sub)
        ]
    ]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 6))

    # 1. FICHA GENERAL
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
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(t_ficha)
    elements.append(Spacer(1, 6))

    # 2. INGRESO DE MATERIAL
    elements.append(Paragraph("2. INGRESO DE MATERIAL Y EVIDENCIA FOTOGRÁFICA", h2_style))
    data_prendas_pdf = [[
        Paragraph("Ítem", cell_bold), Paragraph("Tipo de Producto / Prenda", cell_bold),
        Paragraph("Ingreso (unid)", cell_bold), Paragraph("Peso unit. (kg)", cell_bold),
        Paragraph("Peso total (kg)", cell_bold), Paragraph("Evidencia", cell_bold)
    ]]

    total_unidades_ingreso = 0
    for i, item in enumerate(lista_items, 1):
        total_unidades_ingreso += item["unidades"]
        data_prendas_pdf.append([
            Paragraph(str(i), cell_style), Paragraph(item["descripcion"], cell_style),
            Paragraph(str(item["unidades"]), cell_style), Paragraph(f"{item['peso_unitario']:.2f}", cell_style),
            Paragraph(f"{item['peso_total']:.2f}", cell_style), Paragraph("Sin foto", cell_style)
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
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(t_prendas)
    elements.append(Spacer(1, 6))

    # 3. TRAZABILIDAD
    elements.append(Paragraph("3. TRAZABILIDAD DEL PROCESO EN UPCYCLING", h2_style))
    data_traza_pdf = [[
        Paragraph("Etapa", cell_bold), Paragraph("Fecha", cell_bold),
        Paragraph("Responsable", cell_bold), Paragraph("Peso (kg)", cell_bold),
        Paragraph("Tipo de Registro", cell_bold), Paragraph("Evidencia", cell_bold)
    ]]

    for t_item in lista_trazabilidad:
        data_traza_pdf.append([
            Paragraph(t_item["etapa"], cell_style), Paragraph(t_item["fecha"], cell_style),
            Paragraph(t_item["responsable"], cell_style), Paragraph(f"{t_item['peso']:.2f}", cell_style),
            Paragraph(t_item["tipo_registro"], cell_style), Paragraph("Sin foto", cell_style)
        ])

    t_traza = Table(data_traza_pdf, colWidths=[90, 70, 130, 60, 100, 90])
    t_traza.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (3,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(t_traza)
    elements.append(Spacer(1, 10))

    # 4. SALIDA DE PRODUCTOS
    elements.append(Paragraph("4. SALIDA DE PRODUCTOS", h2_style))
    data_prod_pdf = [[
        Paragraph("Producto", cell_bold), Paragraph("Cantidad (Unidades)", cell_bold), Paragraph("Evidencia", cell_bold)
    ]]

    total_prod_unidades = 0
    for p_item in lista_productos:
        total_prod_unidades += p_item["cantidad"]
        data_prod_pdf.append([
            Paragraph(p_item["producto"], cell_style), Paragraph(str(p_item["cantidad"]), cell_style), Paragraph("Sin foto", cell_style)
        ])

    data_prod_pdf.append([
        Paragraph("<b>SUMA TOTAL</b>", cell_bold), Paragraph(f"<b>{total_prod_unidades}</b>", cell_bold), Paragraph("-", cell_bold)
    ])

    t_prod = Table(data_prod_pdf, colWidths=[240, 150, 150])
    t_prod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_prod)
    elements.append(Spacer(1, 10))

    # 5. BALANCE DE MATERIAL
    elements.append(Paragraph("5. BALANCE DE MATERIAL", h2_style))
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
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(t_balance)
    elements.append(Spacer(1, 10))

    # 6. IMPACTO AMBIENTAL
    elements.append(Paragraph("6. RESUMEN DE IMPACTO AMBIENTAL (CO<sub>2</sub>e)", h2_style))
    data_co2_box = [
        [
            Paragraph("<b>(+) CO<sub>2</sub> Evitado</b>", card_sub), 
            Paragraph("<b>(-) Emisiones Proceso</b>", card_sub), 
            Paragraph("<b>(=) Impacto Neto</b>", card_sub)
        ],
        [
            Paragraph(f"<b>{co2_evitado_total:.2f} kg CO<sub>2</sub>e</b>", card_title), 
            Paragraph(f"<b>{emisiones_proceso:.2f} kg CO<sub>2</sub>e</b>", card_title), 
            Paragraph(f"<b>{co2_neto:.2f} kg CO<sub>2</sub>e</b>", card_title)
        ]
    ]
    t_co2_box = Table(data_co2_box, colWidths=[180, 180, 180])
    t_co2_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_co2_box)
    elements.append(Spacer(1, 10))

    # 7. IMPACTO SOCIAL
    elements.append(Paragraph("7. RESUMEN DE IMPACTO SOCIAL", h2_style))
    elements.append(Paragraph(f"El proyecto acumuló un total de <b>{horas_totales:.2f} horas de trabajo directo</b> distribuidas entre <b>{cant_personas} participantes</b>.", cell_style))

    # CONSTRUCCIÓN DEL DOCUMENTO
    doc.build(elements, canvasmaker=ReporteCanvas)
    
    # REBOBINAR EL BUFFER
    buffer.seek(0)
    return buffer


# ==============================================================================
# 4. INTERFAZ DE USUARIO CON STREAMLIT
# ==============================================================================
st.title("📄 Generador de Informes de Valorización Textil")
st.write("Haz clic en el botón para generar y descargar tu archivo PDF de prueba.")

# Generación del archivo en memoria al hacer clic
if st.button("Generar PDF"):
    with st.spinner("Creando documento PDF..."):
        pdf_bytes = generar_pdf_oficial(
            cliente="Empresa Ejemplo S.A.C.",
            ruc="20123456789",
            proyecto_nom="Upcycling Uniformes 2024",
            codigo_proy="PROY-2024-001",
            fe_inicio="01/02/2024",
            fe_fin="15/02/2024",
            responsable="Juan Pérez",
            area="Sostenibilidad",
            tipo_material="Textil / Poliéster",
            valorizacion="Upcycling",
            unidad_medida="Kilogramos (kg)",
            guia_remision="GR-001-9876",
            origen="Almacén Central",
            destino="Taller Upcycling",
            lista_items=[
                {"descripcion": "Polos Usados Corporativos", "unidades": 100, "peso_unitario": 0.25, "peso_total": 25.0}
            ],
            lista_trazabilidad=[
                {"etapa": "Recepción y Selección", "fecha": "01/02/2024", "responsable": "Maria L.", "peso": 25.0, "tipo_registro": "Ingreso Almacén"}
            ],
            lista_productos=[
                {"producto": "Cartucheras Ecológicas", "cantidad": 80}
            ],
            mat_transformado=20.0,
            retazos_aprovechables=3.5,
            perdida_no_aprovechable=1.5,
            total_procesado=25.0,
            pct_aprovechamiento_total=94.0,
            pct_perdida=6.0,
            horas_totales=45.0,
            cant_personas=3,
            co2_evitado_total=120.0,
            emisiones_transporte=2.5,
            emisiones_lavado=1.2,
            emisiones_corte=0.5,
            emisiones_bordado=0.8
        )

        st.success("¡PDF generado con éxito!")
        
        # Botón para descargar el PDF generado en vivo
        st.download_button(
            label="⬇️ Descargar Informe PDF",
            data=pdf_bytes,
            file_name="Informe_Valorizacion_Textil.pdf",
            mime="application/pdf"
        )
