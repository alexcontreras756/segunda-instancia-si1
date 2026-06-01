from flask import Blueprint, render_template, request, send_file, session
from models.report import Report
from utils.decorators import login_required, permission_required

from io import BytesIO
from datetime import datetime
from urllib.parse import urlencode

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)


report_bp = Blueprint('reports', __name__, url_prefix='/reports')


def _clean_filter(value):
    """
    Limpiar filtros vacíos.
    """
    if value is None:
        return None

    value = str(value).strip()

    if value == '':
        return None

    return value


def _get_filters_from_request():
    """
    Obtener filtros del request GET.
    """
    return {
        'fecha_inicio': _clean_filter(request.args.get('fecha_inicio')),
        'fecha_fin': _clean_filter(request.args.get('fecha_fin')),
        'codigo_usuario': _clean_filter(request.args.get('codigo_usuario')),
        'id_tipo_pago': _clean_filter(request.args.get('id_tipo_pago')),
        'estado': _clean_filter(request.args.get('estado')) or 'todos',
        'search': _clean_filter(request.args.get('search'))
    }


def _get_selected_fields():
    """
    Obtener campos seleccionados.
    Si no se selecciona ninguno, se usan campos por defecto.
    """
    available_fields = Report.get_available_fields()
    selected_fields = request.args.getlist('fields')

    selected_fields = [
        field for field in selected_fields
        if field in available_fields
    ]

    if not selected_fields:
        selected_fields = Report.get_default_fields()

    return selected_fields


def _format_value(value, field_name=None):
    """
    Formatear valores para mostrar en HTML y PDF.
    """
    if value is None:
        return '-'

    if field_name == 'fecha_hora':
        try:
            return value.strftime('%d/%m/%Y %H:%M:%S')
        except Exception:
            return str(value)

    if field_name in ['monto_total', 'monto_final']:
        try:
            return f'Bs {float(value):.2f}'
        except Exception:
            return str(value)

    if field_name == 'pagado':
        return 'Sí' if value else 'No'

    if field_name == 'estado':
        return 'Activa' if value else 'Anulada'

    return str(value)


def _build_pdf_query(selected_fields, filters):
    """
    Construir querystring para el botón de descarga PDF.
    """
    query_data = {}

    for key, value in filters.items():
        if value:
            query_data[key] = value

    query_data['fields'] = selected_fields

    return urlencode(query_data, doseq=True)


def _build_pdf(rows, summary, selected_fields, filters):
    """
    Generar PDF del reporte de ventas usando ReportLab.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name='TitleCenter',
        parent=styles['Title'],
        alignment=TA_CENTER,
        fontSize=16,
        leading=20,
        spaceAfter=10
    )

    subtitle_style = ParagraphStyle(
        name='SubtitleCenter',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=9,
        textColor=colors.HexColor('#555555'),
        spaceAfter=12
    )

    normal_style = ParagraphStyle(
        name='NormalReport',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_LEFT
    )

    small_style = ParagraphStyle(
        name='SmallReport',
        parent=styles['Normal'],
        fontSize=7,
        leading=9
    )

    elements = []

    elements.append(Paragraph('MiniMarket QuickStore', title_style))
    elements.append(Paragraph('Reporte de Ventas', title_style))

    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    elements.append(Paragraph(f'Generado el: {generated_at}', subtitle_style))

    filtros_texto = []

    if filters.get('fecha_inicio'):
        filtros_texto.append(f"Fecha inicio: {filters['fecha_inicio']}")

    if filters.get('fecha_fin'):
        filtros_texto.append(f"Fecha fin: {filters['fecha_fin']}")

    if filters.get('codigo_usuario'):
        filtros_texto.append(f"Usuario: {filters['codigo_usuario']}")

    if filters.get('id_tipo_pago'):
        filtros_texto.append(f"Tipo de pago ID: {filters['id_tipo_pago']}")

    if filters.get('estado') and filters.get('estado') != 'todos':
        filtros_texto.append(f"Estado: {filters['estado']}")

    if filters.get('search'):
        filtros_texto.append(f"Búsqueda: {filters['search']}")

    if not filtros_texto:
        filtros_texto.append('Sin filtros aplicados')

    elements.append(Paragraph('Filtros: ' + ' | '.join(filtros_texto), normal_style))
    elements.append(Spacer(1, 0.25 * cm))

    resumen_data = [
        ['Total registros', 'Ventas activas', 'Ventas anuladas', 'Total activo', 'Total general'],
        [
            str(summary['total_registros']),
            str(summary['ventas_activas']),
            str(summary['ventas_anuladas']),
            f"Bs {float(summary['total_activo']):.2f}",
            f"Bs {float(summary['total_general']):.2f}"
        ]
    ]

    resumen_table = Table(resumen_data, repeatRows=1)
    resumen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#cccccc')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(resumen_table)
    elements.append(Spacer(1, 0.4 * cm))

    available_fields = Report.get_available_fields()

    header = [
        Paragraph(f'<b>{available_fields[field]}</b>', small_style)
        for field in selected_fields
    ]

    data = [header]

    for row in rows:
        row_data = []

        for field in selected_fields:
            formatted_value = _format_value(row.get(field), field)
            row_data.append(Paragraph(formatted_value, small_style))

        data.append(row_data)

    if len(data) == 1:
        data.append([
            Paragraph('No existen datos para los filtros seleccionados.', small_style)
        ] + ['' for _ in selected_fields[1:]])

    table = Table(data, repeatRows=1)

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor('#f9fafb')
        ]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ])

    table.setStyle(table_style)

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)

    return buffer


@report_bp.route('/sales')
@login_required
@permission_required('report_sales_read')
def sales_report():
    """
    Pantalla del reporte de ventas.
    """
    filters = _get_filters_from_request()
    selected_fields = _get_selected_fields()

    rows = Report.get_sales_report(
        fecha_inicio=filters['fecha_inicio'],
        fecha_fin=filters['fecha_fin'],
        codigo_usuario=filters['codigo_usuario'],
        id_tipo_pago=filters['id_tipo_pago'],
        estado=filters['estado'],
        search=filters['search']
    )

    summary = Report.calculate_summary(rows)

    users = Report.get_users_for_filter()
    payment_types = Report.get_payment_types_for_filter()

    pdf_query = _build_pdf_query(selected_fields, filters)

    return render_template(
        'reports/sales.html',
        rows=rows,
        summary=summary,
        users=users,
        payment_types=payment_types,
        filters=filters,
        available_fields=Report.get_available_fields(),
        selected_fields=selected_fields,
        pdf_query=pdf_query,
        format_value=_format_value
    )


@report_bp.route('/sales/pdf')
@login_required
@permission_required('report_sales_pdf')
def sales_report_pdf():
    """
    Descargar el reporte de ventas en PDF.
    """
    filters = _get_filters_from_request()
    selected_fields = _get_selected_fields()

    rows = Report.get_sales_report(
        fecha_inicio=filters['fecha_inicio'],
        fecha_fin=filters['fecha_fin'],
        codigo_usuario=filters['codigo_usuario'],
        id_tipo_pago=filters['id_tipo_pago'],
        estado=filters['estado'],
        search=filters['search']
    )

    summary = Report.calculate_summary(rows)

    pdf_buffer = _build_pdf(
        rows=rows,
        summary=summary,
        selected_fields=selected_fields,
        filters=filters
    )

    try:
        Report.register_report_action(
            codigo_usuario=session.get('user_id'),
            accion='DESCARGA DE REPORTE DE VENTAS PDF',
            detalle=f'Se descargó reporte de ventas con {summary["total_registros"]} registros.'
        )
    except Exception:
        pass

    filename = f'reporte_ventas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )