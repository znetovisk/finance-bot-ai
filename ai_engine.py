import requests
import json
import re
import fitz
import base64
import logging
from typing import Optional, Union, Dict, List
from config import Config

logger = logging.getLogger(__name__)

class AIService:
    def pdf_to_image(self, pdf_base64_str: str) -> Optional[str]:
        """
        Converte a primeira página de um PDF (Base64) para Imagem (Base64/PNG).
        Utiliza Matrix(2,2) para aumentar o DPI e melhorar a precisão do OCR.
        """
        try:
            pdf_data = base64.b64decode(pdf_base64_str)
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            
            if doc.page_count < 1:
                logger.warning("PDF recebido vazio ou inválido.")
                return None

            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
            img_bytes = pix.tobytes("png")
            
            return base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Erro na conversão PDF->Img: {e}")
            return None

    def _unload_model(self) -> None:
        """Libera a VRAM do modelo no servidor Ollama imediatamente após o uso."""
        try:
            requests.post(Config.OLLAMA_URL, json={
                "model": Config.OLLAMA_MODEL,
                "keep_alive": 0
            }, timeout=5)
        except Exception as e:
            logger.warning(f"Falha ao liberar memória do modelo: {e}")

    def extract_data(self, base64_image: str) -> Union[Dict, str, None]:
        """
        Envia a imagem para o modelo LLM e extrai dados estruturados JSON.
        
        Returns:
            Dict: Dados extraídos com sucesso.
            str: Mensagem de erro específica (ex: 'INVALID_RECEIVER').
            None: Erro genérico de processamento.
        """
        if not base64_image or len(base64_image) < 100:
            return None

        # Injeta o nome do beneficiário configurado no prompt para guiar a IA
        beneficiary_name = Config.BENEFICIARY_NAME
        
        prompt = (
            "TASK: OCR and Information Extraction.\n"
            "INSTRUCTIONS:\n"
            "1. Analyze the receipt image provided.\n"
            "2. Extract the following fields into a raw JSON format only.\n"
            "3. Do not include markdown formatting (```json) or conversational text.\n"
            "4. Fields required: 'valor' (float), 'recebedor' (string), 'banco' (string), "
            "'pagador' (string), 'id_transacao' (string), 'data_texto' (string dd/mm/yyyy).\n"
            f"5. Verify if the receiver matches '{beneficiary_name}' or parts of this name."
        )
        
        payload = {
            "model": Config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "images": [base64_image],
            "options": {
                "temperature": 0.1,
                "num_predict": 1024,
                "top_k": 20
            }
        }
        
        try:
            logger.info("Enviando imagem para análise da IA...")
            response = requests.post(Config.OLLAMA_URL, json=payload, timeout=120)
            
            if response.status_code != 200:
                logger.error(f"Erro API Ollama ({response.status_code}): {response.text}")
                return None
            
            raw_text = response.json().get('response', '').strip()
            return self._parse_llm_response(raw_text)

        except requests.exceptions.Timeout:
            logger.error("Timeout na comunicação com o Ollama.")
            return None
        except Exception as e:
            logger.error(f"Exceção no processamento da IA: {e}")
            return None
        finally:
            self._unload_model()

    def _parse_llm_response(self, raw_text: str) -> Union[Dict, str, None]:
        """Processa a string retornada pela LLM, valida o JSON e verifica o beneficiário."""
        try:
            # Extração robusta de JSON (remove texto antes/depois das chaves)
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not match:
                logger.warning(f"JSON não encontrado na resposta da IA: {raw_text[:50]}...")
                return "JSON_ERROR"

            # Tratamento para aspas simples (comum em LLMs menores)
            json_str = match.group(0).replace("'", '"')
            data = json.loads(json_str)

            if "erro" in data:
                return None

            # Normalização de Datas e Valores
            data['data_completa'] = data.get('data_texto', 'N/A')
            
            val = data.get('valor', 0)
            if isinstance(val, str):
                # Limpa R$, espaços e converte vírgula para ponto
                clean_val = re.sub(r'[^\d,.]', '', val).replace(',', '.')
                try:
                    val = float(clean_val)
                except ValueError:
                    val = 0.0
            data['valor'] = val

            # Validação Dinâmica do Beneficiário via Config
            return self._validate_receiver(data)

        except json.JSONDecodeError:
            logger.error("Falha ao decodificar JSON da IA.")
            return "JSON_ERROR"
        except Exception as e:
            logger.error(f"Erro no parsing da resposta: {e}")
            return None

    def _validate_receiver(self, data: Dict) -> Union[Dict, str]:
        """Verifica se o recebedor no comprovante bate com a configuração."""
        recebedor_ocr = str(data.get('recebedor', '')).lower()
        target_name = Config.BENEFICIARY_NAME.lower()
        
        # Cria uma whitelist dinâmica baseada nos nomes configurados
        # Ex: "Fulano de Tal" -> verifica "fulano", "tal" e o nome completo
        name_parts = [n for n in target_name.split() if len(n) > 2]
        
        is_valid = any(part in recebedor_ocr for part in name_parts)
        
        if is_valid:
            return data
        
        logger.warning(f"Recebedor inválido detectado: '{recebedor_ocr}' (Esperado: {target_name})")
        return "INVALID_RECEIVER"