import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

# ──────────────────────────────────────────────
#  CONFIGURAÇÕES
# ──────────────────────────────────────────────
CARGOS_PERMITIDOS   = []       # Insira o id do cargo que pode dar advertencia

CARGOS_ADVERTENCIA  = {
    "ADV1": , # Insira o id do cargo ADV1
    "ADV2": , #  Insira o id do cargo ADV2
    "ADV3": , #  Insira o id do cargo ADV3
    "ADV4": , #  Insira o id do cargo ADV4
}

CANAL_PENALIDADES_ID = # canal de penalidades (embed limpo)
CANAL_LOG_ADV_ID     = # canal de log


# ──────────────────────────────────────────────
#  MODAL — preenchido pelo aplicador
# ──────────────────────────────────────────────
class AdvertenciaModal(discord.ui.Modal, title="📄 Aplicar Advertência"):

    id_membro = discord.ui.TextInput(
        label="ID Discord do oficial",
        placeholder="Ex: 123456789012345678",
        required=True,
        max_length=20,
    )

    tipo_adv = discord.ui.TextInput(
        label="Tipo de advertência",
        placeholder="ADV1, ADV2, ADV3 ou ADV4",
        required=True,
        max_length=4,
    )

    duracao = discord.ui.TextInput(
        label="Duração em dias (vazio = permanente)",
        placeholder="Ex: 30",
        required=False,
        max_length=5,
    )

    motivo = discord.ui.TextInput(
        label="Motivo",
        placeholder="Descreva o motivo da advertência...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    def __init__(self, cog: "Advertencias"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        aplicador = interaction.user
        guild     = interaction.guild

        # ── Verifica permissão ──────────────────
        if not any(r.id in self.cog.cargos_permitidos for r in aplicador.roles):
            await interaction.followup.send("⛔ Você não tem permissão para aplicar advertências.", ephemeral=True)
            return

        # ── Valida ID do membro ─────────────────
        membro_id_str = self.id_membro.value.strip()
        if not membro_id_str.isdigit():
            await interaction.followup.send("⚠️ ID inválido. Digite apenas números.", ephemeral=True)
            return

        membro = guild.get_member(int(membro_id_str))
        if not membro:
            try:
                membro = await guild.fetch_member(int(membro_id_str))
            except discord.NotFound:
                await interaction.followup.send("⚠️ Membro não encontrado neste servidor.", ephemeral=True)
                return

        # ── Valida tipo ─────────────────────────
        tipo = self.tipo_adv.value.strip().upper()
        if tipo not in self.cog.cargos_advertencia:
            tipos_validos = ", ".join(self.cog.cargos_advertencia.keys())
            await interaction.followup.send(f"⚠️ Tipo inválido. Use: `{tipos_validos}`", ephemeral=True)
            return

        # ── Valida duração ──────────────────────
        duracao_str = self.duracao.value.strip()
        if duracao_str:
            if not duracao_str.isdigit() or int(duracao_str) <= 0:
                await interaction.followup.send("⚠️ Duração inválida. Digite um número inteiro positivo ou deixe em branco.", ephemeral=True)
                return
            duracao_dias = int(duracao_str)
        else:
            duracao_dias = None  # permanente

        motivo_texto = self.motivo.value.strip()
        duracao_label = f"{duracao_dias} dias" if duracao_dias else "Permanente"

        # ── Valida hierarquia ───────────────────
        cargo_id = self.cog.cargos_advertencia[tipo]
        cargo    = guild.get_role(cargo_id)

        if not cargo:
            await interaction.followup.send("⚠️ Cargo de advertência não encontrado. Verifique o ID.", ephemeral=True)
            return

        if cargo.position >= guild.me.top_role.position:
            await interaction.followup.send("⚠️ Esse cargo está acima do meu na hierarquia. Não consigo aplicá-lo.", ephemeral=True)
            return

        if membro.top_role.position >= guild.me.top_role.position:
            await interaction.followup.send("⚠️ Esse membro tem um cargo acima ou igual ao meu. Não posso modificá-lo.", ephemeral=True)
            return

        # ── Remove cargos de advertência anteriores e aplica o novo ────
        cargos_adv_ids = set(self.cog.cargos_advertencia.values())
        cargos_para_remover = [r for r in membro.roles if r.id in cargos_adv_ids and r.id != cargo_id]
        if cargos_para_remover:
            await membro.remove_roles(*cargos_para_remover, reason=f"Substituído por [{tipo}]")

        await membro.add_roles(cargo, reason=f"[{tipo}] {motivo_texto}")

        agora = datetime.now(timezone.utc).strftime("%d/%m/%Y às %H:%M")

        # ── Embed de penalidades (limpo) ────────
        embed_penalidades = discord.Embed(
            title="📄 Advertência Aplicada",
            description=f"<@{membro.id}> recebeu uma advertência do tipo **{tipo}**.",
            color=discord.Color.orange(),
        )
        embed_penalidades.add_field(name="📝 Motivo",    value=motivo_texto,      inline=False)
        embed_penalidades.add_field(name="⏳ Duração",   value=duracao_label,     inline=True)
        embed_penalidades.add_field(name="👤 Aplicador", value=aplicador.mention, inline=True)
        embed_penalidades.set_footer(
            text=f"Ação realizada em {agora}",
            icon_url=aplicador.avatar.url if aplicador.avatar else None,
        )

        # ── Embed de log (detalhado) ────────────
        embed_log = discord.Embed(
            title="📋 Log de Advertência",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        embed_log.add_field(name="👤 Membro advertido", value=f"{membro.mention}\n`{membro.id}`",        inline=True)
        embed_log.add_field(name="🔖 Tipo",             value=tipo,                                      inline=True)
        embed_log.add_field(name="⏳ Duração",          value=duracao_label,                             inline=True)
        embed_log.add_field(name="📝 Motivo",           value=motivo_texto,                              inline=False)
        embed_log.add_field(name="🛡️ Aplicador",       value=f"{aplicador.mention}\n`{aplicador.id}`", inline=True)
        embed_log.add_field(name="📅 Data/Hora",        value=agora,                                     inline=True)
        embed_log.set_thumbnail(url=membro.avatar.url if membro.avatar else None)
        embed_log.set_footer(text=f"Servidor: {guild.name}")

        # ── DM ao membro ────────────────────────
        try:
            await membro.send(
                f"⚠️ Você foi advertido no servidor **{guild.name}**.\n"
                f"**Motivo:** {motivo_texto}\n"
                f"**Tipo:** {tipo}\n"
                f"**Duração:** {duracao_label}\n"
                f"**Aplicador:** {aplicador.display_name}"
            )
        except discord.Forbidden:
            pass  # DM fechada — intencional

        # ── Envia no canal de penalidades ───────
        canal_penalidades = self.cog.bot.get_channel(self.cog.canal_penalidades_id)
        if canal_penalidades:
            await canal_penalidades.send(content=f"<@{membro.id}>", embed=embed_penalidades)
        else:
            await interaction.followup.send("⚠️ Canal de penalidades não encontrado.", ephemeral=True)

        # ── Envia no canal de log ───────────────
        canal_log = self.cog.bot.get_channel(self.cog.canal_log_adv_id)
        if canal_log:
            await canal_log.send(embed=embed_log)

        # ── Confirmação ephemeral ───────────────
        await interaction.followup.send(
            f"✅ Advertência **{tipo}** aplicada a <@{membro.id}> com sucesso.",
            ephemeral=True,
        )


# ──────────────────────────────────────────────
#  VIEW PERSISTENTE — botão no embed
# ──────────────────────────────────────────────
class AdvertenciaView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)  # persistente — sobrevive a restart

    @discord.ui.button(
        label="Aplicar Advertência",
        style=discord.ButtonStyle.danger,
        emoji="📄",
        custom_id="adv_abrir_modal",   # ID fixo obrigatório para views persistentes
    )
    async def abrir_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.cogs.get("Advertencias")
        if not cog:
            await interaction.response.send_message("⚠️ Cog não carregada.", ephemeral=True)
            return

        # Verifica permissão antes de abrir o modal
        if not any(r.id in cog.cargos_permitidos for r in interaction.user.roles):
            await interaction.response.send_message("⛔ Você não tem permissão para usar isso.", ephemeral=True)
            return

        await interaction.response.send_modal(AdvertenciaModal(cog))


# ──────────────────────────────────────────────
#  COG PRINCIPAL
# ──────────────────────────────────────────────
class Advertencias(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot                  = bot
        self.cargos_permitidos    = CARGOS_PERMITIDOS
        self.cargos_advertencia   = CARGOS_ADVERTENCIA
        self.canal_penalidades_id = CANAL_PENALIDADES_ID
        self.canal_log_adv_id     = CANAL_LOG_ADV_ID

    async def cog_load(self):
        """Registra a view persistente no bot ao carregar a cog."""
        self.bot.add_view(AdvertenciaView())

    @app_commands.command(name="setup_advertencia", description="Envia o embed persistente de advertência no canal atual.")
    @app_commands.default_permissions(administrator=True)
    async def setup_advertencia(self, interaction: discord.Interaction):
        """
        Envia o embed persistente de advertência no canal atual.
        Apenas administradores podem executar esse comando.
        """
        embed = discord.Embed(
            title="⚠️ Sistema de Advertências",
            description=(
                "Clique no botão abaixo para abrir o formulário de advertência.\n\n"
                "Preencha os campos corretamente:\n"
                "• **ID Discord** do oficial a ser advertido\n"
                "• **Tipo:** ADV1, ADV2, ADV3 ou ADV4\n"
                "• **Duração** em dias (opcional — permanente se vazio)\n"
                "• **Motivo** da advertência"
            ),
            color=discord.Color.dark_red(),
        )
        embed.set_footer(text="Apenas oficiais autorizados podem aplicar advertências.")

        await interaction.channel.send(embed=embed, view=AdvertenciaView())
        await interaction.response.send_message("Painel de advertência enviado com sucesso!", ephemeral=True)


# ──────────────────────────────────────────────
#  SETUP
# ──────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Advertencias(bot))
