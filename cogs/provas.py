import discord
from discord.ext import commands
from discord import app_commands

# 🧩 Esta classe cuida apenas da INTERFACE (o botão e a criação dos canais)
class ProvasView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Botão não expira

    # ✨ O custom_id é o que garante que o botão vai funcionar mesmo se o bot reiniciar
    @discord.ui.button(label="Crie seu chat", style=discord.ButtonStyle.green, custom_id="btn_criar_aba_provas", emoji="📂")
    async def criar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        # 🛡️ Verificação de Cargo (Polícia Civil)
        ID_CARGO_POLICIA = 1394099683265220690
        tem_cargo = any(role.id == ID_CARGO_POLICIA for role in user.roles)

        if not tem_cargo:
            return await interaction.response.send_message(
                "❌ Você não tem permissão de criar a aba de provas, por favor faça seu cadastro ou procure um delegado para suporte.", 
                ephemeral=True
            )

        # 1. Verifica se a categoria já existe
        categoria_nome = user.display_name
        categoria_existente = discord.utils.get(guild.categories, name=categoria_nome)
        
        if categoria_existente:
            return await interaction.response.send_message(
                f"🎫 Você já tem um canal em `{categoria_nome}`.", 
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
            canais = ["👤￤identidade", "🗯￤chat", "📸￤provas", "🎫￤boletins-de-ocorrencia"]
            
            for nome_canal in canais:
                await guild.create_text_channel(nome_canal, category=cat)

            await interaction.followup.send(f"✅ Canais criados na categoria `{categoria_nome}`!", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ O bot não tem permissão para gerenciar canais.", ephemeral=True)


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
        embed = discord.Embed(
            title="CRIE SUA ABA DE PROVAS",
            description=(
                "▶️ | Clique no botão abaixo para criar sua categoria individual de provas.\n\n"
                "⚠️ | **OBSERVAÇÃO:** Este painel criará canais privados de Identidade, Chat, Provas e B.O. "
                "Utilize seu canal de forma organizada para registrar suas ocorrências.\n\n"
                "👮‍♂️ • Atenciosamente, Arima"
            ),
            color=discord.Color.dark_theme()
        )
        
        view = ProvasView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Painel de provas enviado com sucesso!", ephemeral=True)


# 🛠️ Setup da extensão
async def setup(bot):
    await bot.add_cog(Provas(bot))