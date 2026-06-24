from flask import Blueprint, render_template, request, jsonify, session
from models.voice_ai_report import VoiceAIReport
from utils.gemini_client import GeminiClient
from utils.decorators import login_required, permission_required


voice_ai_bp = Blueprint(
    "voice_ai",
    __name__,
    url_prefix="/reports/voice-ai"
)


@voice_ai_bp.route("/")
@login_required
@permission_required("report_sales_read")
def voice_ai_page():
    """
    Pantalla del Reporte de Voz con IA.
    """
    return render_template("reports/voice_ai.html")


@voice_ai_bp.route("/ask", methods=["POST"])
@login_required
@permission_required("report_sales_read")
def ask_voice_ai():
    """
    Recibe una pregunta del usuario, consulta datos reales de PostgreSQL
    y usa Gemini para redactar la respuesta.
    """

    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({
            "ok": False,
            "message": "Debe ingresar o dictar una pregunta.",
            "answer": "",
            "report": {}
        }), 400

    try:
        report_data = VoiceAIReport.execute_question(question)

        answer = GeminiClient.generate_report_response(
            question=question,
            report_data=report_data
        )

        VoiceAIReport.register_voice_ai_action(
            codigo_usuario=session.get("user_id"),
            question=question,
            intent=report_data.get("intent", "sin_intencion")
        )

        return jsonify({
            "ok": True,
            "message": "Consulta procesada correctamente.",
            "answer": answer,
            "report": report_data
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "message": f"Error al procesar la consulta: {str(e)}",
            "answer": "",
            "report": {}
        }), 500