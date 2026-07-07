import discord
from discord.ext import commands
from discord import app_commands

import utils.ui as ui

# ==========================================
# Padrão esperado de canais criados pela cog
# ==========================================
CANAIS_PADRAO = ["👤・identidade", "🗯・chat", "📸・provas", "🎫・boletins-de-ocorrencia"]


# ==========================================
# View de Confirmação para deletar categoria
# ==========================================
class ConfirmarDeleteView(discord.ui.View):
    """View ephemeral com botões de Confirmar / Cancelar a exclusão de uma categoria."""

    def __init__(self, categoria: discord.CategoryChannel):
        super().__init__(timeout=60)
        self.categoria = categoria

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            nome = self.categoria.name
            # Deleta todos os canais dentro da categoria primeiro
            for canal in self.categoria.channels:
                await canal.delete(reason=f"Exclusão da aba de provas '{nome}' por {interaction.user}")

            # Depois deleta a categoria em si
            await self.categoria.delete(reason=f"Exclusão da aba de provas '{nome}' por {interaction.user}")

            await interaction.followup.send(
                embed=ui.build_success_embed(f"Categoria `{nome}` e todos os seus canais foram deletados com sucesso."),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=ui.build_error_embed("O bot não tem permissão para deletar canais/categorias."),
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.followup.send(
                embed=ui.build_warn_embed("A categoria já foi deletada ou não existe mais."),
                ephemeral=True
            )

        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=ui.build_warn_embed("Operação cancelada. Nenhum canal foi deletado."),
            ephemeral=True
        )
        self.stop()


# ==========================================
# Modal para receber o ID da categoria
# ==========================================
class DeletarCategoriaModal(discord.ui.Modal, title="Deletar Aba de Provas"):
    """Modal que solicita o ID da categoria a ser deletada."""

    categoria_id = discord.ui.TextInput(
        label="ID da Categoria",
        placeholder="Ex: 1234567890123456789",
        required=True,
        min_length=15,
        max_length=25,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        input_id = self.categoria_id.value.strip()

        # --- Validação: o valor precisa ser um número ---
        if not input_id.isdigit():
            return await interaction.response.send_message(
                embed=ui.build_error_embed("O ID informado não é válido. Insira apenas números."),
                ephemeral=True
            )

        categoria_id = int(input_id)
        categoria = guild.get_channel(categoria_id)

        # --- Validação: o canal existe e é uma categoria? ---
        if categoria is None or not isinstance(categoria, discord.CategoryChannel):
            return await interaction.response.send_message(
                embed=ui.build_error_embed("Nenhuma categoria foi encontrada com esse ID neste servidor."),
                ephemeral=True
            )

        # --- Validação: a categoria segue o padrão da cog Provas? ---
        nomes_canais = sorted([ch.name for ch in categoria.channels])
        nomes_esperados = sorted(CANAIS_PADRAO)

        if nomes_canais != nomes_esperados:
            return await interaction.response.send_message(
                embed=ui.build_error_embed(
                    "Esta categoria **não segue o padrão** de uma aba de provas.\n\n"
                    f"**Esperado:** {', '.join(CANAIS_PADRAO)}\n"
                    f"**Encontrado:** {', '.join([ch.name for ch in categoria.channels]) or 'nenhum canal'}"
                ),
                ephemeral=True
            )

        # --- Tudo certo: pede confirmação ---
        lista_canais = "\n".join([f"• `{ch.name}`" for ch in categoria.channels])
        embed = ui.build_embed(
            title="🗑️ Confirmar Exclusão",
            description=(
                f"Você está prestes a deletar a categoria **{categoria.name}** e os seguintes canais:\n\n"
                f"{lista_canais}\n\n"
                "⚠️ **Esta ação é irreversível.** Deseja continuar?"
            ),
            color=ui.UI_COLOR_ERROR
        )

        view = ConfirmarDeleteView(categoria)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==========================================
# 🧩 View principal do painel de provas
# ==========================================
class ProvasView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Botão não expira

    # ✨ O custom_id é o que garante que o botão vai funcionar mesmo se o bot reiniciar
    @discord.ui.button(label="Crie seu chat", style=discord.ButtonStyle.green, custom_id="btn_criar_aba_provas", emoji="📂")
    async def criar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        # 🛡️ Verificação de Cargo (FBI)
        ID_CARGO_POLICIA = 1519099990507520035  # Cargo FBI
        tem_cargo = any(role.id == ID_CARGO_POLICIA for role in user.roles)

        if not tem_cargo:
            return await interaction.response.send_message(
                embed=ui.build_error_embed("Você não tem permissão de criar a aba de provas, por favor faça seu cadastro ou procure um delegado para suporte."), 
                ephemeral=True
            )

        # 1. Verifica se a categoria já existe
        categoria_nome = user.display_name
        categoria_existente = discord.utils.get(guild.categories, name=categoria_nome)
        
        if categoria_existente:
            return await interaction.response.send_message(
                embed=ui.build_warn_embed(f"Você já tem um canal em `{categoria_nome}`."), 
                ephemeral=True
            )

        # ✨ Mantido apenas um defer() para evitar conflitos na API do Discord
        await interaction.response.defer(ephemeral=True)

        try:
            # 2. Permissões e Criação
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }

            cat = await guild.create_category(categoria_nome, overwrites=overwrites)
            
            for nome_canal in CANAIS_PADRAO:
                await guild.create_text_channel(nome_canal, category=cat)

            await interaction.followup.send(embed=ui.build_success_embed(f"Canais criados na categoria `{categoria_nome}`!"), ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send(embed=ui.build_error_embed("O bot não tem permissão para gerenciar canais."), ephemeral=True)

    # 🗑️ Botão de Deletar Chat — restrito a administradores
    @discord.ui.button(label="Deletar Chat", style=discord.ButtonStyle.danger, custom_id="btn_deletar_aba_provas", emoji="🗑️")
    async def deletar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🛡️ Apenas administradores podem usar
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=ui.build_error_embed("Apenas administradores podem clicar nesse botão."),
                ephemeral=True
            )

        # Abre o modal para receber o ID da categoria
        await interaction.response.send_modal(DeletarCategoriaModal())


# 🚀 Esta classe cuida apenas do COMANDO de Setup
class Provas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ✨ Essencial: Avisa ao bot para "lembrar" desse botão quando for ligado
    async def cog_load(self):
        self.bot.add_view(ProvasView())

    # ✨ Alterado para slash command, focado no uso da administração
    @app_commands.command(name="setup_provas", description="Envia o painel permanente de criação de provas")
    @app_commands.default_permissions(administrator=True)
    async def setup_provas(self, interaction: discord.Interaction):
        """Envia o painel permanente de criação de provas"""
            
        # 📝 Criação do Embed com estética semelhante aos prints enviados
        embed = ui.build_embed(
            title="CRIE SUA ABA DE PROVAS",
            description=(
                "▶️ | Clique no botão abaixo para criar sua categoria individual de provas.\n\n"
                "⚠️ | **OBSERVAÇÃO:** Este painel criará canais privados de Identidade, Chat, Provas e B.O. "
                "Utilize seu canal de forma organizada para registrar suas ocorrências.\n\n"
                "👮‍♂️ • Atenciosamente, Arima"
            ),
            color=ui.UI_COLOR_MAIN
        )
        
        view = ProvasView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(embed=ui.build_success_embed("Painel de provas enviado com sucesso!"), ephemeral=True)


# 🛠️ Setup da extensão
async def setup(bot):
    await bot.add_cog(Provas(bot))