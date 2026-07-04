import os


class GeminiClient:
    """
    Cliente para comunicarse con Gemini AI.

    Importante:
    - La API Key se lee desde GEMINI_API_KEY.
    - No se debe escribir la API Key en el código.
    - Si Gemini falla, el sistema devuelve una respuesta local segura.
    """

    DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    @staticmethod
    def is_configured():
        """
        Verifica si existe la API Key de Gemini en variables de entorno.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        return bool(api_key and api_key.strip())

    @staticmethod
    def generate_report_response(question, report_data):
        """
        Genera una respuesta en lenguaje natural usando Gemini.

        question: pregunta realizada por el usuario.
        report_data: diccionario con datos reales consultados desde PostgreSQL.
        """

        if not GeminiClient.is_configured():
            return GeminiClient._fallback_response(question, report_data)

        try:
            from google import genai
            from google.genai import types

            api_key = os.getenv("GEMINI_API_KEY")
            model = GeminiClient.DEFAULT_MODEL

            client = genai.Client(api_key=api_key)

            prompt = GeminiClient._build_prompt(question, report_data)

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.25,
                    max_output_tokens=900
                )
            )

            if hasattr(response, "text") and response.text:
                return response.text.strip()

            return GeminiClient._fallback_response(question, report_data)

        except Exception as e:
            return (
                "No se pudo conectar correctamente con Gemini AI, "
                "pero el sistema sí obtuvo los datos reales desde QuickStore.\n\n"
                f"Detalle técnico: {str(e)}\n\n"
                + GeminiClient._fallback_response(question, report_data)
            )

    @staticmethod
    def generate_managerial_analysis(indicators):
        """
        Genera análisis gerencial para el CU19 - Generar Análisis Gerencial Inteligente.

        indicators:
        Diccionario con indicadores reales obtenidos desde PostgreSQL.

        Importante:
        - No inventa datos.
        - Usa únicamente los indicadores recibidos desde el sistema.
        - Si Gemini falla, genera un análisis local básico.
        """

        if not GeminiClient.is_configured():
            return GeminiClient._fallback_managerial_analysis(indicators)

        try:
            from google import genai
            from google.genai import types

            api_key = os.getenv("GEMINI_API_KEY")
            model = GeminiClient.DEFAULT_MODEL

            client = genai.Client(api_key=api_key)

            prompt = GeminiClient._build_managerial_prompt(indicators)

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.25,
                    max_output_tokens=1000
                )
            )

            if hasattr(response, "text") and response.text:
                return response.text.strip()

            return GeminiClient._fallback_managerial_analysis(indicators)

        except Exception as e:
            return (
                "No se pudo generar el análisis con Gemini AI, "
                "pero el sistema sí obtuvo los indicadores reales desde QuickStore.\n\n"
                f"Detalle técnico: {str(e)}\n\n"
                + GeminiClient._fallback_managerial_analysis(indicators)
            )

    @staticmethod
    def _build_prompt(question, report_data):
        """
        Construye el prompt seguro.
        Gemini solo recibe datos ya consultados por Flask.
        No recibe credenciales ni acceso directo a PostgreSQL.
        """

        return f"""
Eres un asistente de reportes para el sistema MiniMarket QuickStore.

Tu tarea:
- Responder en español.
- Explicar los datos de forma clara y breve.
- No inventar datos.
- Si hay pocos datos, dilo claramente.
- Si hay alertas de inventario, prioriza productos críticos.
- Usa tono profesional y sencillo.
- No menciones consultas SQL.
- No digas que tienes acceso directo a la base de datos.
- Los datos ya fueron obtenidos por el sistema QuickStore.

Pregunta del usuario:
{question}

Datos reales obtenidos desde QuickStore:
{report_data}

Genera una respuesta clara para mostrar en pantalla y leer por voz.
"""

    @staticmethod
    def _build_managerial_prompt(indicators):
        """
        Construye el prompt para el análisis gerencial del CU19.
        """

        return f"""
Eres un asesor gerencial para el sistema MiniMarket QuickStore.

Tu tarea es generar un análisis administrativo breve, claro y útil para el administrador del minimarket.

Reglas obligatorias:
- Responde en español.
- No inventes datos.
- Usa únicamente los indicadores reales recibidos.
- No menciones consultas SQL.
- No digas que tienes acceso directo a PostgreSQL.
- El tono debe ser profesional, sencillo y orientado a decisiones.
- Incluye recomendaciones administrativas concretas.
- Si un indicador está en cero, interprétalo con cautela y no exageres.
- Prioriza alertas sobre stock bajo, productos agotados, productos próximos a vencer, pérdidas por notas de salida, cajas abiertas, utilidad, compras y ventas.

Indicadores reales de QuickStore:
{indicators}

Estructura esperada:
1. Resumen general del estado del minimarket.
2. Alertas o puntos de atención.
3. Recomendaciones gerenciales concretas.

Genera un análisis listo para enviar por correo al administrador.
"""

    @staticmethod
    def _fallback_response(question, report_data):
        """
        Respuesta local cuando Gemini no está disponible.
        """

        title = report_data.get("title", "Reporte solicitado")
        summary = report_data.get("summary", {})
        rows = report_data.get("rows", [])

        response = f"{title}.\n\n"

        if summary:
            response += "Resumen:\n"
            for key, value in summary.items():
                label = str(key).replace("_", " ").capitalize()
                response += f"- {label}: {value}\n"

        if rows:
            response += f"\nSe encontraron {len(rows)} registro(s). "
            response += "Puedes revisar el detalle en la tabla mostrada en pantalla."
        else:
            response += "\nNo se encontraron registros para esta consulta."

        return response

    @staticmethod
    def _fallback_managerial_analysis(indicators):
        """
        Análisis local básico cuando Gemini no está disponible.

        Este respaldo evita que el CU19 falle por completo si:
        - No existe GEMINI_API_KEY.
        - Gemini no responde.
        - Hay un error temporal con la API.
        """

        formatted = indicators.get("formatted", {})
        payment_method = indicators.get("metodo_pago_mas_usado", {})

        ventas_dia = formatted.get("ventas_dia", "Bs 0.00")
        ventas_mes = formatted.get("ventas_mes", "Bs 0.00")
        utilidad_mes = formatted.get("utilidad_mes", "Bs 0.00")
        compras_mes = formatted.get("compras_mes", "Bs 0.00")
        perdidas = formatted.get("perdidas_notas_salida", "Bs 0.00")

        stock_bajo = indicators.get("productos_stock_bajo", 0)
        agotados = indicators.get("productos_agotados", 0)
        proximos_vencer = indicators.get("productos_proximos_vencer", 0)
        cajas_abiertas = indicators.get("cajas_abiertas", 0)

        metodo_pago = payment_method.get("metodo_pago", "Sin registros")
        metodo_pago_cantidad = payment_method.get("cantidad", 0)

        analysis = (
            "1. Resumen general del estado del minimarket\n"
            f"El minimarket registra ventas del día por {ventas_dia} y ventas del mes por {ventas_mes}. "
            f"La utilidad estimada del mes es {utilidad_mes}. "
            f"Las compras del mes alcanzan {compras_mes}. "
            f"El método de pago más usado es {metodo_pago}, con {metodo_pago_cantidad} uso(s) registrados.\n\n"
            "2. Alertas o puntos de atención\n"
            f"Actualmente existen {stock_bajo} producto(s) con stock bajo, "
            f"{agotados} producto(s) agotado(s) y {proximos_vencer} producto(s) próximos a vencer. "
            f"Las pérdidas por notas de salida alcanzan {perdidas}. "
            f"También se registran {cajas_abiertas} caja(s) abierta(s), por lo que se recomienda verificar su cierre oportuno.\n\n"
            "3. Recomendaciones gerenciales concretas\n"
            "Se recomienda revisar los productos agotados y con stock bajo para evitar pérdida de ventas. "
            "También conviene controlar los productos próximos a vencer para reducir mermas. "
            "Las notas de salida deben revisarse por motivo para identificar pérdidas recurrentes. "
            "Si existen cajas abiertas, se recomienda cerrarlas al finalizar el turno para mantener un mejor control de efectivo. "
            "Finalmente, es conveniente comparar las compras del mes con las ventas y la utilidad para evaluar si el abastecimiento está siendo eficiente."
        )

        return analysis