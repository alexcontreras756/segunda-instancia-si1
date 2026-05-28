from database.connection import db
from decimal import Decimal


class OutputNote:

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
    def _to_decimal(value):
        """
        Convertir valor a Decimal de forma segura.
        """
        if value is None:
            return Decimal('0.00')

        return Decimal(str(value))

    @staticmethod
    def _generate_output_note_code(cursor):
        """
        Generar código automático para nota de salida.
        Ejemplo: NS001, NS002, NS003.
        """
        cursor.execute("""
            SELECT codigo
            FROM public.nota_salida
            WHERE codigo ~ '^NS[0-9]+$'
            ORDER BY CAST(SUBSTRING(codigo FROM 3) AS INTEGER) DESC
            LIMIT 1
        """)

        last_note = cursor.fetchone()

        if not last_note:
            return 'NS001'

        last_code = last_note['codigo']
        last_number = int(last_code.replace('NS', ''))
        new_number = last_number + 1

        return f'NS{new_number:03d}'

    @staticmethod
    def count_all():
        """
        Contar notas de salida activas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM public.nota_salida
                WHERE COALESCE(estado, true) = true
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_warehouses():
        """
        Obtener almacenes para filtrar inventario disponible.
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
    def get_available_inventory():
        """
        Obtener lotes de inventario disponibles.
        La nota de salida trabaja directamente con id_inventario.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.id AS id_inventario,
                    i.codigo_producto,
                    p.nombre AS producto,
                    p.precio_compra,
                    p.precio_venta,
                    i.codigo_almacen,
                    a.nombre AS almacen,
                    i.cantidad,
                    i.fecha_entrada,
                    i.fecha_vencimiento,
                    i.estado
                FROM public.inventario i
                JOIN public.producto p ON i.codigo_producto = p.codigo
                JOIN public.almacen a ON i.codigo_almacen = a.codigo
                WHERE i.estado = true
                AND i.cantidad > 0
                AND p.estado = true
                ORDER BY
                    a.codigo,
                    p.nombre,
                    COALESCE(i.fecha_vencimiento, DATE '9999-12-31') ASC,
                    i.fecha_entrada ASC,
                    i.id ASC
            """)

            return cursor.fetchall()

    @staticmethod
    def get_all(limit=100):
        """
        Listar notas de salida.
        La tabla nota_salida NO tiene codigo_almacen.
        El almacén se obtiene desde detalle_salida -> inventario -> almacen.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    ns.codigo,
                    ns.fecha_hora,
                    ns.motivo_general,
                    ns.monto_total_perdida,
                    ns.codigo_usuario,
                    u.nombre AS usuario,
                    COALESCE(ns.estado, true) AS estado,
                    COUNT(ds.id) AS total_items,
                    COALESCE(SUM(ds.cantidad), 0) AS total_unidades,
                    COALESCE(
                        STRING_AGG(DISTINCT a.nombre, ', '),
                        '-'
                    ) AS almacenes
                FROM public.nota_salida ns
                JOIN public.usuario u ON ns.codigo_usuario = u.codigo
                LEFT JOIN public.detalle_salida ds
                    ON ns.codigo = ds.codigo_nota_salida
                LEFT JOIN public.inventario i
                    ON ds.id_inventario = i.id
                LEFT JOIN public.almacen a
                    ON i.codigo_almacen = a.codigo
                GROUP BY
                    ns.codigo,
                    ns.fecha_hora,
                    ns.motivo_general,
                    ns.monto_total_perdida,
                    ns.codigo_usuario,
                    u.nombre,
                    ns.estado
                ORDER BY ns.fecha_hora DESC
                LIMIT %s
            """, (limit,))

            return cursor.fetchall()

    @staticmethod
    def find_by_code(codigo):
        """
        Buscar nota de salida por código.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    ns.codigo,
                    ns.fecha_hora,
                    ns.motivo_general,
                    ns.monto_total_perdida,
                    ns.codigo_usuario,
                    u.nombre AS usuario,
                    u.rol AS usuario_rol,
                    COALESCE(ns.estado, true) AS estado,
                    COUNT(ds.id) AS total_items,
                    COALESCE(SUM(ds.cantidad), 0) AS total_unidades,
                    COALESCE(
                        STRING_AGG(DISTINCT a.nombre, ', '),
                        '-'
                    ) AS almacenes
                FROM public.nota_salida ns
                JOIN public.usuario u ON ns.codigo_usuario = u.codigo
                LEFT JOIN public.detalle_salida ds
                    ON ns.codigo = ds.codigo_nota_salida
                LEFT JOIN public.inventario i
                    ON ds.id_inventario = i.id
                LEFT JOIN public.almacen a
                    ON i.codigo_almacen = a.codigo
                WHERE ns.codigo = %s
                GROUP BY
                    ns.codigo,
                    ns.fecha_hora,
                    ns.motivo_general,
                    ns.monto_total_perdida,
                    ns.codigo_usuario,
                    u.nombre,
                    u.rol,
                    ns.estado
            """, (codigo,))

            return cursor.fetchone()

    @staticmethod
    def get_details(codigo):
        """
        Obtener detalle de una nota de salida.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    ds.id,
                    ds.codigo_nota_salida,
                    ds.id_inventario,
                    ds.cantidad,
                    ds.costo_unitario_momento,
                    ds.subtotal_perdida,
                    ds.motivo_especifico,
                    i.codigo_producto,
                    p.nombre AS producto,
                    i.codigo_almacen,
                    a.nombre AS almacen,
                    i.fecha_entrada,
                    i.fecha_vencimiento
                FROM public.detalle_salida ds
                JOIN public.inventario i ON ds.id_inventario = i.id
                JOIN public.producto p ON i.codigo_producto = p.codigo
                JOIN public.almacen a ON i.codigo_almacen = a.codigo
                WHERE ds.codigo_nota_salida = %s
                ORDER BY ds.id
            """, (codigo,))

            return cursor.fetchall()

    @staticmethod
    def create_output_note(codigo_usuario, motivo_general, items):
        """
        Registrar nota de salida:
        - Crea nota_salida.
        - Crea detalle_salida.
        - Descuenta cantidad del id_inventario seleccionado.
        - Calcula costo_unitario_momento desde producto.precio_compra.
        - Calcula subtotal_perdida.
        - Actualiza monto_total_perdida.
        - Actualiza capacidad_actual del almacén.
        - Registra historial.
        """

        if not codigo_usuario:
            raise ValueError('No se encontró el usuario de la sesión.')

        if not motivo_general:
            raise ValueError('Debe ingresar el motivo general de la salida.')

        if not items:
            raise ValueError('Debe agregar al menos un producto a la nota de salida.')

        with db.get_cursor() as cursor:

            codigo_nota = OutputNote._generate_output_note_code(cursor)

            cursor.execute("""
                INSERT INTO public.nota_salida (
                    codigo,
                    fecha_hora,
                    motivo_general,
                    monto_total_perdida,
                    codigo_usuario,
                    estado
                )
                VALUES (%s, CURRENT_TIMESTAMP, %s, 0, %s, true)
                RETURNING
                    codigo,
                    fecha_hora,
                    motivo_general,
                    monto_total_perdida,
                    codigo_usuario,
                    estado
            """, (
                codigo_nota,
                motivo_general,
                codigo_usuario
            ))

            note = cursor.fetchone()

            monto_total_perdida = Decimal('0.00')
            total_unidades = 0

            for item in items:
                id_inventario = item.get('id_inventario')
                cantidad = item.get('cantidad')
                motivo_especifico = item.get('motivo_especifico')

                if not id_inventario:
                    raise ValueError('Hay un producto/lote sin seleccionar.')

                id_inventario = OutputNote._to_int(id_inventario, 'inventario')
                cantidad = OutputNote._to_int(cantidad, 'cantidad')

                if cantidad <= 0:
                    raise ValueError('La cantidad debe ser mayor a cero.')

                cursor.execute("""
                    SELECT
                        i.id,
                        i.codigo_producto,
                        i.codigo_almacen,
                        i.cantidad,
                        i.estado,
                        p.nombre AS producto,
                        COALESCE(p.precio_compra, 0) AS precio_compra,
                        a.nombre AS almacen
                    FROM public.inventario i
                    JOIN public.producto p ON i.codigo_producto = p.codigo
                    JOIN public.almacen a ON i.codigo_almacen = a.codigo
                    WHERE i.id = %s
                    FOR UPDATE
                """, (id_inventario,))

                inventory = cursor.fetchone()

                if not inventory:
                    raise ValueError('El lote de inventario seleccionado no existe.')

                if not inventory['estado'] or inventory['cantidad'] <= 0:
                    raise ValueError(
                        f'El lote del producto {inventory["producto"]} no tiene stock disponible.'
                    )

                if inventory['cantidad'] < cantidad:
                    raise ValueError(
                        f'Stock insuficiente para {inventory["producto"]}. '
                        f'Disponible en lote: {inventory["cantidad"]}, solicitado: {cantidad}.'
                    )

                costo_unitario = OutputNote._to_decimal(inventory['precio_compra'])

                if costo_unitario <= 0:
                    raise ValueError(
                        f'El producto {inventory["producto"]} no tiene precio de compra válido. '
                        f'Actualice el precio de compra antes de registrar la salida.'
                    )

                subtotal = costo_unitario * Decimal(cantidad)

                cursor.execute("""
                    INSERT INTO public.detalle_salida (
                        codigo_nota_salida,
                        id_inventario,
                        cantidad,
                        costo_unitario_momento,
                        subtotal_perdida,
                        motivo_especifico
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    codigo_nota,
                    id_inventario,
                    cantidad,
                    costo_unitario,
                    subtotal,
                    motivo_especifico
                ))

                if inventory['cantidad'] == cantidad:
                    cursor.execute("""
                        UPDATE public.inventario
                        SET cantidad = 0,
                            estado = false
                        WHERE id = %s
                    """, (id_inventario,))
                else:
                    cursor.execute("""
                        UPDATE public.inventario
                        SET cantidad = cantidad - %s
                        WHERE id = %s
                    """, (
                        cantidad,
                        id_inventario
                    ))

                cursor.execute("""
                    UPDATE public.almacen
                    SET capacidad_actual = GREATEST(capacidad_actual - %s, 0)
                    WHERE codigo = %s
                """, (
                    cantidad,
                    inventory['codigo_almacen']
                ))

                monto_total_perdida += subtotal
                total_unidades += cantidad

            cursor.execute("""
                UPDATE public.nota_salida
                SET monto_total_perdida = %s
                WHERE codigo = %s
                RETURNING
                    codigo,
                    fecha_hora,
                    motivo_general,
                    monto_total_perdida,
                    codigo_usuario,
                    estado
            """, (
                monto_total_perdida,
                codigo_nota
            ))

            updated_note = cursor.fetchone()

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
                'REGISTRO DE NOTA DE SALIDA',
                'nota_salida',
                codigo_nota,
                f'Nota de salida {codigo_nota} registrada. Unidades: {total_unidades}. Pérdida Bs {monto_total_perdida}.'
            ))

            return updated_note

    @staticmethod
    def cancel_output_note(codigo_nota, codigo_usuario):
        """
        Anular nota de salida:
        - Devuelve cantidades a los mismos id_inventario.
        - Reactiva inventario si estaba en false.
        - Actualiza capacidad_actual del almacén.
        - Cambia estado de nota_salida a false.
        """

        if not codigo_nota:
            raise ValueError('No se encontró la nota de salida.')

        if not codigo_usuario:
            raise ValueError('No se encontró el usuario de la sesión.')

        with db.get_cursor() as cursor:

            cursor.execute("""
                SELECT
                    codigo,
                    monto_total_perdida,
                    COALESCE(estado, true) AS estado
                FROM public.nota_salida
                WHERE codigo = %s
                FOR UPDATE
            """, (codigo_nota,))

            note = cursor.fetchone()

            if not note:
                raise ValueError('La nota de salida no existe.')

            if note['estado'] is False:
                raise ValueError('La nota de salida ya está anulada.')

            cursor.execute("""
                SELECT
                    ds.id,
                    ds.id_inventario,
                    ds.cantidad,
                    i.codigo_almacen
                FROM public.detalle_salida ds
                JOIN public.inventario i ON ds.id_inventario = i.id
                WHERE ds.codigo_nota_salida = %s
                ORDER BY ds.id
            """, (codigo_nota,))

            details = cursor.fetchall()

            total_unidades = 0

            for detail in details:
                cursor.execute("""
                    UPDATE public.inventario
                    SET cantidad = cantidad + %s,
                        estado = true
                    WHERE id = %s
                """, (
                    detail['cantidad'],
                    detail['id_inventario']
                ))

                cursor.execute("""
                    UPDATE public.almacen
                    SET capacidad_actual = capacidad_actual + %s
                    WHERE codigo = %s
                """, (
                    detail['cantidad'],
                    detail['codigo_almacen']
                ))

                total_unidades += detail['cantidad']

            cursor.execute("""
                UPDATE public.nota_salida
                SET estado = false
                WHERE codigo = %s
                RETURNING codigo, estado
            """, (codigo_nota,))

            cancelled_note = cursor.fetchone()

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
                'ANULACION DE NOTA DE SALIDA',
                'nota_salida',
                codigo_nota,
                f'Nota de salida {codigo_nota} anulada. Se devolvieron {total_unidades} unidades al inventario.'
            ))

            return cancelled_note