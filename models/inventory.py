from database.connection import db


class Inventory:

    @staticmethod
    def _to_int(value, field_name='valor'):
        """
        Convertir valor a entero de forma segura.
        """
        try:
            number = int(value)
        except Exception:
            raise ValueError(f'El campo {field_name} debe ser un número entero.')

        return number

    @staticmethod
    def _sync_warehouse_capacity(cursor, codigo_almacen):
        """
        Recalcular la capacidad actual del almacén usando inventario activo.
        Esto evita descuadres entre inventario y almacen.capacidad_actual.
        """
        cursor.execute("""
            SELECT COALESCE(SUM(cantidad), 0) AS total
            FROM public.inventario
            WHERE codigo_almacen = %s
            AND estado = true
            AND cantidad > 0
        """, (codigo_almacen,))

        result = cursor.fetchone()
        total = result['total'] if result else 0

        cursor.execute("""
            UPDATE public.almacen
            SET capacidad_actual = %s
            WHERE codigo = %s
        """, (total, codigo_almacen))

        return total

    @staticmethod
    def count_inventory_items():
        """
        Contar productos con inventario activo por almacén.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM (
                    SELECT codigo_producto, codigo_almacen
                    FROM public.inventario
                    WHERE estado = true
                    AND cantidad > 0
                    GROUP BY codigo_producto, codigo_almacen
                ) AS inv
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def count_low_stock():
        """
        Contar productos cuyo stock total está en alerta.
        La alerta se calcula comparando el stock total contra producto.stock_minimo.
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
                    HAVING COALESCE(SUM(i.cantidad), 0) <= COALESCE(p.stock_minimo, 0)
                ) AS alerta
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def count_out_of_stock():
        """
        Contar productos activos sin stock.
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
    def get_counters():
        """
        Obtener contadores principales para la pantalla de inventario.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(cantidad), 0) AS total_unidades
                FROM public.inventario
                WHERE estado = true
                AND cantidad > 0
            """)

            total_units = cursor.fetchone()

            return {
                'inventory_items': Inventory.count_inventory_items(),
                'low_stock': Inventory.count_low_stock(),
                'out_of_stock': Inventory.count_out_of_stock(),
                'total_units': total_units['total_unidades'] if total_units else 0
            }

    @staticmethod
    def get_warehouses():
        """
        Obtener almacenes para filtros y formularios.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    direccion,
                    capacidad_actual,
                    capacidad_total
                FROM public.almacen
                ORDER BY codigo
            """)

            return cursor.fetchall()

    @staticmethod
    def get_products():
        """
        Obtener productos activos para ajustes de inventario.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    precio_compra,
                    precio_venta,
                    stock_minimo,
                    estado
                FROM public.producto
                WHERE estado = true
                ORDER BY nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def get_summary(search=None, codigo_almacen=None, estado_stock=None):
        """
        Obtener inventario agrupado por almacén y producto.
        También calcula el stock total del producto en todos los almacenes.
        """
        search = search.strip() if search else None
        codigo_almacen = codigo_almacen.strip() if codigo_almacen else None
        estado_stock = estado_stock.strip() if estado_stock else None

        params = []

        query = """
            WITH stock_por_almacen AS (
                SELECT
                    codigo_producto,
                    codigo_almacen,
                    COALESCE(SUM(cantidad), 0) AS cantidad_almacen,
                    MAX(fecha_entrada) AS ultima_entrada,
                    MIN(fecha_vencimiento) FILTER (
                        WHERE fecha_vencimiento IS NOT NULL
                        AND cantidad > 0
                    ) AS proximo_vencimiento
                FROM public.inventario
                WHERE estado = true
                AND cantidad > 0
                GROUP BY codigo_producto, codigo_almacen
            ),
            stock_global AS (
                SELECT
                    codigo_producto,
                    COALESCE(SUM(cantidad), 0) AS stock_total_producto
                FROM public.inventario
                WHERE estado = true
                AND cantidad > 0
                GROUP BY codigo_producto
            )
            SELECT
                spa.codigo_almacen,
                a.nombre AS almacen,
                a.direccion AS almacen_direccion,
                spa.codigo_producto,
                p.nombre AS producto,
                p.precio_compra,
                p.precio_venta,
                COALESCE(p.stock_minimo, 0) AS stock_minimo,
                spa.cantidad_almacen,
                COALESCE(sg.stock_total_producto, 0) AS stock_total_producto,
                spa.ultima_entrada,
                spa.proximo_vencimiento
            FROM stock_por_almacen spa
            JOIN public.producto p ON spa.codigo_producto = p.codigo
            JOIN public.almacen a ON spa.codigo_almacen = a.codigo
            LEFT JOIN stock_global sg ON spa.codigo_producto = sg.codigo_producto
            WHERE p.estado = true
        """

        if codigo_almacen:
            query += " AND spa.codigo_almacen = %s"
            params.append(codigo_almacen)

        if search:
            query += """
                AND (
                    p.nombre ILIKE %s
                    OR p.codigo ILIKE %s
                    OR a.nombre ILIKE %s
                    OR a.codigo ILIKE %s
                )
            """
            term = f'%{search}%'
            params.extend([term, term, term, term])

        query += """
            ORDER BY
                a.codigo,
                p.nombre
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        inventory = []

        for row in rows:
            item = dict(row)

            stock_total = item['stock_total_producto'] or 0
            stock_minimo = item['stock_minimo'] or 0

            if stock_total <= 0:
                item['estado_stock'] = 'agotado'
            elif stock_minimo > 0 and stock_total <= stock_minimo:
                item['estado_stock'] = 'bajo'
            else:
                item['estado_stock'] = 'normal'

            if estado_stock and item['estado_stock'] != estado_stock:
                continue

            inventory.append(item)

        return inventory

    @staticmethod
    def get_low_stock_alerts(search=None):
        """
        Obtener productos con stock bajo o agotado.
        Incluye productos activos aunque no tengan registros en inventario.
        """
        search = search.strip() if search else None
        params = []

        query = """
            SELECT
                p.codigo AS codigo_producto,
                p.nombre AS producto,
                p.precio_compra,
                p.precio_venta,
                COALESCE(p.stock_minimo, 0) AS stock_minimo,
                COALESCE(SUM(i.cantidad), 0) AS stock_total,
                CASE
                    WHEN COALESCE(SUM(i.cantidad), 0) <= 0 THEN 'agotado'
                    WHEN COALESCE(SUM(i.cantidad), 0) <= COALESCE(p.stock_minimo, 0) THEN 'bajo'
                    ELSE 'normal'
                END AS estado_stock
            FROM public.producto p
            LEFT JOIN public.inventario i
                ON p.codigo = i.codigo_producto
                AND i.estado = true
                AND i.cantidad > 0
            WHERE p.estado = true
        """

        if search:
            query += """
                AND (
                    p.nombre ILIKE %s
                    OR p.codigo ILIKE %s
                )
            """
            term = f'%{search}%'
            params.extend([term, term])

        query += """
            GROUP BY
                p.codigo,
                p.nombre,
                p.precio_compra,
                p.precio_venta,
                p.stock_minimo
            HAVING COALESCE(SUM(i.cantidad), 0) <= COALESCE(p.stock_minimo, 0)
            ORDER BY
                estado_stock,
                p.nombre
        """

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    @staticmethod
    def get_detail(codigo_almacen, codigo_producto):
        """
        Obtener resumen de un producto en un almacén específico.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    a.codigo AS codigo_almacen,
                    a.nombre AS almacen,
                    a.direccion AS almacen_direccion,
                    a.capacidad_actual,
                    a.capacidad_total,
                    p.codigo AS codigo_producto,
                    p.nombre AS producto,
                    p.precio_compra,
                    p.precio_venta,
                    COALESCE(p.stock_minimo, 0) AS stock_minimo,
                    COALESCE((
                        SELECT SUM(i.cantidad)
                        FROM public.inventario i
                        WHERE i.codigo_almacen = a.codigo
                        AND i.codigo_producto = p.codigo
                        AND i.estado = true
                        AND i.cantidad > 0
                    ), 0) AS stock_almacen,
                    COALESCE((
                        SELECT SUM(i2.cantidad)
                        FROM public.inventario i2
                        WHERE i2.codigo_producto = p.codigo
                        AND i2.estado = true
                        AND i2.cantidad > 0
                    ), 0) AS stock_total_producto
                FROM public.almacen a
                CROSS JOIN public.producto p
                WHERE a.codigo = %s
                AND p.codigo = %s
                AND p.estado = true
            """, (codigo_almacen, codigo_producto))

            detail = cursor.fetchone()

            if not detail:
                return None

            cursor.execute("""
                SELECT
                    id,
                    codigo_producto,
                    codigo_almacen,
                    cantidad,
                    fecha_entrada,
                    fecha_vencimiento,
                    estado
                FROM public.inventario
                WHERE codigo_almacen = %s
                AND codigo_producto = %s
                ORDER BY
                    estado DESC,
                    fecha_entrada DESC,
                    id DESC
            """, (codigo_almacen, codigo_producto))

            lots = cursor.fetchall()

            detail = dict(detail)
            stock_total = detail['stock_total_producto'] or 0
            stock_minimo = detail['stock_minimo'] or 0

            if stock_total <= 0:
                detail['estado_stock'] = 'agotado'
            elif stock_minimo > 0 and stock_total <= stock_minimo:
                detail['estado_stock'] = 'bajo'
            else:
                detail['estado_stock'] = 'normal'

            return {
                'detail': detail,
                'lots': lots
            }

    @staticmethod
    def register_adjustment(
        codigo_almacen,
        codigo_producto,
        tipo_movimiento,
        cantidad,
        codigo_usuario,
        motivo=None,
        fecha_vencimiento=None
    ):
        """
        Registrar ajuste de inventario.

        tipo_movimiento:
        - entrada: agrega unidades al inventario
        - salida: descuenta unidades del inventario usando FEFO/FIFO
        """

        if not codigo_almacen:
            raise ValueError('Debe seleccionar un almacén.')

        if not codigo_producto:
            raise ValueError('Debe seleccionar un producto.')

        if not tipo_movimiento:
            raise ValueError('Debe seleccionar el tipo de movimiento.')

        tipo_movimiento = tipo_movimiento.lower().strip()

        if tipo_movimiento not in ['entrada', 'salida']:
            raise ValueError('El tipo de movimiento debe ser entrada o salida.')

        cantidad = Inventory._to_int(cantidad, 'cantidad')

        if cantidad <= 0:
            raise ValueError('La cantidad debe ser mayor a cero.')

        if not codigo_usuario:
            raise ValueError('No se encontró el usuario de la sesión.')

        if fecha_vencimiento == '':
            fecha_vencimiento = None

        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    capacidad_actual,
                    capacidad_total
                FROM public.almacen
                WHERE codigo = %s
                FOR UPDATE
            """, (codigo_almacen,))

            warehouse = cursor.fetchone()

            if not warehouse:
                raise ValueError('El almacén seleccionado no existe.')

            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    estado
                FROM public.producto
                WHERE codigo = %s
                AND estado = true
            """, (codigo_producto,))

            product = cursor.fetchone()

            if not product:
                raise ValueError('El producto seleccionado no existe o está inactivo.')

            cursor.execute("""
                SELECT COALESCE(SUM(cantidad), 0) AS stock_actual_almacen
                FROM public.inventario
                WHERE codigo_almacen = %s
                AND codigo_producto = %s
                AND estado = true
                AND cantidad > 0
            """, (codigo_almacen, codigo_producto))

            stock = cursor.fetchone()
            stock_actual_almacen = stock['stock_actual_almacen'] if stock else 0

            if tipo_movimiento == 'entrada':
                capacidad_actual = warehouse['capacidad_actual'] or 0
                capacidad_total = warehouse['capacidad_total'] or 0

                if capacidad_total > 0 and capacidad_actual + cantidad > capacidad_total:
                    raise ValueError(
                        'La entrada supera la capacidad total del almacén seleccionado.'
                    )

                cursor.execute("""
                    INSERT INTO public.inventario (
                        codigo_producto,
                        codigo_almacen,
                        cantidad,
                        fecha_entrada,
                        fecha_vencimiento,
                        estado
                    )
                    VALUES (%s, %s, %s, CURRENT_DATE, %s, true)
                    RETURNING
                        id,
                        codigo_producto,
                        codigo_almacen,
                        cantidad,
                        fecha_entrada,
                        fecha_vencimiento,
                        estado
                """, (
                    codigo_producto,
                    codigo_almacen,
                    cantidad,
                    fecha_vencimiento
                ))

                inventory_record = cursor.fetchone()

                Inventory._sync_warehouse_capacity(cursor, codigo_almacen)

                accion = 'AJUSTE DE INVENTARIO - ENTRADA'
                valor_nuevo = (
                    f'Entrada manual de {cantidad} unidades del producto '
                    f'{codigo_producto} al almacén {codigo_almacen}. '
                    f'Motivo: {motivo or "Sin motivo"}'
                )

                id_afectado = str(inventory_record['id'])

            else:
                if stock_actual_almacen < cantidad:
                    raise ValueError(
                        f'Stock insuficiente. Disponible: {stock_actual_almacen}, solicitado: {cantidad}.'
                    )

                cursor.execute("""
                    SELECT
                        id,
                        cantidad
                    FROM public.inventario
                    WHERE codigo_almacen = %s
                    AND codigo_producto = %s
                    AND estado = true
                    AND cantidad > 0
                    ORDER BY
                        COALESCE(fecha_vencimiento, DATE '9999-12-31') ASC,
                        fecha_entrada ASC,
                        id ASC
                    FOR UPDATE
                """, (codigo_almacen, codigo_producto))

                lots = cursor.fetchall()
                remaining = cantidad

                for lot in lots:
                    if remaining <= 0:
                        break

                    lot_quantity = lot['cantidad']

                    if lot_quantity <= remaining:
                        cursor.execute("""
                            UPDATE public.inventario
                            SET cantidad = 0,
                                estado = false
                            WHERE id = %s
                        """, (lot['id'],))

                        remaining -= lot_quantity

                    else:
                        cursor.execute("""
                            UPDATE public.inventario
                            SET cantidad = cantidad - %s
                            WHERE id = %s
                        """, (remaining, lot['id']))

                        remaining = 0

                Inventory._sync_warehouse_capacity(cursor, codigo_almacen)

                accion = 'AJUSTE DE INVENTARIO - SALIDA'
                valor_nuevo = (
                    f'Salida manual de {cantidad} unidades del producto '
                    f'{codigo_producto} del almacén {codigo_almacen}. '
                    f'Motivo: {motivo or "Sin motivo"}'
                )

                id_afectado = codigo_producto

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
                'inventario',
                id_afectado,
                valor_nuevo
            ))

            return {
                'codigo_almacen': codigo_almacen,
                'codigo_producto': codigo_producto,
                'tipo_movimiento': tipo_movimiento,
                'cantidad': cantidad
            }