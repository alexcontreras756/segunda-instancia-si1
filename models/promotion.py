from database.connection import db
from decimal import Decimal
from datetime import date


class Promotion:

    @staticmethod
    def _clean_code(codigo):
        if not codigo or not str(codigo).strip():
            raise ValueError('El código de la promoción es obligatorio.')

        codigo = str(codigo).strip().upper()

        if len(codigo) < 3:
            raise ValueError('El código debe tener al menos 3 caracteres.')

        if len(codigo) > 20:
            raise ValueError('El código no puede superar los 20 caracteres.')

        return codigo

    @staticmethod
    def _clean_name(nombre):
        if not nombre or not str(nombre).strip():
            raise ValueError('El nombre de la promoción es obligatorio.')

        nombre = str(nombre).strip()

        if len(nombre) < 3:
            raise ValueError('El nombre debe tener al menos 3 caracteres.')

        if len(nombre) > 100:
            raise ValueError('El nombre no puede superar los 100 caracteres.')

        return nombre

    @staticmethod
    def _clean_text(value):
        if value is None:
            return None

        value = str(value).strip()

        if value == '':
            return None

        return value

    @staticmethod
    def _to_decimal(value, field_name='valor'):
        if value is None or str(value).strip() == '':
            raise ValueError(f'El campo {field_name} es obligatorio.')

        value = str(value).strip().replace(',', '.')

        try:
            number = Decimal(value)
        except Exception:
            raise ValueError(f'El campo {field_name} debe ser un valor numérico.')

        return number

    @staticmethod
    def _validate_tipo_aplicacion(tipo_aplicacion):
        if not tipo_aplicacion:
            tipo_aplicacion = 'monto'

        tipo_aplicacion = str(tipo_aplicacion).strip().lower()

        if tipo_aplicacion not in ['monto', 'producto']:
            raise ValueError('El tipo de aplicación debe ser monto o producto.')

        return tipo_aplicacion

    @staticmethod
    def _validate_dates(fecha_inicio, fecha_fin):
        if not fecha_inicio:
            raise ValueError('La fecha de inicio es obligatoria.')

        if not fecha_fin:
            raise ValueError('La fecha de fin es obligatoria.')

        if fecha_fin < fecha_inicio:
            raise ValueError('La fecha de fin no puede ser menor que la fecha de inicio.')

    @staticmethod
    def count_all(active_only=False):
        with db.get_cursor() as cursor:
            if active_only:
                cursor.execute("""
                    SELECT COUNT(*) AS total
                    FROM public.promocion
                    WHERE activo = true
                """)
            else:
                cursor.execute("""
                    SELECT COUNT(*) AS total
                    FROM public.promocion
                """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def count_active_valid():
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM public.promocion
                WHERE activo = true
                AND CURRENT_DATE BETWEEN fecha_inicio AND fecha_fin
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_products_for_form():
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    precio_venta,
                    estado
                FROM public.producto
                WHERE estado = true
                ORDER BY nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def get_all(search=None):
        search = search.strip() if search else None
        params = []

        query = """
            SELECT
                pr.codigo,
                pr.nombre,
                pr.descripcion,
                pr.tipo_aplicacion,
                pr.codigo_producto,
                p.nombre AS producto,
                pr.valor,
                pr.es_porcentaje,
                pr.compra_minima,
                pr.fecha_inicio,
                pr.fecha_fin,
                pr.activo,
                pr.fecha_creacion,
                CASE
                    WHEN pr.activo = true
                    AND CURRENT_DATE BETWEEN pr.fecha_inicio AND pr.fecha_fin
                    THEN true
                    ELSE false
                END AS vigente
            FROM public.promocion pr
            LEFT JOIN public.producto p ON pr.codigo_producto = p.codigo
            WHERE 1 = 1
        """

        if search:
            query += """
                AND (
                    pr.codigo ILIKE %s
                    OR pr.nombre ILIKE %s
                    OR pr.descripcion ILIKE %s
                    OR p.nombre ILIKE %s
                )
            """
            term = f'%{search}%'
            params.extend([term, term, term, term])

        query += """
            ORDER BY
                pr.activo DESC,
                pr.fecha_inicio DESC,
                pr.codigo ASC
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    @staticmethod
    def get_active_valid():
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    pr.codigo,
                    pr.nombre,
                    pr.descripcion,
                    pr.tipo_aplicacion,
                    pr.codigo_producto,
                    p.nombre AS producto,
                    pr.valor,
                    pr.es_porcentaje,
                    pr.compra_minima,
                    pr.fecha_inicio,
                    pr.fecha_fin,
                    pr.activo
                FROM public.promocion pr
                LEFT JOIN public.producto p ON pr.codigo_producto = p.codigo
                WHERE pr.activo = true
                AND CURRENT_DATE BETWEEN pr.fecha_inicio AND pr.fecha_fin
                ORDER BY pr.nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def find_by_code(codigo):
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    pr.codigo,
                    pr.nombre,
                    pr.descripcion,
                    pr.tipo_aplicacion,
                    pr.codigo_producto,
                    p.nombre AS producto,
                    pr.valor,
                    pr.es_porcentaje,
                    pr.compra_minima,
                    pr.fecha_inicio,
                    pr.fecha_fin,
                    pr.activo,
                    pr.fecha_creacion
                FROM public.promocion pr
                LEFT JOIN public.producto p ON pr.codigo_producto = p.codigo
                WHERE pr.codigo = %s
            """, (codigo,))

            return cursor.fetchone()

    @staticmethod
    def find_by_name(nombre, exclude_codigo=None):
        nombre = Promotion._clean_name(nombre)

        with db.get_cursor() as cursor:
            if exclude_codigo:
                cursor.execute("""
                    SELECT codigo, nombre
                    FROM public.promocion
                    WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
                    AND codigo <> %s
                    LIMIT 1
                """, (nombre, exclude_codigo))
            else:
                cursor.execute("""
                    SELECT codigo, nombre
                    FROM public.promocion
                    WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
                    LIMIT 1
                """, (nombre,))

            return cursor.fetchone()

    @staticmethod
    def create(
        codigo,
        nombre,
        descripcion,
        tipo_aplicacion,
        codigo_producto,
        valor,
        es_porcentaje,
        compra_minima,
        fecha_inicio,
        fecha_fin,
        codigo_usuario=None
    ):
        codigo = Promotion._clean_code(codigo)
        nombre = Promotion._clean_name(nombre)
        descripcion = Promotion._clean_text(descripcion)
        tipo_aplicacion = Promotion._validate_tipo_aplicacion(tipo_aplicacion)

        valor = Promotion._to_decimal(valor, 'valor')

        if valor <= 0:
            raise ValueError('El valor de la promoción debe ser mayor a cero.')

        es_porcentaje = bool(es_porcentaje)

        if es_porcentaje and valor > 100:
            raise ValueError('Si la promoción es porcentaje, el valor no puede superar 100.')

        if compra_minima is None or str(compra_minima).strip() == '':
            compra_minima = Decimal('0.00')
        else:
            compra_minima = Promotion._to_decimal(compra_minima, 'compra mínima')

        if compra_minima < 0:
            raise ValueError('La compra mínima no puede ser negativa.')

        Promotion._validate_dates(fecha_inicio, fecha_fin)

        if tipo_aplicacion == 'producto':
            if not codigo_producto:
                raise ValueError('Debe seleccionar un producto para una promoción por producto.')
        else:
            codigo_producto = None

        existing_code = Promotion.find_by_code(codigo)

        if existing_code:
            raise ValueError('Ya existe una promoción con ese código.')

        existing_name = Promotion.find_by_name(nombre)

        if existing_name:
            raise ValueError('Ya existe una promoción con ese nombre.')

        with db.get_cursor() as cursor:
            if codigo_producto:
                cursor.execute("""
                    SELECT codigo
                    FROM public.producto
                    WHERE codigo = %s
                    AND estado = true
                """, (codigo_producto,))

                product = cursor.fetchone()

                if not product:
                    raise ValueError('El producto seleccionado no existe o está inactivo.')

            cursor.execute("""
                INSERT INTO public.promocion (
                    codigo,
                    nombre,
                    descripcion,
                    tipo_aplicacion,
                    codigo_producto,
                    valor,
                    es_porcentaje,
                    compra_minima,
                    fecha_inicio,
                    fecha_fin,
                    activo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
                RETURNING
                    codigo,
                    nombre,
                    descripcion,
                    tipo_aplicacion,
                    codigo_producto,
                    valor,
                    es_porcentaje,
                    compra_minima,
                    fecha_inicio,
                    fecha_fin,
                    activo
            """, (
                codigo,
                nombre,
                descripcion,
                tipo_aplicacion,
                codigo_producto,
                valor,
                es_porcentaje,
                compra_minima,
                fecha_inicio,
                fecha_fin
            ))

            promotion = cursor.fetchone()

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
                    'CREACIÓN DE PROMOCIÓN',
                    'promocion',
                    codigo,
                    f'Promoción creada: {nombre}'
                ))

            return promotion

    @staticmethod
    def update(
        codigo,
        nombre,
        descripcion,
        tipo_aplicacion,
        codigo_producto,
        valor,
        es_porcentaje,
        compra_minima,
        fecha_inicio,
        fecha_fin,
        activo,
        codigo_usuario=None
    ):
        promotion = Promotion.find_by_code(codigo)

        if not promotion:
            raise ValueError('La promoción no existe.')

        nombre = Promotion._clean_name(nombre)
        descripcion = Promotion._clean_text(descripcion)
        tipo_aplicacion = Promotion._validate_tipo_aplicacion(tipo_aplicacion)

        valor = Promotion._to_decimal(valor, 'valor')

        if valor <= 0:
            raise ValueError('El valor de la promoción debe ser mayor a cero.')

        es_porcentaje = bool(es_porcentaje)

        if es_porcentaje and valor > 100:
            raise ValueError('Si la promoción es porcentaje, el valor no puede superar 100.')

        if compra_minima is None or str(compra_minima).strip() == '':
            compra_minima = Decimal('0.00')
        else:
            compra_minima = Promotion._to_decimal(compra_minima, 'compra mínima')

        if compra_minima < 0:
            raise ValueError('La compra mínima no puede ser negativa.')

        Promotion._validate_dates(fecha_inicio, fecha_fin)

        if tipo_aplicacion == 'producto':
            if not codigo_producto:
                raise ValueError('Debe seleccionar un producto para una promoción por producto.')
        else:
            codigo_producto = None

        existing_name = Promotion.find_by_name(nombre, exclude_codigo=codigo)

        if existing_name:
            raise ValueError('Ya existe otra promoción con ese nombre.')

        activo = bool(activo)

        with db.get_cursor() as cursor:
            if codigo_producto:
                cursor.execute("""
                    SELECT codigo
                    FROM public.producto
                    WHERE codigo = %s
                    AND estado = true
                """, (codigo_producto,))

                product = cursor.fetchone()

                if not product:
                    raise ValueError('El producto seleccionado no existe o está inactivo.')

            cursor.execute("""
                UPDATE public.promocion
                SET
                    nombre = %s,
                    descripcion = %s,
                    tipo_aplicacion = %s,
                    codigo_producto = %s,
                    valor = %s,
                    es_porcentaje = %s,
                    compra_minima = %s,
                    fecha_inicio = %s,
                    fecha_fin = %s,
                    activo = %s
                WHERE codigo = %s
                RETURNING
                    codigo,
                    nombre,
                    descripcion,
                    tipo_aplicacion,
                    codigo_producto,
                    valor,
                    es_porcentaje,
                    compra_minima,
                    fecha_inicio,
                    fecha_fin,
                    activo
            """, (
                nombre,
                descripcion,
                tipo_aplicacion,
                codigo_producto,
                valor,
                es_porcentaje,
                compra_minima,
                fecha_inicio,
                fecha_fin,
                activo,
                codigo
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
                    'ACTUALIZACIÓN DE PROMOCIÓN',
                    'promocion',
                    codigo,
                    f'Promoción actualizada: {nombre}. Activa: {activo}'
                ))

            return updated

    @staticmethod
    def toggle_status(codigo, codigo_usuario=None):
        promotion = Promotion.find_by_code(codigo)

        if not promotion:
            raise ValueError('La promoción no existe.')

        new_status = not promotion['activo']

        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public.promocion
                SET activo = %s
                WHERE codigo = %s
                RETURNING codigo, nombre, activo
            """, (new_status, codigo))

            updated = cursor.fetchone()

            if codigo_usuario:
                accion = (
                    'ACTIVACIÓN DE PROMOCIÓN'
                    if updated['activo']
                    else 'DESACTIVACIÓN DE PROMOCIÓN'
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
                    'promocion',
                    codigo,
                    f'Promoción {updated["nombre"]}. Activa: {updated["activo"]}'
                ))

            return updated