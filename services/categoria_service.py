from models.categoria import Categoria


class CategoriaService:

    @staticmethod
    def validate_category_data(nombre, descripcion, id_padre, category_id=None):
        """
        Validaciones comunes de datos para registro y edición.
        """
        if not nombre or not nombre.strip():
            raise ValueError("El nombre de la categoría es obligatorio.")

        if len(nombre) > 100:
            raise ValueError("El nombre no puede exceder los 100 caracteres.")

        if descripcion and len(descripcion) > 150:
            raise ValueError("La descripción no puede exceder los 150 caracteres.")

        # Evitar que una categoría sea su propia categoría padre
        if id_padre and category_id and int(id_padre) == int(category_id):
            raise ValueError("Una categoría no puede ser su propia categoría padre.")

        # Validar duplicados (insensible a mayúsculas/minúsculas y espacios)
        existing = Categoria.find_by_name(nombre.strip())
        if existing:
            # Si estamos editando y el ID coincide, no es duplicado.
            if category_id is None or int(existing['id']) != int(category_id):
                raise ValueError("Ya existe una categoría con este nombre.")

    @staticmethod
    def register_category(nombre, descripcion, id_padre, estado=True):
        """
        Registrar una nueva categoría aplicando reglas de negocio.
        """
        id_padre_val = int(id_padre) if id_padre and str(id_padre).strip() else None

        CategoriaService.validate_category_data(nombre, descripcion, id_padre_val)

        return Categoria.create(nombre, descripcion, id_padre_val, estado)

    @staticmethod
    def update_category(category_id, nombre, descripcion, id_padre, estado):
        """
        Actualizar una categoría existente aplicando reglas de negocio.
        """
        id_padre_val = int(id_padre) if id_padre and str(id_padre).strip() else None
        estado_val = bool(estado)

        CategoriaService.validate_category_data(nombre, descripcion, id_padre_val, category_id)

        # Verificar que la categoría existe
        category = Categoria.find_by_id(category_id)
        if not category:
            raise ValueError("La categoría a editar no existe.")

        return Categoria.update(category_id, nombre, descripcion, id_padre_val, estado_val)

    @staticmethod
    def toggle_category_status(category_id, estado):
        """
        Activar o desactivar categoría.
        """
        category = Categoria.find_by_id(category_id)
        if not category:
            raise ValueError("La categoría no existe.")

        return Categoria.toggle_status(category_id, bool(estado))

    @staticmethod
    def delete_category(category_id):
        """
        Eliminar físicamente una categoría si no tiene productos asociados.
        """
        category = Categoria.find_by_id(category_id)
        if not category:
            raise ValueError("La categoría no existe.")

        if Categoria.has_products(category_id):
            raise ValueError(
                "No es posible eliminar esta categoría porque tiene productos asociados. "
                "Puede desactivarla o reasignar los productos primero."
            )

        return Categoria.delete(category_id)
