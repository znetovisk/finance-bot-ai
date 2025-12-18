import requests
import math
import re
import logging
from datetime import datetime
from typing import Dict, Any

from config import Config
from database import Database
from ai_engine import AIService

logger = logging.getLogger(__name__)

class FinanceBot:
    def __init__(self):
        self.db = Database()
        self.ai = AIService()
        self.pending_confirmations: Dict[str, Dict] = {}

    def send_text(self, to: str, msg: str) -> None:
        """Envia mensagem de texto via API do WhatsApp."""
        try:
            payload = {"phone": to, "message": msg}
            requests.post(f"{Config.WPP_API_URL}/send-message", headers=Config.HEADERS, json=payload)
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem para {to}: {e}")

    def send_poll(self, to: str, text: str) -> None:
        """Cria enquete de confirmação."""
        phone = to.split('@')[0]
        payload = {
            "phone": phone,
            "name": text,
            "choices": ["Confirmar ✅", "Cancelar ❌"],
            "options": {"selectableCount": 1}
        }
        try:
            requests.post(f"{Config.WPP_API_URL}/send-poll-message", headers=Config.HEADERS, json=payload)
        except Exception as e:
            logger.error(f"Falha ao enviar enquete para {to}: {e}")

    def process_webhook(self, data: Dict[str, Any]) -> None:
        event = data.get('event')
        sender = data.get('from', '')
        chat_id = data.get('chatId') or sender
        is_group = "@g.us" in chat_id
        body = str(data.get('body', '')).strip()
        
        # Verificação de Admin
        sender_clean = re.sub(r'\D', '', sender)
        admin_clean = re.sub(r'\D', '', Config.ADMIN_PHONE)
        is_admin = sender_clean.endswith(admin_clean[-8:])

        if is_group:
            return # Ignora grupos
        
        if event == 'onpollresponse':
            self._handle_poll(data, chat_id, is_admin)
            return

        if event in ['onselfmessage', 'onmessage']:
            command = body.split()[0].lower() if body else ""

            # Roteamento de Comandos
            if command == '/saldo':
                self._cmd_saldo(chat_id, body, is_admin)
            elif command == '/bf':
                self._cmd_bf_admin(chat_id, body, is_admin)
            elif command == '/del':
                self._cmd_del(chat_id, body, is_admin)
            elif command == '/listar':
                self._cmd_listar(chat_id, is_admin)
            
            # Processamento de Mídia
            elif data.get('type') == 'image':
                self._handle_image(chat_id, data.get('body'), is_admin)
            elif data.get('type') == 'document':
                self._handle_document(chat_id, data, is_admin)

    def _handle_poll(self, data: Dict, chat_id: str, is_admin: bool) -> None:
        opts = data.get('selectedOptions', [])
        if not opts or chat_id not in self.pending_confirmations:
            return

        choice = opts[0].get('name') if isinstance(opts[0], dict) else str(opts[0])
        
        if "Confirmar" in choice:
            info = self.pending_confirmations.pop(chat_id)
            saldo_ant, saldo_novo = self.db.registrar_transacao(info)
            
            # Feedback Matemático
            msg = (f"📝 *Atualização Financeira*\n\n"
                   f"Anterior: R${int(saldo_ant)}\n"
                   f"Ajuste: {info['sinal']} R${int(info['valor'])}\n"
                   f"────────────────\n"
                   f"💰 *Total: R${int(saldo_novo)}*")
            
            # Notifica Cliente
            client_jid = f"{info['numero']}@c.us"
            self.send_text(client_jid, msg)
            
            # Se a confirmação veio de outro lugar (Admin), notifica quem confirmou
            if chat_id != client_jid:
                self.send_text(chat_id, f"✅ Transação processada para {info['numero']}.")
            elif not is_admin:
                # Log para Admin
                self.send_text(Config.ADMIN_JID, f"📢 LOG: {info['numero']}\n{msg}")
        else:
            self.pending_confirmations.pop(chat_id)
            self.send_text(chat_id, "🚫 Operação cancelada.")

    def _cmd_saldo(self, chat_id: str, body: str, is_admin: bool) -> None:
        target = chat_id.split('@')[0]
        parts = body.split()
        
        # Modo Espião (Admin ver saldo de outro)
        if is_admin and len(parts) > 1:
            target = parts[1]
            
        saldo, vencimento = self.db.get_saldo(target)
        saldo_int = int(saldo)
        
        if saldo_int <= 0:
            status = "✅ *Tudo em dia!*" if saldo_int == 0 else f"💎 *Crédito: R${abs(saldo_int)}*"
            self.send_text(chat_id, f"{status}\nSem pendências atuais.")
        else:
            venc_str = vencimento if vencimento else "_A definir_"
            msg = (f"💳 *Extrato Financeiro*\n"
                   f"━━━━━━━━━━━━━━━━\n"
                   f"👤 Cliente: {target}\n"
                   f"💰 *Débito: R${saldo_int}*\n"
                   f"📅 Vencimento: {venc_str}\n"
                   f"━━━━━━━━━━━━━━━━\n\n"
                   f"🚀 *Pix para pagamento:*\n"
                   f"`{Config.PIX_KEY}`\n"
                   f"({Config.BENEFICIARY_NAME})\n\n"
                   f"📸 Envie o comprovante aqui.")
            self.send_text(chat_id, msg)

    def _cmd_bf_admin(self, chat_id: str, body: str, is_admin: bool) -> None:
        """Centraliza comandos administrativos (/bf)"""
        if not is_admin: return
        
        parts = body.split()
        if len(parts) < 2: return

        action = parts[1].lower()

        # Help - Documentação Completa
        if action == 'help':
            msg = (
                "🤖 *SISTEMA FINANCEIRO - MANUAL ADMIN*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "💸 *TRANSAÇÕES RÁPIDAS*\n"
                "• `/bf [valor]`\n"
                "  _Adiciona débito no chat atual._\n"
                "  Ex: `/bf 100` (Add R$100) | `/bf -50` (Abate R$50)\n\n"
                "• `/bf [valor] [%]`\n"
                "  _Adiciona valor + porcentagem._\n"
                "  Ex: `/bf 100 10` (Lança R$110)\n\n"
                "🕵️ *MODO ESPIÃO (Remoto)*\n"
                "• `/bf [numero] [valor]`\n"
                "  _Lança débito para um cliente específico._\n"
                "  Ex: `/bf 556199998888 50`\n\n"
                "• `/saldo [numero]`\n"
                "  _Consulta o extrato de um cliente._\n\n"
                "🛠️ *GESTÃO DE CONTAS*\n"
                "• `/bf set [numero] [valor]`\n"
                "  _Define o saldo EXATO (sobrescreve)._\n"
                "  Ex: `/bf set 556199998888 0` (Zera conta)\n\n"
                "• `/bf cobrar [numero] [dd/mm]`\n"
                "  _Define data de vencimento._\n"
                "  Ex: `/bf cobrar 556199998888 25/12`\n\n"
                "• `/del [numero]`\n"
                "  _Apaga cliente e histórico._\n\n"
                "📊 *RELATÓRIOS*\n"
                "• `/listar` - Ranking de devedores."
            )
            self.send_text(chat_id, msg)
            return

        # Cobrança Manual
        if action == 'cobrar' and len(parts) >= 4:
            try:
                self.db.set_vencimento(parts[2], parts[3])
                self.send_text(chat_id, f"📅 Vencimento de {parts[2]} setado para {parts[3]}")
            except Exception:
                self.send_text(chat_id, "❌ Erro. Use: /bf cobrar [numero] [dd/mm]")
            return

        # Set Saldo Absoluto
        if action == 'set' and len(parts) >= 4:
            try:
                self.db.set_saldo(parts[2], float(parts[3]))
                self.send_text(chat_id, f"✅ Saldo de {parts[2]} atualizado.")
            except Exception:
                self.send_text(chat_id, "❌ Erro no valor.")
            return

        # Lançamento Inteligente (Espião ou Local)
        # Verifica se é lançamento para terceiros (args: /bf numero valor)
        if len(parts) == 3 and len(parts[1]) > 9:
            target, val_str = parts[1], parts[2]
            try:
                val = float(val_str.replace(',', '.'))
                sinal = "+" if val >= 0 else "-"
                self.pending_confirmations[chat_id] = {
                    'numero': target, 'valor': abs(val), 'sinal': sinal,
                    'tipo': 'Manual Admin', 'id_id': f"MAN_{int(datetime.now().timestamp())}"
                }
                self.send_poll(chat_id, f"Lançar {sinal}R${int(abs(val))} para {target}?")
            except ValueError:
                self.send_text(chat_id, "❌ Valor inválido.")
            return

        # Lançamento Local (args: /bf valor)
        try:
            val_str = parts[1]
            sinal = "-" if val_str.startswith('-') else "+"
            val = abs(float(val_str.replace(',', '.')))
            
            # Suporte a porcentagem (/bf 100 10 -> 110)
            if len(parts) > 2:
                pct = float(parts[2])
                val = math.ceil(val + (val * (pct / 100)))

            target = chat_id.split('@')[0]
            self.pending_confirmations[chat_id] = {
                'numero': target, 'valor': val, 'sinal': sinal,
                'tipo': 'Manual', 'id_id': f"MAN_{int(datetime.now().timestamp())}"
            }
            self.send_poll(chat_id, f"Lançar R${int(val)} ({sinal})?")
        except ValueError:
            self.send_text(chat_id, "❌ Erro de formato.")

    def _cmd_del(self, chat_id: str, body: str, is_admin: bool) -> None:
        if not is_admin: return
        try:
            target = body.split()[1]
            self.db.deletar_cliente(target)
            self.send_text(chat_id, f"🗑️ Cliente {target} removido.")
        except IndexError:
            self.send_text(chat_id, "❌ Use: /del [numero]")

    def _cmd_listar(self, chat_id: str, is_admin: bool) -> None:
        if not is_admin: return
        devedores = self.db.get_devedores()
        if not devedores:
            self.send_text(chat_id, "✅ Nenhuma dívida ativa.")
            return
            
        msg = "📋 *Ranking de Devedores*\n\n"
        total = 0.0
        for num, saldo in devedores:
            msg += f"👤 {num}: R${int(saldo)}\n"
            total += saldo
        msg += f"\n💰 *Total: R${int(total)}*"
        self.send_text(chat_id, msg)

    def _handle_document(self, chat_id: str, data: Dict, is_admin: bool) -> None:
        mimetype = data.get('mimetype', '')
        if 'pdf' in mimetype:
            logger.info(f"PDF recebido de {chat_id}. Convertendo...")
            img_base64 = self.ai.pdf_to_image(data.get('body'))
            if img_base64:
                self._handle_image(chat_id, img_base64, is_admin)
            else:
                self.send_text(chat_id, "❌ Falha ao ler PDF.")

    def _handle_image(self, chat_id: str, base64_img: str, is_admin: bool) -> None:
        target_num = chat_id.split('@')[0]

        # 1. Filtro de Segurança
        if not is_admin and not self.db.cliente_existe(target_num):
            return 

        # 2. Processamento Silencioso (Não avisa nada ainda)
        logger.info(f"Processando imagem recebida de {target_num}...")
        dados = self.ai.extract_data(base64_img)
        
        # 3. Decisão baseada no retorno da IA
        if isinstance(dados, dict):
            # CENÁRIO: É UM COMPROVANTE VÁLIDO
            
            # Feedback imediato para o cliente (agora que temos certeza)
            self.send_text(chat_id, "📄 Comprovante identificado! Enviado para validação.")

            # Valida duplicidade
            if self.db.check_duplicidade(dados.get('id_transacao'), dados.get('data_completa')):
                msg_dup = (f"⚠️ *ALERTA DE DUPLICIDADE*\n"
                           f"👤 Cliente: {target_num}\n"
                           f"📄 ID: {dados.get('id_transacao')}\n"
                           f"Este comprovante já foi utilizado anteriormente!")
                self.send_text(Config.ADMIN_JID, msg_dup)
                return

            val = math.ceil(dados['valor'])
            
            # Prepara objeto de confirmação para o Admin
            self.pending_confirmations[Config.ADMIN_JID] = {
                'numero': target_num,     
                'valor': val, 
                'sinal': '-',
                'tipo': 'Pix IA', 
                'pagador': dados.get('pagador'),
                'banco': dados.get('banco'),
                'id_id': dados.get('id_transacao'), 
                'data_full': dados.get('data_completa')
            }

            msg_admin = (f"📉 *Validar Pagamento*\n"
                         f"👤 Cliente: {target_num}\n"
                         f"🏦 Banco: {dados.get('banco', '-')}\n"
                         f"💰 Valor: R${int(val)}\n"
                         f"📅 Data: {dados.get('data_completa')}\n"
                         f"🆔 ID: ...{str(dados.get('id_transacao'))[-6:]}\n\n"
                         f"Confirmar abatimento?")
            
            self.send_poll(Config.ADMIN_JID, msg_admin)
            
        elif dados == "INVALID_RECEIVER":
            # CENÁRIO: Comprovante, mas conta errada
            self.send_text(Config.ADMIN_JID, f"🚫 *Recusado (Beneficiário Incorreto)*\nCliente: {target_num}\nA IA detectou um nome diferente no comprovante.")
            
        else:
            # CENÁRIO: Foto aleatória, meme ou ilegível
            logger.info(f"Imagem descartada de {target_num} (Não é comprovante ou ilegível).")