from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.purchase import Purchase
from utils.decorators import login_required, permission_required


purchase_bp = Blueprint('purchases', __name__, url_prefix='/purchases')


@purchase_bp.route('/')
@login_required
@permission_required('purchase_read')
def list_purchases():
    """
    Listar compras registradas.
    """
    purchases = Purchase.get_all()

    return render_template(
        'purchases/list.html',
        purchases=purchases
    )


@purchase_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('purchase_create')
def create_purchase():
    """
    Registrar nueva compra.
    """
    providers = Purchase.get_providers_for_purchase()
    warehouses = Purchase.get_warehouses_for_purchase()
    products = Purchase.get_products_for_purchase()

    if request.method == 'POST':
        codigo_proveedor = request.form.get('codigo_proveedor')
        codigo_almacen = request.form.get('codigo_almacen')
        observacion = request.form.get('observacion')

        product_codes = request.form.getlist('codigo_producto[]')
        quantities = request.form.getlist('cantidad[]')
        costs = request.form.getlist('costo_unitario[]')
        sale_prices = request.form.getlist('precio_venta[]')
        expiration_dates = request.form.getlist('fecha_vencimiento[]')

        items = []

        for codigo_producto, cantidad, costo_unitario, precio_venta, fecha_vencimiento in zip(
            product_codes,
            quantities,
            costs,
            sale_prices,
            expiration_dates
        ):
            if codigo_producto:
                items.append({
                    'codigo_producto': codigo_producto,
                    'cantidad': cantidad,
                    'costo_unitario': costo_unitario,
                    'precio_venta': precio_venta,
                    'fecha_vencimiento': fecha_vencimiento
                })

        try:
            result = Purchase.create_purchase(
                codigo_proveedor=codigo_proveedor,
                codigo_almacen=codigo_almacen,
                codigo_usuario=session.get('user_id'),
                items=items,
                observacion=observacion
            )

            purchase_code = result['purchase']['codigo']

            flash(f'Compra {purchase_code} registrada correctamente.', 'success')
            return redirect(url_for('purchases.detail_purchase', codigo=purchase_code))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al registrar la compra: {str(e)}', 'danger')

    return render_template(
        'purchases/create.html',
        providers=providers,
        warehouses=warehouses,
        products=products
    )


@purchase_bp.route('/detail/<codigo>')
@login_required
@permission_required('purchase_detail')
def detail_purchase(codigo):
    """
    Ver detalle de una compra.
    """
    purchase = Purchase.find_by_code(codigo)

    if not purchase:
        flash('Compra no encontrada.', 'danger')
        return redirect(url_for('purchases.list_purchases'))

    details = Purchase.get_details(codigo)

    return render_template(
        'purchases/detail.html',
        purchase=purchase,
        details=details
    )