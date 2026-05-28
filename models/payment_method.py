from database.connection import db


class PaymentMethod:

    @staticmethod
    def _clean_name(nombre):
        """
        Limpiar y validar nombre del método de pago.
        """
        if not nombre or not str(nombre).strip():
            raise ValueError('El nombre del método de pago es obligatorio.')

        nombre = str(nombre).strip()

        if len(nombre) < 2:
            raise ValueError('El nombre del método de pago debe tener al menos 2 caracteres.')

        if len(nombre) > 50:
            raise ValueError('El nombre del método de pago no puede superar los 50 caracteres.')

        return nombre

    @staticmethod
    def _clean_description(descripcion):
        """
        Limpiar descripción.
        """
        if descripcion is None:
            return None

        descripcion = str(descripcion).strip()

        if descripcion == '':
            return None

        if len(descripcion) > 150:
            raise ValueError('La descripción no puede superar los 150 caracteres.')

        return descripcion

    @staticmethod
    def count_all(active_only=True):
        """
        Contar métodos de pago.
        Por defecto cuenta solo activos para el dashboard.
        """
        with db.get_cursor() as cursor:
            if active_only:
                cursor.execute("""
                    SELECT COUNT(*) AS total
                    FROM public.tipo_pago
                    WHERE activo = true
                """)
            else:
                cursor.execute("""
                    SELECT COUNT(*) AS total
                    FROM public.tipo_pago
                """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def count_inactive():
        """
        Contar métodos de pago inactivos.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM public.tipo_pago
                WHERE activo = false
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_all(search=None):
        """
        Obtener todos los métodos de pago.
        Incluye activos e inactivos.
        """
        search = search.strip() if search else None
        params = []

        query = """
            SELECT
                id,
                nombre,
                descripcion,
                activo
            FROM public.tipo_pago
            WHERE 1 = 1
        """

        if search:
            query += """
                AND (
                    nombre ILIKE %s
                    OR descripcion ILIKE %s
                )
            """
            term = f'%{search}%'
            params.extend([term, term])

        query += """
            ORDER BY activo DESC, nombre ASC
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    @staticmethod
    def get_active():
        """
        Obtener métodos de pago activos.
        Se puede reutilizar si luego quieres centralizar la lógica de ventas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    nombre,
                    descripcion,
                    activo
                FROM public.tipo_pago
                WHERE activo = true
                ORDER BY nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def find_by_id(payment_method_id):
        """
        Buscar método de pago por ID.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    nombre,
                    descripcion,
                    activo
                FROM public.tipo_pago
                WHERE id = %s
            """, (payment_method_id,))

            return cursor.fetchone()

    @staticmethod
    def find_by_name(nombre, exclude_id=None):
        """
        Buscar método de pago por nombre, ignorando mayúsculas/minúsculas.
        Sirve para evitar duplicados.
        """
        nombre = PaymentMethod._clean_name(nombre)

        with db.get_cursor() as cursor:
            if exclude_id:
                cursor.execute("""
                    SELECT
                        id,
                        nombre,
                        descripcion,
                        activo
                    FROM public.tipo_pago
                    WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
                    AND id <> %s
                    LIMIT 1
                """, (nombre, exclude_id))
            else:
                cursor.execute("""
                    SELECT
                        id,
                        nombre,
                        descripcion,
                        activo
                    FROM public.tipo_pago
                    WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
                    LIMIT 1
                """, (nombre,))

            return cursor.fetchone()

    @staticmethod
    def create(nombre, descripcion=None, codigo_usuario=None):
        """
        Crear método de pago.
        No permite nombres duplicados.
        """
        nombre = PaymentMethod._clean_name(nombre)
        descripcion = PaymentMethod._clean_description(descripcion)

        existing = PaymentMethod.find_by_name(nombre)

        if existing:
            raise ValueError('Ya existe un método de pago con ese nombre.')

        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO public.tipo_pago (
                    nombre,
                    descripcion,
                    activo
                )
                VALUES (%s, %s, true)
                RETURNING
                    id,
                    nombre,
                    descripcion,
                    activo
            """, (
                nombre,
                descripcion
            ))

            payment_method = cursor.fetchone()

            if codigo_usuario:
                cursor.execute("""
                    INSERT INTO public.historial (
                        codigo_usuario,
                        accion,
                        tabla_afectada,
                        id_registro_afectado,
                        valor_nuevo,
                        fecha_hora
                    )
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    codigo_usuario,
                    'CREACIÓN DE MÉTODO DE PAGO',
                    'tipo_pago',
                    str(payment_method['id']),
                    f'Método de pago creado: {payment_method["nombre"]}'
                ))

            return payment_method

    @staticmethod
    def update(payment_method_id, nombre, descripcion=None, activo=True, codigo_usuario=None):
        """
        Actualizar método de pago.
        No cambia ni elimina ventas históricas.
        """
        payment_method = PaymentMethod.find_by_id(payment_method_id)

        if not payment_method:
            raise ValueError('El método de pago no existe.')

        nombre = PaymentMethod._clean_name(nombre)
        descripcion = PaymentMethod._clean_description(descripcion)

        existing = PaymentMethod.find_by_name(nombre, exclude_id=payment_method_id)

        if existing:
            raise ValueError('Ya existe otro método de pago con ese nombre.')

        activo = bool(activo)

        if activo is False:
            active_count = PaymentMethod.count_all(active_only=True)

            if payment_method['activo'] is True and active_count <= 1:
                raise ValueError(
                    'No se puede desactivar el único método de pago activo. '
                    'Debe existir al menos un método activo para registrar ventas.'
                )

        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public.tipo_pago
                SET
                    nombre = %s,
                    descripcion = %s,
                    activo = %s
                WHERE id = %s
                RETURNING
                    id,
                    nombre,
                    descripcion,
                    activo
            """, (
                nombre,
                descripcion,
                activo,
                payment_method_id
            ))

            updated = cursor.fetchone()

            if codigo_usuario:
                cursor.execute("""
                    INSERT INTO public.historial (
                        codigo_usuario,
                        accion,
                        tabla_afectada,
                        id_registro_afectado,
                        valor_nuevo,
                        fecha_hora
                    )
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    codigo_usuario,
                    'ACTUALIZACIÓN DE MÉTODO DE PAGO',
                    'tipo_pago',
                    str(updated['id']),
                    f'Método de pago actualizado: {updated["nombre"]}. Activo: {updated["activo"]}'
                ))

            return updated

    @staticmethod
    def toggle_status(payment_method_id, codigo_usuario=None):
        """
        Activar o desactivar método de pago.
        No elimina físicamente para no dañar ventas ni caja.
        """
        payment_method = PaymentMethod.find_by_id(payment_method_id)

        if not payment_method:
            raise ValueError('El método de pago no existe.')

        new_status = not payment_method['activo']

        if new_status is False:
            active_count = PaymentMethod.count_all(active_only=True)

            if payment_method['activo'] is True and active_count <= 1:
                raise ValueError(
                    'No se puede desactivar el único método de pago activo. '
                    'Debe existir al menos un método activo para registrar ventas.'
                )

        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public.tipo_pago
                SET activo = %s
                WHERE id = %s
                RETURNING
                    id,
                    nombre,
                    descripcion,
                    activo
            """, (
                new_status,
                payment_method_id
            ))

            updated = cursor.fetchone()

            if codigo_usuario:
                accion = (
                    'ACTIVACIÓN DE MÉTODO DE PAGO'
                    if updated['activo']
                    else 'DESACTIVACIÓN DE MÉTODO DE PAGO'
                )

                cursor.execute("""
                    INSERT INTO public.historial (
                        codigo_usuario,
                        accion,
                        tabla_afectada,
                        id_registro_afectado,
                        valor_nuevo,
                        fecha_hora
                    )
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    codigo_usuario,
                    accion,
                    'tipo_pago',
                    str(updated['id']),
                    f'Método de pago {updated["nombre"]}. Activo: {updated["activo"]}'
                ))

            return updated