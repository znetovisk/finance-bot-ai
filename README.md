# 🤖 WhatsApp Finance Bot & AI OCR

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge\&logo=python)
![Flask](https://img.shields.io/badge/Flask-Microservice-lightgrey?style=for-the-badge\&logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue?style=for-the-badge\&logo=sqlite)
![Ollama](https://img.shields.io/badge/AI-Ollama%20%7C%20Qwen-orange?style=for-the-badge)

Um sistema automatizado de gestão financeira e cobrança via WhatsApp, capaz de **ler e validar comprovantes bancários (Pix) automaticamente** utilizando Inteligência Artificial (Vision LLM) rodando localmente de forma 100% gratuita.

O projeto elimina a necessidade de conferência manual de comprovantes e planilhas, integrando um chatbot conversacional, um agendador de cobranças e um motor de OCR inteligente que protege contra duplicidade e fraudes.

---

## 🚀 Funcionalidades Principais

### 🧠 1. Validação de Pagamentos com IA

* **OCR Inteligente:** Utiliza modelos de visão (Qwen/Llava) via **Ollama** para extrair dados de imagens e PDFs.
* **Detecção de Fraude:** Verifica automaticamente se o ID da transação já existe no banco de dados.
* **Validação de Beneficiário:** Confirma se o pagamento foi destinado à conta correta antes de notificar o administrador.

### 📅 2. Automação de Cobranças (Scheduler)

* Monitoramento contínuo de vencimentos em *background*.
* Envio de lembretes automáticos ("Vence Amanhã" ou "Vence Hoje").
* **Anti-Spam:** Janela de envio configurada apenas para horário comercial (09h às 20h), com limite de 1 aviso por dia.

### 💬 3. Gestão via Chat (Comandos Admin)

* **Modo Espião:** O administrador pode lançar débitos, verificar saldos e definir vencimentos de qualquer cliente remotamente.
* **Fluxo de Aprovação:** A IA analisa o comprovante, mas o Admin recebe uma enquete no privado ("Confirmar" ou "Cancelar") para efetivar o abatimento no saldo.

---

## 🛠️ Stack Tecnológica

* **Linguagem:** Python 3.
* **Core:** Flask (Webhook & API).
* **Banco de Dados:** SQLite (Armazenamento leve, sem necessidade de servidor dedicado).
* **AI/LLM:** Ollama (Qwen3-VL ou Llava).
* **Mensageria:** Integração via API REST (WPPConnect Server).
* **Processamento:** PyMuPDF (Conversão de PDF para Imagem) + Threading (Agendador).

---

## 📂 Estrutura do Projeto

```text
/finance-bot
│
├── app.py               # Entry point (Flask + Scheduler Thread)
├── bot_controller.py    # Lógica de negócio, comandos e fluxo de mensagens
├── ai_engine.py         # Motor de IA (Conexão com Ollama e OCR)
├── database.py          # Camada de persistência e migrações automáticas
├── scheduler.py         # Agendador de cobranças em background
├── config.py            # Gerenciamento de variáveis de ambiente
├── .env.example         # Modelo de configuração
└── requirements.txt     # Dependências do Python
```

---

## ⚙️ Instalação e Configuração

### Pré-requisitos

1. **Python 3.9+** instalado.
2. **Ollama** rodando localmente com um modelo de visão:

```bash
ollama pull qwen3-vl:8b
```

3. **WPPConnect Server** (ou outra API de WhatsApp compatível) rodando.

### Passo a Passo

1. **Clone o repositório:**

```bash
git clone https://github.com/znetovisk/finance-bot-ai.git
cd finance-bot-ai
```

2. **Crie e ative o ambiente virtual:**

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

3. **Instale as dependências:**

```bash
pip install -r requirements.txt
```

4. **Configuração de Ambiente (.env):**
   Duplique o arquivo `.env.example`, renomeie para `.env` e configure suas credenciais:

```ini
# --- Configuração do WhatsApp API ---
WPP_BASE_URL=http://localhost:21465/api
WPP_SESSION=sua_sessao_aqui
WPP_TOKEN=seu_token_secreto_aqui

# --- Configuração da IA (Ollama) ---
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen3-vl:8b

# --- Dados do Administrador e Negócio ---
ADMIN_PHONE=5511999999999
# Nome exato ou parcial para a IA validar no comprovante
BENEFICIARY_NAME=Seu Nome Completo
PIX_KEY=seuemail@pix.com.br
```

5. **Execute a aplicação:**

```bash
python app.py
```

*O terminal exibirá logs indicando que o Bot e o Agendador foram iniciados.*

---

## 📖 Manual de Comandos (Admin)

O bot possui um sistema de permissões que libera os comandos abaixo apenas para o número configurado em `ADMIN_PHONE`.

### 💰 Gestão Financeira

| Comando               | Descrição                           | Exemplo                   |
| --------------------- | ----------------------------------- | ------------------------- |
| `/bf [valor]`         | Lança débito no chat atual.         | `/bf 50`                  |
| `/bf [valor] [%]`     | Lança valor + porcentagem.          | `/bf 100 10` (Total: 110) |
| `/bf set [num] [val]` | Define o saldo exato (sobrescreve). | `/bf set 55119... 0`      |
| `/bf [num] [val]`     | **Espião:** Lança débito remoto.    | `/bf 55119... 150`        |

### 📅 Cobrança e Relatórios

| Comando                   | Descrição                                  |
| ------------------------- | ------------------------------------------ |
| `/bf cobrar [num] [data]` | Define data de vencimento (dd/mm).         |
| `/listar`                 | Exibe ranking de devedores e total.        |
| `/saldo [num]`            | Verifica extrato de um cliente específico. |
| `/del [num]`              | Remove cliente e histórico do banco.       |

### 📸 Fluxo de Comprovantes

1. Cliente envia **Imagem** ou **PDF**.
2. Sistema analisa silenciosamente (sem responder spam).
3. Se for um comprovante válido, o Admin recebe uma **Enquete**.
4. Ao clicar em **"Confirmar ✅"**, o saldo é abatido e o cliente é notificado.

---

## 🛡️ Segurança

* **Anti-Spam:** O bot ignora imagens enviadas por números que não possuem cadastro financeiro no banco de dados.
* **Logs:** O sistema gera logs detalhados de erros de IA e comunicação com a API, mas oculta logs excessivos do servidor web (Flask).
* **Concorrência:** Utiliza `Threading.Event` para gerenciar o ciclo de vida do agendador de cobranças de forma segura.

---

## 📄 Licença

Este projeto está sob a licença MIT. Sinta-se livre para contribuir e adaptar para seu uso!

---

**Autor:** Diogo Neto

[LinkedIn](https://www.linkedin.com/in/diogo-neto-420433227/) | [Email](mailto:diogoabreudaan@gmail.com)
