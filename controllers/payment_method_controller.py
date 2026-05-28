from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.payment_method import PaymentMethod
from utils.decorators import login_required, permission_required


payment_method_bp = Blueprint(
    'payment_methods',
    __name__,
    url_prefix='/payment-methods'
)


@payment_method_bp.route('/')
@login_required
@permission_required('payment_method_read')
def list_payment_methods():
    """
    Listar métodos de pago.
    """
    search = request.args.get('search', '')

    payment_methods = PaymentMethod.get_all(search=search)
    active_count = PaymentMethod.count_all(active_only=True)
    inactive_count = PaymentMethod.count_inactive()

    return render_template(
        'payment_methods/list.html',
        payment_methods=payment_methods,
        search=search,
        active_count=active_count,
        inactive_count=inactive_count
    )


@payment_method_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('payment_method_create')
def create_payment_method():
    """
    Crear método de pago.
    """
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')

        try:
            payment_method = PaymentMethod.create(
                nombre=nombre,
                descripcion=descripcion,
                codigo_usuario=session.get('user_id')
            )

            flash(
                f'Método de pago {payment_method["nombre"]} creado correctamente.',
                'success'
            )
            return redirect(url_for('payment_methods.list_payment_methods'))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al crear método de pago: {str(e)}', 'danger')

    return render_template('payment_methods/create.html')


@payment_method_bp.route('/edit/<int:payment_method_id>', methods=['GET', 'POST'])
@login_required
@permission_required('payment_method_update')
def edit_payment_method(payment_method_id):
    """
    Editar método de pago.
    """
    payment_method = PaymentMethod.find_by_id(payment_method_id)

    if not payment_method:
        flash('Método de pago no encontrado.', 'danger')
        return redirect(url_for('payment_methods.list_payment_methods'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        activo = request.form.get('activo') == 'on'

        try:
            updated = PaymentMethod.update(
                payment_method_id=payment_method_id,
                nombre=nombre,
                descripcion=descripcion,
                activo=activo,
                codigo_usuario=session.get('user_id')
            )

            flash(
                f'Método de pago {updated["nombre"]} actualizado correctamente.',
                'success'
            )
            return redirect(url_for('payment_methods.list_payment_methods'))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al actualizar método de pago: {str(e)}', 'danger')

    return render_template(
        'payment_methods/edit.html',
        payment_method=payment_method
    )


@payment_method_bp.route('/toggle/<int:payment_method_id>')
@login_required
@permission_required('payment_method_toggle')
def toggle_payment_method(payment_method_id):
    """
    Activar o desactivar método de pago.
    """
    try:
        updated = PaymentMethod.toggle_status(
            payment_method_id=payment_method_id,
            codigo_usuario=session.get('user_id')
        )

        if updated['activo']:
            flash(
                f'Método de pago {updated["nombre"]} activado correctamente.',
                'success'
            )
        else:
            flash(
                f'Método de pago {updated["nombre"]} desactivado correctamente.',
                'warning'
            )

    except ValueError as e:
        flash(str(e), 'danger')

    except Exception as e:
        flash(f'Error al cambiar estado del método de pago: {str(e)}', 'danger')

    return redirect(url_for('payment_methods.list_payment_methods'))