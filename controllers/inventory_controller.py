from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.inventory import Inventory
from utils.decorators import login_required, permission_required


inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')


@inventory_bp.route('/')
@login_required
@permission_required('inventory_read')
def list_inventory():
    """
    Listar inventario agrupado por almacén y producto.
    Incluye estado de stock: normal, bajo o agotado.
    """
    search = request.args.get('search', '')
    codigo_almacen = request.args.get('codigo_almacen', '')
    estado_stock = request.args.get('estado_stock', '')

    inventory = Inventory.get_summary(
        search=search,
        codigo_almacen=codigo_almacen,
        estado_stock=estado_stock
    )

    warehouses = Inventory.get_warehouses()
    counters = Inventory.get_counters()

    return render_template(
        'inventory/list.html',
        inventory=inventory,
        warehouses=warehouses,
        counters=counters,
        search=search,
        codigo_almacen=codigo_almacen,
        estado_stock=estado_stock
    )


@inventory_bp.route('/alerts')
@login_required
@permission_required('inventory_alerts')
def stock_alerts():
    """
    Ver productos con stock bajo o agotado.
    """
    search = request.args.get('search', '')

    alerts = Inventory.get_low_stock_alerts(search=search)
    counters = Inventory.get_counters()

    return render_template(
        'inventory/alerts.html',
        alerts=alerts,
        counters=counters,
        search=search
    )


@inventory_bp.route('/detail/<codigo_almacen>/<codigo_producto>')
@login_required
@permission_required('inventory_detail')
def detail_inventory(codigo_almacen, codigo_producto):
    """
    Ver detalle de lotes de inventario de un producto en un almacén.
    """
    result = Inventory.get_detail(codigo_almacen, codigo_producto)

    if not result:
        flash('No se encontró el inventario solicitado.', 'danger')
        return redirect(url_for('inventory.list_inventory'))

    return render_template(
        'inventory/detail.html',
        detail=result['detail'],
        lots=result['lots']
    )


@inventory_bp.route('/adjust', methods=['GET', 'POST'])
@login_required
@permission_required('inventory_adjust')
def adjust_inventory():
    """
    Registrar ajuste manual de inventario.
    Permite entrada o salida.
    """
    warehouses = Inventory.get_warehouses()
    products = Inventory.get_products()

    selected_warehouse = request.args.get('codigo_almacen', '')
    selected_product = request.args.get('codigo_producto', '')

    if request.method == 'POST':
        codigo_almacen = request.form.get('codigo_almacen')
        codigo_producto = request.form.get('codigo_producto')
        tipo_movimiento = request.form.get('tipo_movimiento')
        cantidad = request.form.get('cantidad')
        fecha_vencimiento = request.form.get('fecha_vencimiento')
        motivo = request.form.get('motivo')

        try:
            result = Inventory.register_adjustment(
                codigo_almacen=codigo_almacen,
                codigo_producto=codigo_producto,
                tipo_movimiento=tipo_movimiento,
                cantidad=cantidad,
                codigo_usuario=session.get('user_id'),
                motivo=motivo,
                fecha_vencimiento=fecha_vencimiento
            )

            flash('Ajuste de inventario registrado correctamente.', 'success')

            return redirect(url_for(
                'inventory.detail_inventory',
                codigo_almacen=result['codigo_almacen'],
                codigo_producto=result['codigo_producto']
            ))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al registrar ajuste de inventario: {str(e)}', 'danger')

    return render_template(
        'inventory/adjust.html',
        warehouses=warehouses,
        products=products,
        selected_warehouse=selected_warehouse,
        selected_product=selected_product
    )