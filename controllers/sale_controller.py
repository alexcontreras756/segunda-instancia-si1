from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.sale import Sale
from utils.decorators import login_required, permission_required

from datetime import datetime
import random


sale_bp = Blueprint('sales', __name__, url_prefix='/sales')


def _is_qr_payment(payment_types, id_tipo_pago):
    """
    Verifica si el tipo de pago seleccionado corresponde a QR.
    Se compara por ID y por nombre del método de pago.
    """
    if not id_tipo_pago:
        return False

    for payment_type in payment_types:
        if str(payment_type['id']) == str(id_tipo_pago):
            nombre = (payment_type['nombre'] or '').lower().strip()
            return 'qr' in nombre

    return False


def _generate_qr_reference():
    """
    Genera una referencia simulada para pago QR.
    Ejemplo: QR-20260621-184533-4821
    """
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    random_code = random.randint(1000, 9999)

    return f'QR-{timestamp}-{random_code}'


@sale_bp.route('/')
@login_required
@permission_required('sale_read')
def list_sales():
    """
    Listar ventas registradas.
    """
    sales = Sale.get_all()

    return render_template(
        'sales/list.html',
        sales=sales
    )


@sale_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('sale_create')
def create_sale():
    """
    Registrar nueva venta.
    Incluye:
    - Cliente
    - Productos
    - Tipo de pago
    - Pago QR simulado
    - Descuento opcional CU14
    - Promoción opcional CU15
    """
    clients = Sale.get_clients_for_sale()
    products = Sale.get_products_for_sale()
    payment_types = Sale.get_payment_types()
    discounts = Sale.get_active_discounts()
    promotions = Sale.get_active_promotions()

    if request.method == 'POST':
        id_cliente = request.form.get('id_cliente')
        id_tipo_pago = request.form.get('id_tipo_pago')
        codigo_descuento = request.form.get('codigo_descuento')

        # CU15 Promociones
        # Se usa id_promocion porque public.promocion usa id, no codigo.
        # También se acepta codigo_promocion como alias por compatibilidad con formularios anteriores.
        id_promocion = request.form.get('id_promocion') or request.form.get('codigo_promocion')

        referencia_externa = request.form.get('referencia_externa')
        qr_payment_confirmed = request.form.get('qr_payment_confirmed') == 'on'

        product_codes = request.form.getlist('codigo_producto[]')
        quantities = request.form.getlist('cantidad[]')

        items = []

        for codigo_producto, cantidad in zip(product_codes, quantities):
            if codigo_producto and cantidad:
                items.append({
                    'codigo_producto': codigo_producto,
                    'cantidad': cantidad
                })

        try:
            is_qr = _is_qr_payment(payment_types, id_tipo_pago)

            if is_qr:
                if not qr_payment_confirmed:
                    flash(
                        'Debe confirmar que el pago QR fue recibido antes de registrar la venta.',
                        'danger'
                    )

                    return render_template(
                        'sales/create.html',
                        clients=clients,
                        products=products,
                        payment_types=payment_types,
                        discounts=discounts,
                        promotions=promotions
                    )

                if not referencia_externa:
                    referencia_externa = _generate_qr_reference()

            result = Sale.create_sale(
                id_cliente=id_cliente,
                codigo_usuario=session.get('user_id'),
                id_tipo_pago=id_tipo_pago,
                items=items,
                referencia_externa=referencia_externa,
                codigo_descuento=codigo_descuento,
                id_promocion=id_promocion
            )

            invoice_code = result['invoice']['codigo']
            promotion = result.get('promotion')
            discount = result.get('discount')

            if is_qr and promotion and discount:
                flash(
                    f'Venta {invoice_code} registrada correctamente con pago QR simulado, '
                    f'descuento y promoción aplicada. Referencia: {referencia_externa}',
                    'success'
                )

            elif is_qr and promotion:
                flash(
                    f'Venta {invoice_code} registrada correctamente con pago QR simulado '
                    f'y promoción aplicada. Referencia: {referencia_externa}',
                    'success'
                )

            elif is_qr and discount:
                flash(
                    f'Venta {invoice_code} registrada correctamente con pago QR simulado '
                    f'y descuento aplicado. Referencia: {referencia_externa}',
                    'success'
                )

            elif is_qr:
                flash(
                    f'Venta {invoice_code} registrada correctamente con pago QR simulado. '
                    f'Referencia: {referencia_externa}',
                    'success'
                )

            elif promotion and discount:
                flash(
                    f'Venta {invoice_code} registrada correctamente con descuento y promoción aplicada.',
                    'success'
                )

            elif promotion:
                flash(
                    f'Venta {invoice_code} registrada correctamente con promoción aplicada.',
                    'success'
                )

            elif discount:
                flash(
                    f'Venta {invoice_code} registrada correctamente con descuento aplicado.',
                    'success'
                )

            else:
                flash(f'Venta {invoice_code} registrada correctamente', 'success')

            return redirect(url_for('sales.detail_sale', codigo=invoice_code))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al registrar la venta: {str(e)}', 'danger')

    return render_template(
        'sales/create.html',
        clients=clients,
        products=products,
        payment_types=payment_types,
        discounts=discounts,
        promotions=promotions
    )


@sale_bp.route('/detail/<codigo>')
@login_required
@permission_required('sale_detail')
def detail_sale(codigo):
    """
    Ver detalle de una venta.
    """
    sale = Sale.find_by_code(codigo)

    if not sale:
        flash('Venta no encontrada', 'danger')
        return redirect(url_for('sales.list_sales'))

    details = Sale.get_details(codigo)

    return render_template(
        'sales/detail.html',
        sale=sale,
        details=details
    )


@sale_bp.route('/cancel/<codigo>')
@login_required
@permission_required('sale_cancel')
def cancel_sale(codigo):
    """
    Anular venta.
    """
    try:
        result = Sale.cancel_sale(
            codigo_factura=codigo,
            codigo_usuario=session.get('user_id')
        )

        if result:
            flash(f'Venta {codigo} anulada correctamente', 'success')
        else:
            flash('La venta no existe o ya fue anulada', 'warning')

    except Exception as e:
        flash(f'Error al anular la venta: {str(e)}', 'danger')

    return redirect(url_for('sales.list_sales'))