from database.connection import db
from decimal import Decimal
from datetime import date, datetime


class VoiceAIReport:
    """
    Modelo para el Reporte de Voz IA.

    Este modelo consulta datos reales del esquema public en PostgreSQL.
    Gemini NO consulta directamente la base de datos.
    """

    @staticmethod
    def _clean_question(question):
        if not question:
            return ""

        return str(question).strip().lower()

    @staticmethod
    def _to_serializable(value):
        """
        Convierte valores de PostgreSQL a datos compatibles con JSON.
        """
        if isinstance(value, Decimal):
            return float(value)

        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y %H:%M:%S")

        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")

        return value

    @staticmethod
    def _rows_to_list(rows):
        """
        Convierte filas RealDictCursor a lista de diccionarios serializables.
        """
        data = []

        for row in rows:
            item = {}

            for key, value in dict(row).items():
                item[key] = VoiceAIReport._to_serializable(value)

            data.append(item)

        return data

    @staticmethod
    def _money(value):
        try:
            return f"Bs {float(value or 0):.2f}"
        except Exception:
            return "Bs 0.00"

    @staticmethod
    def detect_intent(question):
        """
        Detecta la intención de la pregunta usando palabras clave simples.
        Esto evita que Gemini decida consultas SQL.
        """

        q = VoiceAIReport._clean_question(question)

        if any(word in q for word in ["stock mínimo", "stock minimo", "stock bajo", "bajo stock", "alerta", "mínimo", "minimo"]):
            return "stock_minimo"

        if any(word in q for word in ["agotado", "agotados", "sin stock", "stock cero"]):
            return "agotados"

        if any(word in q for word in ["utilidad hoy", "ganancia hoy", "ganancias hoy"]):
            return "utilidad_hoy"

        if any(word in q for word in ["utilidad mes", "utilidad mensual", "ganancia mes", "ganancias mes"]):
            return "utilidad_mes"

        if any(word in q for word in ["venta hoy", "ventas hoy", "vendió hoy", "vendio hoy"]):
            return "ventas_hoy"

        if any(word in q for word in ["venta mes", "ventas mes", "ventas mensual", "vendido este mes"]):
            return "ventas_mes"

        if any(word in q for word in ["caja", "cajas", "apertura", "cierre"]):
            return "caja"

        if any(word in q for word in ["compra", "compras", "proveedor", "proveedores"]):
            return "compras_mes"

        if any(word in q for word in ["nota de salida", "notas de salida", "salidas", "pérdida", "perdida"]):
            return "notas_salida_mes"

        if any(word in q for word in ["resumen", "general", "estado del minimarket", "estado general", "dashboard"]):
            return "resumen_general"

        return "resumen_general"

    @staticmethod
    def execute_question(question):
        """
        Ejecuta la consulta correspondiente según la intención detectada.
        """

        intent = VoiceAIReport.detect_intent(question)

        if intent == "stock_minimo":
            return VoiceAIReport.get_low_stock_report()

        if intent == "agotados":
            return VoiceAIReport.get_out_of_stock_report()

        if intent == "utilidad_hoy":
            return VoiceAIReport.get_profit_report(period="today")

        if intent == "utilidad_mes":
            return VoiceAIReport.get_profit_report(period="month")

        if intent == "ventas_hoy":
            return VoiceAIReport.get_sales_report(period="today")

        if intent == "ventas_mes":
            return VoiceAIReport.get_sales_report(period="month")

        if intent == "caja":
            return VoiceAIReport.get_cash_report()

        if intent == "compras_mes":
            return VoiceAIReport.get_purchase_report()

        if intent == "notas_salida_mes":
            return VoiceAIReport.get_output_notes_report()

        return VoiceAIReport.get_general_summary()

    @staticmethod
    def get_low_stock_report():
        """
        Productos con stock bajo o agotado.
        Compara stock total contra producto.stock_minimo.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.codigo AS codigo_producto,
                    p.nombre AS producto,
                    COALESCE(p.stock_minimo, 0) AS stock_minimo,
                    COALESCE(SUM(i.cantidad), 0) AS stock_total,
                    COALESCE(p.precio_compra, 0) AS precio_compra,
                    COALESCE(p.precio_venta, 0) AS precio_venta,
                    CASE
                        WHEN COALESCE(SUM(i.cantidad), 0) <= 0 THEN 'Agotado'
                        WHEN COALESCE(SUM(i.cantidad), 0) <= COALESCE(p.stock_minimo, 0) THEN 'Stock bajo'
                        ELSE 'Normal'
                    END AS estado_stock
                FROM public.producto p
                LEFT JOIN public.inventario i
                    ON p.codigo = i.codigo_producto
                    AND i.estado = true
                    AND i.cantidad > 0
                WHERE p.estado = true
                GROUP BY
                    p.codigo,
                    p.nombre,
                    p.stock_minimo,
                    p.precio_compra,
                    p.precio_venta
                HAVING COALESCE(SUM(i.cantidad), 0) <= COALESCE(p.stock_minimo, 0)
                ORDER BY
                    COALESCE(SUM(i.cantidad), 0) ASC,
                    p.nombre ASC
            """)

            rows = VoiceAIReport._rows_to_list(cursor.fetchall())

        agotados = len([r for r in rows if r["estado_stock"] == "Agotado"])
        bajos = len([r for r in rows if r["estado_stock"] == "Stock bajo"])

        return {
            "intent": "stock_minimo",
            "title": "Productos con stock mínimo o agotado",
            "summary": {
                "total_productos_en_alerta": len(rows),
                "productos_agotados": agotados,
                "productos_con_stock_bajo": bajos
            },
            "columns": [
                "codigo_producto",
                "producto",
                "stock_minimo",
                "stock_total",
                "precio_compra",
                "precio_venta",
                "estado_stock"
            ],
            "rows": rows
        }

    @staticmethod
    def get_out_of_stock_report():
        """
        Productos activos sin stock.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.codigo AS codigo_producto,
                    p.nombre AS producto,
                    COALESCE(p.stock_minimo, 0) AS stock_minimo,
                    COALESCE(SUM(i.cantidad), 0) AS stock_total,
                    COALESCE(p.precio_venta, 0) AS precio_venta,
                    'Agotado' AS estado_stock
                FROM public.producto p
                LEFT JOIN public.inventario i
                    ON p.codigo = i.codigo_producto
                    AND i.estado = true
                    AND i.cantidad > 0
                WHERE p.estado = true
                GROUP BY
                    p.codigo,
                    p.nombre,
                    p.stock_minimo,
                    p.precio_venta
                HAVING COALESCE(SUM(i.cantidad), 0) = 0
                ORDER BY p.nombre ASC
            """)

            rows = VoiceAIReport._rows_to_list(cursor.fetchall())

        return {
            "intent": "agotados",
            "title": "Productos agotados",
            "summary": {
                "total_productos_agotados": len(rows)
            },
            "columns": [
                "codigo_producto",
                "producto",
                "stock_minimo",
                "stock_total",
                "precio_venta",
                "estado_stock"
            ],
            "rows": rows
        }

    @staticmethod
    def get_profit_report(period="today"):
        """
        Reporte de utilidad.
        Utilidad = monto_final cobrado - costo de productos vendidos.
        """

        if period == "month":
            title = "Utilidad del mes actual"
            date_condition = "DATE_TRUNC('month', f.fecha_hora) = DATE_TRUNC('month', CURRENT_DATE)"
        else:
            title = "Utilidad de hoy"
            date_condition = "DATE(f.fecha_hora) = CURRENT_DATE"

        with db.get_cursor() as cursor:
            cursor.execute(f"""
                WITH ventas AS (
                    SELECT
                        f.codigo,
                        f.monto_final
                    FROM public.factura f
                    WHERE f.estado = true
                    AND {date_condition}
                ),
                costos AS (
                    SELECT
                        COALESCE(SUM(df.cantidad * COALESCE(p.precio_compra, 0)), 0) AS costo_productos
                    FROM ventas v
                    JOIN public.detalle_factura df
                        ON v.codigo = df.codigo_factura
                    JOIN public.producto p
                        ON df.codigo_producto = p.codigo
                )
                SELECT
                    COUNT(v.codigo) AS cantidad_ventas,
                    COALESCE(SUM(v.monto_final), 0) AS total_final_cobrado,
                    COALESCE(c.costo_productos, 0) AS costo_productos_vendidos,
                    COALESCE(SUM(v.monto_final), 0) - COALESCE(c.costo_productos, 0) AS utilidad
                FROM ventas v
                CROSS JOIN costos c
                GROUP BY c.costo_productos
            """)

            result = cursor.fetchone()

        if not result:
            result = {
                "cantidad_ventas": 0,
                "total_final_cobrado": 0,
                "costo_productos_vendidos": 0,
                "utilidad": 0
            }

        data = {
            key: VoiceAIReport._to_serializable(value)
            for key, value in dict(result).items()
        }

        return {
            "intent": f"utilidad_{period}",
            "title": title,
            "summary": {
                "cantidad_ventas": data["cantidad_ventas"],
                "total_final_cobrado": VoiceAIReport._money(data["total_final_cobrado"]),
                "costo_productos_vendidos": VoiceAIReport._money(data["costo_productos_vendidos"]),
                "utilidad": VoiceAIReport._money(data["utilidad"])
            },
            "columns": [
                "cantidad_ventas",
                "total_final_cobrado",
                "costo_productos_vendidos",
                "utilidad"
            ],
            "rows": [data]
        }

    @staticmethod
    def get_sales_report(period="today"):
        """
        Resumen de ventas por día o mes.
        """

        if period == "month":
            title = "Ventas del mes actual"
            date_condition = "DATE_TRUNC('month', f.fecha_hora) = DATE_TRUNC('month', CURRENT_DATE)"
        else:
            title = "Ventas de hoy"
            date_condition = "DATE(f.fecha_hora) = CURRENT_DATE"

        with db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    COUNT(f.codigo) AS cantidad_ventas,
                    COALESCE(SUM(f.monto_total), 0) AS total_bruto,
                    COALESCE(SUM(f.monto_final), 0) AS total_final,
                    COALESCE(AVG(f.monto_final), 0) AS promedio_venta
                FROM public.factura f
                WHERE f.estado = true
                AND {date_condition}
            """)

            summary_row = cursor.fetchone()

            cursor.execute(f"""
                SELECT
                    f.codigo AS factura,
                    f.fecha_hora,
                    c.nombre AS cliente,
                    u.nombre AS usuario,
                    tp.nombre AS tipo_pago,
                    f.monto_total,
                    f.monto_final
                FROM public.factura f
                JOIN public.cliente c
                    ON f.id_cliente = c.id
                JOIN public.usuario u
                    ON f.codigo_usuario = u.codigo
                JOIN public.tipo_pago tp
                    ON f.id_tipo_pago = tp.id
                WHERE f.estado = true
                AND {date_condition}
                ORDER BY f.fecha_hora DESC
                LIMIT 10
            """)

            rows = VoiceAIReport._rows_to_list(cursor.fetchall())

        summary_row = dict(summary_row) if summary_row else {}

        summary = {
            "cantidad_ventas": VoiceAIReport._to_serializable(summary_row.get("cantidad_ventas", 0)),
            "total_bruto": VoiceAIReport._money(summary_row.get("total_bruto", 0)),
            "total_final": VoiceAIReport._money(summary_row.get("total_final", 0)),
            "promedio_venta": VoiceAIReport._money(summary_row.get("promedio_venta", 0))
        }

        return {
            "intent": f"ventas_{period}",
            "title": title,
            "summary": summary,
            "columns": [
                "factura",
                "fecha_hora",
                "cliente",
                "usuario",
                "tipo_pago",
                "monto_total",
                "monto_final"
            ],
            "rows": rows
        }

    @staticmethod
    def get_cash_report():
        """
        Reporte de caja.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE estado = 'abierta') AS cajas_abiertas,
                    COUNT(*) FILTER (
                        WHERE estado = 'cerrada'
                        AND DATE(fecha_cierre) = CURRENT_DATE
                    ) AS cajas_cerradas_hoy,
                    COALESCE(SUM(total_ventas) FILTER (
                        WHERE estado = 'cerrada'
                        AND DATE(fecha_cierre) = CURRENT_DATE
                    ), 0) AS total_ventas_cajas_cerradas_hoy,
                    COALESCE(SUM(diferencia) FILTER (
                        WHERE estado = 'cerrada'
                        AND DATE(fecha_cierre) = CURRENT_DATE
                    ), 0) AS diferencia_total_hoy
                FROM public.caja
            """)

            summary_row = cursor.fetchone()

            cursor.execute("""
                SELECT
                    c.codigo,
                    u.nombre AS usuario,
                    c.fecha_apertura,
                    c.fecha_cierre,
                    c.monto_inicial,
                    c.monto_final,
                    c.total_ventas,
                    c.diferencia,
                    c.estado
                FROM public.caja c
                JOIN public.usuario u
                    ON c.codigo_usuario = u.codigo
                ORDER BY c.fecha_apertura DESC
                LIMIT 10
            """)

            rows = VoiceAIReport._rows_to_list(cursor.fetchall())

        summary_row = dict(summary_row) if summary_row else {}

        return {
            "intent": "caja",
            "title": "Resumen de caja",
            "summary": {
                "cajas_abiertas": VoiceAIReport._to_serializable(summary_row.get("cajas_abiertas", 0)),
                "cajas_cerradas_hoy": VoiceAIReport._to_serializable(summary_row.get("cajas_cerradas_hoy", 0)),
                "total_ventas_cajas_cerradas_hoy": VoiceAIReport._money(summary_row.get("total_ventas_cajas_cerradas_hoy", 0)),
                "diferencia_total_hoy": VoiceAIReport._money(summary_row.get("diferencia_total_hoy", 0))
            },
            "columns": [
                "codigo",
                "usuario",
                "fecha_apertura",
                "fecha_cierre",
                "monto_inicial",
                "monto_final",
                "total_ventas",
                "diferencia",
                "estado"
            ],
            "rows": rows
        }

    @staticmethod
    def get_purchase_report():
        """
        Compras del mes actual.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) AS cantidad_compras,
                    COALESCE(SUM(monto_total), 0) AS total_compras
                FROM public.nota_compra
                WHERE estado = true
                AND DATE_TRUNC('month', fecha_hora) = DATE_TRUNC('month', CURRENT_DATE)
            """)

            summary_row = cursor.fetchone()

            cursor.execute("""
                SELECT
                    nc.codigo,
                    nc.fecha_hora,
                    pr.nombre AS proveedor,
                    u.nombre AS usuario,
                    a.nombre AS almacen,
                    nc.monto_total,
                    nc.observacion
                FROM public.nota_compra nc
                JOIN public.proveedor pr
                    ON nc.codigo_proveedor = pr.codigo
                JOIN public.usuario u
                    ON nc.codigo_usuario = u.codigo
                JOIN public.almacen a
                    ON nc.codigo_almacen = a.codigo
                WHERE nc.estado = true
                AND DATE_TRUNC('month', nc.fecha_hora) = DATE_TRUNC('month', CURRENT_DATE)
                ORDER BY nc.fecha_hora DESC
                LIMIT 10
            """)

            rows = VoiceAIReport._rows_to_list(cursor.fetchall())

        summary_row = dict(summary_row) if summary_row else {}

        return {
            "intent": "compras_mes",
            "title": "Compras del mes actual",
            "summary": {
                "cantidad_compras": VoiceAIReport._to_serializable(summary_row.get("cantidad_compras", 0)),
                "total_compras": VoiceAIReport._money(summary_row.get("total_compras", 0))
            },
            "columns": [
                "codigo",
                "fecha_hora",
                "proveedor",
                "usuario",
                "almacen",
                "monto_total",
                "observacion"
            ],
            "rows": rows
        }

    @staticmethod
    def get_output_notes_report():
        """
        Notas de salida del mes actual.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) AS cantidad_notas_salida,
                    COALESCE(SUM(monto_total_perdida), 0) AS total_perdida
                FROM public.nota_salida
                WHERE COALESCE(estado, true) = true
                AND DATE_TRUNC('month', fecha_hora) = DATE_TRUNC('month', CURRENT_DATE)
            """)

            summary_row = cursor.fetchone()

            cursor.execute("""
                SELECT
                    ns.codigo,
                    ns.fecha_hora,
                    ns.motivo_general,
                    ns.monto_total_perdida,
                    u.nombre AS usuario,
                    COALESCE(ns.estado, true) AS estado
                FROM public.nota_salida ns
                JOIN public.usuario u
                    ON ns.codigo_usuario = u.codigo
                WHERE COALESCE(ns.estado, true) = true
                AND DATE_TRUNC('month', ns.fecha_hora) = DATE_TRUNC('month', CURRENT_DATE)
                ORDER BY ns.fecha_hora DESC
                LIMIT 10
            """)

            rows = VoiceAIReport._rows_to_list(cursor.fetchall())

        summary_row = dict(summary_row) if summary_row else {}

        return {
            "intent": "notas_salida_mes",
            "title": "Notas de salida del mes actual",
            "summary": {
                "cantidad_notas_salida": VoiceAIReport._to_serializable(summary_row.get("cantidad_notas_salida", 0)),
                "total_perdida": VoiceAIReport._money(summary_row.get("total_perdida", 0))
            },
            "columns": [
                "codigo",
                "fecha_hora",
                "motivo_general",
                "monto_total_perdida",
                "usuario",
                "estado"
            ],
            "rows": rows
        }

    @staticmethod
    def get_general_summary():
        """
        Resumen general del minimarket.
        """

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total_productos
                FROM public.producto
                WHERE estado = true
            """)
            total_productos = cursor.fetchone()["total_productos"]

            cursor.execute("""
                SELECT COUNT(*) AS total_clientes
                FROM public.cliente
            """)
            total_clientes = cursor.fetchone()["total_clientes"]

            cursor.execute("""
                SELECT COUNT(*) AS total_proveedores
                FROM public.proveedor
            """)
            total_proveedores = cursor.fetchone()["total_proveedores"]

            cursor.execute("""
                SELECT COALESCE(SUM(cantidad), 0) AS total_unidades_inventario
                FROM public.inventario
                WHERE estado = true
                AND cantidad > 0
            """)
            total_unidades_inventario = cursor.fetchone()["total_unidades_inventario"]

            cursor.execute("""
                SELECT COUNT(*) AS productos_alerta
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
                    HAVING COALESCE(SUM(i.cantidad), 0) <= COALESCE(p.stock_minimo, 0)
                ) alerta
            """)
            productos_alerta = cursor.fetchone()["productos_alerta"]

            cursor.execute("""
                SELECT
                    COUNT(*) AS ventas_hoy,
                    COALESCE(SUM(monto_final), 0) AS total_ventas_hoy
                FROM public.factura
                WHERE estado = true
                AND DATE(fecha_hora) = CURRENT_DATE
            """)
            ventas_hoy = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(*) AS cajas_abiertas
                FROM public.caja
                WHERE estado = 'abierta'
            """)
            cajas_abiertas = cursor.fetchone()["cajas_abiertas"]

        row = {
            "total_productos": VoiceAIReport._to_serializable(total_productos),
            "total_clientes": VoiceAIReport._to_serializable(total_clientes),
            "total_proveedores": VoiceAIReport._to_serializable(total_proveedores),
            "total_unidades_inventario": VoiceAIReport._to_serializable(total_unidades_inventario),
            "productos_alerta_stock": VoiceAIReport._to_serializable(productos_alerta),
            "ventas_hoy": VoiceAIReport._to_serializable(ventas_hoy["ventas_hoy"]),
            "total_ventas_hoy": VoiceAIReport._to_serializable(ventas_hoy["total_ventas_hoy"]),
            "cajas_abiertas": VoiceAIReport._to_serializable(cajas_abiertas)
        }

        return {
            "intent": "resumen_general",
            "title": "Resumen general del MiniMarket QuickStore",
            "summary": {
                "total_productos": row["total_productos"],
                "total_clientes": row["total_clientes"],
                "total_proveedores": row["total_proveedores"],
                "total_unidades_inventario": row["total_unidades_inventario"],
                "productos_alerta_stock": row["productos_alerta_stock"],
                "ventas_hoy": row["ventas_hoy"],
                "total_ventas_hoy": VoiceAIReport._money(row["total_ventas_hoy"]),
                "cajas_abiertas": row["cajas_abiertas"]
            },
            "columns": [
                "total_productos",
                "total_clientes",
                "total_proveedores",
                "total_unidades_inventario",
                "productos_alerta_stock",
                "ventas_hoy",
                "total_ventas_hoy",
                "cajas_abiertas"
            ],
            "rows": [row]
        }

    @staticmethod
    def register_voice_ai_action(codigo_usuario, question, intent):
        """
        Registrar consulta de voz IA en bitácora public.historial.
        """

        if not codigo_usuario:
            return None

        try:
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
                    "CONSULTA REPORTE DE VOZ IA",
                    "reportes",
                    "voice_ai",
                    f"Pregunta: {question}. Intención detectada: {intent}"
                ))

                return cursor.fetchone()

        except Exception:
            return None