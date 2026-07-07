import discord

# ==========================================
# Constantes de Cores e Estilos (Design System)
# ==========================================
UI_COLOR_MAIN = 0x2b2d31
UI_COLOR_SUCCESS = discord.Color.brand_green()
UI_COLOR_ERROR = discord.Color.brand_red()
UI_COLOR_WARNING = discord.Color.gold()
UI_COLOR_INFO = discord.Color.blurple()

# ==========================================
# Emojis Padrões
# ==========================================
EMOJI_SUCCESS = "✅"
EMOJI_ERROR = "❌"
EMOJI_WARN = "⚠️"
EMOJI_INFO = "ℹ️"
EMOJI_LOCK = "🔒"
EMOJI_TICKET = "🎟️"

# ==========================================
# Configurações Globais
# ==========================================
FOOTER_TEXT = "FBI | Miami City"

def build_embed(title: str, description: str, color: int = UI_COLOR_MAIN) -> discord.Embed:
    """Cria um embed padrão do sistema com o rodapé e a cor configurados."""
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=FOOTER_TEXT)
    return embed

def build_success_embed(message: str, title: str = f"{EMOJI_SUCCESS} Sucesso!") -> discord.Embed:
    """Cria um embed focado em feedback de sucesso."""
    return build_embed(title=title, description=message, color=UI_COLOR_SUCCESS)

def build_error_embed(message: str, title: str = f"{EMOJI_ERROR} Erro!") -> discord.Embed:
    """Cria um embed focado em feedback de erro."""
    return build_embed(title=title, description=message, color=UI_COLOR_ERROR)

def build_warn_embed(message: str, title: str = f"{EMOJI_WARN} Aviso!") -> discord.Embed:
    """Cria um embed focado em feedback de aviso."""
    return build_embed(title=title, description=message, color=UI_COLOR_WARNING)
