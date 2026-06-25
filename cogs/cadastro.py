import discord
from discord.ext import commands
from discord import app_commands
import re

# 🧩 Serviços e utilitários
from services.membro_service import (
    adicionar_registro,
    aprovar_registro,
    listar_registros_aprovados,
    remover_registro,
    buscar_registro_por_discord_id
)
from utils.logger import log_event
from utils.permissao import is_admin

# 🔧 IDs e configuração
Cargos_aprovadores = [] # Lista de cargos que podem recrutar
Cargo_membro = # Cargo policia civil
Canal_logs = # Cargos logs
canal_aprovacao =# Canal de aprovação


# 🔹 Função para enviar logs e embeds
async def enviar_log(guild, mensagem=None, view=None, embed=None):
    canal = guild.get_channel(Canal_logs)
    if canal:
        if embed:
            await canal.send(embed=embed)
        else:
            await canal.send(mensagem, view=view)


# 🟢 View Persistente de Aprovação
class AprovacaoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Timeout=None a torna persistente

    async def verificar_permissao(self, interaction: discord.Interaction):
        aprovador = interaction.user
        if not is_admin(aprovador) and not any(r.id in Cargos_aprovadores for r in aprovador.roles):
            await interaction.response.send_message("❌ Sem permissão para interagir com este registro.", ephemeral=True)
            return False
        return True

    def extrair_id_usuario(self, interaction: discord.Interaction):
        # Extrai o ID do usuário do rodapé (footer) do embed
        embed = interaction.message.embeds[0]
        footer_text = embed.footer.text
        # Pega apenas os números do texto do footer "ID do Usuário: 123456789"
        return int(re.search(r'\d+', footer_text).group())

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.green, custom_id="btn_aprovar_registro", emoji="✔️")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.verificar_permissao(interaction): return
        
        user_id = self.extrair_id_usuario(interaction)
        registro = buscar_registro_por_discord_id(user_id)
        
        if not registro:
            return await interaction.response.send_message("❌ Registro não encontrado no banco de dados. Talvez já tenha sido processado.", ephemeral=True)
        if registro.get("aprovado", False):
            return await interaction.response.send_message("⚠️ Este registro já foi aprovado.", ephemeral=True)

        aprovar_registro(user_id)
        log_event(str(interaction.user), "Aprovou registro", registro["usuario"])

        membro = interaction.guild.get_member(user_id)
        cargo = interaction.guild.get_role(Cargo_membro)
        
        if membro and cargo:
            await membro.add_roles(cargo, reason="Registro aprovado")
            # ✨ Novo nickname com estética "ID | Nome"
            nome_limite = registro["nome"][:20]
            novo_nick = f"{registro['id']} | {nome_limite}"
            try:
                await membro.edit(nick=novo_nick)
            except discord.Forbidden:
                print("❌ Permissão insuficiente para mudar o apelido.")
            except discord.HTTPException as e:
                print(f"❌ Erro ao editar apelido: {e}")

        # Atualiza a mensagem original para remover os botões
        embed_atualizado = interaction.message.embeds[0]
        embed_atualizado.color = discord.Color.green()
        await interaction.response.edit_message(
            content=f"✅ Registro aprovado por {interaction.user.mention}.",
            embed=embed_atualizado,
            view=None
        )

        await interaction.channel.send(f"🎉 O membro <@{user_id}> foi aprovado por {interaction.user.mention}.")

        # 📝 Envia embed de aprovação para logs
        embed_log = discord.Embed(
            title="✅ Registro Aprovado",
            description=(
                f"👤 {registro['usuario']}\n"
                f"🆔 Discord ID: {user_id}\n"
                f"📛 Nome: {registro['nome']}\n"
                f"📞 Telefone: {registro['telefone']}\n"
                f"👮 Aprovado por: {interaction.user.mention}"
            ),
            color=discord.Color.green()
        )
        await enviar_log(interaction.guild, embed=embed_log)

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red, custom_id="btn_recusar_registro", emoji="❌")
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.verificar_permissao(interaction): return
        
        user_id = self.extrair_id_usuario(interaction)
        registro = buscar_registro_por_discord_id(user_id)
        
        if registro:
            remover_registro(user_id)
            log_event(str(interaction.user), "Recusou registro", registro["usuario"])

        embed_atualizado = interaction.message.embeds[0]
        embed_atualizado.color = discord.Color.red()
        await interaction.response.edit_message(
            content=f"❌ Registro recusado por {interaction.user.mention}.",
            embed=embed_atualizado,
            view=None
        )
        
        try:
            membro = interaction.guild.get_member(user_id)
            if membro:
                await membro.send(f"Seu registro foi reprovado por{interaction.user.name}.")
        except:
            pass # Ignora se a DM do usuário estiver fechada


# 📥 Modal de Registro
class RegistroModal(discord.ui.Modal, title="Registre seus dados"):
    nome = discord.ui.TextInput(label="Nome e Sobrenome", max_length=32)
    user_id = discord.ui.TextInput(label="Passaporte", max_length=32)
    telefone = discord.ui.TextInput(label="Telefone", max_length=10)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        telefone_fmt = self.telefone.value
        if not re.fullmatch(r"\d{3}(-\d{3})?", telefone_fmt):      
            return await interaction.response.send_message("❌ Formato inválido! Use 000-000 ou 000.", ephemeral=True)

        if buscar_registro_por_discord_id(interaction.user.id):
            return await interaction.response.send_message("⛔ Você já tem um registro em andamento/aprovado.", ephemeral=True)

        registro = {
            "nome": self.nome.value,
            "id": self.user_id.value,
            "telefone": telefone_fmt,
            "usuario": interaction.user.name,
            "discord_id": interaction.user.id,
            "aprovado": False
        }
        adicionar_registro(registro)

        # Confirmação efêmera para o usuário
        embed_confirma = discord.Embed(
            title="✅ Registro enviado com sucesso!",
            description=f"{interaction.user.mention}, seus dados foram enviados para aprovação.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed_confirma, ephemeral=True)

        # ✨ Embed semelhante ao Print 1 (Aprovação)
        embed_pendente = discord.Embed(
            title="💠 Solicitação de Entrada na Civil",
            description="**Novo membro solicitando entrada na civil!**\n",
            color=discord.Color.gold()
        )
        embed_pendente.add_field(name="👤 Solicitante", value=f"{interaction.user.mention}\n`{interaction.user.name}`", inline=False)
        embed_pendente.add_field(name="📛 Nome Cadastrado", value=f"`{self.nome.value}`", inline=True)
        embed_pendente.add_field(name="🆔 Passaporte", value=f"`{self.user_id.value}`", inline=True)
        embed_pendente.add_field(name="📞 Telefone", value=f"`{telefone_fmt}`", inline=True)
        
        if interaction.user.display_avatar:
            embed_pendente.set_thumbnail(url=interaction.user.display_avatar.url)
            
        # O truque de persistência: salvar o ID no rodapé para a AprovacaoView conseguir ler
        embed_pendente.set_footer(text=f"ID do Usuário: {interaction.user.id}")

        await interaction.guild.get_channel(canal_aprovacao).send(
            content="📥 **Registro pendente:**\n@everyone favor revisar.",
            embed=embed_pendente,
            view=AprovacaoView(), # View sem argumentos (stateless)
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )


# 🟢 View Persistente de Início de Registro (Print 2)
class RegistroView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Iniciar Meu Registro", style=discord.ButtonStyle.green, custom_id="btn_iniciar_registro", emoji="✔️")
    async def iniciar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistroModal(self.bot))


# ❌ Modal de Demissão (Mantido quase igual, não precisa ser persistente)
class DemitirModal(discord.ui.Modal, title="Digite o ID discord do membro"):
    discord_id = discord.ui.TextInput(label="ID do Discord", placeholder="123456789012345678", max_length=18)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            did = int(self.discord_id.value)
        except:
            return await interaction.response.send_message("❌ ID inválido.", ephemeral=True)

        usr = buscar_registro_por_discord_id(did)
        if not usr:
            return await interaction.response.send_message(f"❌ Usuário com ID `{did}` não registrado.", ephemeral=True)

        async def confirma(inter: discord.Interaction):
            remover_registro(did)
            log_event(str(inter.user), "Demitido", usr['usuario'])

            membro = inter.guild.get_member(did)
            cargo = inter.guild.get_role(Cargo_membro)
            if membro and cargo:
                await membro.remove_roles(cargo, reason="Demitido")

            await inter.response.send_message(f"✅ {usr['usuario']} demitido.", ephemeral=True)

            embed_demissao = discord.Embed(
                title="❌ Registro Removido",
                description=(
                    f"👤 {usr['usuario']}\n"
                    f"📛 Nome: {usr['nome']}\n"
                    f"🆔 Passaporte: {usr['id']}\n"
                    f"🆔 Discord ID: {did}\n"
                    f"👮 Removido por: {inter.user.mention}"
                ),
                color=discord.Color.red()
            )
            await enviar_log(inter.guild, embed=embed_demissao)

        view = discord.ui.View()
        botao = discord.ui.Button(label="Confirmar", style=discord.ButtonStyle.danger)
        botao.callback = confirma
        view.add_item(botao)
        await interaction.response.send_message(f"⚠️ Confirma a demissão de {usr['usuario']}?", view=view, ephemeral=True)


# 🔧 Comandos principais
class Cadastro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Inicializa as views persistentes quando o Cog carrega
    async def cog_load(self):
        self.bot.add_view(RegistroView(self.bot))
        self.bot.add_view(AprovacaoView())

    # 🛠️ NOVO COMANDO: Cria a mensagem permanente de Registro (Print 2)
    @app_commands.command(name="setup_registro", description="Cria a mensagem permanente de Registro")
    @app_commands.default_permissions(administrator=True)
    async def setup_registro(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Cadastro para Policia Civil",
            description=(
                "▶️ | Clique no botão abaixo para iniciar o registro na policia civil.\n\n"
                "⚠️ | **OBSERVAÇÃO:** Este é o processo de registro para os membros da policia civil, em caso de erro, chamar o Arima.\n\n"
                "👮‍♂️ • Atenciosamente, Arima"
            ),
            color=discord.Color.dark_orange()
        )
        
        await interaction.channel.send(embed=embed, view=RegistroView(self.bot))
        await interaction.response.send_message("Painel de registro enviado com sucesso!", ephemeral=True)

    @app_commands.command(name="listar_registros", description="Lista todos os registros aprovados")
    @app_commands.default_permissions(administrator=True)
    async def listar_registros(self, interaction: discord.Interaction):
        registros_aprovados = listar_registros_aprovados()
        if not registros_aprovados:
            await interaction.response.send_message("📭 Nenhum registro aprovado encontrado.", ephemeral=True)
            return

        await interaction.response.defer()

        for i in range(0, len(registros_aprovados), 5):
            bloco = registros_aprovados[i:i+5]
            embed = discord.Embed(
                title="📋 Oficiais da policia civil",
                description="Lista dos Agentes da policia civil cadastrados",
                color=discord.Color.green()
            )
            for idx, registro in enumerate(bloco, start=i+1):
                embed.add_field(
                    name=f"{idx}. 👤 {registro['usuario']}",
                    value=f"**Nome:** {registro['nome']}\n**ID:** {registro['id']}\n**Telefone:** {registro['telefone']}",
                    inline=False
                )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="demitir", description="Demitir um oficial da polícia civil")
    @app_commands.default_permissions(administrator=True)
    async def demitir(self, interaction: discord.Interaction):
        view = discord.ui.View()
        async def abrir_modal(inter: discord.Interaction):
            await inter.response.send_modal(DemitirModal(self.bot))

        botao = discord.ui.Button(label="Demitir", style=discord.ButtonStyle.danger)
        botao.callback = abrir_modal
        view.add_item(botao)
        await interaction.response.send_message("Clique para exonerar o oficial da policia civil", view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Cadastro(bot))
