from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.categoria import Categoria
from services.categoria_service import CategoriaService
from utils.decorators import login_required, permission_required

categorias_bp = Blueprint('categorias', __name__, url_prefix='/categorias')


@categorias_bp.route('/')
@login_required
@permission_required('category_read')
def listar_categorias():
    """Listar categorías con búsqueda y filtrado"""
    search = request.args.get('search', '').strip()
    estado = request.args.get('estado', '').strip()

    categorias = Categoria.get_all(search=search, estado=estado)
    return render_template(
        'categorias/list.html',
        categorias=categorias,
        search=search,
        estado=estado
    )


@categorias_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
@permission_required('category_create')
def crear_categoria():
    """Registrar nueva categoría"""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        id_padre = request.form.get('id_padre', '').strip()

        try:
            CategoriaService.register_category(nombre, descripcion, id_padre, estado=True)
            flash('Categoría registrada correctamente', 'success')
            return redirect(url_for('categorias.listar_categorias'))
        except ValueError as e:
            flash(str(e), 'danger')

    # Cargar las categorías existentes para elegir padre (solo activas)
    categorias_padres = Categoria.get_all(estado='activo')
    return render_template('categorias/create.html', categorias=categorias_padres)


@categorias_bp.route('/<int:category_id>')
@login_required
@permission_required('category_read')
def ver_categoria(category_id):
    """Consultar detalle de una categoría (sólo lectura)"""
    categoria = Categoria.find_by_id(category_id)
    if not categoria:
        flash('Categoría no encontrada', 'danger')
        return redirect(url_for('categorias.listar_categorias'))

    return render_template('categorias/detail.html', categoria=categoria)


@categorias_bp.route('/<int:category_id>/editar', methods=['GET', 'POST'])
@login_required
@permission_required('category_update')
def editar_categoria(category_id):
    """Modificar categoría"""
    categoria = Categoria.find_by_id(category_id)
    if not categoria:
        flash('Categoría no encontrada', 'danger')
        return redirect(url_for('categorias.listar_categorias'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        id_padre = request.form.get('id_padre', '').strip()
        estado = 'estado' in request.form

        try:
            CategoriaService.update_category(category_id, nombre, descripcion, id_padre, estado)
            flash('Categoría actualizada correctamente', 'success')
            return redirect(url_for('categorias.listar_categorias'))
        except ValueError as e:
            flash(str(e), 'danger')

    # Cargar las categorías activas (excluyéndose a sí misma) para el select de padre
    todas_categorias = Categoria.get_all(estado='activo')
    categorias_padres = [c for c in todas_categorias if int(c['id']) != int(category_id)]

    return render_template(
        'categorias/edit.html',
        categoria=categoria,
        categorias=categorias_padres
    )


@categorias_bp.route('/<int:category_id>/estado', methods=['POST'])
@login_required
@permission_required('category_toggle')
def cambiar_estado(category_id):
    """Activar y desactivar categoría"""
    categoria = Categoria.find_by_id(category_id)
    if not categoria:
        flash('Categoría no encontrada', 'danger')
        return redirect(url_for('categorias.listar_categorias'))

    nuevo_estado = not categoria['estado']

    try:
        CategoriaService.toggle_category_status(category_id, nuevo_estado)
        if nuevo_estado:
            flash('Categoría activada correctamente', 'success')
        else:
            flash('Categoría desactivada correctamente', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('categorias.listar_categorias'))


@categorias_bp.route('/<int:category_id>/eliminar', methods=['POST'])
@login_required
@permission_required('category_update')
def eliminar_categoria(category_id):
    """Eliminar físicamente una categoría"""
    try:
        CategoriaService.delete_category(category_id)
        flash('Categoría eliminada correctamente', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('categorias.listar_categorias'))
