from database.connection import db
from decimal import Decimal


class Report:
    """
    Modelo para reportes del sistema MiniMarket QuickStore.
    Actualmente incluye el reporte de ventas filtrado por:
    - Fecha
    - Usuario
    - Tipo de pago
    - Estado
    - Búsqueda por factura, cliente o CI
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
    def get_available_fields():
        """
        Retorna los campos disponibles para mostrar en el reporte.
        """
        return Report.AVAILABLE_FIELDS

    @staticmethod
    def get_default_fields():
        """
        Retorna los campos por defecto para el reporte.
        """
        return Report.DEFAULT_FIELDS

    @staticmethod
    def get_users_for_filter():
        """
        Obtener usuarios activos para el filtro del reporte.
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
        Obtener tipos de pago para el filtro del reporte.
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
            monto_final = row['monto_final'] or Decimal('0.00')

            if not isinstance(monto_final, Decimal):
                monto_final = Decimal(str(monto_final))

            total_general += monto_final

            if row['estado']:
                ventas_activas += 1
                total_activo += monto_final
            else:
                ventas_anuladas += 1
                total_anulado += monto_final

            usuario_key = row['codigo_usuario']
            usuario_nombre = row['usuario']

            if usuario_key not in resumen_usuarios:
                resumen_usuarios[usuario_key] = {
                    'codigo_usuario': usuario_key,
                    'usuario': usuario_nombre,
                    'cantidad': 0,
                    'total': Decimal('0.00')
                }

            resumen_usuarios[usuario_key]['cantidad'] += 1
            resumen_usuarios[usuario_key]['total'] += monto_final

            tipo_pago_key = row['tipo_pago'] or 'Sin tipo'

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

    @staticmethod
    def register_report_action(codigo_usuario, accion, detalle):
        """
        Registrar acción relacionada a reportes en la bitácora.
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
                'reporte_ventas',
                detalle
            ))

            return cursor.fetchone()