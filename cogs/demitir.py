import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import asyncio
import logging

# 🧩 Serviços e utilitários
from services.membro_service import remover_registro, buscar_registro_por_discord_id
from utils.logger import log_event_async
import utils.ui as ui

logger = logging.getLogger("bot.demitir")

# ──────────────────────────────────────────────
#  CONFIGURAÇÕES
# ──────────────────────────────────────────────
CARGOS_PERMITIDOS    = [1519099990587473926]   # 🔑| Perm. Advertência (mesmo de advertencia.py)
CARGO_EXONERADO_ID   = 1519099990507520037     # ADV4 (cargo de exonerado)

CANAL_EXONERACAO_ID  = 1519099991631593487 # Canal ❌・exonerações
CANAL_BLACKLIST_ID   = 15241138385369170320 # Canal 💀・blacklist-permanente


# ──────────────────────────────────────────────
#  VIEW DE CONFIRMAÇÃO — Confirmar / Cancelar
# ──────────────────────────────────────────────
class ConfirmarDemissaoView(discord.ui.View):
    """View ephemeral com botões de Confirmar / Cancelar a exoneração."""

    def __init__(
        self,
        cog: "Demissao",
        membro: discord.Member,
        registro: dict,
        motivo: str,
        blacklist_valor: str | None,
        blacklist_label: str,
    ):
        super().__init__(timeout=120)
        self.cog = cog
        self.membro = membro
        self.registro = registro
        self.motivo = motivo
        self.blacklist_valor = blacklist_valor  # None = sem blacklist
        self.blacklist_label = blacklist_label  # "Nenhuma", "X dias", "Permanente"

    @discord.ui.button(label="Confirmar Exoneração", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        guild     = interaction.guild
        aplicador = interaction.user
        membro    = self.membro
        agora     = datetime.now(timezone.utc).strftime("%d/%m/%Y às %H:%M")

        # ── 1. Remove todos os cargos e aplica somente ADV4 ──
        cargo_exonerado = guild.get_role(self.cog.cargo_exonerado_id)

        try:
            # Remove todos os cargos gerenciáveis do membro
            cargos_para_remover = [r for r in membro.roles if r != guild.default_role and r.is_assignable()]
            if cargos_para_remover:
                await membro.remove_roles(*cargos_para_remover, reason=f"Exoneração por {aplicador}")

            # Aplica o cargo de exonerado (ADV4)
            if cargo_exonerado:
                await membro.add_roles(cargo_exonerado, reason=f"Exoneração por {aplicador}")
        except discord.Forbidden:
            await interaction.followup.send(
                embed=ui.build_error_embed("Não foi possível modificar os cargos do membro. Verifique as permissões do bot."),
                ephemeral=True,
            )
            self.stop()
            return

        # ── 2. Remove registro do banco de dados ──
        await asyncio.to_thread(remover_registro, membro.id)
        await log_event_async(str(aplicador), "Exoneração", self.registro["usuario"], extra=self.motivo)

        # ── 3. Embed de exoneração (canal de exoneração — SEMPRE) ──
        embed_exoneracao = ui.build_embed(
            title="❌ Exoneração Realizada",
            description=f"<@{membro.id}> foi exonerado do FBI.",
            color=ui.UI_COLOR_ERROR,
        )
        embed_exoneracao.add_field(name="👤 Membro exonerado", value=f"{membro.mention}\n`{membro.id}`",        inline=True)
        embed_exoneracao.add_field(name="📛 Nome",             value=f"`{self.registro['nome']}`",              inline=True)
        embed_exoneracao.add_field(name="🆔 Passaporte",       value=f"`{self.registro['id']}`",                inline=True)
        embed_exoneracao.add_field(name="📝 Motivo",           value=self.motivo,                                inline=False)
        embed_exoneracao.add_field(name="🚫 Blacklist",        value=self.blacklist_label,                       inline=True)
        embed_exoneracao.add_field(name="🛡️ Exonerado por",   value=f"{aplicador.mention}\n`{aplicador.id}`",  inline=True)
        embed_exoneracao.add_field(name="📅 Data/Hora",        value=agora,                                      inline=True)
        embed_exoneracao.set_thumbnail(url=membro.avatar.url if membro.avatar else None)
        embed_exoneracao.set_footer(
            text=f"{ui.FOOTER_TEXT} • Ação realizada em {agora}",
            icon_url=aplicador.avatar.url if aplicador.avatar else None,
        )

        canal_exoneracao = self.cog.bot.get_channel(self.cog.canal_exoneracao_id)
        if canal_exoneracao:
            await canal_exoneracao.send(content=f"<@{membro.id}>", embed=embed_exoneracao)
        else:
            logger.warning("Canal de exoneração não encontrado (ID: %s)", self.cog.canal_exoneracao_id)

        # ── 4. Embed de blacklist permanente (canal de blacklist — SÓ SE permanente) ──
        if self.blacklist_valor and self.blacklist_valor.lower() == "permanente":
            embed_blacklist = ui.build_embed(
                title="🚫 Blacklist Permanente",
                description=f"<@{membro.id}> recebeu blacklist **permanente** do FBI.",
                color=ui.UI_COLOR_ERROR,
            )
            embed_blacklist.add_field(name="👤 Membro",          value=f"{membro.mention}\n`{membro.id}`",        inline=True)
            embed_blacklist.add_field(name="📛 Nome",            value=f"`{self.registro['nome']}`",              inline=True)
            embed_blacklist.add_field(name="🆔 Passaporte",      value=f"`{self.registro['id']}`",                inline=True)
            embed_blacklist.add_field(name="📝 Motivo",          value=self.motivo,                                inline=False)
            embed_blacklist.add_field(name="🛡️ Aplicado por",   value=f"{aplicador.mention}\n`{aplicador.id}`",  inline=True)
            embed_blacklist.add_field(name="📅 Data/Hora",       value=agora,                                      inline=True)
            embed_blacklist.set_thumbnail(url=membro.avatar.url if membro.avatar else None)
            embed_blacklist.set_footer(text=f"{ui.FOOTER_TEXT} • Blacklist permanente")

            canal_blacklist = self.cog.bot.get_channel(self.cog.canal_blacklist_id)
            if canal_blacklist:
                await canal_blacklist.send(content=f"<@{membro.id}>", embed=embed_blacklist)
            else:
                logger.warning("Canal de blacklist não encontrado (ID: %s)", self.cog.canal_blacklist_id)

        # ── 5. Confirmação ephemeral ──
        await interaction.followup.send(
            embed=ui.build_success_embed(f"<@{membro.id}> foi exonerado com sucesso."),
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=ui.build_warn_embed("Operação cancelada. Nenhuma exoneração foi realizada."),
            ephemeral=True,
        )
        self.stop()


# ──────────────────────────────────────────────
#  MODAL — preenchido pelo aplicador
# ──────────────────────────────────────────────
class DemissaoModal(discord.ui.Modal, title="📄 Exoneração de Oficial"):

    id_membro = discord.ui.TextInput(
        label="ID Discord do oficial",
        placeholder="Ex: 123456789012345678",
        required=True,
        max_length=20,
    )

    motivo = discord.ui.TextInput(
        label="Motivo da demissão",
        placeholder="Descreva o motivo da exoneração...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    blacklist = discord.ui.TextInput(
        label="Blacklist (dias, 'permanente' ou vazio)",
        placeholder="Ex: 30, permanente ou deixe vazio",
        required=False,
        max_length=20,
    )

    def __init__(self, cog: "Demissao"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        aplicador = interaction.user
        guild     = interaction.guild

        # ── Verifica permissão do aplicador ─────────
        if not any(r.id in self.cog.cargos_permitidos for r in aplicador.roles):
            await interaction.followup.send(
                embed=ui.build_error_embed("Você não tem permissão para realizar exonerações."),
                ephemeral=True,
            )
            return

        # ── Valida ID do membro ─────────────────────
        membro_id_str = self.id_membro.value.strip()
        if not membro_id_str.isdigit():
            await interaction.followup.send(
                embed=ui.build_warn_embed("ID inválido. Digite apenas números."),
                ephemeral=True,
            )
            return

        membro = guild.get_member(int(membro_id_str))
        if not membro:
            try:
                membro = await guild.fetch_member(int(membro_id_str))
            except discord.NotFound:
                await interaction.followup.send(
                    embed=ui.build_warn_embed("Membro não encontrado neste servidor."),
                    ephemeral=True,
                )
                return

        # ── Verifica hierarquia (mesma lógica de advertencia.py) ──
        if membro.top_role.position >= aplicador.top_role.position:
            await interaction.followup.send(
                embed=ui.build_error_embed("Você não pode exonerar um membro com cargo igual ou superior ao seu."),
                ephemeral=True,
            )
            return

        if membro.top_role.position >= guild.me.top_role.position:
            await interaction.followup.send(
                embed=ui.build_error_embed("Esse membro tem um cargo acima ou igual ao meu. Não posso modificá-lo."),
                ephemeral=True,
            )
            return

        # ── Verifica registro no banco de dados ─────
        registro = await asyncio.to_thread(buscar_registro_por_discord_id, membro.id)
        if not registro:
            await interaction.followup.send(
                embed=ui.build_error_embed(f"O membro <@{membro.id}> não possui registro no banco de dados."),
                ephemeral=True,
            )
            return

        # ── Valida campo de blacklist ────────────────
        blacklist_raw = self.blacklist.value.strip()
        blacklist_valor = None
        blacklist_label = "Nenhuma"

        if blacklist_raw:
            bl_lower = blacklist_raw.lower()
            if bl_lower == "permanente":
                blacklist_valor = "permanente"
                blacklist_label = "Permanente"
            elif blacklist_raw.isdigit() and int(blacklist_raw) > 0:
                blacklist_valor = blacklist_raw
                blacklist_label = f"{blacklist_raw} dias"
            else:
                await interaction.followup.send(
                    embed=ui.build_warn_embed(
                        "Valor de blacklist inválido.\n\n"
                        "Valores aceitos:\n"
                        "• **Número** de dias (ex: `30`)\n"
                        "• **Permanente** (escreva `permanente`)\n"
                        "• **Vazio** para nenhuma blacklist"
                    ),
                    ephemeral=True,
                )
                return

        motivo_texto = self.motivo.value.strip()

        # ── Monta embed de confirmação ───────────────
        embed_confirma = ui.build_embed(
            title="⚠️ Confirmar Exoneração",
            description=(
                f"Você está prestes a exonerar <@{membro.id}> do FBI.\n\n"
                f"**📛 Nome:** `{registro['nome']}`\n"
                f"**🆔 Passaporte:** `{registro['id']}`\n"
                f"**📝 Motivo:** {motivo_texto}\n"
                f"**🚫 Blacklist:** {blacklist_label}\n\n"
                "⚠️ **Esta ação é irreversível.** Deseja continuar?"
            ),
            color=ui.UI_COLOR_ERROR,
        )

        view = ConfirmarDemissaoView(
            cog=self.cog,
            membro=membro,
            registro=registro,
            motivo=motivo_texto,
            blacklist_valor=blacklist_valor,
            blacklist_label=blacklist_label,
        )

        await interaction.followup.send(embed=embed_confirma, view=view, ephemeral=True)


# ──────────────────────────────────────────────
#  VIEW PERSISTENTE — botão no embed
# ──────────────────────────────────────────────
class DemissaoView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)  # persistente — sobrevive a restart

    @discord.ui.button(
        label="Iniciar Exoneração",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="btn_iniciar_demissao",  # ID fixo obrigatório para views persistentes
    )
    async def abrir_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.cogs.get("Demissao")
        if not cog:
            await interaction.response.send_message(
                embed=ui.build_error_embed("Cog não carregada."),
                ephemeral=True,
            )
            return

        # Verifica permissão antes de abrir o modal
        if not any(r.id in cog.cargos_permitidos for r in interaction.user.roles):
            await interaction.response.send_message(
                embed=ui.build_error_embed("Você não tem permissão para usar isso."),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(DemissaoModal(cog))


# ──────────────────────────────────────────────
#  COG PRINCIPAL
# ──────────────────────────────────────────────
class Demissao(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot                = bot
        self.cargos_permitidos  = CARGOS_PERMITIDOS
        self.cargo_exonerado_id = CARGO_EXONERADO_ID
        self.canal_exoneracao_id = CANAL_EXONERACAO_ID
        self.canal_blacklist_id  = CANAL_BLACKLIST_ID

    async def cog_load(self):
        """Registra a view persistente no bot ao carregar a cog."""
        self.bot.add_view(DemissaoView())

    @app_commands.command(name="setup_demissao", description="Envia o embed persistente de exoneração no canal atual.")
    @app_commands.default_permissions(administrator=True)
    async def setup_demissao(self, interaction: discord.Interaction):
        """
        Envia o embed persistente de exoneração no canal atual.
        Apenas administradores podem executar esse comando.
        """
        embed = ui.build_embed(
            title="❌ Sistema de Exoneração",
            description=(
                "Clique no botão abaixo para abrir o formulário de exoneração.\n\n"
                "Preencha os campos corretamente:\n"
                "• **ID Discord** do oficial a ser exonerado\n"
                "• **Motivo** da exoneração\n"
                "• **Blacklist** (número de dias, 'permanente' ou vazio)"
            ),
        )
        embed.set_footer(text=f"{ui.FOOTER_TEXT} • Apenas oficiais autorizados podem realizar exonerações.")

        await interaction.channel.send(embed=embed, view=DemissaoView())
        await interaction.response.send_message(
            embed=ui.build_success_embed("Painel de exoneração enviado com sucesso!"),
            ephemeral=True,
        )


# ──────────────────────────────────────────────
#  SETUP
# ──────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Demissao(bot))
