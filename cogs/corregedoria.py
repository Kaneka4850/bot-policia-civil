"""
corregedoria.py — Cog de Corregedoria para Discord.py 2.x
Funcionalidades:
  - Setup persistente com Select de categorias
  - Modal obrigatório ao abrir ticket
  - Controle de duplicidade (1 ticket por usuário)
  - Permissões configuráveis por cargo
  - Botões de controle de ticket (Solicitar, Assumir, Fechar, Pokar)
  - Transcript HTML ao fechar ticket (via chat_exporter)
  - Log estruturado em canal dedicado
"""

import discord
from discord.ext import commands
from discord import app_commands
import datetime

# ─────────────────────────────────────────────
# CONFIGURAÇÃO — Altere os IDs aqui
# ─────────────────────────────────────────────

LOG_CHANNEL_ID       = 1404103397195518053   # Canal de logs
TICKET_CATEGORY_ID   = 1497594352212508843   # Categoria onde os tickets são criados
CORREGEDORIA_ROLE_ID = 1470812693484142796   # Cargo de Corregedoria (preencha)


# ─────────────────────────────────────────────
# HELPER: Verificação de permissão de staff
# ─────────────────────────────────────────────

def é_staff(member: discord.Member) -> bool:
    """
    Retorna True se o membro pode operar botões de staff.
    Critérios (qualquer um satisfaz):
      - Permissão administrator no servidor
      - Permissão manage_channels no servidor
      - Possui o cargo CORREGEDORIA_ROLE_ID
    """
    perms = member.guild_permissions
    if perms.administrator or perms.manage_channels:
        return True
    if CORREGEDORIA_ROLE_ID and any(r.id == CORREGEDORIA_ROLE_ID for r in member.roles):
        return True
    return False


# ─────────────────────────────────────────────
# HELPER: Geração de log
# ─────────────────────────────────────────────

async def gerar_log(bot, autor, acao: str, membro=None, moderador=None, extras: dict = None):
    """Envia um embed de log no canal configurado."""
    canal_logs = bot.get_channel(LOG_CHANNEL_ID)
    if not canal_logs:
        return

    hora = discord.utils.format_dt(datetime.datetime.now(), style='F')
    descricao = (
        f"{autor.mention} {acao.lower()} {membro.mention}"
        if membro
        else f"{autor.mention} executou: {acao}"
    )

    embed = discord.Embed(
        title=f"📋 Log de {acao}",
        description=descricao,
        color=discord.Color.dark_purple()
    )
    embed.add_field(name="🕒 Horário", value=hora)
    if moderador:
        embed.add_field(name="👤 Moderador", value=moderador)
    if extras:
        for k, v in extras.items():
            embed.add_field(name=k, value=v, inline=False)

    embed.set_footer(text=f"Ação feita por: {autor}", icon_url=autor.display_avatar.url)
    await canal_logs.send(embed=embed)


# ─────────────────────────────────────────────
# HELPER: Gerar transcript HTML e distribuir
# ─────────────────────────────────────────────

async def gerar_e_enviar_transcript(bot, canal, criador: discord.Member):
    """
    Gera transcript HTML do canal usando chat_exporter.
    Tenta enviar por DM ao criador; em caso de falha, envia no canal de logs.
    Requer: pip install chat-exporter
    """
    try:
        import chat_exporter
        import io

        transcript = await chat_exporter.export(canal)
        if not transcript:
            return

        arquivo = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f"transcript-{canal.name}.html"
        )

        embed_transcript = discord.Embed(
            title="📄 Transcript do Ticket",
            description=f"Seu ticket **{canal.name}** foi encerrado. Segue o transcript.",
            color=discord.Color.greyple()
        )

        enviado_dm = False
        try:
            await criador.send(embed=embed_transcript, file=arquivo)
            enviado_dm = True
        except discord.Forbidden:
            pass

        # Se DM falhou, envia no canal de logs
        if not enviado_dm:
            canal_logs = bot.get_channel(LOG_CHANNEL_ID)
            if canal_logs:
                # Recria o arquivo (o anterior foi consumido)
                arquivo_log = discord.File(
                    io.BytesIO(transcript.encode()),
                    filename=f"transcript-{canal.name}.html"
                )
                embed_log = discord.Embed(
                    title="📄 Transcript (DM bloqueada)",
                    description=f"Não foi possível enviar transcript por DM para {criador.mention}.",
                    color=discord.Color.orange()
                )
                await canal_logs.send(embed=embed_log, file=arquivo_log)

    except ImportError:
        # chat_exporter não instalado — registra aviso no log
        canal_logs = bot.get_channel(LOG_CHANNEL_ID)
        if canal_logs:
            await canal_logs.send(
                "⚠️ `chat_exporter` não está instalado. Instale com `pip install chat-exporter` para habilitar transcrição de tickets."
            )


# ─────────────────────────────────────────────
# MODAL: Encerramento de ticket
# ─────────────────────────────────────────────

class ModalFecharTicket(discord.ui.Modal, title="Encerramento de Ticket"):
    """Modal preenchido pelo staff ao encerrar um ticket."""

    def __init__(self, bot, criador: discord.Member):
        super().__init__()
        self.bot = bot
        self.criador = criador  # Membro que abriu o ticket (para envio do transcript)

    motivo   = discord.ui.TextInput(label="Motivo",           style=discord.TextStyle.paragraph)
    veredito = discord.ui.TextInput(label="Veredito",         placeholder="Deferido / Indeferido",   style=discord.TextStyle.short)
    punicao  = discord.ui.TextInput(label="Houve punição?",   placeholder="Sim / Não / Em análise",  style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ Encerrando ticket e gerando transcript...", ephemeral=True)

        # Gera e distribui transcript antes de deletar o canal
        await gerar_e_enviar_transcript(self.bot, interaction.channel, self.criador)

        await gerar_log(
            self.bot,
            interaction.user,
            "Encerramento de Ticket",
            moderador=interaction.user.name,
            extras={
                "Motivo":         str(self.motivo),
                "Veredito":       str(self.veredito),
                "Houve Punição":  str(self.punicao)
            }
        )
        await interaction.channel.delete()


# ─────────────────────────────────────────────
# MODAL: Pokar membro
# ─────────────────────────────────────────────

class PokeModal(discord.ui.Modal, title="Pokar Membro"):
    """Modal para convocar um membro ao ticket via ID."""

    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    membro_id = discord.ui.TextInput(
        label="ID do Membro",
        placeholder="Insira o ID válido",
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            membro_id = int(self.membro_id.value)
        except ValueError:
            return await interaction.response.send_message("❌ ID inválido.", ephemeral=True)

        membro = self.channel.guild.get_member(membro_id)
        if membro is None:
            try:
                membro = await self.channel.guild.fetch_member(membro_id)
            except discord.NotFound:
                return await interaction.response.send_message("❌ Membro não encontrado.", ephemeral=True)

        await self.channel.set_permissions(membro, view_channel=True, send_messages=True)

        embed_dm = discord.Embed(
            title="📌 Você foi pokado em um ticket de corregedoria",
            description="Para verificar o ticket, clique no botão abaixo.",
            color=discord.Color.blue()
        )
        view_link = discord.ui.View()
        view_link.add_item(
            discord.ui.Button(label="Abrir Ticket", url=self.channel.jump_url, style=discord.ButtonStyle.link)
        )
        try:
            await membro.send(embed=embed_dm, view=view_link)
        except discord.Forbidden:
            pass  # DM bloqueada — sem ação adicional necessária

        await gerar_log(self.bot, interaction.user, "Convocação", membro=membro, moderador=interaction.user.name)
        await interaction.response.send_message(f"✅ {membro.mention} foi pokado!", ephemeral=True)


# ─────────────────────────────────────────────
# MODAL: Abertura de ticket (novo)
# ─────────────────────────────────────────────

class ModalAbrirTicket(discord.ui.Modal, title="Abertura de Ticket"):
    """Modal exibido ao usuário ao selecionar categoria. Coleta o relato inicial."""

    def __init__(self, bot, tipo: str):
        super().__init__()
        self.bot  = bot
        self.tipo = tipo

    relato = discord.ui.TextInput(
        label="Explique resumidamente o ocorrido",
        style=discord.TextStyle.paragraph,
        min_length=10,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild    = interaction.guild
        usuario  = interaction.user
        categoria = guild.get_channel(TICKET_CATEGORY_ID)

        # ── Controle de duplicidade ──────────────────
        # Verifica se o usuário já possui um ticket aberto dentro da categoria
        if categoria:
            for canal in categoria.text_channels:
                if canal.topic and f"ticket:{usuario.id}" in canal.topic:
                    return await interaction.response.send_message(
                        f"⚠️ Você já possui um ticket aberto: {canal.mention}. Encerre-o antes de abrir outro.",
                        ephemeral=True
                    )

        # ── Monta os overwrites de permissão ────────
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            usuario:            discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        # Cargo de Corregedoria — acesso explícito pois pode não ter manage_channels
        role_corregedoria = guild.get_role(CORREGEDORIA_ROLE_ID)
        if role_corregedoria:
            overwrites[role_corregedoria] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        # Membros com administrator/manage_channels já herdam acesso via permissões de servidor;
        # não é necessário overwrite explícito para eles.

        # ── Cria o canal de ticket ───────────────────
        canal = await guild.create_text_channel(
            name=f"corregedoria-{usuario.name}",
            category=categoria,
            overwrites=overwrites,
            topic=f"ticket:{usuario.id} | Tipo: {self.tipo}"  # Usado no controle de duplicidade
        )

        # ── Embed inicial com relato ─────────────────
        embed_ticket = discord.Embed(
            title=f"📝 Ticket — {self.tipo}",
            description=(
                f"**Solicitante:** {usuario.mention}\n"
                f"**Categoria:** {self.tipo}\n\n"
                f"**Relato inicial:**\n{str(self.relato)}"
            ),
            color=discord.Color.blurple()
        )
        embed_ticket.set_footer(text=f"Aberto em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")

        # ── Envia embed + botões de controle ─────────
        await canal.send(
            content=f"{usuario.mention}",
            embed=embed_ticket,
            view=TicketView(self.bot, usuario)
        )

        await gerar_log(self.bot, usuario, "Abertura de Ticket", extras={"Categoria": self.tipo})
        await interaction.response.send_message(f"✅ Ticket criado: {canal.mention}", ephemeral=True)


# ─────────────────────────────────────────────
# VIEW: Botões de controle do ticket
# ─────────────────────────────────────────────

class TicketView(discord.ui.View):
    """
    View persistente com os botões de controle do ticket.
    Preserva integralmente a lógica original dos botões.
    """

    def __init__(self, bot, autor):
        super().__init__(timeout=None)
        self.bot   = bot
        self.autor = autor

    @discord.ui.button(label="Solicitar Atendimento", style=discord.ButtonStyle.success, custom_id="verde_solicitar")
    async def solicitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.autor:
            return await interaction.response.send_message("⛔ Você não é o autor deste ticket.", ephemeral=True)
        await gerar_log(self.bot, interaction.user, "Solicitação de Atendimento")
        await interaction.response.send_message("✅ Atendimento solicitado.", ephemeral=True)

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, custom_id="vermelho_fechar")
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not é_staff(interaction.user):
            return await interaction.response.send_message("⛔ Apenas staff pode encerrar.", ephemeral=True)

        # Tenta identificar o criador do ticket via topic do canal
        criador = None
        if interaction.channel.topic and "ticket:" in interaction.channel.topic:
            try:
                uid = int(interaction.channel.topic.split("ticket:")[1].split(" ")[0])
                criador = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
            except Exception:
                pass

        await interaction.response.send_modal(ModalFecharTicket(self.bot, criador))

    @discord.ui.button(label="Assumir Ticket", style=discord.ButtonStyle.secondary, custom_id="cinza_assumir")
    async def assumir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not é_staff(interaction.user):
            return await interaction.response.send_message("⛔ Você não tem permissão.", ephemeral=True)

        apelido = interaction.user.display_name
        await interaction.channel.edit(name=f"corregedoria-{apelido}")

        # Atualiza label do botão para refletir responsável atual
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == "cinza_assumir":
                item.label = f"Assumido por {apelido}"
                break
        await interaction.message.edit(view=self)

        await gerar_log(self.bot, interaction.user, "Assumiu Ticket")
        await interaction.response.send_message("📌 Ticket assumido!", ephemeral=True)

    @discord.ui.button(label="Pokar Membro", style=discord.ButtonStyle.secondary, custom_id="cinza_poke")
    async def pokar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not é_staff(interaction.user):
            return await interaction.response.send_message("⛔ Apenas staff pode usar.", ephemeral=True)
        await interaction.response.send_modal(PokeModal(self.bot, interaction.channel))


# ─────────────────────────────────────────────
# SELECT: Seleção de categoria do ticket (setup)
# ─────────────────────────────────────────────

class CategoriaSetupSelect(discord.ui.Select):
    """
    Select persistente enviado pelo comando !setup_corregedoria.
    Opções: Ticket de corregedoria, Suporte, Revisão de advertência, Resetar escolha.
    """

    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Ticket de corregedoria",
                description="Abrir um ticket de corregedoria",
                emoji="🛡️",
                value="corregedoria"
            ),
            discord.SelectOption(
                label="Suporte",
                description="Solicitar atendimento de suporte",
                emoji="🎧",
                value="suporte"
            ),
            discord.SelectOption(
                label="Revisão de advertência",
                description="Contestar advertência aplicada",
                emoji="🧾",
                value="revisao"
            ),
            discord.SelectOption(
                label="Resetar escolha",
                description="Cancelar a seleção atual",
                emoji="🔄",
                value="resetar"
            ),
        ]
        super().__init__(
            placeholder="Escolha o tipo de atendimento",
            options=options,
            custom_id="setup_categoria_select"  # custom_id fixo para persistência
        )

    async def callback(self, interaction: discord.Interaction):
        valor = self.values[0]

        # Resetar: apenas confirma sem abrir ticket
        if valor == "resetar":
            return await interaction.response.send_message(
                "🔄 Escolha resetada. Selecione uma categoria novamente quando quiser.",
                ephemeral=True
            )

        # Mapeia valor → label legível
        labels = {
            "corregedoria": "Ticket de corregedoria",
            "suporte":      "Suporte",
            "revisao":      "Revisão de advertência",
        }
        tipo = labels.get(valor, valor)

        # Abre modal de relato antes de criar o ticket
        await interaction.response.send_modal(ModalAbrirTicket(self.bot, tipo))


class SetupView(discord.ui.View):
    """View persistente do embed de setup."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(CategoriaSetupSelect(bot))


# ─────────────────────────────────────────────
# SELECT: Legado — mantido para compatibilidade
# ─────────────────────────────────────────────

class CategoriaSelect(discord.ui.Select):
    """
    Select legado (comando !corregedoria).
    Mantido para compatibilidade com fluxo anterior.
    Redireciona para o modal de relato como o novo fluxo.
    """

    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Denúncia contra oficial",                   description="Má conduta policial ou quebra de procedimento",         emoji="🛡️"),
            discord.SelectOption(label="Revisão de advertência",                     description="Contestar advertência aplicada",                         emoji="🧾"),
            discord.SelectOption(label="Registrar abuso policial contra policial",   description="Usado em caso de abuso de oficial contra oficial",        emoji="🚫"),
            discord.SelectOption(label="Solicitação de pacificação",                 description="Solicitar pacificação contra facção",                    emoji="🎯"),
        ]
        super().__init__(placeholder="Escolha o tipo de ocorrência", options=options, custom_id="menu_ocorrencia")

    async def callback(self, interaction: discord.Interaction):
        tipo = self.values[0]
        await interaction.response.send_modal(ModalAbrirTicket(self.bot, tipo))


class CategoriaView(discord.ui.View):
    """View legada usada pelo comando !corregedoria."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(CategoriaSelect(bot))


# ─────────────────────────────────────────────
# COG PRINCIPAL
# ─────────────────────────────────────────────

class Corregedoria(commands.Cog):
    """Cog de Corregedoria — sistema de tickets com controle completo."""

    def __init__(self, bot):
        self.bot = bot

    # ── Registra as views persistentes ao carregar a Cog ──
    async def cog_load(self):
        """Registra as Persistent Views para que funcionem após restart."""
        self.bot.add_view(SetupView(self.bot))
        self.bot.add_view(CategoriaView(self.bot))
        self.bot.add_view(TicketView(self.bot, autor=None))  # autor=None pois é reconstruída por interação

    # ── Comando legado ──
    @app_commands.command(name="corregedoria", description="Envia o embed de abertura de ticket no modo legado.")
    async def corregedoria_cmd(self, interaction: discord.Interaction):
        """Envia o embed de abertura de ticket no modo legado."""
        embed = discord.Embed(
            title="🚨 Abrir Ticket de Corregedoria",
            description="Selecione abaixo o tipo de ocorrência a ser registrada.",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed, view=CategoriaView(self.bot))
        await interaction.response.send_message("Menu de corregedoria enviado!", ephemeral=True)

    # ── Comando de setup ──
    @app_commands.command(name="setup_corregedoria", description="Envia o embed persistente de abertura de tickets (novo sistema).")
    @app_commands.default_permissions(administrator=True)
    async def setup_corregedoria(self, interaction: discord.Interaction):
        """
        Envia o embed persistente de abertura de tickets (novo sistema).
        Requer permissão de administrador.
        """
        embed = discord.Embed(
            title="📋 Central de Atendimento — Corregedoria",
            description=(
                "Utilize o menu abaixo para abrir um ticket.\n\n"
                "• **Ticket de corregedoria** — Denúncias e ocorrências internas\n"
                "• **Suporte** — Dúvidas e solicitações gerais\n"
                "• **Revisão de advertência** — Contestar advertências aplicadas\n"
                "• **Resetar escolha** — Cancela a seleção atual"
            ),
            color=discord.Color.dark_red()
        )
        embed.set_footer(text="Selecione uma categoria para iniciar")
        await interaction.channel.send(embed=embed, view=SetupView(self.bot))
        await interaction.response.send_message("Painel de corregedoria enviado com sucesso!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Corregedoria(bot))