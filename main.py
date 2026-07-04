import os
import sys
import signal
import logging
import faulthandler
import traceback
import asyncio
import threading
import platform

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# 0. FAULTHANDLER — deve ser a primeira coisa
# ──────────────────────────────────────────────
# Habilita dump de traceback em caso de segfault (SIGSEGV),
# SIGABRT ou SIGFPE. Essencial para diagnosticar crashes fatais.
faulthandler.enable()

load_dotenv()

# ──────────────────────────────────────────────
# 1. LOGGING COMPLETO — arquivo + console
# ──────────────────────────────────────────────
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configura logging root para arquivo e console
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Handler: console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
root_logger.addHandler(console_handler)

# Handler: arquivo (persiste entre restarts se montado via volume)
try:
    file_handler = logging.FileHandler("bot.log", encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(file_handler)
except Exception as e:
    logging.warning(f"Não foi possível criar arquivo de log: {e}")

logger = logging.getLogger("bot.main")

# ──────────────────────────────────────────────
# 2. INTENTS
# ──────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


# ──────────────────────────────────────────────
# 3. BOT CLASS COM INSTRUMENTAÇÃO
# ──────────────────────────────────────────────
class MyBot(commands.Bot):
    async def setup_hook(self):
        # ── Carrega todas as cogs ──
        await load_cogs()

        # ── Remove comandos guild-específicos (executa UMA vez antes do bot aceitar eventos) ──
        for guild_id_str in (os.getenv("GUILD_IDS", "")).split(","):
            guild_id_str = guild_id_str.strip()
            if guild_id_str.isdigit():
                guild_obj = discord.Object(id=int(guild_id_str))
                self.tree.clear_commands(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
                logger.info(f"🧹 Comandos guild-específicos removidos do servidor ID: {guild_id_str}")

        # Sync global (pode demorar até 1h para propagar no Discord)
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ {len(synced)} slash commands sincronizados globalmente.")
        except Exception as e:
            logger.error(f"❌ Erro ao sincronizar comandos globalmente: {e}")

        # ── Inicia monitor de recursos ──
        if not self.monitor_recursos.is_running():
            self.monitor_recursos.start()
        logger.info("📊 Monitor de recursos iniciado (intervalo: 30s).")

        # ── Registra exception handler global do asyncio ──
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(self._asyncio_exception_handler)
        logger.info("🛡️ Exception handler global do asyncio registrado.")

    async def on_ready(self):
        logger.info(f"🤖 Bot online como: {self.user}")
        logger.info(f"📊 Servidores conectados: {[g.name for g in self.guilds]}")
        logger.info(f"📊 Latência do Gateway: {self.latency * 1000:.1f}ms")

    async def close(self):
        """Override para logar quando o bot está sendo encerrado."""
        logger.warning("⚠️ bot.close() foi chamado — o bot está sendo encerrado.")
        logger.warning(f"   Stack trace:\n{''.join(traceback.format_stack())}")
        if self.monitor_recursos.is_running():
            self.monitor_recursos.cancel()
        await super().close()

    # ── Exception handler global do asyncio ──
    @staticmethod
    def _asyncio_exception_handler(loop, context):
        exception = context.get("exception")
        message = context.get("message", "Nenhuma mensagem")
        future = context.get("future")

        logger.error("=" * 60)
        logger.error("🚨 EXCEÇÃO NÃO TRATADA NO ASYNCIO")
        logger.error(f"   Mensagem: {message}")
        if exception:
            logger.error(f"   Exceção: {type(exception).__name__}: {exception}")
            logger.error(f"   Traceback:\n{''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))}")
        if future:
            logger.error(f"   Future: {future}")
        logger.error("=" * 60)

    # ── Monitor de recursos (a cada 30 segundos) ──
    @tasks.loop(seconds=30)
    async def monitor_recursos(self):
        """Monitora e registra uso de memória, CPU, threads e tasks."""
        try:
            import resource as res_module
            mem_mb = res_module.getrusage(res_module.RUSAGE_SELF).ru_maxrss / 1024  # Linux: KB → MB
        except ImportError:
            # Windows/fallback: tenta psutil, senão usa info básica
            try:
                import psutil
                process = psutil.Process(os.getpid())
                mem_mb = process.memory_info().rss / (1024 * 1024)
            except ImportError:
                mem_mb = -1  # Não disponível

        # Contagem de tasks do asyncio
        try:
            all_tasks = asyncio.all_tasks()
            num_tasks = len(all_tasks)
        except RuntimeError:
            num_tasks = -1

        # Contagem de threads
        num_threads = threading.active_count()

        # Latência do Gateway
        latency_ms = self.latency * 1000

        # Log
        logger.info(
            f"📊 MONITOR | "
            f"Memória: {mem_mb:.1f}MB | "
            f"Tasks asyncio: {num_tasks} | "
            f"Threads: {num_threads} | "
            f"Latência Gateway: {latency_ms:.1f}ms | "
            f"Guilds: {len(self.guilds)} | "
            f"PID: {os.getpid()}"
        )

        # Alerta se memória estiver alta (> 200MB para um bot simples)
        if mem_mb > 200:
            logger.warning(f"⚠️ ALERTA DE MEMÓRIA: {mem_mb:.1f}MB — possível vazamento!")

        # Alerta se muitas tasks
        if num_tasks > 50:
            logger.warning(f"⚠️ ALERTA DE TASKS: {num_tasks} tasks ativas — possível acúmulo!")

    @monitor_recursos.before_loop
    async def before_monitor(self):
        await self.wait_until_ready()


bot = MyBot(command_prefix="!", intents=intents)

COGS = [
    "cogs.cadastro",
    "cogs.alinhamento",
    "cogs.advertencia",
    "cogs.corregedoria",
    "cogs.registro_prisao",
    "cogs.provas",
    "cogs.acao",
    "cogs.status_acao",
    "cogs.ausencia",
    "cogs.cursos",
]

@bot.tree.command(name="comandos", description="Lista todos os comandos disponíveis")
async def comandos(interaction: discord.Interaction):
    embed = discord.Embed()
    embed.title = "📝 Lista de Comandos Disponiveis"
    embed.description = "Esses são os comandos do bot, eles agora funcionam usando `/` (slash commands)."
    embed.color = discord.Color.blue()
    embed.add_field(name="/setup_provas",            value="(Apenas Arima pode usar esse comando)", inline=False)
    embed.add_field(name="/setup_registro",          value="(Apenas Arima pode usar esse comando).", inline=False)
    embed.add_field(name="/painel_acao",             value="(Apenas Administradores) Cria o painel de registro de ações.", inline=False)
    embed.add_field(name="/listar_registros",        value="Lista todos os registros aprovados.", inline=False)
    embed.add_field(name="/setup_ausencia",          value="Comando para criar o menu de ausência (apenas administradores).", inline=False)
    embed.add_field(name="/setup_cursos",            value="Comando para criar o menu de cursos (apenas administradores).", inline=False)
    embed.add_field(name="/demitir",                 value="Demitir um agente (apenas admins).", inline=False)
    embed.add_field(name="/convocar",                value="Convoca um membro para uma reunião.", inline=False)
    embed.add_field(name="/advertir",                value="Aplica uma advertência a um membro.", inline=False)
    embed.add_field(name="/prisao",                  value="Registra uma prisão.", inline=False)
    embed.add_field(name="/status_acao",             value="Exibe estatísticas globais de ações por tipo.", inline=False)
    embed.add_field(name="/status_membro [@usuário]",value="Ranking top-15 ou ficha individual de um membro.", inline=False)
    embed.add_field(name="/setup_status",            value="(Apenas Administradores) Posta o embed global de estatísticas no canal atual.", inline=False)
    embed.add_field(name="/sync_acoes [N]",          value="(Apenas Administradores) Importa histórico retroativo de ações (padrão: 200 mensagens).", inline=False)
    embed.add_field(name="/comandos",                value="Lista todos os comandos disponíveis.", inline=False)
    embed.set_footer(text="Use os comandos apenas em caso de necessidade, não abuse do bot.")
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info(f"✅ Cog carregado: {cog}")
        except Exception as e:
            logger.error(f"❌ Erro ao carregar {cog}: {e}", exc_info=True)


# ──────────────────────────────────────────────
# 4. HANDLERS DE SINAIS
# ──────────────────────────────────────────────
def _handle_signal(signum, frame):
    """Handler para SIGTERM e SIGINT — registra o sinal antes de encerrar."""
    sig_name = signal.Signals(signum).name
    logger.critical(f"🚨 SINAL RECEBIDO: {sig_name} (signum={signum})")
    logger.critical(f"   Frame: {frame}")
    logger.critical(f"   Stack trace:\n{''.join(traceback.format_stack(frame))}")

    # Flush dos logs antes de encerrar
    for handler in logging.root.handlers:
        handler.flush()

    # Re-levanta o sinal padrão para que o Python encerre normalmente
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


# ──────────────────────────────────────────────
# 5. PONTO DE ENTRADA
# ──────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Iniciando o bot...")
    logger.info(f"   Python: {sys.version}")
    logger.info(f"   discord.py: {discord.__version__}")
    logger.info(f"   Plataforma: {platform.platform()}")
    logger.info(f"   PID: {os.getpid()}")
    logger.info(f"   faulthandler: ativado")
    logger.info("=" * 60)

    # Registra handlers de sinais (apenas em Unix/Linux — Docker)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)
        logger.info("🛡️ Handler para SIGTERM registrado.")
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _handle_signal)
        logger.info("🛡️ Handler para SIGINT registrado.")

    # Captura exceções não tratadas no nível global
    def global_exception_handler(exc_type, exc_value, exc_tb):
        logger.critical("🚨 EXCEÇÃO GLOBAL NÃO TRATADA:")
        logger.critical("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        for handler in logging.root.handlers:
            handler.flush()

    sys.excepthook = global_exception_handler

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("Token do Discord não encontrado nas variáveis de ambiente (.env)!")

    bot.run(token, log_handler=None)  # log_handler=None → usa o nosso logging customizado
