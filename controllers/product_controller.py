from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.product import Product
from models.categoria import Categoria
from utils.decorators import login_required, permission_required

product_bp = Blueprint('products', __name__, url_prefix='/products')


@product_bp.route('/')
@login_required
@permission_required('product_read')
def list_products():
    """Listar productos"""
    products = Product.get_all()
    return render_template('products/list.html', products=products)


@product_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('product_create')
def create_product():
    """Crear producto"""
    categories = Categoria.get_all(estado='activo')

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        stock = request.form.get('stock')
        category_id = request.form.get('category_id')

        if not all([name, price, stock, category_id]):
            flash('Todos los campos son obligatorios', 'danger')
            return render_template('products/create.html', categories=categories)

        try:
            price = float(price)
            stock = int(stock)
            category_id = int(category_id)
        except ValueError:
            flash('El precio, el stock y la categoría deben ser válidos', 'danger')
            return render_template('products/create.html', categories=categories)

        if price <= 0 or stock < 0:
            flash('El precio debe ser mayor a 0 y el stock no puede ser negativo', 'danger')
            return render_template('products/create.html', categories=categories)

        product = Product.create(name, price, stock, category_id)

        if product:
            flash(f'Producto {product["nombre"]} creado exitosamente', 'success')
            return redirect(url_for('products.list_products'))
        else:
            flash('Error al crear el producto', 'danger')

    return render_template('products/create.html')


@product_bp.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@permission_required('product_update')
def edit_product(product_id):
    """Editar producto"""
    product = Product.find_by_id(product_id)

    if not product:
        flash('Producto no encontrado', 'danger')
        return redirect(url_for('products.list_products'))

    # Cargar las categorías activas y asegurar incluir la categoría actual del producto
    categories = Categoria.get_all(estado='activo')
    current_category_id = product.get('id_categoria')
    if current_category_id and not any(int(c['id']) == int(current_category_id) for c in categories):
        current_cat = Categoria.find_by_id(current_category_id)
        if current_cat:
            categories.append(current_cat)

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        stock = request.form.get('stock')
        category_id = request.form.get('category_id')
        estado = 'estado' in request.form

        if not all([name, price, stock, category_id]):
            flash('Todos los campos son obligatorios', 'danger')
            return render_template('products/edit.html', product=product, categories=categories)

        try:
            price = float(price)
            stock = int(stock)
            category_id = int(category_id)
        except ValueError:
            flash('El precio, el stock y la categoría deben ser válidos', 'danger')
            return render_template('products/edit.html', product=product, categories=categories)

        if price <= 0 or stock < 0:
            flash('El precio debe ser mayor a 0 y el stock no puede ser negativo', 'danger')
            return render_template('products/edit.html', product=product, categories=categories)

        updated_product = Product.update(product_id, name, price, stock, category_id, estado)

        if updated_product:
            flash(f'Producto {updated_product["nombre"]} actualizado exitosamente', 'success')
            return redirect(url_for('products.list_products'))
        else:
            flash('Error al actualizar el producto', 'danger')

    return render_template('products/edit.html', product=product)


@product_bp.route('/delete/<int:product_id>')
@login_required
@permission_required('product_delete')
def delete_product(product_id):
    """Eliminar producto"""
    result = Product.delete(product_id)

    if result:
        flash('Producto eliminado exitosamente', 'success')
    else:
        flash('Error al eliminar el producto', 'danger')

    return redirect(url_for('products.list_products'))