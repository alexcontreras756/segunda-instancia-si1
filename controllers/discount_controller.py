from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.discount import Discount
from utils.decorators import login_required, permission_required


discount_bp = Blueprint(
    'discounts',
    __name__,
    url_prefix='/discounts'
)


@discount_bp.route('/')
@login_required
@permission_required('discount_read')
def list_discounts():
    """
    Listar descuentos.
    """
    search = request.args.get('search', '')

    discounts = Discount.get_all(search=search)
    active_count = Discount.count_all(active_only=True)
    inactive_count = Discount.count_inactive()

    return render_template(
        'discounts/list.html',
        discounts=discounts,
        search=search,
        active_count=active_count,
        inactive_count=inactive_count
    )


@discount_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('discount_create')
def create_discount():
    """
    Crear descuento.
    """
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        descripcion = request.form.get('descripcion')
        valor = request.form.get('valor')
        es_porcentaje = request.form.get('es_porcentaje') == 'on'
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')

        try:
            discount = Discount.create(
                codigo=codigo,
                descripcion=descripcion,
                valor=valor,
                es_porcentaje=es_porcentaje,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                codigo_usuario=session.get('user_id')
            )

            flash(
                f'Descuento {discount["codigo"]} creado correctamente.',
                'success'
            )
            return redirect(url_for('discounts.list_discounts'))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al crear descuento: {str(e)}', 'danger')

    return render_template('discounts/create.html')


@discount_bp.route('/edit/<codigo>', methods=['GET', 'POST'])
@login_required
@permission_required('discount_update')
def edit_discount(codigo):
    """
    Editar descuento.
    """
    discount = Discount.find_by_code(codigo)

    if not discount:
        flash('Descuento no encontrado.', 'danger')
        return redirect(url_for('discounts.list_discounts'))

    if request.method == 'POST':
        descripcion = request.form.get('descripcion')
        valor = request.form.get('valor')
        es_porcentaje = request.form.get('es_porcentaje') == 'on'
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        activo = request.form.get('activo') == 'on'

        try:
            updated = Discount.update(
                codigo=codigo,
                descripcion=descripcion,
                valor=valor,
                es_porcentaje=es_porcentaje,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                activo=activo,
                codigo_usuario=session.get('user_id')
            )

            flash(
                f'Descuento {updated["codigo"]} actualizado correctamente.',
                'success'
            )
            return redirect(url_for('discounts.list_discounts'))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al actualizar descuento: {str(e)}', 'danger')

    return render_template(
        'discounts/edit.html',
        discount=discount
    )


@discount_bp.route('/toggle/<codigo>')
@login_required
@permission_required('discount_toggle')
def toggle_discount(codigo):
    """
    Activar o desactivar descuento.
    """
    try:
        updated = Discount.toggle_status(
            codigo=codigo,
            codigo_usuario=session.get('user_id')
        )

        if updated['activo']:
            flash(
                f'Descuento {updated["codigo"]} activado correctamente.',
                'success'
            )
        else:
            flash(
                f'Descuento {updated["codigo"]} desactivado correctamente.',
                'warning'
            )

    except ValueError as e:
        flash(str(e), 'danger')

    except Exception as e:
        flash(f'Error al cambiar estado del descuento: {str(e)}', 'danger')

    return redirect(url_for('discounts.list_discounts'))