from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.promotion import Promotion
from utils.decorators import login_required, permission_required


promotion_bp = Blueprint('promotions', __name__, url_prefix='/promotions')


@promotion_bp.route('/')
@login_required
@permission_required('promotion_read')
def list_promotions():
    """
    Listar promociones.
    """
    search = request.args.get('search', '')

    promotions = Promotion.get_all(search=search)
    active_count = Promotion.count_all(active_only=True)
    valid_count = Promotion.count_active_valid()
    total_count = Promotion.count_all(active_only=False)

    return render_template(
        'promotions/list.html',
        promotions=promotions,
        search=search,
        active_count=active_count,
        valid_count=valid_count,
        total_count=total_count
    )


@promotion_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('promotion_create')
def create_promotion():
    """
    Crear promoción.
    """
    products = Promotion.get_products_for_form()

    if request.method == 'POST':
        codigo = request.form.get('codigo')
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        tipo_aplicacion = request.form.get('tipo_aplicacion')
        codigo_producto = request.form.get('codigo_producto')
        valor = request.form.get('valor')
        es_porcentaje = request.form.get('es_porcentaje') == 'on'
        compra_minima = request.form.get('compra_minima')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')

        try:
            promotion = Promotion.create(
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion,
                tipo_aplicacion=tipo_aplicacion,
                codigo_producto=codigo_producto,
                valor=valor,
                es_porcentaje=es_porcentaje,
                compra_minima=compra_minima,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                codigo_usuario=session.get('user_id')
            )

            flash(f'Promoción {promotion["nombre"]} creada correctamente.', 'success')
            return redirect(url_for('promotions.list_promotions'))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al crear promoción: {str(e)}', 'danger')

    return render_template(
        'promotions/create.html',
        products=products
    )


@promotion_bp.route('/edit/<codigo>', methods=['GET', 'POST'])
@login_required
@permission_required('promotion_update')
def edit_promotion(codigo):
    """
    Editar promoción.
    """
    promotion = Promotion.find_by_code(codigo)

    if not promotion:
        flash('Promoción no encontrada.', 'danger')
        return redirect(url_for('promotions.list_promotions'))

    products = Promotion.get_products_for_form()

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        tipo_aplicacion = request.form.get('tipo_aplicacion')
        codigo_producto = request.form.get('codigo_producto')
        valor = request.form.get('valor')
        es_porcentaje = request.form.get('es_porcentaje') == 'on'
        compra_minima = request.form.get('compra_minima')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        activo = request.form.get('activo') == 'on'

        try:
            updated = Promotion.update(
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion,
                tipo_aplicacion=tipo_aplicacion,
                codigo_producto=codigo_producto,
                valor=valor,
                es_porcentaje=es_porcentaje,
                compra_minima=compra_minima,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                activo=activo,
                codigo_usuario=session.get('user_id')
            )

            flash(f'Promoción {updated["nombre"]} actualizada correctamente.', 'success')
            return redirect(url_for('promotions.list_promotions'))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al actualizar promoción: {str(e)}', 'danger')

    return render_template(
        'promotions/edit.html',
        promotion=promotion,
        products=products
    )


@promotion_bp.route('/toggle/<codigo>')
@login_required
@permission_required('promotion_toggle')
def toggle_promotion(codigo):
    """
    Activar o desactivar promoción.
    """
    try:
        updated = Promotion.toggle_status(
            codigo=codigo,
            codigo_usuario=session.get('user_id')
        )

        if updated['activo']:
            flash(f'Promoción {updated["nombre"]} activada correctamente.', 'success')
        else:
            flash(f'Promoción {updated["nombre"]} desactivada correctamente.', 'warning')

    except ValueError as e:
        flash(str(e), 'danger')

    except Exception as e:
        flash(f'Error al cambiar estado de la promoción: {str(e)}', 'danger')

    return redirect(url_for('promotions.list_promotions'))