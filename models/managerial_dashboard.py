from database.connection import db
from decimal import Decimal
from datetime import datetime


class ManagerialDashboard:
    """
    Modelo para CU19 - Generar Análisis Gerencial Inteligente.

    Centraliza las consultas gerenciales del minimarket sin tocar la lógica
    existente de ventas, compras, caja, inventario, reportes o promociones.
    """

    @staticmethod
    def _to_decimal(value):
        """
        Convertir valores numéricos a Decimal de forma segura.
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
    def _format_money(value):
        """
        Formatear importes para mostrar en plantillas y correos.
        """
        value = ManagerialDashboard._to_decimal(value)
        return f'Bs {value:.2f}'

    @staticmethod
    def get_sales_today():
        """
        Total vendido en el día actual, solo facturas activas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(monto_final), 0) AS total
                FROM public.factura
                WHERE estado = true
                AND DATE(fecha_hora) = CURRENT_DATE
            """)

            result = cursor.fetchone()
            return ManagerialDashboard._to_decimal(result['total'] if result else 0)

    @staticmethod
    def get_sales_month():
        """
        Total vendido en el mes actual, solo facturas activas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(monto_final), 0) AS total
                FROM public.factura
                WHERE estado = true
                AND fecha_hora >= DATE_TRUNC('month', CURRENT_DATE)
                AND fecha_hora < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
            """)

            result = cursor.fetchone()
            return ManagerialDashboard._to_decimal(result['total'] if result else 0)

    @staticmethod
    def get_profit_month():
        """
        Utilidad del mes actual.

        Mantiene la lógica del reporte de utilidad existente:
        Utilidad = Total final cobrado - Costo de productos vendidos.

        Total final cobrado = public.factura.monto_final
        Costo = public.detalle_factura.cantidad * public.producto.precio_compra
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                WITH costos_por_factura AS (
                    SELECT
                        df.codigo_factura,
                        COALESCE(
                            SUM(df.cantidad * COALESCE(p.precio_compra, 0)),
                            0
                        ) AS costo_total
                    FROM public.detalle_factura df
                    JOIN public.producto p
                        ON df.codigo_producto = p.codigo
                    GROUP BY df.codigo_factura
                )
                SELECT
                    COALESCE(
                        SUM(
                            COALESCE(f.monto_final, 0)
                            - COALESCE(cpf.costo_total, 0)
                        ),
                        0
                    ) AS utilidad
                FROM public.factura f
                LEFT JOIN costos_por_factura cpf
                    ON f.codigo = cpf.codigo_factura
                WHERE f.estado = true
                AND f.fecha_hora >= DATE_TRUNC('month', CURRENT_DATE)
                AND f.fecha_hora < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
            """)

            result = cursor.fetchone()
            return ManagerialDashboard._to_decimal(result['utilidad'] if result else 0)

    @staticmethod
    def get_low_stock_count():
        """
        Contar productos activos con stock bajo.
        Stock bajo: stock total mayor a 0 y menor o igual al stock mínimo.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM (
                    SELECT
                        p.codigo,
                        COALESCE(SUM(i.cantidad), 0) AS stock_total,
                        COALESCE(p.stock_minimo, 0) AS stock_minimo
                    FROM public.producto p
                    LEFT JOIN public.inventario i
                        ON p.codigo = i.codigo_producto
                        AND i.estado = true
                        AND i.cantidad > 0
                    WHERE p.estado = true
                    GROUP BY p.codigo, p.stock_minimo
                    HAVING COALESCE(SUM(i.cantidad), 0) > 0
                       AND COALESCE(SUM(i.cantidad), 0) <= COALESCE(p.stock_minimo, 0)
                ) AS stock_bajo
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_out_of_stock_count():
        """
        Contar productos activos agotados.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM (
                    SELECT
                        p.codigo,
                        COALESCE(SUM(i.cantidad), 0) AS stock_total
                    FROM public.producto p
                    LEFT JOIN public.inventario i
                        ON p.codigo = i.codigo_producto
                        AND i.estado = true
                        AND i.cantidad > 0
                    WHERE p.estado = true
                    GROUP BY p.codigo
                    HAVING COALESCE(SUM(i.cantidad), 0) = 0
                ) AS agotados
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_expiring_products_count(days=30):
        """
        Contar lotes/productos próximos a vencer en los próximos N días.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM public.inventario i
                JOIN public.producto p
                    ON i.codigo_producto = p.codigo
                WHERE i.estado = true
                AND i.cantidad > 0
                AND p.estado = true
                AND i.fecha_vencimiento IS NOT NULL
                AND i.fecha_vencimiento >= CURRENT_DATE
                AND i.fecha_vencimiento <= CURRENT_DATE + (%s || ' days')::INTERVAL
            """, (days,))

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_purchases_month():
        """
        Total de compras registradas en el mes actual.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(monto_total), 0) AS total
                FROM public.nota_compra
                WHERE estado = true
                AND fecha_hora >= DATE_TRUNC('month', CURRENT_DATE)
                AND fecha_hora < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
            """)

            result = cursor.fetchone()
            return ManagerialDashboard._to_decimal(result['total'] if result else 0)

    @staticmethod
    def get_output_losses_month():
        """
        Total de pérdidas por notas de salida activas en el mes actual.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(monto_total_perdida), 0) AS total
                FROM public.nota_salida
                WHERE COALESCE(estado, true) = true
                AND fecha_hora >= DATE_TRUNC('month', CURRENT_DATE)
                AND fecha_hora < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
            """)

            result = cursor.fetchone()
            return ManagerialDashboard._to_decimal(result['total'] if result else 0)

    @staticmethod
    def get_open_cash_count():
        """
        Contar cajas abiertas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM public.caja
                WHERE estado = 'abierta'
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_most_used_payment_method_month():
        """
        Método de pago más usado en el mes actual.
        Se muestra como tarjeta, no como gráfica.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    tp.nombre AS metodo_pago,
                    COUNT(*) AS cantidad,
                    COALESCE(SUM(p.monto_pagado), 0) AS total_pagado
                FROM public.pago p
                JOIN public.tipo_pago tp
                    ON p.id_tipo_pago = tp.id
                JOIN public.factura f
                    ON p.codigo_factura = f.codigo
                WHERE f.estado = true
                AND p.fecha_pago >= DATE_TRUNC('month', CURRENT_DATE)
                AND p.fecha_pago < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                GROUP BY tp.nombre
                ORDER BY cantidad DESC, total_pagado DESC, tp.nombre ASC
                LIMIT 1
            """)

            result = cursor.fetchone()

            if not result:
                return {
                    'metodo_pago': 'Sin registros',
                    'cantidad': 0,
                    'total_pagado': Decimal('0.00')
                }

            return {
                'metodo_pago': result['metodo_pago'],
                'cantidad': result['cantidad'],
                'total_pagado': ManagerialDashboard._to_decimal(result['total_pagado'])
            }

    @staticmethod
    def get_sales_by_day_current_month():
        """
        Total vendido por cada día del mes actual.
        Devuelve todos los días del mes actual con cero si no hubo ventas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                WITH dias AS (
                    SELECT GENERATE_SERIES(
                        DATE_TRUNC('month', CURRENT_DATE)::DATE,
                        (
                            DATE_TRUNC('month', CURRENT_DATE)
                            + INTERVAL '1 month'
                            - INTERVAL '1 day'
                        )::DATE,
                        INTERVAL '1 day'
                    )::DATE AS dia
                ),
                ventas AS (
                    SELECT
                        DATE(fecha_hora) AS dia,
                        COALESCE(SUM(monto_final), 0) AS total
                    FROM public.factura
                    WHERE estado = true
                    AND fecha_hora >= DATE_TRUNC('month', CURRENT_DATE)
                    AND fecha_hora < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                    GROUP BY DATE(fecha_hora)
                )
                SELECT
                    EXTRACT(DAY FROM d.dia)::INTEGER AS dia_numero,
                    d.dia,
                    COALESCE(v.total, 0) AS total
                FROM dias d
                LEFT JOIN ventas v
                    ON d.dia = v.dia
                ORDER BY d.dia
            """)

            rows = cursor.fetchall()

            return [
                {
                    'day': row['dia_numero'],
                    'date': row['dia'].strftime('%Y-%m-%d') if row['dia'] else '',
                    'total': float(ManagerialDashboard._to_decimal(row['total']))
                }
                for row in rows
            ]

    @staticmethod
    def get_indicators():
        """
        Obtener todos los indicadores del dashboard gerencial.
        """
        payment_method = ManagerialDashboard.get_most_used_payment_method_month()

        indicators = {
            'ventas_dia': ManagerialDashboard.get_sales_today(),
            'ventas_mes': ManagerialDashboard.get_sales_month(),
            'utilidad_mes': ManagerialDashboard.get_profit_month(),
            'productos_stock_bajo': ManagerialDashboard.get_low_stock_count(),
            'productos_agotados': ManagerialDashboard.get_out_of_stock_count(),
            'productos_proximos_vencer': ManagerialDashboard.get_expiring_products_count(days=30),
            'compras_mes': ManagerialDashboard.get_purchases_month(),
            'perdidas_notas_salida': ManagerialDashboard.get_output_losses_month(),
            'cajas_abiertas': ManagerialDashboard.get_open_cash_count(),
            'metodo_pago_mas_usado': payment_method,
            'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        }

        indicators['formatted'] = {
            'ventas_dia': ManagerialDashboard._format_money(indicators['ventas_dia']),
            'ventas_mes': ManagerialDashboard._format_money(indicators['ventas_mes']),
            'utilidad_mes': ManagerialDashboard._format_money(indicators['utilidad_mes']),
            'compras_mes': ManagerialDashboard._format_money(indicators['compras_mes']),
            'perdidas_notas_salida': ManagerialDashboard._format_money(indicators['perdidas_notas_salida']),
            'metodo_pago_total': ManagerialDashboard._format_money(payment_method['total_pagado'])
        }

        return indicators

    @staticmethod
    def get_dashboard_data():
        """
        Datos completos para renderizar el dashboard gerencial.
        """
        indicators = ManagerialDashboard.get_indicators()
        sales_by_day = ManagerialDashboard.get_sales_by_day_current_month()
        has_month_sales = any(item['total'] > 0 for item in sales_by_day)

        return {
            'indicators': indicators,
            'sales_by_day': sales_by_day,
            'chart_labels': [str(item['day']) for item in sales_by_day],
            'chart_values': [item['total'] for item in sales_by_day],
            'has_month_sales': has_month_sales
        }

    @staticmethod
    def register_action(codigo_usuario, accion, detalle=None):
        """
        Registrar acción del CU19 en bitácora.
        """
        if not codigo_usuario:
            return None

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
                'managerial_dashboard',
                detalle or accion
            ))

            return cursor.fetchone()