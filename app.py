from flask import Flask, render_template, session, redirect, url_for, request
from config import config

from models.user import User
from models.client import Client
from models.attendance import Attendance
from models.permission import Permission
from models.product import Product
from models.provider import Provider
from models.sale import Sale
from models.cash import Cash
from models.warehouse import Warehouse
from models.purchase import Purchase
from models.inventory import Inventory
from models.output_note import OutputNote
from models.payment_method import PaymentMethod
from models.discount import Discount
from models.promotion import Promotion

from utils.decorators import login_required

from controllers.auth_controller import auth_bp
from controllers.user_controller import user_bp
from controllers.permission_controller import permission_bp
from controllers.client_controller import client_bp
from controllers.attendance_controller import attendance_bp
from controllers.product_controller import product_bp
from controllers.provider_controller import provider_bp
from controllers.sale_controller import sale_bp
from controllers.cash_controller import cash_bp
from controllers.warehouse_controller import warehouse_bp
from controllers.purchase_controller import purchase_bp
from controllers.inventory_controller import inventory_bp
from controllers.output_note_controller import output_note_bp
from controllers.payment_method_controller import payment_method_bp
from controllers.discount_controller import discount_bp
from controllers.promotion_controller import promotion_bp
from controllers.report_controller import report_bp
from controllers.voice_ai_controller import voice_ai_bp
from controllers.managerial_dashboard_controller import managerial_dashboard_bp
from controllers.abc_classification_controller import abc_classification_bp


app = Flask(__name__)
app.config.from_object(config['development'])


@app.before_request
def clear_session_if_needed():
    """
    Control de sesión.
    Permite entrar al login, logout, recuperación de contraseña y archivos estáticos.
    Si no hay sesión, manda al login.
    """
    allowed_routes = [
        'auth.login',
        'auth.logout',
        'auth.forgot_password',
        'auth.reset_password',
        'static'
    ]

    if request.endpoint in allowed_routes:
        return None

    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    return None


# Registrar todos los Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(permission_bp)
app.register_blueprint(client_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(product_bp)
app.register_blueprint(provider_bp)
app.register_blueprint(sale_bp)
app.register_blueprint(cash_bp)
app.register_blueprint(warehouse_bp)
app.register_blueprint(purchase_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(output_note_bp)
app.register_blueprint(payment_method_bp)
app.register_blueprint(discount_bp)
app.register_blueprint(promotion_bp)
app.register_blueprint(report_bp)
app.register_blueprint(voice_ai_bp)
app.register_blueprint(managerial_dashboard_bp)
app.register_blueprint(abc_classification_bp)


# Rutas principales
@app.route('/')
def index():
    """
    Entrada principal del sistema.
    Si no hay sesión, muestra login.
    Si hay sesión, manda al dashboard.
    """
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard principal con bloques según permisos.
    """

    codigo_usuario = session.get('user_id')

    # Verificación de permisos para cada módulo
    can_view_users = Permission.has_permission(codigo_usuario, 'user_read')
    can_view_clients = Permission.has_permission(codigo_usuario, 'client_read')
    can_view_attendance = Permission.has_permission(codigo_usuario, 'attendance_read')
    can_view_permissions = Permission.has_permission(codigo_usuario, 'permission_read')
    can_view_products = Permission.has_permission(codigo_usuario, 'product_read')
    can_view_providers = Permission.has_permission(codigo_usuario, 'provider_read')
    can_view_sales = Permission.has_permission(codigo_usuario, 'sale_read')
    can_view_cash = Permission.has_permission(codigo_usuario, 'cash_read')
    can_view_warehouses = Permission.has_permission(codigo_usuario, 'warehouse_read')
    can_view_purchases = Permission.has_permission(codigo_usuario, 'purchase_read')
    can_view_inventory = Permission.has_permission(codigo_usuario, 'inventory_read')
    can_view_output_notes = Permission.has_permission(codigo_usuario, 'output_note_read')
    can_view_payment_methods = Permission.has_permission(codigo_usuario, 'payment_method_read')
    can_view_discounts = Permission.has_permission(codigo_usuario, 'discount_read')
    can_view_promotions = Permission.has_permission(codigo_usuario, 'promotion_read')

    # Reportes
    can_view_sales_report = Permission.has_permission(codigo_usuario, 'report_sales_read')
    can_view_profit_report = Permission.has_permission(codigo_usuario, 'report_profit_read')

    # Reporte de Voz IA usará el mismo permiso base de reportes de ventas
    # para no crear permisos nuevos ni tocar la base de datos.
    can_view_voice_ai_report = can_view_sales_report

    # Clasificación ABC usará el mismo permiso base del Reporte de Utilidad
    # para no crear permisos nuevos ni tocar la base de datos.
    can_view_abc_classification = can_view_profit_report

    # Permiso general para mostrar el bloque de Reportes
    can_view_reports = (
        can_view_sales_report
        or can_view_profit_report
        or can_view_voice_ai_report
        or can_view_abc_classification
    )

    stats = {}

    # Estadísticas para cada módulo según los permisos
    if can_view_users:
        users = User.get_all()
        stats['users'] = len(users)

    if can_view_clients:
        clients = Client.get_all()
        stats['clients'] = len(clients)

    if can_view_attendance:
        today_attendance = Attendance.get_today_actions()
        stats['today_attendance'] = len(today_attendance)

    if can_view_permissions:
        permissions = Permission.get_all()
        stats['permissions'] = len(permissions)

    if can_view_products:
        products = Product.get_all()
        stats['products'] = len(products)

    if can_view_providers:
        providers = Provider.get_all()
        stats['providers'] = len(providers)

    if can_view_sales:
        stats['sales'] = Sale.count_all()

    if can_view_cash:
        stats['cash'] = Cash.count_all()
        stats['cash_open'] = Cash.count_open()

    if can_view_warehouses:
        stats['warehouses'] = Warehouse.count_all()

    if can_view_purchases:
        stats['purchases'] = Purchase.count_all()

    if can_view_inventory:
        stats['inventory_items'] = Inventory.count_inventory_items()
        stats['low_stock'] = Inventory.count_low_stock()

    if can_view_output_notes:
        stats['output_notes'] = OutputNote.count_all()

    if can_view_payment_methods:
        stats['payment_methods'] = PaymentMethod.count_all(active_only=True)
        stats['payment_methods_inactive'] = PaymentMethod.count_inactive()

    if can_view_discounts:
        stats['discounts'] = Discount.count_all(active_only=True)
        stats['discounts_inactive'] = Discount.count_inactive()

    if can_view_promotions:
        stats['promotions'] = Promotion.count_all()
        stats['active_promotions'] = Promotion.count_active_valid()

    if can_view_reports:
        reports_count = 0

        if can_view_sales_report:
            reports_count += 1

        if can_view_profit_report:
            reports_count += 1

        if can_view_voice_ai_report:
            reports_count += 1

        if can_view_abc_classification:
            reports_count += 1

        stats['reports'] = reports_count

    # Diccionario con permisos para mostrar los bloques correspondientes
    permissions_dashboard = {
        'can_view_users': can_view_users,
        'can_view_clients': can_view_clients,
        'can_view_attendance': can_view_attendance,
        'can_view_permissions': can_view_permissions,
        'can_view_products': can_view_products,
        'can_view_providers': can_view_providers,
        'can_view_sales': can_view_sales,
        'can_view_cash': can_view_cash,
        'can_view_warehouses': can_view_warehouses,
        'can_view_purchases': can_view_purchases,
        'can_view_inventory': can_view_inventory,
        'can_view_output_notes': can_view_output_notes,
        'can_view_payment_methods': can_view_payment_methods,
        'can_view_discounts': can_view_discounts,
        'can_view_promotions': can_view_promotions,

        # Reportes
        'can_view_reports': can_view_reports,
        'can_view_sales_report': can_view_sales_report,
        'can_view_profit_report': can_view_profit_report,
        'can_view_voice_ai_report': can_view_voice_ai_report,
        'can_view_abc_classification': can_view_abc_classification
    }

    return render_template(
        'dashboard.html',
        stats=stats,
        permissions_dashboard=permissions_dashboard
    )


if __name__ == '__main__':
    app.run(
        host='127.0.0.1',
        port=5050,
        debug=True,
        use_reloader=False
    )