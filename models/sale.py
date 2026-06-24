from database.connection import db
from decimal import Decimal


class Sale:

    @staticmethod
    def _to_decimal(value):
        """
        Convertir valor a Decimal de forma segura.
        """
        if value is None:
            return Decimal('0.00')

        return Decimal(str(value))

    @staticmethod
    def _get_table_columns(cursor, table_name):
        """
        Obtener columnas reales de una tabla del esquema public.
        Sirve para trabajar sin romper si la tabla promocion todavía
        solo tiene las columnas originales del documento.
        """
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
        """, (table_name,))

        return {row['column_name'] for row in cursor.fetchall()}

    @staticmethod
    def count_all():
        """
        Contar ventas activas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM public.factura
                WHERE estado = true
            """)

            result = cursor.fetchone()
            return result['total'] if result else 0

    @staticmethod
    def get_payment_types():
        """
        Obtener tipos de pago activos.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, nombre, descripcion, activo
                FROM public.tipo_pago
                WHERE activo = true
                ORDER BY id
            """)

            return cursor.fetchall()

    @staticmethod
    def get_active_discounts():
        """
        Obtener descuentos activos y vigentes para ventas.
        Usa tabla real public.descuento.
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
    def get_discounts_for_sale():
        """
        Alias para compatibilidad con controladores anteriores.
        """
        return Sale.get_active_discounts()

    @staticmethod
    def get_active_promotions():
        """
        Obtener promociones activas y vigentes para ventas.

        Usa la estructura real:
        - public.promocion.id
        - public.promocion.nombre
        - public.promocion.descripcion
        - public.promocion.fecha_inicio
        - public.promocion.fecha_fin
        - public.promocion.activo
        - public.promocion_producto.id_promocion
        - public.promocion_producto.codigo_producto

        Si en el SQL de CU15 agregaste columnas extra como valor,
        es_porcentaje, compra_minima o tipo_aplicacion, también las usa.
        """
        with db.get_cursor() as cursor:
            columns = Sale._get_table_columns(cursor, 'promocion')

            tipo_select = (
                "pr.tipo_aplicacion"
                if 'tipo_aplicacion' in columns
                else "'producto'::VARCHAR AS tipo_aplicacion"
            )

            valor_select = (
                "pr.valor"
                if 'valor' in columns
                else "0::NUMERIC AS valor"
            )

            es_porcentaje_select = (
                "pr.es_porcentaje"
                if 'es_porcentaje' in columns
                else "false::BOOLEAN AS es_porcentaje"
            )

            compra_minima_select = (
                "pr.compra_minima"
                if 'compra_minima' in columns
                else "0::NUMERIC AS compra_minima"
            )

            cursor.execute(f"""
                SELECT
                    pr.id,
                    pr.nombre,
                    pr.descripcion,
                    pr.fecha_inicio,
                    pr.fecha_fin,
                    pr.activo,
                    {tipo_select},
                    {valor_select},
                    {es_porcentaje_select},
                    {compra_minima_select},
                    COUNT(pp.codigo_producto) AS total_productos,
                    COALESCE(
                        STRING_AGG(DISTINCT p.nombre, ', '),
                        'Promoción general'
                    ) AS productos
                FROM public.promocion pr
                LEFT JOIN public.promocion_producto pp
                    ON pr.id = pp.id_promocion
                LEFT JOIN public.producto p
                    ON pp.codigo_producto = p.codigo
                WHERE pr.activo = true
                AND pr.fecha_inicio <= CURRENT_DATE
                AND pr.fecha_fin >= CURRENT_DATE
                GROUP BY
                    pr.id,
                    pr.nombre,
                    pr.descripcion,
                    pr.fecha_inicio,
                    pr.fecha_fin,
                    pr.activo
                    {", pr.tipo_aplicacion" if 'tipo_aplicacion' in columns else ""}
                    {", pr.valor" if 'valor' in columns else ""}
                    {", pr.es_porcentaje" if 'es_porcentaje' in columns else ""}
                    {", pr.compra_minima" if 'compra_minima' in columns else ""}
                ORDER BY pr.nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def get_promotions_for_sale():
        """
        Alias para compatibilidad con controladores.
        """
        return Sale.get_active_promotions()

    @staticmethod
    def get_clients_for_sale():
        """
        Obtener clientes disponibles para ventas.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, ci, nombre, correo_electronico, telefono
                FROM public.cliente
                ORDER BY nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def get_products_for_sale():
        """
        Obtener productos activos disponibles para venta.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    codigo,
                    nombre,
                    precio_venta,
                    precio_compra,
                    stock_minimo,
                    estado
                FROM public.producto
                WHERE estado = true
                ORDER BY nombre
            """)

            return cursor.fetchall()

    @staticmethod
    def _generate_invoice_code(cursor):
        """
        Generar código automático de factura.
        Ejemplo: FAC001, FAC002, FAC003.
        """
        cursor.execute("""
            SELECT codigo
            FROM public.factura
            WHERE codigo ~ '^FAC[0-9]+$'
            ORDER BY CAST(SUBSTRING(codigo FROM 4) AS INTEGER) DESC
            LIMIT 1
        """)

        last_invoice = cursor.fetchone()

        if not last_invoice:
            return 'FAC001'

        last_code = last_invoice['codigo']
        last_number = int(last_code.replace('FAC', ''))
        new_number = last_number + 1

        return f'FAC{new_number:03d}'

    @staticmethod
    def _get_product(cursor, codigo_producto):
        """
        Obtener producto activo por código.
        """
        cursor.execute("""
            SELECT
                codigo,
                nombre,
                precio_venta,
                estado
            FROM public.producto
            WHERE codigo = %s
            AND estado = true
        """, (codigo_producto,))

        return cursor.fetchone()

    @staticmethod
    def _get_discount(cursor, codigo_descuento):
        """
        Obtener descuento activo y vigente.
        Si no se selecciona descuento, retorna None.
        """
        if not codigo_descuento:
            return None

        codigo_descuento = str(codigo_descuento).strip().upper()

        if codigo_descuento == '':
            return None

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
            AND activo = true
            AND (fecha_inicio IS NULL OR fecha_inicio <= CURRENT_DATE)
            AND (fecha_fin IS NULL OR fecha_fin >= CURRENT_DATE)
            LIMIT 1
        """, (codigo_descuento,))

        discount = cursor.fetchone()

        if not discount:
            raise ValueError('El descuento seleccionado no existe, está inactivo o no está vigente.')

        return discount

    @staticmethod
    def _calculate_discount_amount(monto_total, discount):
        """
        Calcular monto descontado por descuento CU14.
        """
        if not discount:
            return Decimal('0.00')

        valor = Decimal(str(discount['valor']))

        if discount['es_porcentaje']:
            if valor <= 0 or valor > 100:
                raise ValueError('El porcentaje del descuento no es válido.')

            descuento = (monto_total * valor) / Decimal('100')
        else:
            if valor <= 0:
                raise ValueError('El valor del descuento no es válido.')

            descuento = valor

        if descuento > monto_total:
            raise ValueError('El descuento no puede ser mayor al total de la venta.')

        return descuento.quantize(Decimal('0.01'))

    @staticmethod
    def _get_promotion(cursor, id_promocion):
        """
        Obtener promoción activa y vigente por ID real.
        No usa codigo porque public.promocion no tiene columna codigo.
        """
        if not id_promocion:
            return None

        id_promocion = str(id_promocion).strip()

        if id_promocion == '':
            return None

        try:
            id_promocion = int(id_promocion)
        except Exception:
            raise ValueError('La promoción seleccionada no es válida.')

        columns = Sale._get_table_columns(cursor, 'promocion')

        tipo_select = (
            "pr.tipo_aplicacion"
            if 'tipo_aplicacion' in columns
            else "'producto'::VARCHAR AS tipo_aplicacion"
        )

        valor_select = (
            "pr.valor"
            if 'valor' in columns
            else "0::NUMERIC AS valor"
        )

        es_porcentaje_select = (
            "pr.es_porcentaje"
            if 'es_porcentaje' in columns
            else "false::BOOLEAN AS es_porcentaje"
        )

        compra_minima_select = (
            "pr.compra_minima"
            if 'compra_minima' in columns
            else "0::NUMERIC AS compra_minima"
        )

        cursor.execute(f"""
            SELECT
                pr.id,
                pr.nombre,
                pr.descripcion,
                pr.fecha_inicio,
                pr.fecha_fin,
                pr.activo,
                {tipo_select},
                {valor_select},
                {es_porcentaje_select},
                {compra_minima_select}
            FROM public.promocion pr
            WHERE pr.id = %s
            AND pr.activo = true
            AND pr.fecha_inicio <= CURRENT_DATE
            AND pr.fecha_fin >= CURRENT_DATE
            LIMIT 1
        """, (id_promocion,))

        promotion = cursor.fetchone()

        if not promotion:
            raise ValueError('La promoción seleccionada no existe, está inactiva o no está vigente.')

        cursor.execute("""
            SELECT
                pp.codigo_producto,
                p.nombre AS producto
            FROM public.promocion_producto pp
            JOIN public.producto p ON pp.codigo_producto = p.codigo
            WHERE pp.id_promocion = %s
            AND p.estado = true
            ORDER BY p.nombre
        """, (id_promocion,))

        products = cursor.fetchall()

        promotion = dict(promotion)
        promotion['productos'] = products
        promotion['product_codes'] = [p['codigo_producto'] for p in products]

        return promotion

    @staticmethod
    def _calculate_promotion_amount(monto_base, promotion, detalles):
        """
        Calcular monto descontado por promoción CU15.

        Importante:
        - Si tu tabla public.promocion solo tiene las columnas originales
          del documento, no existe valor monetario para descontar.
          En ese caso se valida y registra la promoción, pero el descuento
          de promoción queda en Bs 0.00.
        - Si tu SQL de CU15 ya agregó valor/es_porcentaje/compra_minima,
          entonces se descuenta correctamente.
        """
        if not promotion:
            return Decimal('0.00')

        monto_base = Sale._to_decimal(monto_base)

        compra_minima = Sale._to_decimal(promotion.get('compra_minima'))

        if monto_base < compra_minima:
            raise ValueError(
                f'La promoción {promotion["nombre"]} requiere una compra mínima de Bs {compra_minima}.'
            )

        product_codes = promotion.get('product_codes') or []

        if product_codes:
            sale_product_codes = [detail['codigo_producto'] for detail in detalles]
            applies = any(code in sale_product_codes for code in product_codes)

            if not applies:
                raise ValueError(
                    f'La promoción {promotion["nombre"]} aplica a productos que no están en la venta.'
                )

        valor = Sale._to_decimal(promotion.get('valor'))

        if valor <= 0:
            return Decimal('0.00')

        tipo_aplicacion = promotion.get('tipo_aplicacion') or 'producto'

        if tipo_aplicacion == 'producto' and product_codes:
            base_calculo = Decimal('0.00')

            for detail in detalles:
                if detail['codigo_producto'] in product_codes:
                    base_calculo += Sale._to_decimal(detail['subtotal'])
        else:
            base_calculo = monto_base

        if base_calculo <= 0:
            return Decimal('0.00')

        if promotion.get('es_porcentaje'):
            if valor <= 0 or valor > 100:
                raise ValueError('El porcentaje de la promoción no es válido.')

            descuento_promocion = (base_calculo * valor) / Decimal('100')
        else:
            descuento_promocion = valor

        if descuento_promocion > monto_base:
            descuento_promocion = monto_base

        return descuento_promocion.quantize(Decimal('0.01'))

    @staticmethod
    def create_sale(
        id_cliente,
        codigo_usuario,
        id_tipo_pago,
        items,
        referencia_externa=None,
        codigo_descuento=None,
        id_promocion=None,
        codigo_promocion=None
    ):
        """
        Registrar una venta completa:
        - factura
        - detalle_factura
        - pago
        - historial

        Incluye:
        - descuento CU14 usando public.descuento y public.factura.codigo_descuento
        - promoción CU15 usando public.promocion.id y public.promocion_producto

        Nota:
        Se acepta codigo_promocion como alias por si algún formulario anterior
        lo manda con ese nombre, pero internamente se trabaja como id_promocion.
        """

        if not id_promocion and codigo_promocion:
            id_promocion = codigo_promocion

        if not id_cliente:
            raise ValueError('Debe seleccionar un cliente.')

        if not codigo_usuario:
            raise ValueError('No se encontró el usuario de la sesión.')

        if not id_tipo_pago:
            raise ValueError('Debe seleccionar un tipo de pago.')

        if not items:
            raise ValueError('Debe agregar al menos un producto a la venta.')

        with db.get_cursor() as cursor:

            cursor.execute("""
                SELECT id, nombre
                FROM public.cliente
                WHERE id = %s
            """, (id_cliente,))

            client = cursor.fetchone()

            if not client:
                raise ValueError('El cliente seleccionado no existe.')

            cursor.execute("""
                SELECT id, nombre
                FROM public.tipo_pago
                WHERE id = %s
                AND activo = true
            """, (id_tipo_pago,))

            payment_type = cursor.fetchone()

            if not payment_type:
                raise ValueError('El tipo de pago seleccionado no existe o está inactivo.')

            discount = Sale._get_discount(cursor, codigo_descuento)
            promotion = Sale._get_promotion(cursor, id_promocion)

            codigo_factura = Sale._generate_invoice_code(cursor)

            detalles = []
            monto_total = Decimal('0.00')

            for item in items:
                codigo_producto = item.get('codigo_producto')
                cantidad = item.get('cantidad')

                if not codigo_producto:
                    raise ValueError('Hay un producto sin código.')

                try:
                    cantidad = int(cantidad)
                except Exception:
                    raise ValueError('La cantidad debe ser un número entero.')

                if cantidad <= 0:
                    raise ValueError('La cantidad debe ser mayor a cero.')

                product = Sale._get_product(cursor, codigo_producto)

                if not product:
                    raise ValueError(f'El producto {codigo_producto} no existe o está inactivo.')

                precio_unitario = Decimal(str(product['precio_venta']))
                subtotal = precio_unitario * Decimal(cantidad)

                detalles.append({
                    'codigo_producto': product['codigo'],
                    'nombre_producto': product['nombre'],
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'subtotal': subtotal
                })

                monto_total += subtotal

            if monto_total <= 0:
                raise ValueError('El monto total de la venta debe ser mayor a cero.')

            monto_descuento = Sale._calculate_discount_amount(monto_total, discount)
            subtotal_con_descuento = monto_total - monto_descuento

            if subtotal_con_descuento < 0:
                raise ValueError('El subtotal con descuento no puede ser negativo.')

            monto_promocion = Sale._calculate_promotion_amount(
                monto_base=subtotal_con_descuento,
                promotion=promotion,
                detalles=detalles
            )

            monto_final = subtotal_con_descuento - monto_promocion

            if monto_final < 0:
                raise ValueError('El monto final no puede ser negativo.')

            codigo_descuento_final = discount['codigo'] if discount else None

            codigo_pedido_final = codigo_factura if promotion else None

            cursor.execute("""
                INSERT INTO public.factura (
                    codigo,
                    id_cliente,
                    codigo_usuario,
                    id_tipo_pago,
                    codigo_descuento,
                    monto_total,
                    monto_final,
                    pagado,
                    estado,
                    codigo_pedido
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, true, true, %s)
                RETURNING
                    codigo,
                    fecha_hora,
                    id_cliente,
                    codigo_usuario,
                    id_tipo_pago,
                    codigo_descuento,
                    monto_total,
                    monto_final,
                    pagado,
                    estado,
                    codigo_pedido
            """, (
                codigo_factura,
                id_cliente,
                codigo_usuario,
                id_tipo_pago,
                codigo_descuento_final,
                monto_total,
                monto_final,
                codigo_pedido_final
            ))

            invoice = cursor.fetchone()

            for detail in detalles:
                cursor.execute("""
                    INSERT INTO public.detalle_factura (
                        codigo_factura,
                        codigo_producto,
                        cantidad,
                        precio_unitario,
                        subtotal
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    codigo_factura,
                    detail['codigo_producto'],
                    detail['cantidad'],
                    detail['precio_unitario'],
                    detail['subtotal']
                ))

            if promotion:
                cursor.execute("""
                    INSERT INTO public.pedido_promocion (
                        codigo_pedido,
                        id_promocion,
                        monto_descontado
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (codigo_pedido, id_promocion)
                    DO UPDATE SET monto_descontado = EXCLUDED.monto_descontado
                """, (
                    codigo_pedido_final,
                    promotion['id'],
                    monto_promocion
                ))

            cursor.execute("""
                INSERT INTO public.pago (
                    codigo_factura,
                    id_tipo_pago,
                    monto_pagado,
                    codigo_usuario,
                    referencia_externa
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, codigo_factura, monto_pagado, referencia_externa
            """, (
                codigo_factura,
                id_tipo_pago,
                monto_final,
                codigo_usuario,
                referencia_externa
            ))

            payment = cursor.fetchone()

            historial_texto = (
                f'Venta registrada. Total Bs {monto_total}. '
                f'Descuento Bs {monto_descuento}. '
                f'Promoción Bs {monto_promocion}. '
                f'Final Bs {monto_final}.'
            )

            if codigo_descuento_final:
                historial_texto += f' Código descuento: {codigo_descuento_final}.'

            if promotion:
                historial_texto += f' Promoción: {promotion["nombre"]} ID {promotion["id"]}.'

            if referencia_externa:
                historial_texto += f' Referencia: {referencia_externa}.'

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
                'REGISTRO DE VENTA',
                'factura',
                codigo_factura,
                historial_texto
            ))

            return {
                'invoice': invoice,
                'details': detalles,
                'payment': payment,
                'discount': discount,
                'promotion': promotion,
                'monto_descuento': monto_descuento,
                'monto_promocion': monto_promocion
            }

    @staticmethod
    def get_all():
        """
        Listar ventas registradas.
        Incluye datos del descuento y promoción si corresponde.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    f.codigo,
                    f.fecha_hora,
                    f.monto_total,
                    f.monto_final,
                    f.pagado,
                    f.estado,
                    f.codigo_descuento,
                    f.codigo_pedido,
                    c.nombre AS cliente,
                    c.ci AS cliente_ci,
                    u.nombre AS usuario,
                    tp.nombre AS tipo_pago,
                    d.descripcion AS descuento_descripcion,
                    d.valor AS descuento_valor,
                    d.es_porcentaje AS descuento_es_porcentaje,
                    promo.id_promocion,
                    promo.promocion_nombre,
                    promo.monto_promocion
                FROM public.factura f
                JOIN public.cliente c ON f.id_cliente = c.id
                JOIN public.usuario u ON f.codigo_usuario = u.codigo
                JOIN public.tipo_pago tp ON f.id_tipo_pago = tp.id
                LEFT JOIN public.descuento d ON f.codigo_descuento = d.codigo
                LEFT JOIN (
                    SELECT
                        pp.codigo_pedido,
                        MIN(pp.id_promocion) AS id_promocion,
                        STRING_AGG(pr.nombre, ', ') AS promocion_nombre,
                        COALESCE(SUM(pp.monto_descontado), 0) AS monto_promocion
                    FROM public.pedido_promocion pp
                    JOIN public.promocion pr ON pp.id_promocion = pr.id
                    GROUP BY pp.codigo_pedido
                ) promo ON promo.codigo_pedido = COALESCE(f.codigo_pedido, f.codigo)
                ORDER BY f.fecha_hora DESC
            """)

            return cursor.fetchall()

    @staticmethod
    def find_by_code(codigo_factura):
        """
        Buscar factura por código.
        Incluye datos del descuento, promoción y referencia externa del pago.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    f.codigo,
                    f.fecha_hora,
                    f.id_cliente,
                    f.codigo_usuario,
                    f.id_tipo_pago,
                    f.codigo_descuento,
                    f.codigo_pedido,
                    f.monto_total,
                    f.monto_final,
                    f.pagado,
                    f.estado,
                    c.nombre AS cliente,
                    c.ci AS cliente_ci,
                    c.telefono AS cliente_telefono,
                    c.correo_electronico AS cliente_email,
                    u.nombre AS usuario,
                    tp.nombre AS tipo_pago,
                    d.descripcion AS descuento_descripcion,
                    d.valor AS descuento_valor,
                    d.es_porcentaje AS descuento_es_porcentaje,
                    promo.id_promocion,
                    promo.promocion_nombre,
                    promo.monto_promocion,
                    p.referencia_externa
                FROM public.factura f
                JOIN public.cliente c ON f.id_cliente = c.id
                JOIN public.usuario u ON f.codigo_usuario = u.codigo
                JOIN public.tipo_pago tp ON f.id_tipo_pago = tp.id
                LEFT JOIN public.descuento d ON f.codigo_descuento = d.codigo
                LEFT JOIN (
                    SELECT
                        pp.codigo_pedido,
                        MIN(pp.id_promocion) AS id_promocion,
                        STRING_AGG(pr.nombre, ', ') AS promocion_nombre,
                        COALESCE(SUM(pp.monto_descontado), 0) AS monto_promocion
                    FROM public.pedido_promocion pp
                    JOIN public.promocion pr ON pp.id_promocion = pr.id
                    GROUP BY pp.codigo_pedido
                ) promo ON promo.codigo_pedido = COALESCE(f.codigo_pedido, f.codigo)
                LEFT JOIN public.pago p ON f.codigo = p.codigo_factura
                WHERE f.codigo = %s
                ORDER BY p.fecha_pago DESC
                LIMIT 1
            """, (codigo_factura,))

            return cursor.fetchone()

    @staticmethod
    def get_details(codigo_factura):
        """
        Obtener detalle de productos de una factura.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    df.id,
                    df.codigo_factura,
                    df.codigo_producto,
                    p.nombre AS producto,
                    df.cantidad,
                    df.precio_unitario,
                    df.subtotal
                FROM public.detalle_factura df
                JOIN public.producto p ON df.codigo_producto = p.codigo
                WHERE df.codigo_factura = %s
                ORDER BY df.id
            """, (codigo_factura,))

            return cursor.fetchall()

    @staticmethod
    def cancel_sale(codigo_factura, codigo_usuario):
        """
        Anular venta.
        No elimina físicamente la factura.
        Solo cambia estado y pagado.
        """
        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public.factura
                SET estado = false,
                    pagado = false
                WHERE codigo = %s
                AND estado = true
                RETURNING codigo, monto_final
            """, (codigo_factura,))

            result = cursor.fetchone()

            if result:
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
                    'ANULACION DE VENTA',
                    'factura',
                    codigo_factura,
                    f'Venta anulada por Bs {result["monto_final"]}'
                ))

            return result