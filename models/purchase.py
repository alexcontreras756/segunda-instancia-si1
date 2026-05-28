from database.connection import db
from decimal import Decimal


class Purchase:

    @staticmethod
    def _to_int(value, field_name='valor'):
        try:
            number = int(value)
        except Exception:
            raise ValueError(f'El campo {field_name} debe ser un número entero.')

        return number

    @staticmethod
    def _to_decimal(value, field_name='valor'):
        """
        Convierte números a Decimal.
        Acepta punto o coma:
        7.50
        7,50
        """
        if value is None or str(value).strip() == '':
            raise ValueError(f'El campo {field_name} es obligatorio.')

        value = str(value).strip().replace(',', '.')

        try:
            number = Decimal(value)
        except Exception:
            raise ValueError(f'El campo {field_name} debe ser un valor numérico.')

        return number

    @staticmethod
    def _generate_purchase_code(cursor):
        """
        Generar código automático para nota de compra.
        Ejemplo: COM001, COM002, COM003.
        """
        cursor.execute("""
            SELECT codigo
            FROM public.nota_compra
            WHERE codigo ~ '^COM[0-9]+$'
            ORDER BY CAST(SUBSTRING(codigo FROM 4) AS INTEGER) DESC
            LIMIT 1
        """)

        last_purchase = cursor.fetchone()

        if not last_purchase:
            return 'COM001'

        last_code = last_purchase['codigo']
        last_number = int(last_code.replace('COM', ''))
        new_number = last_number + 1

        return f'COM{new_number:03d}'

    @staticmethod
    def count_all():
        """
        Contar notas de compra activas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM public.nota_compra
                WHERE estado = true
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_all(limit=100):
        """
        Listar notas de compra registradas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    nc.codigo,
                    nc.fecha_hora,
                    nc.codigo_proveedor,
                    pr.nombre AS proveedor,
                    nc.codigo_usuario,
                    u.nombre AS usuario,
                    nc.codigo_almacen,
                    a.nombre AS almacen,
                    nc.monto_total,
                    nc.observacion,
                    nc.estado
                FROM public.nota_compra nc
                JOIN public.proveedor pr ON nc.codigo_proveedor = pr.codigo
                JOIN public.usuario u ON nc.codigo_usuario = u.codigo
                JOIN public.almacen a ON nc.codigo_almacen = a.codigo
                ORDER BY nc.fecha_hora DESC
                LIMIT %s
            """, (limit,))

            return cursor.fetchall()

    @staticmethod
    def get_providers_for_purchase():
        """
        Obtener proveedores para registrar compras.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    telefono,
                    email
                FROM public.proveedor
                ORDER BY nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def get_warehouses_for_purchase():
        """
        Obtener almacenes para recibir la compra.
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
    def get_products_for_purchase():
        """
        Obtener productos activos para registrar compra.
        Se incluye codigo_proveedor para filtrar productos según el proveedor seleccionado.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    precio_compra,
                    precio_venta,
                    stock_minimo,
                    codigo_proveedor,
                    estado
                FROM public.producto
                WHERE estado = true
                ORDER BY nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def find_by_code(codigo_compra):
        """
        Buscar nota de compra por código.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    nc.codigo,
                    nc.fecha_hora,
                    nc.codigo_proveedor,
                    pr.nombre AS proveedor,
                    pr.telefono AS proveedor_telefono,
                    pr.email AS proveedor_email,
                    nc.codigo_usuario,
                    u.nombre AS usuario,
                    nc.codigo_almacen,
                    a.nombre AS almacen,
                    a.direccion AS almacen_direccion,
                    nc.monto_total,
                    nc.observacion,
                    nc.estado
                FROM public.nota_compra nc
                JOIN public.proveedor pr ON nc.codigo_proveedor = pr.codigo
                JOIN public.usuario u ON nc.codigo_usuario = u.codigo
                JOIN public.almacen a ON nc.codigo_almacen = a.codigo
                WHERE nc.codigo = %s
            """, (codigo_compra,))

            return cursor.fetchone()

    @staticmethod
    def get_details(codigo_compra):
        """
        Obtener detalle de una nota de compra.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    dc.id,
                    dc.codigo_nota_compra,
                    dc.codigo_producto,
                    p.nombre AS producto,
                    dc.cantidad,
                    dc.costo_unitario,
                    dc.subtotal,
                    dc.fecha_vencimiento
                FROM public.detalle_compra dc
                JOIN public.producto p ON dc.codigo_producto = p.codigo
                WHERE dc.codigo_nota_compra = %s
                ORDER BY dc.id
            """, (codigo_compra,))

            return cursor.fetchall()

    @staticmethod
    def create_purchase(codigo_proveedor, codigo_almacen, codigo_usuario, items, observacion=None):
        """
        Registrar compra:
        - Inserta nota_compra.
        - Inserta detalle_compra.
        - Actualiza precio_compra/precio_venta del producto.
        - Inserta inventario.
        - Actualiza capacidad_actual del almacén.
        - Registra historial.
        """

        if not codigo_proveedor:
            raise ValueError('Debe seleccionar un proveedor.')

        if not codigo_almacen:
            raise ValueError('Debe seleccionar un almacén.')

        if not codigo_usuario:
            raise ValueError('No se encontró el usuario de la sesión.')

        if not items:
            raise ValueError('Debe agregar al menos un producto a la compra.')

        with db.get_cursor() as cursor:

            cursor.execute("""
                SELECT codigo, nombre
                FROM public.proveedor
                WHERE codigo = %s
            """, (codigo_proveedor,))

            provider = cursor.fetchone()

            if not provider:
                raise ValueError('El proveedor seleccionado no existe.')

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

            codigo_compra = Purchase._generate_purchase_code(cursor)

            detalles = []
            monto_total = Decimal('0.00')
            cantidad_total_compra = 0

            for item in items:
                codigo_producto = item.get('codigo_producto')
                cantidad = item.get('cantidad')
                costo_unitario = item.get('costo_unitario')
                precio_venta = item.get('precio_venta')
                fecha_vencimiento = item.get('fecha_vencimiento')

                if not codigo_producto:
                    raise ValueError('Hay un producto sin seleccionar.')

                cantidad = Purchase._to_int(cantidad, 'cantidad')

                if cantidad <= 0:
                    raise ValueError('La cantidad debe ser mayor a cero.')

                costo_unitario = Purchase._to_decimal(costo_unitario, 'costo unitario')

                if costo_unitario <= 0:
                    raise ValueError('El costo unitario debe ser mayor a cero.')

                if fecha_vencimiento == '':
                    fecha_vencimiento = None

                cursor.execute("""
                    SELECT
                        codigo,
                        nombre,
                        precio_compra,
                        precio_venta,
                        codigo_proveedor,
                        estado
                    FROM public.producto
                    WHERE codigo = %s
                    AND estado = true
                """, (codigo_producto,))

                product = cursor.fetchone()

                if not product:
                    raise ValueError(f'El producto {codigo_producto} no existe o está inactivo.')

                if product['codigo_proveedor'] != codigo_proveedor:
                    raise ValueError(
                        f'El producto {product["nombre"]} no pertenece al proveedor seleccionado.'
                    )

                if precio_venta is None or str(precio_venta).strip() == '':
                    precio_venta_final = product['precio_venta']
                else:
                    precio_venta_final = Purchase._to_decimal(precio_venta, 'precio de venta')

                    if precio_venta_final <= 0:
                        raise ValueError('El precio de venta debe ser mayor a cero.')

                subtotal = costo_unitario * Decimal(cantidad)

                detalles.append({
                    'codigo_producto': product['codigo'],
                    'nombre_producto': product['nombre'],
                    'cantidad': cantidad,
                    'costo_unitario': costo_unitario,
                    'precio_venta': precio_venta_final,
                    'subtotal': subtotal,
                    'fecha_vencimiento': fecha_vencimiento
                })

                monto_total += subtotal
                cantidad_total_compra += cantidad

            capacidad_actual = warehouse['capacidad_actual'] or 0
            capacidad_total = warehouse['capacidad_total'] or 0

            if capacidad_total > 0 and capacidad_actual + cantidad_total_compra > capacidad_total:
                raise ValueError('La compra supera la capacidad total del almacén seleccionado.')

            cursor.execute("""
                INSERT INTO public.nota_compra (
                    codigo,
                    fecha_hora,
                    codigo_proveedor,
                    codigo_usuario,
                    codigo_almacen,
                    monto_total,
                    observacion,
                    estado
                )
                VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, true)
                RETURNING
                    codigo,
                    fecha_hora,
                    codigo_proveedor,
                    codigo_usuario,
                    codigo_almacen,
                    monto_total,
                    observacion,
                    estado
            """, (
                codigo_compra,
                codigo_proveedor,
                codigo_usuario,
                codigo_almacen,
                monto_total,
                observacion
            ))

            purchase = cursor.fetchone()

            for detail in detalles:
                cursor.execute("""
                    INSERT INTO public.detalle_compra (
                        codigo_nota_compra,
                        codigo_producto,
                        cantidad,
                        costo_unitario,
                        subtotal,
                        fecha_vencimiento
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    codigo_compra,
                    detail['codigo_producto'],
                    detail['cantidad'],
                    detail['costo_unitario'],
                    detail['subtotal'],
                    detail['fecha_vencimiento']
                ))

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
                """, (
                    detail['codigo_producto'],
                    codigo_almacen,
                    detail['cantidad'],
                    detail['fecha_vencimiento']
                ))

                cursor.execute("""
                    UPDATE public.producto
                    SET
                        precio_compra = %s,
                        precio_venta = %s,
                        codigo_proveedor = %s
                    WHERE codigo = %s
                """, (
                    detail['costo_unitario'],
                    detail['precio_venta'],
                    codigo_proveedor,
                    detail['codigo_producto']
                ))

            cursor.execute("""
                UPDATE public.almacen
                SET capacidad_actual = capacidad_actual + %s
                WHERE codigo = %s
            """, (
                cantidad_total_compra,
                codigo_almacen
            ))

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
                'REGISTRO DE COMPRA',
                'nota_compra',
                codigo_compra,
                f'Compra registrada por Bs {monto_total} al proveedor {codigo_proveedor}'
            ))

            return {
                'purchase': purchase,
                'details': detalles
            }