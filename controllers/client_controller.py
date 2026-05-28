from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.client import Client
from utils.decorators import login_required, permission_required


client_bp = Blueprint('clients', __name__, url_prefix='/clients')


@client_bp.route('/')
@login_required
@permission_required('client_read')
def list_clients():
    """Listar clientes"""
    clients = Client.get_all()
    return render_template('clients/list.html', clients=clients)


@client_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('client_create')
def create_client():
    """Crear cliente"""
    if request.method == 'POST':
        ci = request.form.get('ci')
        nombre = request.form.get('nombre')
        correo_electronico = request.form.get('email')
        telefono = request.form.get('telefono')
        tipo_cliente = request.form.get('tipo_cliente')

        if not all([ci, nombre, tipo_cliente]):
            flash('Documento, nombre y tipo de cliente son requeridos', 'danger')
            return render_template('clients/create.html')

        existing = Client.find_by_document(ci)

        if existing:
            flash('Ya existe un cliente con ese documento', 'danger')
            return render_template('clients/create.html')

        try:
            client = Client.create(
                ci,
                nombre,
                correo_electronico,
                telefono,
                tipo_cliente
            )

            if client:
                flash(f'Cliente {client["nombre"]} creado exitosamente', 'success')
                return redirect(url_for('clients.list_clients'))
            else:
                flash('Error al crear el cliente', 'danger')

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al crear el cliente: {str(e)}', 'danger')

    return render_template('clients/create.html')


@client_bp.route('/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
@permission_required('client_update')
def edit_client(client_id):
    """Editar cliente"""
    client = Client.find_by_id(client_id)

    if not client:
        flash('Cliente no encontrado', 'danger')
        return redirect(url_for('clients.list_clients'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo_electronico = request.form.get('email')
        telefono = request.form.get('telefono')
        tipo_cliente = request.form.get('tipo_cliente')

        if not all([nombre, tipo_cliente]):
            flash('El nombre del cliente y el tipo de cliente son obligatorios', 'danger')
            return render_template('clients/edit.html', client=client)

        try:
            updated_client = Client.update(
                client_id,
                nombre=nombre,
                correo_electronico=correo_electronico,
                telefono=telefono,
                tipo_cliente=tipo_cliente
            )

            if updated_client:
                flash(f'Cliente {updated_client["nombre"]} actualizado exitosamente', 'success')
                return redirect(url_for('clients.list_clients'))
            else:
                flash('Error al actualizar el cliente', 'danger')

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            flash(f'Error al actualizar el cliente: {str(e)}', 'danger')

    return render_template('clients/edit.html', client=client)


@client_bp.route('/delete/<int:client_id>')
@login_required
@permission_required('client_delete')
def delete_client(client_id):
    """Eliminar cliente"""
    result = Client.delete(client_id)

    if result:
        flash('Cliente eliminado exitosamente', 'success')
    else:
        flash('Error al eliminar el cliente', 'danger')

    return redirect(url_for('clients.list_clients'))


@client_bp.route('/search')
@login_required
def search_clients():
    """API: Buscar clientes"""
    term = request.args.get('term', '')

    if len(term) < 2:
        return jsonify([])

    clients = Client.search(term)

    return jsonify([{
        'id': c['id'],
        'document_id': c['ci'],
        'full_name': c['nombre'],
        'email': c['correo_electronico'],
        'phone': c['telefono'],
        'tipo_cliente': c['tipo_cliente']
    } for c in clients])