from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.output_note import OutputNote
from utils.decorators import login_required, permission_required


output_note_bp = Blueprint('output_notes', __name__, url_prefix='/output-notes')


@output_note_bp.route('/')
@login_required
@permission_required('output_note_read')
def list_output_notes():
    """
    Listar notas de salida.
    """
    notes = OutputNote.get_all()

    return render_template(
        'output_notes/list.html',
        notes=notes
    )


@output_note_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('output_note_create')
def create_output_note():
    """
    Registrar nueva nota de salida.

    Esta versión trabaja con las tablas reales:
    - public.nota_salida
    - public.detalle_salida
    - public.inventario

    La salida se registra seleccionando directamente un lote de inventario.
    """
    warehouses = OutputNote.get_warehouses()
    available_inventory = OutputNote.get_available_inventory()

    if request.method == 'POST':
        motivo_general = request.form.get('motivo_general')

        inventory_ids = request.form.getlist('id_inventario[]')
        quantities = request.form.getlist('cantidad[]')
        specific_reasons = request.form.getlist('motivo_especifico[]')

        items = []

        for id_inventario, cantidad, motivo_especifico in zip(
            inventory_ids,
            quantities,
            specific_reasons
        ):
            if id_inventario:
                items.append({
                    'id_inventario': id_inventario,
                    'cantidad': cantidad,
                    'motivo_especifico': motivo_especifico
                })

        try:
            note = OutputNote.create_output_note(
                codigo_usuario=session.get('user_id'),
                motivo_general=motivo_general,
                items=items
            )

            flash(f'Nota de salida {note["codigo"]} registrada correctamente.', 'success')
            return redirect(url_for('output_notes.detail_output_note', codigo=note['codigo']))

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al registrar la nota de salida: {str(e)}', 'danger')

    return render_template(
        'output_notes/create.html',
        warehouses=warehouses,
        available_inventory=available_inventory
    )


@output_note_bp.route('/detail/<codigo>')
@login_required
@permission_required('output_note_detail')
def detail_output_note(codigo):
    """
    Ver detalle de una nota de salida.
    """
    note = OutputNote.find_by_code(codigo)

    if not note:
        flash('Nota de salida no encontrada.', 'danger')
        return redirect(url_for('output_notes.list_output_notes'))

    details = OutputNote.get_details(codigo)

    return render_template(
        'output_notes/detail.html',
        note=note,
        details=details
    )


@output_note_bp.route('/cancel/<codigo>')
@login_required
@permission_required('output_note_cancel')
def cancel_output_note(codigo):
    """
    Anular una nota de salida.
    Devuelve el stock al mismo lote de inventario.
    """
    try:
        result = OutputNote.cancel_output_note(
            codigo_nota=codigo,
            codigo_usuario=session.get('user_id')
        )

        if result:
            flash(
                f'Nota de salida {codigo} anulada correctamente. '
                f'El stock fue devuelto al inventario.',
                'success'
            )
        else:
            flash('No se pudo anular la nota de salida.', 'warning')

    except ValueError as e:
        flash(str(e), 'danger')

    except Exception as e:
        flash(f'Error al anular la nota de salida: {str(e)}', 'danger')

    return redirect(url_for('output_notes.detail_output_note', codigo=codigo))