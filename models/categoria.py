from database.connection import db


class Categoria:

    @staticmethod
    def get_all(search=None, estado=None):
        """
        Obtener todas las categorías ordenadas por nombre de manera ascendente.
        Incluye el nombre del padre y la cantidad de productos asociados.
        """
        query = """
            SELECT 
                c.id, 
                c.nombre, 
                c.descripcion, 
                c.id_padre, 
                c.estado, 
                cp.nombre AS padre_nombre,
                COALESCE(p_count.total, 0) AS total_productos
            FROM public.categoria c
            LEFT JOIN public.categoria cp ON c.id_padre = cp.id
            LEFT JOIN (
                SELECT id_categoria, COUNT(*) AS total
                FROM public.producto
                GROUP BY id_categoria
            ) p_count ON c.id = p_count.id_categoria
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (c.nombre ILIKE %s OR c.descripcion ILIKE %s)"
            search_param = f"%{search.strip()}%"
            params.extend([search_param, search_param])

        if estado == 'activo':
            query += " AND c.estado = true"
        elif estado == 'inactivo':
            query += " AND c.estado = false"

        query += " ORDER BY c.nombre ASC"

        with db.get_cursor() as cursor:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    @staticmethod
    def find_by_id(category_id):
        """Buscar categoría por su ID"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    c.id, 
                    c.nombre, 
                    c.descripcion, 
                    c.id_padre, 
                    c.estado, 
                    cp.nombre AS padre_nombre,
                    (SELECT COUNT(*) FROM public.producto p WHERE p.id_categoria = c.id) AS total_productos
                FROM public.categoria c
                LEFT JOIN public.categoria cp ON c.id_padre = cp.id
                WHERE c.id = %s
            """, (category_id,))
            return cursor.fetchone()

    @staticmethod
    def find_by_name(name):
        """Buscar categoría por nombre (insensible a mayúsculas y sin espacios al inicio/final)"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, nombre, descripcion, id_padre, estado
                FROM public.categoria
                WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
            """, (name,))
            return cursor.fetchone()

    @staticmethod
    def create(nombre, descripcion, id_padre, estado=True):
        """Crear una nueva categoría"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO public.categoria (nombre, descripcion, id_padre, estado)
                VALUES (%s, %s, %s, %s)
                RETURNING id, nombre, descripcion, id_padre, estado
            """, (nombre.strip(), descripcion.strip() if descripcion else None, id_padre, estado))
            return cursor.fetchone()

    @staticmethod
    def update(category_id, nombre, descripcion, id_padre, estado):
        """Actualizar una categoría existente"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public.categoria
                SET 
                    nombre = %s,
                    descripcion = %s,
                    id_padre = %s,
                    estado = %s
                WHERE id = %s
                RETURNING id, nombre, descripcion, id_padre, estado
            """, (nombre.strip(), descripcion.strip() if descripcion else None, id_padre, estado, category_id))
            return cursor.fetchone()

    @staticmethod
    def toggle_status(category_id, estado):
        """Activar o desactivar categoría"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public.categoria
                SET estado = %s
                WHERE id = %s
                RETURNING id, nombre, estado
            """, (estado, category_id))
            return cursor.fetchone()

    @staticmethod
    def delete(category_id):
        """Eliminar físicamente una categoría"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM public.categoria
                WHERE id = %s
                RETURNING id
            """, (category_id,))
            return cursor.fetchone()

    @staticmethod
    def has_products(category_id):
        """Verifica si la categoría tiene productos asociados"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 1 
                FROM public.producto 
                WHERE id_categoria = %s 
                LIMIT 1
            """, (category_id,))
            return cursor.fetchone() is not None
