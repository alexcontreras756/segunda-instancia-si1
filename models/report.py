from database.connection import db
from decimal import Decimal


class Report:
    """
    Modelo para reportes del sistema MiniMarket QuickStore.

    Incluye:
    - Reporte de ventas
    - CU17 Reporte de utilidad

    CU17 calcula:
    Utilidad = Total final cobrado - Costo de productos vendidos

    Donde:
    - Total final cobrado viene de public.factura.monto_final
    - Costo de productos vendidos viene de:
      public.detalle_factura.cantidad * public.producto.precio_compra

    Importante:
    factura.monto_final ya contiene el efecto final de descuentos y promociones,
    por eso no se vuelve a restar descuentos/promociones en la utilidad.
    """

    AVAILABLE_FIELDS = {
        'codigo_factura': 'Factura',
        'fecha_hora': 'Fecha y hora',
        'cliente': 'Cliente',
        'cliente_ci': 'CI cliente',
        'codigo_usuario': 'Código usuario',
        'usuario': 'Usuario',
        'tipo_pago': 'Tipo de pago',
        'monto_total': 'Monto total',
        'monto_final': 'Monto final',
        'pagado': 'Pagado',
        'estado': 'Estado',
        'referencia_externa': 'Referencia'
    }

    DEFAULT_FIELDS = [
        'codigo_factura',
        'fecha_hora',
        'cliente',
        'usuario',
        'tipo_pago',
        'monto_final',
        'estado'
    ]

    @staticmethod
    def _to_decimal(value):
        """
        Convertir valor a Decimal de forma segura.
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
    def get_available_fields():
        """
        Retorna los campos disponibles para mostrar en el reporte de ventas.
        """
        return Report.AVAILABLE_FIELDS

    @staticmethod
    def get_default_fields():
        """
        Retorna los campos por defecto para el reporte de ventas.
        """
        return Report.DEFAULT_FIELDS

    @staticmethod
    def get_users_for_filter():
        """
        Obtener usuarios activos para filtros de reportes.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    rol
                FROM public.usuario
                WHERE estado = true
                ORDER BY rol, nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def get_payment_types_for_filter():
        """
        Obtener tipos de pago para filtros de reportes.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    nombre,
                    activo
                FROM public.tipo_pago
                ORDER BY activo DESC, nombre ASC
            """)

            return cursor.fetchall()

    @staticmethod
    def get_products_for_filter():
        """
        Obtener productos activos para filtrar el reporte de utilidad.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    precio_compra,
                    precio_venta,
                    estado
                FROM public.producto
                WHERE estado = true
                ORDER BY nombre
            """)

            return cursor.fetchall()

    # =========================================================
    # REPORTE DE VENTAS EXISTENTE
    # =========================================================

    @staticmethod
    def get_sales_report(
        fecha_inicio=None,
        fecha_fin=None,
        codigo_usuario=None,
        id_tipo_pago=None,
        estado='todos',
        search=None
    ):
        """
        Obtener ventas según filtros.
        """

        params = []

        query = """
            SELECT
                f.codigo AS codigo_factura,
                f.fecha_hora,
                f.id_cliente,
                c.nombre AS cliente,
                c.ci AS cliente_ci,
                f.codigo_usuario,
                u.nombre AS usuario,
                u.rol AS usuario_rol,
                f.id_tipo_pago,
                tp.nombre AS tipo_pago,
                f.monto_total,
                f.monto_final,
                f.pagado,
                f.estado,
                p.referencia_externa
            FROM public.factura f
            JOIN public.cliente c
                ON f.id_cliente = c.id
            JOIN public.usuario u
                ON f.codigo_usuario = u.codigo
            JOIN public.tipo_pago tp
                ON f.id_tipo_pago = tp.id
            LEFT JOIN public.pago p
                ON f.codigo = p.codigo_factura
            WHERE 1 = 1
        """

        if fecha_inicio:
            query += " AND DATE(f.fecha_hora) >= %s"
            params.append(fecha_inicio)

        if fecha_fin:
            query += " AND DATE(f.fecha_hora) <= %s"
            params.append(fecha_fin)

        if codigo_usuario:
            query += " AND f.codigo_usuario = %s"
            params.append(codigo_usuario)

        if id_tipo_pago:
            query += " AND f.id_tipo_pago = %s"
            params.append(id_tipo_pago)

        if estado == 'activa':
            query += " AND f.estado = true"

        elif estado == 'anulada':
            query += " AND f.estado = false"

        if search:
            query += """
                AND (
                    f.codigo ILIKE %s
                    OR c.nombre ILIKE %s
                    OR c.ci ILIKE %s
                    OR u.nombre ILIKE %s
                    OR u.codigo ILIKE %s
                    OR tp.nombre ILIKE %s
                )
            """

            term = f'%{search}%'
            params.extend([term, term, term, term, term, term])

        query += """
            ORDER BY f.fecha_hora DESC, f.codigo DESC
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    @staticmethod
    def calculate_summary(rows):
        """
        Calcular resumen del reporte de ventas.
        """
        total_registros = len(rows)
        ventas_activas = 0
        ventas_anuladas = 0

        total_general = Decimal('0.00')
        total_activo = Decimal('0.00')
        total_anulado = Decimal('0.00')

        resumen_usuarios = {}
        resumen_tipos_pago = {}

        for row in rows:
            monto_final = Report._to_decimal(row.get('monto_final'))

            total_general += monto_final

            if row.get('estado'):
                ventas_activas += 1
                total_activo += monto_final
            else:
                ventas_anuladas += 1
                total_anulado += monto_final

            usuario_key = row.get('codigo_usuario')
            usuario_nombre = row.get('usuario')

            if usuario_key not in resumen_usuarios:
                resumen_usuarios[usuario_key] = {
                    'codigo_usuario': usuario_key,
                    'usuario': usuario_nombre,
                    'cantidad': 0,
                    'total': Decimal('0.00')
                }

            resumen_usuarios[usuario_key]['cantidad'] += 1
            resumen_usuarios[usuario_key]['total'] += monto_final

            tipo_pago_key = row.get('tipo_pago') or 'Sin tipo'

            if tipo_pago_key not in resumen_tipos_pago:
                resumen_tipos_pago[tipo_pago_key] = {
                    'tipo_pago': tipo_pago_key,
                    'cantidad': 0,
                    'total': Decimal('0.00')
                }

            resumen_tipos_pago[tipo_pago_key]['cantidad'] += 1
            resumen_tipos_pago[tipo_pago_key]['total'] += monto_final

        return {
            'total_registros': total_registros,
            'ventas_activas': ventas_activas,
            'ventas_anuladas': ventas_anuladas,
            'total_general': total_general,
            'total_activo': total_activo,
            'total_anulado': total_anulado,
            'resumen_usuarios': list(resumen_usuarios.values()),
            'resumen_tipos_pago': list(resumen_tipos_pago.values())
        }

    # =========================================================
    # CU17 - REPORTE DE UTILIDAD
    # =========================================================

    @staticmethod
    def get_profit_report(
        fecha_inicio=None,
        fecha_fin=None,
        codigo_usuario=None,
        codigo_producto=None,
        id_tipo_pago=None,
        estado='activa',
        search=None
    ):
        """
        Obtener reporte de utilidad por factura.

        Fórmula:
        utilidad = factura.monto_final - SUM(detalle_factura.cantidad * producto.precio_compra)

        Nota:
        Si se filtra por producto, se muestran las facturas donde ese producto participa.
        El total, costo y utilidad se calculan sobre la factura completa.

        Corrección:
        public.descuento no usa columna nombre.
        Se usa public.descuento.descripcion y public.descuento.codigo.
        """

        params = []

        query = """
            WITH detalle_costos AS (
                SELECT
                    df.codigo_factura,
                    COALESCE(SUM(df.subtotal), 0) AS total_detalle_bruto,
                    COALESCE(
                        SUM(
                            df.cantidad * COALESCE(p.precio_compra, 0)
                        ),
                        0
                    ) AS costo_total_productos,
                    COALESCE(SUM(df.cantidad), 0) AS total_unidades,
                    STRING_AGG(DISTINCT p.nombre, ', ' ORDER BY p.nombre) AS productos
                FROM public.detalle_factura df
                JOIN public.producto p
                    ON df.codigo_producto = p.codigo
                GROUP BY df.codigo_factura
            ),
            pago_factura AS (
                SELECT
                    codigo_factura,
                    MAX(referencia_externa) AS referencia_externa,
                    COALESCE(SUM(monto_pagado), 0) AS monto_pagado
                FROM public.pago
                GROUP BY codigo_factura
            ),
            promocion_factura AS (
                SELECT
                    f.codigo AS codigo_factura,
                    COALESCE(SUM(pp.monto_descontado), 0) AS monto_promocion,
                    STRING_AGG(DISTINCT pr.nombre, ', ' ORDER BY pr.nombre) AS promociones
                FROM public.factura f
                LEFT JOIN public.pedido_promocion pp
                    ON f.codigo_pedido = pp.codigo_pedido
                LEFT JOIN public.promocion pr
                    ON pp.id_promocion = pr.id
                GROUP BY f.codigo
            )
            SELECT
                f.codigo AS codigo_factura,
                f.fecha_hora,
                f.id_cliente,
                c.nombre AS cliente,
                c.ci AS cliente_ci,
                f.codigo_usuario,
                u.nombre AS usuario,
                u.rol AS usuario_rol,
                f.id_tipo_pago,
                tp.nombre AS tipo_pago,
                f.monto_total AS total_bruto,
                f.monto_final AS total_final_cobrado,

                COALESCE(dc.costo_total_productos, 0) AS costo_total_productos,

                (
                    COALESCE(f.monto_final, 0)
                    - COALESCE(dc.costo_total_productos, 0)
                ) AS utilidad,

                CASE
                    WHEN COALESCE(f.monto_final, 0) > 0 THEN
                        (
                            (
                                COALESCE(f.monto_final, 0)
                                - COALESCE(dc.costo_total_productos, 0)
                            )
                            / COALESCE(f.monto_final, 1)
                        ) * 100
                    ELSE 0
                END AS margen_utilidad,

                (
                    COALESCE(f.monto_total, 0)
                    - COALESCE(f.monto_final, 0)
                ) AS descuento_total,

                COALESCE(promo.monto_promocion, 0) AS monto_promocion,

                d.codigo AS codigo_descuento,
                COALESCE(d.descripcion, d.codigo, '-') AS descuento,
                d.valor AS valor_descuento,
                d.es_porcentaje AS descuento_es_porcentaje,

                promo.promociones,
                dc.total_unidades,
                dc.productos,
                f.pagado,
                f.estado,
                pago.referencia_externa,
                pago.monto_pagado

            FROM public.factura f
            JOIN public.cliente c
                ON f.id_cliente = c.id
            JOIN public.usuario u
                ON f.codigo_usuario = u.codigo
            JOIN public.tipo_pago tp
                ON f.id_tipo_pago = tp.id
            LEFT JOIN detalle_costos dc
                ON f.codigo = dc.codigo_factura
            LEFT JOIN pago_factura pago
                ON f.codigo = pago.codigo_factura
            LEFT JOIN promocion_factura promo
                ON f.codigo = promo.codigo_factura
            LEFT JOIN public.descuento d
                ON f.codigo_descuento = d.codigo
            WHERE 1 = 1
        """

        if fecha_inicio:
            query += " AND DATE(f.fecha_hora) >= %s"
            params.append(fecha_inicio)

        if fecha_fin:
            query += " AND DATE(f.fecha_hora) <= %s"
            params.append(fecha_fin)

        if codigo_usuario:
            query += " AND f.codigo_usuario = %s"
            params.append(codigo_usuario)

        if id_tipo_pago:
            query += " AND f.id_tipo_pago = %s"
            params.append(id_tipo_pago)

        if codigo_producto:
            query += """
                AND EXISTS (
                    SELECT 1
                    FROM public.detalle_factura df_filter
                    WHERE df_filter.codigo_factura = f.codigo
                    AND df_filter.codigo_producto = %s
                )
            """
            params.append(codigo_producto)

        if estado == 'activa':
            query += " AND f.estado = true"

        elif estado == 'anulada':
            query += " AND f.estado = false"

        if search:
            query += """
                AND (
                    f.codigo ILIKE %s
                    OR c.nombre ILIKE %s
                    OR c.ci ILIKE %s
                    OR u.nombre ILIKE %s
                    OR u.codigo ILIKE %s
                    OR tp.nombre ILIKE %s
                    OR COALESCE(dc.productos, '') ILIKE %s
                    OR COALESCE(d.codigo, '') ILIKE %s
                    OR COALESCE(d.descripcion, '') ILIKE %s
                    OR COALESCE(promo.promociones, '') ILIKE %s
                )
            """

            term = f'%{search}%'
            params.extend([
                term,
                term,
                term,
                term,
                term,
                term,
                term,
                term,
                term,
                term
            ])

        query += """
            ORDER BY f.fecha_hora DESC, f.codigo DESC
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    @staticmethod
    def calculate_profit_summary(rows):
        """
        Calcular totales generales del reporte de utilidad.
        """
        total_facturas = len(rows)
        facturas_activas = 0
        facturas_anuladas = 0

        total_bruto = Decimal('0.00')
        total_final_cobrado = Decimal('0.00')
        costo_total_productos = Decimal('0.00')
        utilidad_total = Decimal('0.00')
        descuento_total = Decimal('0.00')
        monto_promocion_total = Decimal('0.00')

        resumen_usuarios = {}
        resumen_tipos_pago = {}

        for row in rows:
            row_total_bruto = Report._to_decimal(row.get('total_bruto'))
            row_total_final = Report._to_decimal(row.get('total_final_cobrado'))
            row_costo = Report._to_decimal(row.get('costo_total_productos'))
            row_utilidad = Report._to_decimal(row.get('utilidad'))
            row_descuento = Report._to_decimal(row.get('descuento_total'))
            row_promocion = Report._to_decimal(row.get('monto_promocion'))

            total_bruto += row_total_bruto
            total_final_cobrado += row_total_final
            costo_total_productos += row_costo
            utilidad_total += row_utilidad
            descuento_total += row_descuento
            monto_promocion_total += row_promocion

            if row.get('estado'):
                facturas_activas += 1
            else:
                facturas_anuladas += 1

            usuario_key = row.get('codigo_usuario')
            usuario_nombre = row.get('usuario')

            if usuario_key not in resumen_usuarios:
                resumen_usuarios[usuario_key] = {
                    'codigo_usuario': usuario_key,
                    'usuario': usuario_nombre,
                    'cantidad': 0,
                    'total_final_cobrado': Decimal('0.00'),
                    'costo_total_productos': Decimal('0.00'),
                    'utilidad': Decimal('0.00')
                }

            resumen_usuarios[usuario_key]['cantidad'] += 1
            resumen_usuarios[usuario_key]['total_final_cobrado'] += row_total_final
            resumen_usuarios[usuario_key]['costo_total_productos'] += row_costo
            resumen_usuarios[usuario_key]['utilidad'] += row_utilidad

            tipo_pago_key = row.get('tipo_pago') or 'Sin tipo'

            if tipo_pago_key not in resumen_tipos_pago:
                resumen_tipos_pago[tipo_pago_key] = {
                    'tipo_pago': tipo_pago_key,
                    'cantidad': 0,
                    'total_final_cobrado': Decimal('0.00'),
                    'costo_total_productos': Decimal('0.00'),
                    'utilidad': Decimal('0.00')
                }

            resumen_tipos_pago[tipo_pago_key]['cantidad'] += 1
            resumen_tipos_pago[tipo_pago_key]['total_final_cobrado'] += row_total_final
            resumen_tipos_pago[tipo_pago_key]['costo_total_productos'] += row_costo
            resumen_tipos_pago[tipo_pago_key]['utilidad'] += row_utilidad

        if total_final_cobrado > 0:
            margen_global = (utilidad_total / total_final_cobrado) * Decimal('100')
        else:
            margen_global = Decimal('0.00')

        return {
            'total_facturas': total_facturas,
            'facturas_activas': facturas_activas,
            'facturas_anuladas': facturas_anuladas,
            'total_bruto': total_bruto,
            'total_final_cobrado': total_final_cobrado,
            'costo_total_productos': costo_total_productos,
            'utilidad_total': utilidad_total,
            'descuento_total': descuento_total,
            'monto_promocion_total': monto_promocion_total,
            'margen_global': margen_global,
            'resumen_usuarios': list(resumen_usuarios.values()),
            'resumen_tipos_pago': list(resumen_tipos_pago.values())
        }

    @staticmethod
    def register_report_action(codigo_usuario, accion, detalle):
        """
        Registrar acción relacionada a reportes en la bitácora.
        """
        if not codigo_usuario:
            return None

        accion_upper = accion.upper() if accion else ''

        if 'UTILIDAD' in accion_upper:
            id_registro_afectado = 'reporte_utilidad'
        else:
            id_registro_afectado = 'reporte_ventas'

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
                id_registro_afectado,
                detalle
            ))

            return cursor.fetchone()