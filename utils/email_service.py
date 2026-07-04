import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailService:
    """
    Servicio centralizado para envío de correos del sistema QuickStore.

    Usa la misma configuración SMTP que recuperación de contraseña.
    Para reportes gerenciales usa ADMIN_REPORT_EMAIL y, si no existe,
    ADMIN_RECOVERY_EMAIL como respaldo.
    """

    @staticmethod
    def _get_smtp_config():
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_email = os.getenv('SMTP_EMAIL')
        smtp_password = os.getenv('SMTP_PASSWORD')

        if not all([smtp_server, smtp_email, smtp_password]):
            raise Exception('Faltan datos SMTP en las variables de entorno.')

        return {
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'smtp_email': smtp_email,
            'smtp_password': smtp_password
        }

    @staticmethod
    def get_admin_report_email():
        """
        Obtener correo destinatario del administrador para reportes.
        ADMIN_REPORT_EMAIL tiene prioridad.
        ADMIN_RECOVERY_EMAIL queda como fallback.
        """
        admin_email = os.getenv('ADMIN_REPORT_EMAIL') or os.getenv('ADMIN_RECOVERY_EMAIL')

        if not admin_email or not admin_email.strip():
            raise Exception('No está configurado ADMIN_REPORT_EMAIL ni ADMIN_RECOVERY_EMAIL.')

        return admin_email.strip()

    @staticmethod
    def send_email(to_email, subject, body):
        """
        Enviar correo en texto plano.
        """
        config = EmailService._get_smtp_config()

        message = MIMEMultipart()
        message['From'] = config['smtp_email']
        message['To'] = to_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        server.starttls()
        server.login(config['smtp_email'], config['smtp_password'])
        server.send_message(message)
        server.quit()

        return True

    @staticmethod
    def send_managerial_analysis(analysis, indicators):
        """
        Enviar análisis gerencial IA al correo configurado del administrador.
        """
        to_email = EmailService.get_admin_report_email()
        subject = 'Análisis Gerencial QuickStore'

        payment_method = indicators.get('metodo_pago_mas_usado', {})
        formatted = indicators.get('formatted', {})

        body = f"""
ANÁLISIS GERENCIAL QUICKSTORE

Fecha y hora de generación: {indicators.get('fecha_generacion', '-')}

ANÁLISIS GENERADO POR GEMINI IA

{analysis}

INDICADORES PRINCIPALES

- Ventas del día: {formatted.get('ventas_dia', 'Bs 0.00')}
- Ventas del mes: {formatted.get('ventas_mes', 'Bs 0.00')}
- Utilidad del mes: {formatted.get('utilidad_mes', 'Bs 0.00')}
- Productos con stock bajo: {indicators.get('productos_stock_bajo', 0)}
- Productos agotados: {indicators.get('productos_agotados', 0)}
- Productos próximos a vencer: {indicators.get('productos_proximos_vencer', 0)}
- Compras del mes: {formatted.get('compras_mes', 'Bs 0.00')}
- Pérdidas por notas de salida: {formatted.get('perdidas_notas_salida', 'Bs 0.00')}
- Cajas abiertas: {indicators.get('cajas_abiertas', 0)}
- Método de pago más usado: {payment_method.get('metodo_pago', 'Sin registros')} ({payment_method.get('cantidad', 0)} uso/s, {formatted.get('metodo_pago_total', 'Bs 0.00')})

Este correo fue generado automáticamente por el sistema MiniMarket QuickStore.
""".strip()

        EmailService.send_email(to_email, subject, body)

        return to_email