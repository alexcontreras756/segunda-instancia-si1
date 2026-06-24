from database.connection import db
from decimal import Decimal
from datetime import datetime


class Discount:

    @staticmethod
    def _to_decimal(value, field_name='valor'):
        """
        Convertir valor a Decimal.
        Acepta punto o coma decimal.
        """
        if value is None or str(value).strip() == '':
            raise ValueError(f'El campo {field_name} es obligatorio.')

        value = str(value).strip().replace(',', '.')

        try:
            number = Decimal(value)
        except Exception:
            raise ValueError(f'El campo {field_name} debe ser numérico.')

        return number

    @staticmethod
    def _clean_code(codigo):
        """
        Limpiar y validar código.
        La tabla real public.descuento usa codigo VARCHAR(10) PRIMARY KEY.
        """
        if codigo is None:
            return None

        codigo = str(codigo).strip().upper()

        if codigo == '':
            return None

        if len(codigo) > 10:
            raise ValueError('El código del descuento no puede superar los 10 caracteres.')

        if ' ' in codigo:
            raise ValueError('El código del descuento no debe contener espacios.')

        return codigo

    @staticmethod
    def _clean_description(descripcion):
        """
        La tabla no tiene campo nombre.
        Se usa descripcion como nombre visible del descuento.
        """
        if not descripcion or not str(descripcion).strip():
            raise ValueError('La descripción del descuento es obligatoria.')

        descripcion = str(descripcion).strip()

        if len(descripcion) < 3:
            raise ValueError('La descripción debe tener al menos 3 caracteres.')

        if len(descripcion) > 200:
            raise ValueError('La descripción no puede superar los 200 caracteres.')

        return descripcion

    @staticmethod
    def _clean_date(value, field_name):
        """
        Valida fechas opcionales con formato YYYY-MM-DD.
        """
        if value is None or str(value).strip() == '':
            return None

        value = str(value).strip()

        try:
            datetime.strptime(value, '%Y-%m-%d')
        except Exception:
            raise ValueError(f'El campo {field_name} debe tener formato YYYY-MM-DD.')

        return value

    @staticmethod
    def _generate_code(cursor):
        """
        Generar código automático.
        Ejemplo: DES001, DES002, DES003.
        """
        cursor.execute("""
            SELECT codigo
            FROM public.descuento
            WHERE codigo ~ '^DES[0-9]+$'
            ORDER BY CAST(SUBSTRING(codigo FROM 4) AS INTEGER) DESC
            LIMIT 1
        """)

        last_discount = cursor.fetchone()

        if not last_discount:
            return 'DES001'

        last_code = last_discount['codigo']
        last_number = int(last_code.replace('DES', ''))
        new_number = last_number + 1

        return f'DES{new_number:03d}'

    @staticmethod
    def count_all(active_only=True):
        """
        Contar descuentos.
        """
        with db.get_cursor() as cursor:
            if active_only:
                cursor.execute("""
                    SELECT COUNT(*) AS total
                    FROM public.descuento
                    WHERE activo = true
                """)
            else:
                cursor.execute("""
                    SELECT COUNT(*) AS total
                    FROM public.descuento
                """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def count_inactive():
        """
        Contar descuentos inactivos.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM public.descuento
                WHERE activo = false
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_all(search=None):
        """
        Listar descuentos.
        Incluye campo calculado vigente.
        """
        search = search.strip() if search else None
        params = []

        query = """
            SELECT
                codigo,
                descripcion,
                valor,
                es_porcentaje,
                fecha_inicio,
                fecha_fin,
                activo,
                CASE
                    WHEN activo = true
                     AND (fecha_inicio IS NULL OR fecha_inicio <= CURRENT_DATE)
                     AND (fecha_fin IS NULL OR fecha_fin >= CURRENT_DATE)
                    THEN true
                    ELSE false
                END AS vigente
            FROM public.descuento
            WHERE 1 = 1
        """

        if search:
            query += """
                AND (
                    codigo ILIKE %s
                    OR descripcion ILIKE %s
                )
            """
            term = f'%{search}%'
            params.extend([term, term])

        query += """
            ORDER BY activo DESC, codigo ASC
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    @staticmethod
    def get_active():
        """
        Descuentos activos y vigentes para aplicar en venta.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    descripcion,
                    valor,
                    es_porcentaje,
                    fecha_inicio,
                    fecha_fin,
                    activo
                FROM public.descuento
                WHERE activo = true
                AND (fecha_inicio IS NULL OR fecha_inicio <= CURRENT_DATE)
                AND (fecha_fin IS NULL OR fecha_fin >= CURRENT_DATE)
                ORDER BY codigo
            """)

            return cursor.fetchall()

    @staticmethod
    def find_by_code(codigo):
        """
        Buscar descuento por código.
        """
        codigo = Discount._clean_code(codigo)

        if not codigo:
            return None

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    descripcion,
                    valor,
                    es_porcentaje,
                    fecha_inicio,
                    fecha_fin,
                    activo
                FROM public.descuento
                WHERE codigo = %s
            """, (codigo,))

            return cursor.fetchone()

    @staticmethod
    def find_by_description(descripcion, exclude_codigo=None):
        """
        Validar descripción duplicada.
        Como la tabla no tiene campo nombre, descripcion funciona como nombre visible.
        """
        if not descripcion:
            return None

        descripcion = str(descripcion).strip()

        with db.get_cursor() as cursor:
            if exclude_codigo:
                cursor.execute("""
                    SELECT codigo, descripcion
                    FROM public.descuento
                    WHERE LOWER(TRIM(descripcion)) = LOWER(TRIM(%s))
                    AND codigo <> %s
                    LIMIT 1
                """, (descripcion, exclude_codigo))
            else:
                cursor.execute("""
                    SELECT codigo, descripcion
                    FROM public.descuento
                    WHERE LOWER(TRIM(descripcion)) = LOWER(TRIM(%s))
                    LIMIT 1
                """, (descripcion,))

            return cursor.fetchone()

    @staticmethod
    def validate_discount_data(
        descripcion,
        valor,
        es_porcentaje=False,
        fecha_inicio=None,
        fecha_fin=None
    ):
        """
        Validar datos principales del descuento.
        """
        descripcion = Discount._clean_description(descripcion)
        valor = Discount._to_decimal(valor, 'valor')

        if valor <= 0:
            raise ValueError('El valor del descuento debe ser mayor a cero.')

        es_porcentaje = bool(es_porcentaje)

        if es_porcentaje and valor > 100:
            raise ValueError('Un descuento porcentual no puede superar el 100%.')

        fecha_inicio = Discount._clean_date(fecha_inicio, 'fecha inicio')
        fecha_fin = Discount._clean_date(fecha_fin, 'fecha fin')

        if fecha_inicio and fecha_fin:
            inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

            if inicio > fin:
                raise ValueError('La fecha de inicio no puede ser mayor que la fecha fin.')

        return {
            'descripcion': descripcion,
            'valor': valor,
            'es_porcentaje': es_porcentaje,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        }

    @staticmethod
    def create(
        codigo=None,
        descripcion=None,
        valor=None,
        es_porcentaje=False,
        fecha_inicio=None,
        fecha_fin=None,
        codigo_usuario=None
    ):
        """
        Crear descuento.
        No elimina ni afecta ventas históricas.
        """
        data = Discount.validate_discount_data(
            descripcion=descripcion,
            valor=valor,
            es_porcentaje=es_porcentaje,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )

        codigo = Discount._clean_code(codigo)

        existing_description = Discount.find_by_description(data['descripcion'])

        if existing_description:
            raise ValueError('Ya existe un descuento con esa descripción.')

        with db.get_cursor() as cursor:
            if not codigo:
                codigo = Discount._generate_code(cursor)

            cursor.execute("""
                SELECT codigo
                FROM public.descuento
                WHERE codigo = %s
                LIMIT 1
            """, (codigo,))

            existing_code = cursor.fetchone()

            if existing_code:
                raise ValueError('Ya existe un descuento con ese código.')

            cursor.execute("""
                INSERT INTO public.descuento (
                    codigo,
                    descripcion,
                    valor,
                    es_porcentaje,
                    fecha_inicio,
                    fecha_fin,
                    activo
                )
                VALUES (%s, %s, %s, %s, %s, %s, true)
                RETURNING
                    codigo,
                    descripcion,
                    valor,
                    es_porcentaje,
                    fecha_inicio,
                    fecha_fin,
                    activo
            """, (
                codigo,
                data['descripcion'],
                data['valor'],
                data['es_porcentaje'],
                data['fecha_inicio'],
                data['fecha_fin']
            ))

            discount = cursor.fetchone()

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
                    'CREACIÓN DE DESCUENTO',
                    'descuento',
                    discount['codigo'],
                    f'Descuento creado: {discount["descripcion"]} - Valor: {discount["valor"]}'
                ))

            return discount

    @staticmethod
    def update(
        codigo,
        descripcion=None,
        valor=None,
        es_porcentaje=False,
        fecha_inicio=None,
        fecha_fin=None,
        activo=True,
        codigo_usuario=None
    ):
        """
        Editar descuento.
        No se modifica el código para no afectar ventas históricas.
        """
        codigo = Discount._clean_code(codigo)

        discount = Discount.find_by_code(codigo)

        if not discount:
            raise ValueError('El descuento no existe.')

        data = Discount.validate_discount_data(
            descripcion=descripcion,
            valor=valor,
            es_porcentaje=es_porcentaje,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )

        existing_description = Discount.find_by_description(
            data['descripcion'],
            exclude_codigo=codigo
        )

        if existing_description:
            raise ValueError('Ya existe otro descuento con esa descripción.')

        activo = bool(activo)

        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public.descuento
                SET
                    descripcion = %s,
                    valor = %s,
                    es_porcentaje = %s,
                    fecha_inicio = %s,
                    fecha_fin = %s,
                    activo = %s
                WHERE codigo = %s
                RETURNING
                    codigo,
                    descripcion,
                    valor,
                    es_porcentaje,
                    fecha_inicio,
                    fecha_fin,
                    activo
            """, (
                data['descripcion'],
                data['valor'],
                data['es_porcentaje'],
                data['fecha_inicio'],
                data['fecha_fin'],
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
                    'ACTUALIZACIÓN DE DESCUENTO',
                    'descuento',
                    updated['codigo'],
                    f'Descuento actualizado: {updated["descripcion"]} - Activo: {updated["activo"]}'
                ))

            return updated

    @staticmethod
    def toggle_status(codigo, codigo_usuario=None):
        """
        Activar o desactivar descuento.
        No elimina físicamente.
        """
        codigo = Discount._clean_code(codigo)

        discount = Discount.find_by_code(codigo)

        if not discount:
            raise ValueError('El descuento no existe.')

        new_status = not discount['activo']

        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public.descuento
                SET activo = %s
                WHERE codigo = %s
                RETURNING
                    codigo,
                    descripcion,
                    valor,
                    es_porcentaje,
                    fecha_inicio,
                    fecha_fin,
                    activo
            """, (
                new_status,
                codigo
            ))

            updated = cursor.fetchone()

            if codigo_usuario:
                accion = (
                    'ACTIVACIÓN DE DESCUENTO'
                    if updated['activo']
                    else 'DESACTIVACIÓN DE DESCUENTO'
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
                    'descuento',
                    updated['codigo'],
                    f'Descuento {updated["descripcion"]}. Activo: {updated["activo"]}'
                ))

            return updated