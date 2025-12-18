import logging
from flask import Flask, request, jsonify
from bot_controller import FinanceBot
from scheduler import PaymentScheduler

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silenciar logs excessivos do Werkzeug
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
bot = FinanceBot()
scheduler = PaymentScheduler()

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        if data:
            bot.process_webhook(data)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Erro Crítico no Webhook: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 FINANCE BOT STARTED")
    print("🤖 AI Engine: Active")
    print("⏰ Scheduler: Active")
    print("="*50 + "\n")
    
    # Inicia agendador em thread separada
    scheduler.start()
    
    # Em produção, utilize gunicorn ou uWSGI
    app.run(host='0.0.0.0', port=5000, debug=False)