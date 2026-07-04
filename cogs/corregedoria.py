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
import logging

import utils.ui as ui

logger = logging.getLogger("bot.corregedoria")

# ─────────────────────────────────────────────
# CONFIGURAÇÃO — Altere os IDs aqui
# ─────────────────────────────────────────────

LOG_CHANNEL_ID       = 1519099991266955301   # Canal de logs
TICKET_CATEGORY_ID   = 1519099992755671141   # Categoria onde os tickets são criados
CORREGEDORIA_ROLE_ID = 1519099990608187596   # Cargo de Corregedoria (preencha)

# ─────────────────────────────────────────────
# HELPER: Verificação de permissão de staff
# ─────────────────────────────────────────────

def é_staff(member: discord.Member) -> bool:
    """Verifica se o membro pertence à equipe (admin/manage_channels/role)."""
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
        f"**Autor:** {autor.mention}\n**Alvo:** {membro.mention}"
        if membro
        else f"**Autor:** {autor.mention}"
    )

    embed = ui.build_embed(
        title=f"📋 | Log de {acao}",
        description=descricao,
        color=ui.UI_COLOR_MAIN
    )
    
    if moderador:
        embed.add_field(name="👤 Moderador", value=moderador, inline=True)
        
    embed.add_field(name="🕒 Horário", value=hora, inline=True)
    
    if extras:
        for k, v in extras.items():
            if v: # Only add if there is content
                # Format to a code block if text is too long or multiline
                embed.add_field(name=f"📌 {k}", value=f"```\n{v}\n```" if len(v) > 20 else v, inline=False)

    embed.set_footer(text=f"{ui.FOOTER_TEXT} • ID do Usuário: {autor.id}", icon_url=autor.display_avatar.url)
    await canal_logs.send(embed=embed)

# ─────────────────────────────────────────────
# HELPER: Gerar transcript HTML e distribuir
# ─────────────────────────────────────────────

async def gerar_e_enviar_transcript(bot, canal, criador: discord.Member):
    """Gera transcript HTML do canal usando chat_exporter."""
    try:
        import chat_exporter
        import io

        # LIMITE: exporta no máximo 500 mensagens para evitar picos de memória
        transcript = await chat_exporter.export(canal, limit=500)
        if not transcript:
            logger.warning(f"Transcript vazio para canal {canal.name}")
            return

        arquivo = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f"transcript-{canal.name}.html"
        )

        embed_transcript = ui.build_embed(
            title="📄 | Transcript do Atendimento",
            description=f"O ticket **{canal.name}** foi encerrado.\nO histórico completo das mensagens está anexado abaixo.",
            color=ui.UI_COLOR_MAIN
        )
        embed_transcript.set_footer(text=f"{ui.FOOTER_TEXT} • Corregedoria — Sistema de Tickets")

        enviado_dm = False
        try:
            if criador:
                await criador.send(embed=embed_transcript, file=arquivo)
                enviado_dm = True
        except discord.Forbidden:
            logger.info(f"DM fechada para {criador} — transcript será enviado ao canal de logs.")

        if not enviado_dm:
            canal_logs = bot.get_channel(LOG_CHANNEL_ID)
            if canal_logs:
                arquivo_log = discord.File(
                    io.BytesIO(transcript.encode()),
                    filename=f"transcript-{canal.name}.html"
                )
                embed_log = ui.build_embed(
                    title="⚠️ | Transcript Retido (DM Fechada)",
                    description=f"Não foi possível enviar o histórico por DM para {criador.mention if criador else 'Usuário Desconhecido'}.",
                    color=ui.UI_COLOR_WARNING
                )
                await canal_logs.send(embed=embed_log, file=arquivo_log)

        # Libera a referência do transcript imediatamente para aliviar memória
        del transcript

    except ImportError:
        logger.warning("`chat_exporter` não está instalado.")
        canal_logs = bot.get_channel(LOG_CHANNEL_ID)
        if canal_logs:
            await canal_logs.send(
                "⚠️ `chat_exporter` não está instalado. Instale com `pip install chat-exporter` para habilitar transcrição de tickets."
            )
    except Exception as e:
        logger.error(f"Erro ao gerar transcript para {canal.name}: {e}", exc_info=True)

# ─────────────────────────────────────────────
# MODAL: Encerramento de ticket
# ─────────────────────────────────────────────

class ModalFecharTicket(discord.ui.Modal, title="🔒 Encerramento de Ticket"):
    def __init__(self, bot, criador: discord.Member):
        super().__init__()
        self.bot = bot
        self.criador = criador

    motivo = discord.ui.TextInput(
        label="Motivo do Encerramento",
        placeholder="Descreva brevemente o porquê do ticket estar sendo fechado...",
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    veredito = discord.ui.TextInput(
        label="Veredito Final",
        placeholder="Ex: Deferido / Indeferido / Resolvido",
        style=discord.TextStyle.short,
        required=True
    )
    
    punicao = discord.ui.TextInput(
        label="Houve aplicação de punição?",
        placeholder="Ex: Sim (1 advertência) / Não",
        style=discord.TextStyle.short,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await gerar_e_enviar_transcript(self.bot, interaction.channel, self.criador)

            await gerar_log(
                self.bot,
                interaction.user,
                "Encerramento de Ticket",
                moderador=interaction.user.name,
                extras={
                    "Motivo":         str(self.motivo.value).strip(),
                    "Veredito":       str(self.veredito.value).strip(),
                    "Houve Punição":  str(self.punicao.value).strip() if self.punicao.value else "Não informado"
                }
            )
            await interaction.channel.delete()
        except Exception as e:
            await interaction.followup.send(
                embed=ui.build_error_embed(f"Ocorreu um erro ao encerrar o ticket: `{e}`"),
                ephemeral=True
            )

# ─────────────────────────────────────────────
# MODAL: Pokar membro
# ─────────────────────────────────────────────

class PokeModal(discord.ui.Modal, title="👉 Convocar Membro"):
    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    membro_id = discord.ui.TextInput(
        label="ID do Usuário",
        placeholder="Cole o ID numérico do usuário (ex: 123456789012345678)",
        style=discord.TextStyle.short,
        min_length=17,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            membro_id_val = int(self.membro_id.value.strip())
        except ValueError:
            return await interaction.response.send_message(embed=ui.build_error_embed("O ID fornecido é inválido. Certifique-se de inserir apenas números."), ephemeral=True)

        membro = self.channel.guild.get_member(membro_id_val)
        if not membro:
            try:
                membro = await self.channel.guild.fetch_member(membro_id_val)
            except discord.NotFound:
                return await interaction.response.send_message(embed=ui.build_error_embed("Membro não encontrado no servidor."), ephemeral=True)

        await self.channel.set_permissions(membro, view_channel=True, send_messages=True)

        embed_dm = ui.build_embed(
            title="🔔 | Convocação em Atendimento",
            description="Você foi convocado pela equipe da Corregedoria em um ticket de atendimento.\n\nPor favor, clique no botão abaixo para acessar o canal.",
            color=ui.UI_COLOR_MAIN
        )
        view_link = discord.ui.View()
        view_link.add_item(
            discord.ui.Button(label="Acessar Ticket", url=self.channel.jump_url, style=discord.ButtonStyle.link)
        )
        try:
            await membro.send(embed=embed_dm, view=view_link)
        except discord.Forbidden:
            pass

        await gerar_log(self.bot, interaction.user, "Convocação", membro=membro, moderador=interaction.user.name)
        await interaction.response.send_message(embed=ui.build_success_embed(f"O membro {membro.mention} foi adicionado ao ticket e notificado!"), ephemeral=True)

# ─────────────────────────────────────────────
# MODAL: Abertura de ticket (novo)
# ─────────────────────────────────────────────

class ModalAbrirTicket(discord.ui.Modal, title="📝 Abertura de Ticket"):
    def __init__(self, bot, tipo: str):
        super().__init__()
        self.bot  = bot
        self.tipo = tipo

    relato = discord.ui.TextInput(
        label="Descreva o ocorrido detalhadamente",
        placeholder="Forneça o máximo de detalhes possível para agilizar seu atendimento...",
        style=discord.TextStyle.paragraph,
        min_length=10,
        max_length=1500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        guild    = interaction.guild
        usuario  = interaction.user
        categoria = guild.get_channel(TICKET_CATEGORY_ID)

        if categoria:
            for canal in categoria.text_channels:
                if canal.topic and f"ticket:{usuario.id}" in canal.topic:
                    return await interaction.followup.send(
                        embed=ui.build_warn_embed(f"Você já possui um ticket em aberto em {canal.mention}. Por favor, encerre-o antes de abrir um novo."),
                        ephemeral=True
                    )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            usuario:            discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_permissions=True),
        }

        role_corregedoria = guild.get_role(CORREGEDORIA_ROLE_ID)
        if role_corregedoria:
            overwrites[role_corregedoria] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)

        nome_canal = f"🎟️・{usuario.name}"
        canal = await guild.create_text_channel(
            name=nome_canal,
            category=categoria,
            overwrites=overwrites,
            topic=f"ticket:{usuario.id} | Tipo: {self.tipo}"
        )

        embed_ticket = ui.build_embed(
            title="🚨 | Central de Atendimento",
            description="Olá! A equipe da Corregedoria analisará o seu caso em breve. Enquanto isso, sinta-se à vontade para enviar quaisquer provas ou informações adicionais.",
            color=ui.UI_COLOR_MAIN
        )
        embed_ticket.add_field(name="👤 Solicitante", value=usuario.mention, inline=True)
        embed_ticket.add_field(name="📂 Categoria", value=f"`{self.tipo}`", inline=True)
        embed_ticket.add_field(name="📝 Relato Inicial", value=f"```\n{str(self.relato.value)}\n```", inline=False)
        embed_ticket.set_footer(text=f"{ui.FOOTER_TEXT} • Aberto em {datetime.datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        if guild.icon:
            embed_ticket.set_thumbnail(url=guild.icon.url)

        await canal.send(
            content=f"{usuario.mention} | <@&{CORREGEDORIA_ROLE_ID}>",
            embed=embed_ticket,
            view=TicketView(self.bot, usuario)
        )

        await gerar_log(self.bot, usuario, "Abertura de Ticket", extras={"Categoria": self.tipo})
        await interaction.followup.send(embed=ui.build_success_embed(f"**Ticket criado com sucesso!** Acesse: {canal.mention}"), ephemeral=True)

# ─────────────────────────────────────────────
# VIEW: Botões de controle do ticket
# ─────────────────────────────────────────────

class TicketView(discord.ui.View):
    def __init__(self, bot, autor):
        super().__init__(timeout=None)
        self.bot   = bot
        self.autor = autor

    @discord.ui.button(label="Solicitar Atendimento", emoji="🛎️", style=discord.ButtonStyle.success, custom_id="verde_solicitar")
    async def solicitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.autor and interaction.user != self.autor:
            # Caso persistente, podemos usar o topic para verificar
            criador_id = None
            if interaction.channel.topic and "ticket:" in interaction.channel.topic:
                try:
                    criador_id = int(interaction.channel.topic.split("ticket:")[1].split(" ")[0])
                except Exception:
                    pass
            if criador_id and interaction.user.id != criador_id:
                return await interaction.response.send_message(embed=ui.build_error_embed("Você não é o autor deste ticket."), ephemeral=True)
                
        await gerar_log(self.bot, interaction.user, "Solicitação de Atendimento (Ping)")
        await interaction.response.send_message(embed=ui.build_success_embed("Atendimento solicitado. A equipe foi notificada novamente."), ephemeral=True)
        
        role = interaction.guild.get_role(CORREGEDORIA_ROLE_ID)
        if role:
            await interaction.channel.send(f"{role.mention}, o usuário {interaction.user.mention} está solicitando atenção no ticket.")

    @discord.ui.button(label="Assumir Ticket", emoji="📌", style=discord.ButtonStyle.primary, custom_id="cinza_assumir")
    async def assumir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not é_staff(interaction.user):
            return await interaction.response.send_message(embed=ui.build_error_embed("Apenas a equipe da corregedoria pode assumir tickets."), ephemeral=True)

        topic = interaction.channel.topic or ""
        
        # Evita renomear múltiplas vezes se já não for um ticket recém-aberto
        if "🎟️" not in interaction.channel.name:
            return await interaction.response.send_message(embed=ui.build_warn_embed("Este ticket já foi assumido ou renomeado."), ephemeral=True)
            
        apelido = interaction.user.display_name.lower().replace(" ", "-")
        
        # Mapeamento do tipo de ticket para o emoji correto
        prefixo = "🛡️" # Padrão
        
        if "Denúncia contra oficial" in topic or "Registrar abuso policial contra policial" in topic or "Denúncia de oficial contra oficial" in topic:
            prefixo = "🚫"
        elif "Revisão de advertência" in topic or "Reversão de punição" in topic:
            prefixo = "🧾"
        elif "Suporte" in topic:
            prefixo = "❓"
        elif "Ticket de corregedoria" in topic or "Corregedoria" in topic:
            prefixo = "🛡️"
            
        novo_nome = f"{prefixo}・{apelido}"
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await interaction.channel.edit(name=novo_nome)
        except discord.Forbidden:
            return await interaction.followup.send(embed=ui.build_error_embed("Sem permissão para renomear o canal."), ephemeral=True)
        except discord.HTTPException:
            pass # Rate limit

        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == "cinza_assumir":
                item.label = f"Assumido por {interaction.user.display_name}"
                item.style = discord.ButtonStyle.secondary
                item.disabled = True
                break
                
        await interaction.message.edit(view=self)

        await gerar_log(self.bot, interaction.user, "Ticket Assumido", extras={"Novo Nome do Canal": novo_nome})
        await interaction.followup.send(embed=ui.build_success_embed("Ticket assumido com sucesso!"), ephemeral=True)

    @discord.ui.button(label="Pokar Membro", emoji="👉", style=discord.ButtonStyle.secondary, custom_id="cinza_poke")
    async def pokar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not é_staff(interaction.user):
            return await interaction.response.send_message(embed=ui.build_error_embed("Apenas a equipe pode usar este comando."), ephemeral=True)
        await interaction.response.send_modal(PokeModal(self.bot, interaction.channel))

    @discord.ui.button(label="Encerrar Ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="vermelho_fechar")
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not é_staff(interaction.user):
            return await interaction.response.send_message(embed=ui.build_error_embed("Apenas a equipe pode encerrar tickets."), ephemeral=True)

        criador = None
        if interaction.channel.topic and "ticket:" in interaction.channel.topic:
            try:
                uid = int(interaction.channel.topic.split("ticket:")[1].split(" ")[0])
                criador = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
            except Exception:
                pass

        await interaction.response.send_modal(ModalFecharTicket(self.bot, criador))

# ─────────────────────────────────────────────
# SELECT: Seleção de categoria do ticket (setup)
# ─────────────────────────────────────────────

class CategoriaSetupSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Ticket de corregedoria",
                description="Denúncias gerais e ocorrências internas",
                emoji="🛡️",
                value="corregedoria"
            ),
            discord.SelectOption(
                label="Denúncia de oficial contra oficial",
                description="Registrar abusos e infrações de oficiais",
                emoji="🚫",
                value="denuncia_oficial"
            ),
            discord.SelectOption(
                label="Reversão de punição",
                description="Contestar advertências ou punições aplicadas",
                emoji="🧾",
                value="revisao"
            ),
            discord.SelectOption(
                label="Suporte",
                description="Dúvidas e solicitações gerais à equipe",
                emoji="🎧",
                value="suporte"
            ),
            discord.SelectOption(
                label="Cancelar",
                description="Resetar escolha atual",
                emoji="❌",
                value="resetar"
            ),
        ]
        super().__init__(
            placeholder="Selecione o tipo de atendimento que deseja...",
            options=options,
            custom_id="setup_categoria_select"
        )

    async def callback(self, interaction: discord.Interaction):
        valor = self.values[0]

        if valor == "resetar":
            return await interaction.response.send_message(
                embed=ui.build_success_embed("Ação cancelada. O menu foi resetado para você."),
                ephemeral=True
            )

        labels = {
            "corregedoria": "Ticket de corregedoria",
            "denuncia_oficial": "Denúncia de oficial contra oficial",
            "suporte": "Suporte",
            "revisao": "Reversão de punição",
        }
        tipo = labels.get(valor, valor)

        await interaction.response.send_modal(ModalAbrirTicket(self.bot, tipo))


class SetupView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(CategoriaSetupSelect(bot))


# ─────────────────────────────────────────────
# SELECT: Legado — mantido para compatibilidade
# ─────────────────────────────────────────────

class CategoriaSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Ticket de corregedoria",
                description="Denúncias gerais e ocorrências internas",
                emoji="🛡️"
            ),
            discord.SelectOption(
                label="Denúncia de oficial contra oficial",
                description="Registrar abusos e infrações de oficiais",
                emoji="🚫"
            ),
            discord.SelectOption(
                label="Reversão de punição",
                description="Contestar advertências ou punições aplicadas",
                emoji="🧾"
            ),
        ]
        super().__init__(
            placeholder="Selecione a categoria desejada...",
            options=options,
            custom_id="menu_ocorrencia"
        )

    async def callback(self, interaction: discord.Interaction):
        tipo = self.values[0]
        await interaction.response.send_modal(ModalAbrirTicket(self.bot, tipo))


class CategoriaView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(CategoriaSelect(bot))


# ─────────────────────────────────────────────
# COG PRINCIPAL
# ─────────────────────────────────────────────

class Corregedoria(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(SetupView(self.bot))
        self.bot.add_view(CategoriaView(self.bot))
        self.bot.add_view(TicketView(self.bot, autor=None))

    @app_commands.command(name="setup_corregedoria", description="Envia o painel de atendimento (tickets) da corregedoria.")
    @app_commands.default_permissions(administrator=True)
    async def setup_corregedoria(self, interaction: discord.Interaction):
        embed = ui.build_embed(
            title="⚖️ | Central de Atendimento — Corregedoria",
            description=(
                "Bem-vindo(a) à Central de Atendimento.\n\n"
                "Para agilizar seu suporte, selecione a opção que melhor se encaixa na sua necessidade no menu abaixo.\n\n"
                "**Categorias Disponíveis:**\n"
                "🛡️ **Ticket de Corregedoria** — Denúncias e ocorrências internas\n"
                "🚫 **Denúncia de Oficial** — Abuso policial ou infrações entre oficiais\n"
                "🧾 **Reversão de Punição** — Contestações de advertências\n"
                "🎧 **Suporte** — Dúvidas e solicitações gerais"
            ),
            color=ui.UI_COLOR_MAIN
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"{ui.FOOTER_TEXT} • Selecione uma categoria para iniciar o atendimento")
        
        await interaction.channel.send(embed=embed, view=SetupView(self.bot))
        await interaction.response.send_message(embed=ui.build_success_embed("Painel de corregedoria configurado com sucesso!"), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Corregedoria(bot))