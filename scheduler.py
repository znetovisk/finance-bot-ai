import time
import threading
import requests
import logging
from datetime import datetime, timedelta
from database import Database
from config import Config

logger = logging.getLogger(__name__)

class PaymentScheduler:
    def __init__(self):
        self.db = Database()
        self.stop_event = threading.Event()

    def start(self):
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
        logger.info("Agendador de cobranças iniciado.")

    def _run_loop(self):
        while not self.stop_event.is_set():
            try:
                self._check_vencimentos()
            except Exception as e:
                logger.error(f"Erro no Scheduler: {e}")
            
            # Verifica a cada hora
            time.sleep(3600) 

    def _check_vencimentos(self):
        now = datetime.now()
        
        # Janela de envio (09h às 20h)
        if not (9 <= now.hour <= 20):
            return

        hoje_str = now.strftime("%d/%m")
        hoje_iso = now.strftime("%Y-%m-%d") # Controle de duplicidade diária
        amanha_str = (now + timedelta(days=1)).strftime("%d/%m")

        pendentes = self.db.get_pendentes_cobranca()

        for cliente in pendentes:
            numero, saldo, vencimento_db, ultimo_aviso = cliente
            
            if ultimo_aviso == hoje_iso:
                continue

            msg = None
            if vencimento_db == amanha_str:
                msg = (f"🔔 *Lembrete*\n\n"
                       f"Olá! Seu saldo de *R${int(saldo)}* vence *AMANHÃ* ({vencimento_db}).\n"
                       "Que tal adiantar? Envie o comprovante Pix por aqui.")
            
            elif vencimento_db == hoje_str:
                msg = (f"⚠️ *Vencimento Hoje*\n\n"
                       f"Seu pagamento de *R${int(saldo)}* vence hoje.\n"
                       "Envie o Pix e mande a foto do comprovante para baixa.")

            if msg:
                if self._send_notification(numero, msg):
                    self.db.registrar_envio_aviso(numero, hoje_iso)
                    logger.info(f"Cobrança enviada para {numero}")

    def _send_notification(self, numero: str, msg: str) -> bool:
        to = f"{numero}@c.us" if "@" not in numero else numero
        try:
            res = requests.post(
                f"{Config.WPP_API_URL}/send-message", 
                headers=Config.HEADERS, 
                json={"phone": to, "message": msg}
            )
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Falha ao notificar {numero}: {e}")
            return False