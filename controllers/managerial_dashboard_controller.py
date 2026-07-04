from flask import Blueprint, render_template, redirect, url_for, flash, session
from models.managerial_dashboard import ManagerialDashboard
from utils.decorators import login_required, admin_required
from utils.gemini_client import GeminiClient
from utils.email_service import EmailService


managerial_dashboard_bp = Blueprint(
    'managerial_dashboard',
    __name__,
    url_prefix='/reports/managerial-dashboard'
)


@managerial_dashboard_bp.route('/')
@login_required
@admin_required
def managerial_dashboard_page():
    """
    Pantalla principal del CU19 - Dashboard Gerencial Inteligente.
    Solo administradores.
    """
    dashboard_data = ManagerialDashboard.get_dashboard_data()

    try:
        ManagerialDashboard.register_action(
            codigo_usuario=session.get('user_id'),
            accion='CONSULTA DASHBOARD GERENCIAL',
            detalle='El administrador consultó el Dashboard Gerencial Inteligente.'
        )
    except Exception:
        pass

    return render_template(
        'reports/managerial_dashboard.html',
        indicators=dashboard_data['indicators'],
        sales_by_day=dashboard_data['sales_by_day'],
        chart_labels=dashboard_data['chart_labels'],
        chart_values=dashboard_data['chart_values'],
        has_month_sales=dashboard_data['has_month_sales']
    )


@managerial_dashboard_bp.route('/send-ai-email', methods=['POST'])
@login_required
@admin_required
def send_ai_email():
    """
    Generar análisis gerencial con Gemini IA y enviarlo por correo.
    Solo administradores.
    """
    try:
        dashboard_data = ManagerialDashboard.get_dashboard_data()
        indicators = dashboard_data['indicators']

        analysis = GeminiClient.generate_managerial_analysis(indicators)
        sent_to = EmailService.send_managerial_analysis(analysis, indicators)

        ManagerialDashboard.register_action(
            codigo_usuario=session.get('user_id'),
            accion='ENVÍO ANÁLISIS GERENCIAL IA POR CORREO',
            detalle=f'Se envió análisis gerencial IA al correo {sent_to}.'
        )

        flash(f'Análisis gerencial IA enviado correctamente a {sent_to}.', 'success')

    except Exception as e:
        try:
            ManagerialDashboard.register_action(
                codigo_usuario=session.get('user_id'),
                accion='ERROR ENVÍO ANÁLISIS GERENCIAL IA POR CORREO',
                detalle=f'Error al enviar análisis gerencial IA: {str(e)}'
            )
        except Exception:
            pass

        flash(f'No se pudo enviar el análisis gerencial: {str(e)}', 'danger')

    return redirect(url_for('managerial_dashboard.managerial_dashboard_page'))