import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.cadastro",
    "cogs.alinhamento",
    "cogs.advertencia",
    "cogs.corregedoria",
    "cogs.registro_prisao",
    "cogs.provas",
    "cogs.acao",
    "cogs.status_acao",  # deve vir após cogs.acao
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
            logging.info(f"✅ Cog carregado: {cog}")
        except Exception as e:
            logging.error(f"❌ Erro ao carregar {cog}: {e}")

@bot.event
async def on_ready():
    logging.info(f"🤖 Bot online como: {bot.user}")
    logging.info(f"📊 Servidores conectados: {[guild.name for guild in bot.guilds]}")
    print(f"Bot online como {bot.user}")

@bot.event
async def setup_hook():
    await load_cogs()
    await bot.tree.sync()

if __name__ == "__main__":
    logging.info("🚀 Iniciando o bot...")
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("Token do Discord não encontrado nas variáveis de ambiente (.env)!")
    bot.run(token)
