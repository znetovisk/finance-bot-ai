import sqlite3
import math
import logging
from datetime import datetime
from typing import Tuple, List, Optional, Any

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name: str = 'finance.db'):
        self.db_name = db_name
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_name)

    def _init_db(self) -> None:
        """Inicializa o esquema do banco de dados e aplica migrações básicas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabela de Clientes/Financeiro
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS financeiro (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero TEXT UNIQUE,
                    saldo REAL DEFAULT 0,
                    vencimento TEXT,
                    ultimo_aviso TEXT
                )
            """)
            
            # Tabela de Histórico
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_cliente TEXT,
                    data_registro TEXT,
                    data_comprovante TEXT,
                    tipo TEXT,
                    valor REAL,
                    saldo_anterior REAL,
                    saldo_novo REAL,
                    pagador TEXT,
                    banco TEXT,
                    id_comprovante TEXT UNIQUE
                )
            """)
            conn.commit()
            self._run_migrations(conn)

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Verifica e cria colunas ausentes para compatibilidade."""
        cursor = conn.cursor()
        columns = [
            ("financeiro", "vencimento", "TEXT"),
            ("financeiro", "ultimo_aviso", "TEXT"),
            ("transacoes", "data_comprovante", "TEXT"),
            ("transacoes", "banco", "TEXT")
        ]
        
        for table, col, dtype in columns:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
            except sqlite3.OperationalError:
                pass # Coluna já existe
        conn.commit()

    def get_saldo(self, numero: str) -> Tuple[float, Optional[str]]:
        """Retorna (saldo, data_vencimento). Se não existir, retorna (0.0, None)."""
        with self._get_connection() as conn:
            res = conn.cursor().execute(
                "SELECT saldo, vencimento FROM financeiro WHERE numero = ?", 
                (numero,)
            ).fetchone()
            
            if not res:
                return 0.0, None
            return res[0], res[1]

    def set_saldo(self, numero: str, valor: float) -> None:
        """Define um saldo absoluto para um cliente."""
        with self._get_connection() as conn:
            conn.cursor().execute("""
                INSERT INTO financeiro (numero, saldo) VALUES (?, ?) 
                ON CONFLICT(numero) DO UPDATE SET saldo=excluded.saldo
            """, (numero, valor))
            conn.commit()

    def deletar_cliente(self, numero: str) -> None:
        """Remove permanentemente o cliente e seu histórico."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM financeiro WHERE numero = ?", (numero,))
            cursor.execute("DELETE FROM transacoes WHERE numero_cliente = ?", (numero,))
            conn.commit()

    def get_devedores(self) -> List[Tuple[str, float]]:
        """Retorna lista de clientes com saldo positivo (dívida)."""
        with self._get_connection() as conn:
            return conn.cursor().execute(
                "SELECT numero, saldo FROM financeiro WHERE saldo > 0 ORDER BY saldo DESC"
            ).fetchall()

    def set_vencimento(self, numero: str, data_str: str) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE financeiro SET vencimento = ?, ultimo_aviso = NULL WHERE numero = ?", 
                (data_str, numero)
            )
            conn.commit()

    def registrar_envio_aviso(self, numero: str, data_hoje: str) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE financeiro SET ultimo_aviso = ? WHERE numero = ?", 
                (data_hoje, numero)
            )
            conn.commit()

    def get_pendentes_cobranca(self) -> List[Tuple]:
        """Retorna clientes que possuem data de vencimento configurada."""
        with self._get_connection() as conn:
            return conn.cursor().execute(
                "SELECT numero, saldo, vencimento, ultimo_aviso FROM financeiro WHERE vencimento IS NOT NULL"
            ).fetchall()

    def check_duplicidade(self, id_transacao: str, data_comprovante: str) -> bool:
        """Verifica se o ID ou a Data do comprovante já existem no banco."""
        with self._get_connection() as conn:
            res = conn.cursor().execute(
                "SELECT id FROM transacoes WHERE id_comprovante = ? OR data_comprovante = ?", 
                (id_transacao, data_comprovante)
            ).fetchone()
            return res is not None

    def cliente_existe(self, numero: str) -> bool:
        with self._get_connection() as conn:
            res = conn.cursor().execute("SELECT id FROM financeiro WHERE numero = ?", (numero,)).fetchone()
            return res is not None
        
    def registrar_transacao(self, dados: dict) -> Tuple[float, float]:
        """
        Registra uma transação financeira, atualiza o saldo e gera histórico.
        Retorna (saldo_anterior, novo_saldo).
        """
        numero = dados['numero']
        valor = float(dados['valor'])
        sinal = dados['sinal']
        
        saldo_ant, _ = self.get_saldo(numero)
        
        # Cálculo financeiro seguro
        if sinal == '+':
            novo_saldo = math.ceil(saldo_ant + valor)
        else:
            novo_saldo = math.ceil(saldo_ant - valor)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Remove vencimento se a dívida for quitada (saldo <= 0)
            limpeza_sql = ", vencimento = NULL, ultimo_aviso = NULL" if novo_saldo <= 0 else ""
            
            # Upsert do Saldo
            cursor.execute(f"UPDATE financeiro SET saldo = ? {limpeza_sql} WHERE numero = ?", (novo_saldo, numero))
            cursor.execute("INSERT OR IGNORE INTO financeiro (numero, saldo) VALUES (?, ?)", (numero, novo_saldo))

            # Log da Transação
            cursor.execute("""
            INSERT INTO transacoes 
            (numero_cliente, data_registro, data_comprovante, tipo, valor, saldo_anterior, saldo_novo, pagador, banco, id_comprovante) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                numero, 
                datetime.now().strftime('%d/%m/%Y %H:%M:%S'), 
                dados.get('data_full', 'N/A'),
                dados['tipo'], 
                valor, 
                saldo_ant, 
                novo_saldo, 
                dados.get('pagador', 'Admin'), 
                dados.get('banco', 'N/A'),
                dados['id_id']
            ))
            conn.commit()
            
        return saldo_ant, novo_saldo