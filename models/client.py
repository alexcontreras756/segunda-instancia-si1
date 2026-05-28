from database.connection import db


class Client:

    @staticmethod
    def validate_tipo_cliente(tipo_cliente):
        """
        Validar tipo de cliente.
        Valores permitidos: temporal o permanente.
        """
        if not tipo_cliente:
            tipo_cliente = 'temporal'

        tipo_cliente = tipo_cliente.lower().strip()

        if tipo_cliente not in ['temporal', 'permanente']:
            raise ValueError('El tipo de cliente debe ser temporal o permanente.')

        return tipo_cliente

    @staticmethod
    def create(ci, nombre, correo_electronico, telefono, tipo_cliente='temporal'):
        """
        Crear nuevo cliente.
        """

        if not ci or not nombre:
            raise ValueError("El Documento (CI) y el Nombre Completo son requeridos.")

        tipo_cliente = Client.validate_tipo_cliente(tipo_cliente)

        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO public.cliente (
                    ci,
                    nombre,
                    correo_electronico,
                    telefono,
                    tipo_cliente
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING
                    id,
                    ci,
                    nombre,
                    correo_electronico,
                    telefono,
                    tipo_cliente
            """, (
                ci,
                nombre,
                correo_electronico,
                telefono,
                tipo_cliente
            ))

            return cursor.fetchone()

    @staticmethod
    def find_by_id(client_id):
        """
        Buscar cliente por ID.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    ci,
                    nombre,
                    correo_electronico,
                    telefono,
                    tipo_cliente
                FROM public.cliente
                WHERE id = %s
            """, (client_id,))

            return cursor.fetchone()

    @staticmethod
    def find_by_ci(ci):
        """
        Buscar cliente por CI.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    ci,
                    nombre,
                    correo_electronico,
                    telefono,
                    tipo_cliente
                FROM public.cliente
                WHERE ci = %s
            """, (ci,))

            return cursor.fetchone()

    @staticmethod
    def find_by_document(document_id):
        """
        Buscar cliente por CI.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    ci,
                    nombre,
                    correo_electronico,
                    telefono,
                    tipo_cliente
                FROM public.cliente
                WHERE ci = %s
            """, (document_id,))

            return cursor.fetchone()

    @staticmethod
    def get_all():
        """
        Obtener todos los clientes.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    ci,
                    nombre,
                    correo_electronico,
                    telefono,
                    tipo_cliente
                FROM public.cliente
                ORDER BY nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def update(client_id, **kwargs):
        """
        Actualizar cliente.
        """

        allowed_fields = [
            'nombre',
            'correo_electronico',
            'telefono',
            'tipo_cliente'
        ]

        updates = []
        values = []

        if 'tipo_cliente' in kwargs:
            kwargs['tipo_cliente'] = Client.validate_tipo_cliente(kwargs['tipo_cliente'])

        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = %s")
                values.append(kwargs[field])

        if not updates:
            return None

        values.append(client_id)

        with db.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE public.cliente
                SET {', '.join(updates)}
                WHERE id = %s
                RETURNING
                    id,
                    ci,
                    nombre,
                    correo_electronico,
                    telefono,
                    tipo_cliente
            """, values)

            return cursor.fetchone()

    @staticmethod
    def delete(client_id):
        """
        Eliminar cliente.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM public.cliente
                WHERE id = %s
                RETURNING id
            """, (client_id,))

            return cursor.fetchone()

    @staticmethod
    def search(term):
        """
        Buscar clientes por término.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    ci,
                    nombre,
                    correo_electronico,
                    telefono,
                    tipo_cliente
                FROM public.cliente
                WHERE nombre ILIKE %s
                   OR ci ILIKE %s
                LIMIT 10
            """, (
                f'%{term}%',
                f'%{term}%'
            ))

            return cursor.fetchall()