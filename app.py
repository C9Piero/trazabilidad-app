import io
import datetime
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from PIL import Image as PILImage

# Importaciones para ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Control Interno - Pequeños Detalles",
    page_icon="🌸",
    layout="wide"
)

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
        usuario_input = st.text_input("Usuario", placeholder="Ingresa tu usuario")
        password_input = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
        
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
        lista_items, kg_transformados, horas_totales, cant_personas,
        emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado
    ):
        kg_recibidos = sum([item["peso_total"] for item in lista_items])
        pct_aprovechamiento = (kg_transformados / kg_recibidos * 100) if kg_recibidos > 0 else 0
        co2_evitado = kg_transformados * 7.3392
        emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
        co2_neto = co2_evitado - emisiones_proceso

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
        ]))
        elements.append(t_cards)
        elements.append(Spacer(1, 8))

        # Sección 1: Ficha General
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

        # Sección 2: Tabla de Material con Foto por Fila
        elements.append(Paragraph("2. INGRESO DE MATERIAL Y EVIDENCIA FOTOGRÁFICA", h2_style))
        
        data_prendas_pdf = [[
            Paragraph("Ítem", cell_bold),
            Paragraph("Descripción", cell_bold),
            Paragraph("Ingreso (unidades)", cell_bold),
            Paragraph("Peso unitario (kg)", cell_bold),
            Paragraph("Peso total (kg)", cell_bold),
            Paragraph("Evidencia", cell_bold)
        ]]

        total_unidades = 0
        for i, item in enumerate(lista_items, 1):
            total_unidades += item["unidades"]
            
            if item["foto"]:
                try:
                    img_data = io.BytesIO(item["foto"].read())
                    item["foto"].seek(0)
                    img_cell = Image(img_data, width=55, height=55)
                except Exception:
                    img_cell = Paragraph("Sin foto", cell_style)
            else:
                img_cell = Paragraph("Sin foto", cell_style)

            data_prendas_pdf.append([
                Paragraph(str(i), cell_style),
                Paragraph(item["descripcion"], cell_style),
                Paragraph(str(item["unidades"]), cell_style),
                Paragraph(f"{item['peso_unitario']:.2f}", cell_style),
                Paragraph(f"{item['peso_total']:.2f}", cell_style),
                img_cell
            ])

        data_prendas_pdf.append([
            Paragraph("<b>TOTAL</b>", cell_bold),
            Paragraph("-", cell_bold),
            Paragraph(f"<b>{total_unidades}</b>", cell_bold),
            Paragraph("-", cell_bold),
            Paragraph(f"<b>{kg_recibidos:.2f} kg</b>", cell_bold),
            Paragraph("-", cell_bold)
        ])

        t_prendas = Table(data_prendas_pdf, colWidths=[35, 175, 80, 75, 75, 100])
        t_prendas.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (2,0), (4,-1), 'CENTER'),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_prendas)

        elements.append(PageBreak())

        # Sección 3: Impacto Ambiental
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

        # Sección 4: Impacto Social
        elements.append(Paragraph("4. RESUMEN DE IMPACTO SOCIAL Y EMPLEO GENERADO", h2_style))
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

        # 2. INGRESO DE MATERIAL Y EVIDENCIA
        st.subheader("2. Ingreso de Material (Ítem, Descripción, Unidades, Peso y Evidencia)")

        if "num_items" not in st.session_state:
            st.session_state.num_items = 2

        col_btn1, col_btn2, _ = st.columns([1, 1, 4])
        if col_btn1.button("➕ Agregar Ítem"):
            st.session_state.num_items += 1
            st.rerun()
        if col_btn2.button("➖ Quitar Ítem") and st.session_state.num_items > 1:
            st.session_state.num_items -= 1
            st.rerun()

        defaults = [
            {"desc": "JEAN CINTA SEGURIDAD", "unid": 11, "peso": 0.70},
            {"desc": "CHALECO ACOLCHADO", "unid": 17, "peso": 0.30},
            {"desc": "CASACA TÉRMICA", "unid": 15, "peso": 0.50},
        ]

        lista_items = []
        peso_total_recibido = 0.0

        for i in range(st.session_state.num_items):
            st.markdown(f"**Ítem {i+1}**")
            col_desc, col_unid, col_peso, col_tot, col_foto = st.columns([3, 1.5, 1.5, 1.5, 3])
            
            def_desc = defaults[i]["desc"] if i < len(defaults) else f"Prenda {i+1}"
            def_unid = defaults[i]["unid"] if i < len(defaults) else 10
            def_peso = defaults[i]["peso"] if i < len(defaults) else 0.40

            desc = col_desc.text_input(f"Descripción", value=def_desc, key=f"desc_{i}")
            unid = col_unid.number_input(f"Ingreso (unid.)", value=def_unid, min_value=1, key=f"unid_{i}")
            peso_u = col_peso.number_input(f"Peso Unit. (kg)", value=def_peso, step=0.05, key=f"peso_{i}")
            
            p_total = unid * peso_u
            col_tot.text_input(f"Peso Total", value=f"{p_total:.2f} kg", disabled=True, key=f"tot_{i}")
            
            foto = col_foto.file_uploader(f"Evidencia (Foto)", type=["jpg", "png", "jpeg"], key=f"foto_{i}")

            peso_total_recibido += p_total
            lista_items.append({
                "descripcion": desc,
                "unidades": unid,
                "peso_unitario": peso_u,
                "peso_total": p_total,
                "foto": foto
            })

        st.info(f"💡 **Total Material Recibido:** {peso_total_recibido:.2f} kg")

        st.write("---")

        # 3. MÉTRICAS DE PROCESO
        st.subheader("3. Métricas de Transformación y Trabajo Social")
        m1, m2, m3 = st.columns(3)
        kg_transformados = m1.number_input("Kg Transformados en Productos", value=min(53.00, float(peso_total_recibido)))
        horas_totales = m2.number_input("Horas Generadas", value=337.73)
        cant_personas = m3.number_input("Cantidad Personas Beneficiadas", value=17, step=1)

        st.write("---")

        # 4. EMISIONES
        st.subheader("4. Desglose de Emisiones del Proceso (kg CO₂e)")
        e1, e2, e3, e4 = st.columns(4)
        emisiones_transporte = e1.number_input("Emisión Transporte", value=9.45)
        emisiones_lavado = e2.number_input("Emisión Lavandería", value=3.90)
        emisiones_corte = e3.number_input("Emisión Corte", value=2.96)
        emisiones_bordado = e4.number_input("Emisión Bordado", value=8.18)

        st.write("---")

        # BOTÓN GENERADOR CON MANEJO LIMPIO DE DUPLICADOS EN BD
        if st.button("🔥 Generar PDF Oficial y Guardar", type="primary", use_container_width=True):
            pct_aprovechamiento = (kg_transformados / peso_total_recibido * 100) if peso_total_recibido > 0 else 0
            co2_evitado = kg_transformados * 7.3392
            emisiones_proceso = emisiones_transporte + emisiones_lavado + emisiones_corte + emisiones_bordado
            co2_neto = co2_evitado - emisiones_proceso

            try:
                supabase.table("proyectos").insert({
                    "codigo": codigo_proy,
                    "cliente": cliente,
                    "fecha": f"{fe_inicio} - {fe_fin}",
                    "peso_recibido": peso_total_recibido,
                    "peso_transformado": kg_transformados,
                    "aprovechamiento": pct_aprovechamiento,
                    "co2_neto": co2_neto,
                    "horas_totales": horas_totales,
                    "ruc": ruc
                }).execute()
                st.success("✅ Guardado correctamente en la base de datos.")
            except Exception as e:
                # Si el código ya existe, lo omitimos suavemente sin romper la ejecución
                st.info("ℹ️ Generando PDF (el registro en BD ya existe, omitiendo duplicación).")

            pdf_oficial = generar_pdf_oficial(
                cliente, ruc, proyecto_nom, codigo_proy, fe_inicio, fe_fin, responsable, area,
                "Uniformes en desuso", "Upcycling", "Kilogramos (kg)",
                guia_remision, origen, destino, lista_items, kg_transformados, horas_totales,
                cant_personas, emisiones_transporte, emisiones_lavado, emisiones_corte, emisiones_bordado
            )

            st.download_button(
                label=f"📥 DESCARGAR INFORME EN PDF ({codigo_proy}.pdf)",
                data=pdf_oficial,
                file_name=f"Informe_Tecnico_{codigo_proy}.pdf",
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
