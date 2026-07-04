from database.connection import db
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime


class ABCClassification:
    """
    Modelo para el reporte de Clasificación ABC de productos.

    La clasificación se basa en ventas reales registradas en:
    - public.factura
    - public.detalle_factura
    - public.producto

    Reglas:
    - Solo facturas activas.
    - Rango de fechas obligatorio.
    - Orden de mayor a menor por valor vendido.
    - Clase A: hasta aproximadamente 80% acumulado.
    - Clase B: mayor a 80% y hasta aproximadamente 95% acumulado.
    - Clase C: mayor a 95% acumulado.
    """

    VALID_CLASSES = ['A', 'B', 'C']

    @staticmethod
    def _to_decimal(value):
        """
        Convertir valores a Decimal de forma segura.
        """
        if value is None:
            return Decimal('0.00')

        if isinstance(value, Decimal):
            return value

        try:
            return Decimal(str(value))
        except Exception:
            return Decimal('0.00')

    @staticmethod
    def _to_percent(value):
        """
        Redondear porcentajes a 2 decimales.
        """
        value = ABCClassification._to_decimal(value)
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _clean_text(value):
        """
        Limpiar texto opcional.
        """
        if value is None:
            return None

        value = str(value).strip()

        if value == '':
            return None

        return value

    @staticmethod
    def _clean_classification(value):
        """
        Validar filtro opcional de clasificación ABC.
        """
        value = ABCClassification._clean_text(value)

        if not value:
            return None

        value = value.upper()

        if value not in ABCClassification.VALID_CLASSES:
            raise ValueError('La clasificación debe ser A, B o C.')

        return value

    @staticmethod
    def _validate_date(value, field_name):
        """
        Validar fecha obligatoria con formato YYYY-MM-DD.
        """
        value = ABCClassification._clean_text(value)

        if not value:
            raise ValueError(f'El campo {field_name} es obligatorio.')

        try:
            datetime.strptime(value, '%Y-%m-%d')
        except Exception:
            raise ValueError(f'El campo {field_name} debe tener formato YYYY-MM-DD.')

        return value

    @staticmethod
    def _validate_date_range(fecha_inicio, fecha_fin):
        """
        Validar rango de fechas obligatorio.
        """
        fecha_inicio = ABCClassification._validate_date(fecha_inicio, 'fecha inicial')
        fecha_fin = ABCClassification._validate_date(fecha_fin, 'fecha final')

        inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

        if inicio > fin:
            raise ValueError('La fecha inicial no puede ser mayor que la fecha final.')

        return fecha_inicio, fecha_fin

    @staticmethod
    def _classify_product(cumulative_percent, index):
        """
        Clasificar producto según porcentaje acumulado.

        Nota:
        Si solo existe un producto o el primer producto supera 80%,
        se mantiene como clase A porque representa la mayor rotación.
        """
        cumulative_percent = ABCClassification._to_decimal(cumulative_percent)

        if index == 0:
            return 'A'

        if cumulative_percent <= Decimal('80.00'):
            return 'A'

        if cumulative_percent <= Decimal('95.00'):
            return 'B'

        return 'C'

    @staticmethod
    def get_report(fecha_inicio, fecha_fin, search=None, classification=None):
        """
        Obtener reporte ABC de productos vendidos.

        Retorna:
        {
            'rows': filas filtradas por clasificación,
            'all_rows': filas completas sin filtrar por clasificación,
            'summary': resumen general
        }
        """
        fecha_inicio, fecha_fin = ABCClassification._validate_date_range(
            fecha_inicio,
            fecha_fin
        )

        search = ABCClassification._clean_text(search)
        classification = ABCClassification._clean_classification(classification)

        params = [fecha_inicio, fecha_fin]

        query = """
            SELECT
                p.codigo AS codigo_producto,
                p.nombre AS producto,
                COALESCE(SUM(df.cantidad), 0) AS cantidad_vendida,
                COALESCE(SUM(df.subtotal), 0) AS valor_vendido,
                COUNT(DISTINCT f.codigo) AS total_facturas
            FROM public.factura f
            JOIN public.detalle_factura df
                ON f.codigo = df.codigo_factura
            JOIN public.producto p
                ON df.codigo_producto = p.codigo
            WHERE f.estado = true
            AND DATE(f.fecha_hora) >= %s
            AND DATE(f.fecha_hora) <= %s
        """

        if search:
            query += """
                AND (
                    p.codigo ILIKE %s
                    OR p.nombre ILIKE %s
                )
            """
            term = f'%{search}%'
            params.extend([term, term])

        query += """
            GROUP BY
                p.codigo,
                p.nombre
            HAVING COALESCE(SUM(df.cantidad), 0) > 0
            ORDER BY
                COALESCE(SUM(df.subtotal), 0) DESC,
                COALESCE(SUM(df.cantidad), 0) DESC,
                p.nombre ASC
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            db_rows = cursor.fetchall()

        total_valor_vendido = Decimal('0.00')
        total_unidades_vendidas = Decimal('0.00')

        for row in db_rows:
            total_valor_vendido += ABCClassification._to_decimal(row.get('valor_vendido'))
            total_unidades_vendidas += ABCClassification._to_decimal(row.get('cantidad_vendida'))

        all_rows = []
        cumulative_raw = Decimal('0.00')

        for index, row in enumerate(db_rows):
            cantidad_vendida = ABCClassification._to_decimal(row.get('cantidad_vendida'))
            valor_vendido = ABCClassification._to_decimal(row.get('valor_vendido'))

            if total_valor_vendido > 0:
                participation_raw = (valor_vendido / total_valor_vendido) * Decimal('100')
            else:
                participation_raw = Decimal('0.00')

            cumulative_raw += participation_raw

            if index == len(db_rows) - 1 and len(db_rows) > 0:
                cumulative_display = Decimal('100.00')
            else:
                cumulative_display = ABCClassification._to_percent(cumulative_raw)

            participation_display = ABCClassification._to_percent(participation_raw)
            abc_class = ABCClassification._classify_product(cumulative_display, index)

            all_rows.append({
                'codigo_producto': row.get('codigo_producto'),
                'producto': row.get('producto'),
                'cantidad_vendida': cantidad_vendida,
                'valor_vendido': valor_vendido,
                'porcentaje_participacion': participation_display,
                'porcentaje_acumulado': cumulative_display,
                'clasificacion': abc_class,
                'total_facturas': row.get('total_facturas') or 0
            })

        class_a = [row for row in all_rows if row['clasificacion'] == 'A']
        class_b = [row for row in all_rows if row['clasificacion'] == 'B']
        class_c = [row for row in all_rows if row['clasificacion'] == 'C']

        if classification:
            rows = [
                row for row in all_rows
                if row['clasificacion'] == classification
            ]
        else:
            rows = all_rows

        summary = {
            'total_productos_vendidos': len(all_rows),
            'total_productos_mostrados': len(rows),
            'total_unidades_vendidas': total_unidades_vendidas,
            'total_valor_vendido': total_valor_vendido,
            'productos_clase_a': len(class_a),
            'productos_clase_b': len(class_b),
            'productos_clase_c': len(class_c),
            'valor_clase_a': sum((row['valor_vendido'] for row in class_a), Decimal('0.00')),
            'valor_clase_b': sum((row['valor_vendido'] for row in class_b), Decimal('0.00')),
            'valor_clase_c': sum((row['valor_vendido'] for row in class_c), Decimal('0.00')),
        }

        return {
            'rows': rows,
            'all_rows': all_rows,
            'summary': summary
        }

    @staticmethod
    def register_action(codigo_usuario, accion, detalle=None):
        """
        Registrar acción del módulo ABC en public.historial.
        """
        if not codigo_usuario:
            return None

        if not detalle:
            detalle = accion

        with db.get_cursor() as cursor:
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
                RETURNING id
            """, (
                codigo_usuario,
                accion,
                'reportes',
                'abc_classification',
                detalle
            ))

            return cursor.fetchone()