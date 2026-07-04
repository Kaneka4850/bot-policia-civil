"""
status_acao.py — COG de estatísticas de ações

Depende de:
    • acao.py  (AcaoCog) já carregado — lê os embeds para extrair dados
    • SQLite   (acoesmembros.db) criado automaticamente na primeira carga
    • acoes_stats.json — criado automaticamente na primeira carga

Comandos expostos:
    !status_acao    → embed global com wins/losses por tipo de ação
    !status_membro  → sem menção: top-15 | com menção: ficha individual
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import unicodedata
from collections import OrderedDict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bot.status_acao")

# Tamanho máximo do cache de mensagens já processadas
_MAX_CACHE_SIZE = 2000

import discord
from discord.ext import commands
from discord import app_commands

import utils.ui as ui

# ──────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────

DB_PATH   = Path("/app/data/acoesmembros.db")
JSON_PATH = Path("/app/data/acoes_stats.json")

# Garante que a pasta existe antes de qualquer operação
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Canal onde o embed global de estatísticas ficará fixo
CANAL_STATUS_ID: int = 1420291627263725738  # canal 🔫・ações

# Lista canônica de ações da cidade
ACOES_CANONICAS: list[str] = [
    "Nióbio",
    "Banco Central",
    "Banco Paleto",
    "Porta Aviões",
    "Joalheria",
    "Galinheiro",
    "Açougue",
    "Cinema",
    "Fleeca Praia",
    "Fleeca Life Invader",
    "Fleeca Rota 68",
]

# ──────────────────────────────────────────────────────────
# HELPERS DE BANCO / JSON
# ──────────────────────────────────────────────────────────

def _init_db() -> None:
    """Cria o banco e as tabelas se ainda não existirem."""
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS participacoes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id  TEXT    NOT NULL,
                tipo_acao   TEXT    NOT NULL,
                resultado   TEXT    NOT NULL CHECK(resultado IN ('win', 'loss')),
                timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_id  TEXT
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_discord_id ON participacoes(discord_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_tipo_acao  ON participacoes(tipo_acao)")
        con.commit()


def _load_json() -> dict:
    """Carrega (ou inicializa) o JSON de estatísticas globais."""
    if JSON_PATH.exists():
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    data = {
        "acoes": {acao: {"win": 0, "loss": 0} for acao in ACOES_CANONICAS}
    }
    _save_json(data)
    return data


def _save_json(data: dict) -> None:
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _remover_acentos(texto: str) -> str:
    """Remove acentos de uma string via decomposição Unicode."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _normalizar_acao(texto: str) -> Optional[str]:
    """
    Mapeia o valor livre do campo 1️⃣ AÇÃO para uma entrada canônica.
    Ignora maiúsculas/minúsculas e acentos.
    Ex: 'banco central', 'BANCO CENTRAL', 'niobio', 'BaNcO CeNtRaL' → canônico correto.
    """
    def norm(s: str) -> str:
        return _remover_acentos(s.casefold().strip())

    texto_norm = norm(texto)
    for acao in ACOES_CANONICAS:
        if norm(acao) in texto_norm or texto_norm in norm(acao):
            return acao
    return None


def _extrair_resultado(embed: discord.Embed) -> Optional[str]:
    """Lê o field '5️⃣ RESULTADO' e retorna 'win' ou 'loss'."""
    for field in embed.fields:
        if "RESULTADO" in field.name.upper():
            val = _remover_acentos(field.value.casefold())
            if "win" in val or "vitoria" in val:
                return "win"
            if "loss" in val or "derrota" in val:
                return "loss"
    return None


def _extrair_tipo_acao(embed: discord.Embed) -> Optional[str]:
    """Lê o field '1️⃣ AÇÃO' e retorna o nome canônico."""
    for field in embed.fields:
        nome_norm = _remover_acentos(field.name.upper())
        if "ACAO" in nome_norm:
            return _normalizar_acao(field.value)
    return None


def _extrair_membros(embed: discord.Embed) -> list[str]:
    """Retorna lista de discord_ids (strings) dos membros confirmados."""
    for field in embed.fields:
        if "Membros Confirmados" in field.name:
            return re.findall(r"<@(\d+)>", field.value)
    return []


def _registrar_participacoes(
    message_id: str,
    tipo_acao: str,
    resultado: str,
    member_ids: list[str],
) -> int:
    """
    Insere participações no DB e atualiza o JSON global.
    Usa uma única conexão para evitar lock de SQLite.
    Conta a ação (win/loss) apenas uma vez por message_id.
    Retorna o número de novos membros inseridos.
    """
    data = _load_json()
    if tipo_acao not in data["acoes"]:
        data["acoes"][tipo_acao] = {"win": 0, "loss": 0}

    novos_membros = 0

    with sqlite3.connect(DB_PATH) as con:
        # Verifica se essa ação já foi contada no JSON (pela existência no DB)
        linha_existente = con.execute(
            "SELECT 1 FROM participacoes WHERE message_id=? LIMIT 1",
            (message_id,),
        ).fetchone()

        if linha_existente is None:
            # Primeira vez processando essa mensagem → conta a ação globalmente
            data["acoes"][tipo_acao][resultado] += 1

        for mid in member_ids:
            ja_existe = con.execute(
                "SELECT 1 FROM participacoes WHERE message_id=? AND discord_id=?",
                (message_id, mid),
            ).fetchone()
            if ja_existe:
                continue
            con.execute(
                "INSERT INTO participacoes (discord_id, tipo_acao, resultado, message_id) "
                "VALUES (?,?,?,?)",
                (mid, tipo_acao, resultado, message_id),
            )
            novos_membros += 1
        con.commit()

    if linha_existente is None or novos_membros:
        _save_json(data)

    return novos_membros


# ──────────────────────────────────────────────────────────
# BUILDERS DE EMBED
# ──────────────────────────────────────────────────────────

def _build_embed_global(bot: commands.Bot) -> discord.Embed:
    """Constrói o embed de estatísticas globais."""
    data  = _load_json()
    acoes = data.get("acoes", {})

    total_win   = sum(v["win"]  for v in acoes.values())
    total_loss  = sum(v["loss"] for v in acoes.values())
    total_geral = total_win + total_loss
    winrate     = round((total_win / total_geral) * 100) if total_geral else 0

    embed = ui.build_embed(
        title="📊 Estatísticas Gerais de Ações",
        description=(
            f"**Total de ações:** {total_geral}\n"
            f"**Vitórias:** {total_win} • **Taxa:** {winrate}%\n"
            f"**Derrotas:** {total_loss} • **Taxa:** {100 - winrate}%"
        ),
        color=ui.UI_COLOR_MAIN,
    )

    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(name="\u200b", value="**Detalhamento por ação:**", inline=False)

    for acao in ACOES_CANONICAS:
        stats = acoes.get(acao, {"win": 0, "loss": 0})
        w = stats["win"]
        derrotas = stats["loss"]
        total = w + derrotas
        if total == 0:
            continue
        wr = round((w / total) * 100)
        embed.add_field(
            name=f"• {acao}",
            value=f"🟢 {w}  🔴 {derrotas}  |  {total} ação(ões)  |  WR: **{wr}%**",
            inline=False,
        )

    if total_geral == 0:
        embed.add_field(
            name="ℹ️ Nenhuma ação registrada ainda.",
            value="Use `!painel_acao` para registrar ações.",
            inline=False,
        )

    # O rodapé padrão já é incluído por ui.build_embed
    return embed


def _build_embed_top15(bot: commands.Bot) -> discord.Embed:
    """Constrói o embed de ranking top-15."""
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute("""
            SELECT
                discord_id,
                COUNT(*)                                          AS total,
                SUM(CASE WHEN resultado='win'  THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN resultado='loss' THEN 1 ELSE 0 END) AS losses
            FROM participacoes
            GROUP BY discord_id
            ORDER BY total DESC
            LIMIT 15
        """).fetchall()

    embed = ui.build_embed(
        title="🏆 Ranking de Ações",
        description="Top **15** membro(s) com mais ações finalizadas registradas.",
        color=ui.UI_COLOR_WARNING,
    )

    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    if not rows:
        embed.add_field(
            name="ℹ️ Nenhum dado disponível.",
            value="Confirme participações nas ações para aparecer aqui.",
            inline=False,
        )
        return embed

    embed.add_field(name="\u200b", value="**Ranking geral**", inline=False)

    medalhas = ["🥇", "🥈", "🥉"]
    for i, (discord_id, total, wins, losses) in enumerate(rows, start=1):
        wr     = round((wins / total) * 100) if total else 0
        prefixo = medalhas[i - 1] if i <= 3 else f"{i}."
        embed.add_field(
            name="\u200b",
            value=(
                f"{prefixo} <@{discord_id}> — **{total}** ação(ões) | "
                f"🟢 {wins} 🔴 {losses} | Winrate: **{wr}%**"
            ),
            inline=False,
        )

    embed.set_footer(text=f"{ui.FOOTER_TEXT} • !status_membro @usuário para ficha")
    return embed


def _build_embed_membro(bot: commands.Bot, member: discord.Member) -> discord.Embed:
    """Constrói a ficha individual de um membro."""
    discord_id = str(member.id)

    with sqlite3.connect(DB_PATH) as con:
        stats_gerais = con.execute("""
            SELECT
                COUNT(*)                                          AS total,
                SUM(CASE WHEN resultado='win'  THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN resultado='loss' THEN 1 ELSE 0 END) AS losses
            FROM participacoes
            WHERE discord_id=?
        """, (discord_id,)).fetchone()

        por_acao = con.execute("""
            SELECT
                tipo_acao,
                COUNT(*)                                          AS total,
                SUM(CASE WHEN resultado='win'  THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN resultado='loss' THEN 1 ELSE 0 END) AS losses
            FROM participacoes
            WHERE discord_id=?
            GROUP BY tipo_acao
            ORDER BY total DESC
        """, (discord_id,)).fetchall()

    total, wins, losses = stats_gerais or (0, 0, 0)
    total  = total  or 0
    wins   = wins   or 0
    losses = losses or 0
    wr     = round((wins / total) * 100) if total else 0

    embed = ui.build_embed(
        title="📋 Estatísticas de Ações",
        description=f"Resumo de participação de {member.mention}.",
        color=ui.UI_COLOR_MAIN,
    )

    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(
        name="Resumo geral",
        value=(
            f"**Total de ações:** {total}\n"
            f"**Vitórias:** {wins} • **Taxa:** {wr}%\n"
            f"**Derrotas:** {losses} • **Taxa:** {100 - wr}%"
        ),
        inline=False,
    )

    if por_acao:
        linhas = [
            f"**{tipo}** — {t} ação(ões) | 🟢 {w} 🔴 {derrotas}"
            for tipo, t, w, derrotas in por_acao
        ]
        embed.add_field(
            name="Locais mais jogados",
            value="\n".join(linhas),
            inline=False,
        )
    else:
        embed.add_field(
            name="ℹ️",
            value="Nenhuma participação registrada para este membro.",
            inline=False,
        )

    # Rodapé padrão já incluso
    return embed


# ──────────────────────────────────────────────────────────
# COG
# ──────────────────────────────────────────────────────────

class StatusAcaoCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        _init_db()
        _load_json()
        # Cache limitado — evita crescimento infinito de memória
        self._mensagens_processadas: OrderedDict[str, None] = OrderedDict()
        self._status_message_id: Optional[int] = None

    # ------------------------------------------------------------------
    # SINCRONIZAÇÃO AUTOMÁTICA
    # ------------------------------------------------------------------

    def _sincronizar_embed(self, message: discord.Message) -> bool:
        if not message.embeds:
            return False
        embed = message.embeds[0]
        if not embed.title or "RELATÓRIO DE AÇÃO" not in embed.title.upper():
            return False

        tipo_acao = _extrair_tipo_acao(embed)
        resultado = _extrair_resultado(embed)
        membros   = _extrair_membros(embed)

        if not tipo_acao or not resultado or not membros:
            return False

        novos = _registrar_participacoes(
            message_id=str(message.id),
            tipo_acao=tipo_acao,
            resultado=resultado,
            member_ids=membros,
        )
        return novos > 0

    def _cache_add(self, mid: str) -> None:
        """Adiciona ID ao cache limitado, removendo o mais antigo se necessário."""
        if mid in self._mensagens_processadas:
            return
        self._mensagens_processadas[mid] = None
        # Evita crescimento infinito — remove os mais antigos
        while len(self._mensagens_processadas) > _MAX_CACHE_SIZE:
            self._mensagens_processadas.popitem(last=False)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author != self.bot.user:
            return
        mid = str(message.id)
        if mid in self._mensagens_processadas:
            return
        self._cache_add(mid)
        try:
            # Executa I/O de SQLite em thread separada para não bloquear o event loop
            sync_result = await asyncio.to_thread(self._sincronizar_embed, message)
            if sync_result:
                await self._atualizar_embed_global()
        except Exception:
            logger.error("Erro ao sincronizar embed em on_message", exc_info=True)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if after.author != self.bot.user:
            return
        try:
            sync_result = await asyncio.to_thread(self._sincronizar_embed, after)
            if sync_result:
                await self._atualizar_embed_global()
        except Exception:
            logger.error("Erro ao sincronizar embed em on_message_edit", exc_info=True)

    # ------------------------------------------------------------------
    # EMBED GLOBAL PERSISTENTE
    # ------------------------------------------------------------------

    async def _atualizar_embed_global(self) -> None:
        if CANAL_STATUS_ID == 0:
            return

        canal = self.bot.get_channel(CANAL_STATUS_ID)
        if not isinstance(canal, discord.TextChannel):
            return

        novo_embed = _build_embed_global(self.bot)

        if self._status_message_id:
            try:
                msg = await canal.fetch_message(self._status_message_id)
                await msg.edit(embed=novo_embed)
                return
            except (discord.NotFound, discord.HTTPException):
                self._status_message_id = None

        msg = await canal.send(embed=novo_embed)
        self._status_message_id = msg.id

    # ------------------------------------------------------------------
    # COMANDO: /status_acao
    # ------------------------------------------------------------------

    @app_commands.command(name="status_acao", description="Exibe estatísticas globais de ações por tipo.")
    async def status_acao(self, interaction: discord.Interaction) -> None:
        """Exibe estatísticas globais de ações por tipo."""
        embed = await asyncio.to_thread(_build_embed_global, self.bot)
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # COMANDO: /status_membro
    # ------------------------------------------------------------------

    @app_commands.command(name="status_membro", description="Ficha individual (com menção) ou top-15 (sem menção).")
    async def status_membro(
        self,
        interaction: discord.Interaction,
        membro: Optional[discord.Member] = None,
    ) -> None:
        """Sem menção → top-15 | Com menção → ficha individual."""
        if membro is None:
            embed = await asyncio.to_thread(_build_embed_top15, self.bot)
        else:
            embed = await asyncio.to_thread(_build_embed_membro, self.bot, membro)
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # COMANDO ADMIN: /setup_status
    # ------------------------------------------------------------------

    @app_commands.command(name="setup_status", description="Posta o embed global no canal atual.")
    @app_commands.default_permissions(administrator=True)
    async def setup_status(self, interaction: discord.Interaction) -> None:
        """Posta o embed global no canal atual e salva o ID para atualizações futuras."""
        global CANAL_STATUS_ID
        CANAL_STATUS_ID = interaction.channel.id

        embed = _build_embed_global(self.bot)
        msg = await interaction.channel.send(embed=embed)
        self._status_message_id = msg.id
        await interaction.response.send_message(
            embed=ui.build_success_embed("Painel de status configurado com sucesso!"), ephemeral=True
        )

    # ------------------------------------------------------------------
    # COMANDO ADMIN: /sync_acoes
    # ------------------------------------------------------------------

    @app_commands.command(name="sync_acoes", description="Varre as últimas N mensagens do canal e importa ações.")
    @app_commands.default_permissions(administrator=True)
    async def sync_acoes(
        self,
        interaction: discord.Interaction,
        limite: int = 200,
    ) -> None:
        """Varre as últimas N mensagens do canal e importa ações ainda não registradas."""
        await interaction.response.send_message(
            embed=ui.build_embed(title="⏳ Sincronizando...", description=f"Analisando últimas {limite} mensagens.")
        )

        total_novos = 0
        async for message in interaction.channel.history(limit=limite):
            if message.author != self.bot.user:
                continue
            try:
                if await asyncio.to_thread(self._sincronizar_embed, message):
                    total_novos += 1
            except Exception:
                logger.error(f"Erro ao sincronizar msg {message.id}", exc_info=True)

        await interaction.edit_original_response(
            content=None,
            embed=ui.build_success_embed(f"Sincronização concluída. {total_novos} ação(ões) nova(s) importada(s).")
        )
        await self._atualizar_embed_global()


# ──────────────────────────────────────────────────────────
# SETUP
# ──────────────────────────────────────────────────────────

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatusAcaoCog(bot))