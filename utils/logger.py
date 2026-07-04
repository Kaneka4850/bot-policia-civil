import logging
import sqlite3
import asyncio
from datetime import datetime

logger = logging.getLogger("bot.logger")

# Configuração básica do logger para console
# (O main.py agora configura o logging global — esta linha é mantida
# como fallback caso o módulo seja importado isoladamente)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ──────────────────────────────────────────────
# Inicialização da tabela (apenas uma vez)
# ──────────────────────────────────────────────
_DB_INITIALIZED = False

def _ensure_table():
    """Cria a tabela de eventos se não existir. Chamada apenas uma vez."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    try:
        conn = sqlite3.connect("eventos.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eventos_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                autor TEXT,
                acao TEXT,
                alvo TEXT,
                extra TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()
        _DB_INITIALIZED = True
    except Exception as e:
        logger.error(f"Erro ao inicializar tabela de eventos: {e}", exc_info=True)

# Inicializa a tabela no import (uma vez só)
_ensure_table()

# ──────────────────────────────────────────────
# Funções de log
# ──────────────────────────────────────────────

# Função para logar no console
def log_console(author, action, target=None, extra=None):
    message = f"Ação: {action} | Autor: {author} | Alvo: {target} | Extra: {extra}"
    logger.info(message)

# Função SÍNCRONA para logar em banco de dados SQLite
# (executada via asyncio.to_thread para não bloquear o event loop)
def _log_event_to_db_sync(author, action, target=None, extra=None):
    """Versão síncrona — NÃO chame diretamente de código async."""
    try:
        conn = sqlite3.connect("eventos.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO eventos_log (autor, acao, alvo, extra, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (str(author), action, str(target), str(extra), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao logar evento no DB: {e}", exc_info=True)

# Mantém a interface original para código síncrono legado
def log_event_to_db(author, action, target=None, extra=None):
    """Versão síncrona legada — prefira log_event_async em código async."""
    _log_event_to_db_sync(author, action, target, extra)

# Função combinada (síncrona — legado)
def log_event(author, action, target=None, extra=None):
    log_console(author, action, target, extra)
    _log_event_to_db_sync(author, action, target, extra)

# ──────────────────────────────────────────────
# Versão ASYNC — use esta em handlers do discord.py
# ──────────────────────────────────────────────
async def log_event_async(author, action, target=None, extra=None):
    """Log no console + DB sem bloquear o event loop."""
    log_console(author, action, target, extra)
    try:
        await asyncio.to_thread(_log_event_to_db_sync, author, action, target, extra)
    except Exception as e:
        logger.error(f"Erro ao logar evento async: {e}", exc_info=True)