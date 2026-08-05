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
                Paragraph("CO<sub>2</sub>e NETO EVITADO", card_sub),
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

        # 6. BALANCE DE IMPACTO AMBIENTAL (CORREGIDO CO2)
        elements.append(Paragraph("6. RESUMEN DE IMPACTO AMBIENTAL DEL PROYECTO (CO<sub>2</sub>e)", h2_style))
        data_co2_box = [
            [Paragraph("<b>(+) CO<sub>2</sub> Evitado por Upcycling</b>", card_sub), Paragraph("<b>(-) Emisiones del Proceso</b>", card_sub), Paragraph("<b>(=) Impacto Ambiental Neto</b>", card_sub)],
            [Paragraph(f"<b>{co2_evitado_total:.2f} kg CO<sub>2</sub>e</b>", card_title), Paragraph(f"<b>{emisiones_proceso:.2f} kg CO<sub>2</sub>e</b>", card_title), Paragraph(f"<b>{co2_neto:.2f} kg CO<sub>2</sub>e</b>", card_title)]
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

        # Interpretación
        interp_style = ParagraphStyle('Interp', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#1E293B'), alignment=1)
        elements.append(Paragraph(f"<b>Interpretación de resultados:</b><br/>El proceso de upcycling permitió evitar la emisión de <b>{co2_neto:.2f} kg de CO<sub>2</sub>e</b> en comparación con la producción de material textil nuevo.", interp_style))
        elements.append(Spacer(1, 10))

        # Desglose de Emisiones
        elements.append(Paragraph("<b>Desglose de emisiones del proceso (kg CO<sub>2</sub>e)</b>", ParagraphStyle('SubSub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#0F172A'), alignment=1)))
        elements.append(Spacer(1, 4))

        data_emisiones = [
            [Paragraph("<b>Etapa</b>", cell_bold), Paragraph("<b>Emisiones (kg CO<sub>2</sub>e)</b>", cell_bold), Paragraph("<b>Participación (%)</b>", cell_bold)],
            [Paragraph("Transporte", cell_style), Paragraph(f"{emisiones_transporte:.2f}", cell_style), Paragraph(f"{(emisiones_transporte/emisiones_proceso*100 if emisiones_proceso>0 else 0):.1f}%", cell_style)],
            [Paragraph("Lavandería", cell_style), Paragraph(f"{emisiones_lavado:.2f}", cell_style), Paragraph(f"{(emisiones_lavado/emisiones_proceso*100 if emisiones_proceso>0 else 0):.1f}%", cell_style)],
            [Paragraph("Corte", cell_style), Paragraph(f"{emisiones_corte:.2f}", cell_style), Paragraph(f"{(emisiones_corte/emisiones_proceso*100 if emisiones_proceso>0 else 0):.1f}%", cell_style)],
            [Paragraph("Bordado", cell_style), Paragraph(f"{emisiones_bordado:.2f}", cell_style), Paragraph(f"{(emisiones_bordado/emisiones_proceso*100 if emisiones_proceso>0 else 0):.1f}%", cell_style)],
            [Paragraph("<b>TOTAL</b>", cell_bold), Paragraph(f"<b>{emisiones_proceso:.2f}</b>", cell_bold), Paragraph("<b>100.0%</b>", cell_bold)],
        ]
        t_emisiones = Table(data_emisiones, colWidths=[240, 150, 150])
        t_emisiones.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5D0FE')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F1F5F9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_emisiones)
        elements.append(Spacer(1, 6))

        nota_emision = ParagraphStyle('NotaEmi', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=7.5, textColor=colors.HexColor('#475569'), alignment=1)
        elements.append(Paragraph("Nota: Las emisiones fueron estimadas considerando factores de emisión por tipo de proceso y transporte.<br/>Las emisiones generadas durante el proceso representaron una fracción menor frente al impacto positivo obtenido, evidenciando la eficiencia ambiental del modelo de reaprovechamiento.", nota_emision))
        elements.append(Spacer(1, 15))

        # 7. Impacto Social
        elements.append(Paragraph("7. RESUMEN DE IMPACTO SOCIAL Y EMPLEO GENERADO", h2_style))
        elements.append(Paragraph(f"El proyecto permitió la inclusión laboral de artesanas y personal de taller, acumulando un total de <b>{horas_totales:.2f} horas de trabajo directo</b> distribuidas entre <b>{cant_personas} participantes</b>.", cell_style))

        doc.build(elements, canvasmaker=ReporteCanvas)
        buffer.seek(0)
        return buffer
