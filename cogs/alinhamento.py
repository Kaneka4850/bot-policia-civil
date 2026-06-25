import re
import discord
from discord.ext import commands
from discord import app_commands

# ─────────────────────────────────────────────
# IDs centralizados
# ─────────────────────────────────────────────
CARGO_PERMITIDO    = # Permissão de advertência
CANAL_ALINHAMENTO  = # Canal onde o embed de convocação é enviado
CANAL_LOGS         = # Canal de logs
LINK_CALL          = # Insira o link do canal de chamada do discord

# ─────────────────────────────────────────────
# Regex de validação
# ─────────────────────────────────────────────
RE_DATA   = re.compile(r"^\d{2}/\d{2}/\d{4}$")
RE_HORARIO = re.compile(r"^\d{2}[h:]\d{2}$")


# ══════════════════════════════════════════════
# Modal de preenchimento
# ══════════════════════════════════════════════
class AlinhamentoModal(discord.ui.Modal, title="📋 Convocar para Alinhamento"):

    id_agente = discord.ui.TextInput(
        label="ID discord do Oficial a ser convocado",
        placeholder="Ex: 123456789012345678",
        required=True,
        max_length=20,
    )
    data_alinhamento = discord.ui.TextInput(
        label="Data do alinhamento (DD/MM/AAAA)",
        placeholder="Ex: 31/10/2018",
        required=True,
        max_length=10,
    )
    horario_alinhamento = discord.ui.TextInput(
        label="Horário do alinhamento (00h00 ou 00:00)",
        placeholder="Ex: 18h00 ou 18:00",
        required=True,
        max_length=5,
    )

    def __init__(self, bot: discord.Client):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        # ── Validação: data ──────────────────────────────────────────
        data_raw = self.data_alinhamento.value.strip()
        if not RE_DATA.match(data_raw):
            await interaction.response.send_message(
                "❌ Data inválida. Use o formato **DD/MM/AAAA** (ex: 31/10/2018).",
                ephemeral=True,
            )
            return

        # ── Validação: horário ───────────────────────────────────────
        hora_raw = self.horario_alinhamento.value.strip()
        if not RE_HORARIO.match(hora_raw):
            await interaction.response.send_message(
                "❌ Horário inválido. Use o formato **00h00** ou **00:00** (ex: 18h00).",
                ephemeral=True,
            )
            return

        # Normaliza separador para exibição (ex: 18:00 → 18h00)
        hora_fmt = hora_raw.replace(":", "h")

        # ── Validação: ID numérico ───────────────────────────────────
        id_raw = self.id_agente.value.strip()
        if not id_raw.isdigit():
            await interaction.response.send_message(
                "❌ O ID do agente deve conter apenas números.",
                ephemeral=True,
            )
            return

        membro_id = int(id_raw)
        guild     = interaction.guild
        moderador = interaction.user          # quem preencheu o modal

        # ── Busca o membro no servidor ───────────────────────────────
        membro = guild.get_member(membro_id)
        if membro is None:
            try:
                membro = await guild.fetch_member(membro_id)
            except discord.NotFound:
                await interaction.response.send_message(
                    "❌ Membro não encontrado neste servidor. Verifique o ID.",
                    ephemeral=True,
                )
                return

        # ── Verifica cargo do moderador ──────────────────────────────
        possui_cargo = any(r.id == CARGO_PERMITIDO for r in moderador.roles)
        if not possui_cargo:
            await interaction.response.send_message(
                "⛔ Você não tem permissão para convocar membros.",
                ephemeral=True,
            )
            return

        # ── Monta embed de convocação ────────────────────────────────
        canal_destino = self.bot.get_channel(CANAL_ALINHAMENTO)
        if canal_destino is None:
            await interaction.response.send_message(
                "❌ Canal de alinhamento não encontrado.", ephemeral=True
            )
            return

        embed_conv = discord.Embed(
            title="📋 Convocação para Alinhamento",
            color=discord.Color.blue(),  # azul
        )
        embed_conv.description = (
            f"Caro {membro.mention}!\n\n"
            "Você foi convocado para o alinhamento para conversarmos sobre seus "
            "atos de conduta na policia.\n\n"
            f"Compareça à call através do link {LINK_CALL} no horário avisado abaixo "
            "para que os pontos sejam alinhados."
        )
        embed_conv.add_field(
            name="🗓️ Data do alinhamento",
            value=data_raw,
            inline=True,
        )
        embed_conv.add_field(
            name="⏰ Horário do alinhamento",
            value=hora_fmt,
            inline=True,
        )
        embed_conv.add_field(
            name="👤 Ao subir, procure por:",
            value=moderador.mention,
            inline=False,
        )
        embed_conv.set_footer(
            text="O não comparecimento em até 24hrs acarretará em sanções maiores.\n\nAtenciosamente, Alto comando da Polícia Civil"
        )

        await canal_destino.send(content=f"|| {membro.mention} ||", embed=embed_conv)

        # ── Log ──────────────────────────────────────────────────────
        canal_logs = self.bot.get_channel(CANAL_LOGS)
        if canal_logs:
            log_embed = discord.Embed(
                title="📋 Log de Alinhamento",
                description=f"{moderador.mention} convocou {membro.mention}",
                color=discord.Color.dark_purple(),
            )
            log_embed.add_field(name="🗓️ Data", value=data_raw, inline=True)
            log_embed.add_field(name="⏰ Horário", value=hora_fmt, inline=True)
            log_embed.add_field(name="👤 Moderador", value=str(moderador), inline=False)
            log_embed.set_footer(
                text=f"Preenchido por: {moderador} ({moderador.id})",
                icon_url=moderador.display_avatar.url,
            )
            await canal_logs.send(embed=log_embed)

        await interaction.response.send_message(
            f"✅ Convocação enviada para {membro.mention} com sucesso!", ephemeral=True
        )


# ══════════════════════════════════════════════
# View persistente (botão que abre o modal)
# ══════════════════════════════════════════════
class AlinhamentoView(discord.ui.View):
    """custom_id fixo garante que o botão continue funcionando após reinicialização."""

    def __init__(self, bot: discord.Client):
        super().__init__(timeout=None)   # persistente
        self.bot = bot

    @discord.ui.button(
        label="📋 Preencher Convocação",
        style=discord.ButtonStyle.primary,
        custom_id="alinhamento:abrir_modal",
    )
    async def abrir_modal(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Verifica cargo antes de abrir o modal
        possui_cargo = any(r.id == CARGO_PERMITIDO for r in interaction.user.roles)
        if not possui_cargo:
            await interaction.response.send_message(
                "⛔ Você não tem permissão para convocar membros.", ephemeral=True
            )
            return

        await interaction.response.send_modal(AlinhamentoModal(self.bot))


# ══════════════════════════════════════════════
# Cog principal
# ══════════════════════════════════════════════
class Convocacao(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Registra a view persistente ao carregar o cog ────────────────
    async def cog_load(self):
        self.bot.add_view(AlinhamentoView(self.bot))

    # ── !setup_alinhamento ───────────────────────────────────────────
    @app_commands.command(name="setup_alinhamento", description="Envia o embed persistente com o botão de convocação.")
    async def setup_alinhamento(self, interaction: discord.Interaction):
        """Envia o embed persistente com o botão de convocação."""
        possui_cargo = any(r.id == CARGO_PERMITIDO for r in interaction.user.roles)
        if not possui_cargo:
            await interaction.response.send_message("⛔ Você não tem permissão para usar esse comando.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚖️ Sistema de Alinhamento",
            description=(
                "Clique no botão abaixo para preencher uma convocação de alinhamento.\n\n"
                "Apenas membros autorizados podem realizar convocações."
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Policia Civil de Meta City")

        await interaction.channel.send(embed=embed, view=AlinhamentoView(self.bot))
        await interaction.response.send_message("Painel de alinhamento enviado com sucesso!", ephemeral=True)



async def setup(bot):
    await bot.add_cog(Convocacao(bot))
