import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import io
import logging
import aiohttp
from datetime import datetime
import utils.ui as ui

logger = logging.getLogger("bot.registro_prisao")

# ==========================================
# VARIÁVEIS DE CONFIGURAÇÃO
# ==========================================
CARGO_AUTORIZADO = 1519099990520369249 # Cargo 📗┋Curso Prisão
CANAL_REGISTRO   = 1519099992348819464 # Canal 🦝・painel-prisões

TIMEOUT_POR_PERGUNTA = 600.0  # 10 minutos por resposta
TIMEOUT_GLOBAL       = 3600.0 # 1 hora no total — segurança contra formulários eternos
MAX_TENTATIVAS_IMG   = 5      # Máximo de tentativas no loop de imagens
EXTENSOES_VALIDAS    = (".png", ".jpg", ".jpeg")


# ==========================================
# HELPER: baixa imagem como bytes (resolve o bug das URLs quebradas)
# ==========================================
async def baixar_imagem(url: str) -> bytes | None:
    """
    Faz download da imagem enquanto o canal temporário ainda existe.
    Retorna os bytes brutos ou None em caso de falha.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception:
        pass
    return None


# ==========================================
# VIEW PERSISTENTE
# ==========================================
class PrisaoView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Registrar prisão",
        style=discord.ButtonStyle.primary,
        custom_id="btn_iniciar_prisao",
        emoji="📋"
    )
    async def btn_prisao(self, interaction: discord.Interaction, button: discord.ui.Button):
        membro = interaction.user
        guild  = interaction.guild

        # --- Verificação de permissão ---
        tem_cargo = discord.utils.get(membro.roles, id=CARGO_AUTORIZADO)
        if not (membro.guild_permissions.administrator or tem_cargo):
            await interaction.response.send_message(
                embed=ui.build_error_embed("Você não tem permissão (Curso de Prisão) para iniciar um registro."),
                ephemeral=True
            )
            return

        # --- Proteção contra múltiplos canais simultâneos ---
        # Verifica se já existe um canal temporário aberto para esse usuário
        nome_esperado = f"prisao-{membro.display_name.lower()}"
        canal_existente = discord.utils.get(guild.text_channels, name=nome_esperado)
        if canal_existente:
            await interaction.response.send_message(
                embed=ui.build_warn_embed(f"Você já tem um registro em andamento: {canal_existente.mention}"),
                ephemeral=True
            )
            return

        # --- Criação do canal temporário ---
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            membro:             discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }

        try:
            canal_temporario = await guild.create_text_channel(
                name=nome_esperado,
                category=interaction.channel.category,
                overwrites=overwrites,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=ui.build_error_embed("Sem permissão para criar canais. Contate a administração."),
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=ui.build_success_embed(f"Seu canal de registro foi criado: {canal_temporario.mention}"),
            ephemeral=True
        )

        cog: RegistroPrisao | None = self.bot.get_cog("RegistroPrisao")
        if cog:
            task = asyncio.create_task(
                cog.executar_formulario(canal_temporario, membro),
                name=f"formulario-prisao-{membro.id}"
            )
            # Armazena referência para evitar garbage collection
            cog._formulario_tasks.add(task)
            task.add_done_callback(cog._formulario_tasks.discard)
            # Callback para capturar exceções silenciosas
            def _on_task_done(t: asyncio.Task):
                if t.cancelled():
                    logger.warning(f"Task formulário cancelada: {t.get_name()}")
                elif t.exception():
                    logger.error(f"Exceção em task formulário {t.get_name()}: {t.exception()}", exc_info=t.exception())
            task.add_done_callback(_on_task_done)


# ==========================================
# COG PRINCIPAL
# ==========================================
class RegistroPrisao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Armazena referências das tasks para evitar garbage collection prematura
        self._formulario_tasks: set[asyncio.Task] = set()

    # ------------------------------------------
    # Comando de setup (somente admin)
    # ------------------------------------------
    @app_commands.command(name="setup_prisao", description="Cria o embed com o botão persistente de registro de prisão.")
    @app_commands.default_permissions(administrator=True)
    async def setup_prisao(self, interaction: discord.Interaction):
        """Cria o embed com o botão persistente de registro de prisão."""
        embed = ui.build_embed(
            title="🚔 Sistema de Registro de Prisões",
            description=(
                "Clique no botão abaixo para iniciar um novo registro de prisão.\n"
                "Um canal privado será criado para você preencher os dados do detento."
            ),
            color=ui.UI_COLOR_MAIN,
        )
        await interaction.channel.send(embed=embed, view=PrisaoView(self.bot))
        await interaction.response.send_message(embed=ui.build_success_embed("Painel de registro de prisão enviado com sucesso!"), ephemeral=True)

    # ------------------------------------------
    # Helpers internos
    # ------------------------------------------
    async def _perguntar(
        self,
        channel: discord.TextChannel,
        user: discord.Member,
        pergunta: str,
    ) -> discord.Message | None:
        """
        Envia uma pergunta e aguarda a resposta do usuário.
        Retorna a mensagem ou None em caso de timeout.
        """
        await channel.send(pergunta)
        def check(m: discord.Message) -> bool:
            return m.author == user and m.channel == channel

        try:
            return await self.bot.wait_for("message", check=check, timeout=TIMEOUT_POR_PERGUNTA)
        except asyncio.TimeoutError:
            return None

    # ------------------------------------------
    # Formulário principal
    # ------------------------------------------
    async def executar_formulario(self, channel: discord.TextChannel, user: discord.Member):

        async def fechar_canal(msg: str):
            """Envia aviso e deleta o canal com segurança."""
            try:
                await channel.send(msg)
                await asyncio.sleep(5)
            except discord.NotFound:
                pass
            finally:
                try:
                    await channel.delete()
                except discord.NotFound:
                    pass

        # Wrapper que cancela tudo se um timeout ocorrer
        try:
            async with asyncio.timeout(TIMEOUT_GLOBAL):
                await self._formulario(channel, user, fechar_canal)
        except TimeoutError:
            await fechar_canal(
                "⏳ **Tempo total esgotado!** O formulário ultrapassou 1 hora. O canal será fechado."
            )

    async def _formulario(self, channel, user, fechar_canal):
        """Lógica real do formulário, separada para facilitar o timeout global."""

        async def ask(pergunta: str) -> str | None:
            """Pergunta e retorna o conteúdo da resposta, ou None se timeout."""
            msg = await self._perguntar(channel, user, pergunta)
            if msg is None:
                await fechar_canal(
                    "⏳ **Tempo esgotado!** Você demorou mais de 10 minutos. O canal será fechado."
                )
                return None
            return msg.content

        try:
            await channel.send(
                f"{user.mention} 📋 **Registro de Prisão — Formulário**\n"
                "Responda cada pergunta no chat. Você tem **10 minutos** por pergunta."
            )

            # ---- Dados obrigatórios ----
            qra          = await ask("Digite o **QRA da Primária**:")
            if qra is None: return

            qra_oficiais = await ask("Digite o **QRA dos Oficiais da Penal**:")
            if qra_oficiais is None: return

            pass_oficiais = await ask("Digite o **Passaporte dos Oficiais da Penal**:")
            if pass_oficiais is None: return

            pass_primaria = await ask("Digite o **Passaporte da Primária**:")
            if pass_primaria is None: return

            nome_preso   = await ask("Digite o **Nome do Preso**:")
            if nome_preso is None: return

            pass_preso   = await ask("Digite o **Passaporte do Preso**:")
            if pass_preso is None: return

            artigos      = await ask("Digite os **Artigos Violados**:")
            if artigos is None: return

            meses        = await ask("Tempo de prisão (em meses):")
            if meses is None: return

            # ---- Multa ----
            multa_resp = await ask("Houve **Multa**? (Sim/Não):")
            if multa_resp is None: return
            multa_tem  = multa_resp.strip().lower() in ("sim", "s")
            multa_txt  = "Sim" if multa_tem else "Não"

            valor_multa_txt = "Não houve"
            if multa_tem:
                vm = await ask("Valor da multa:")
                if vm is None: return
                valor_multa_txt = vm

            # ---- Advogado ----
            adv_raw = await ask("Digite o **Advogado** (opcional — ou `pular`):")
            if adv_raw is None: return
            advogado_txt = None if adv_raw.lower() == "pular" else adv_raw

            padv_raw = await ask("Digite o **Passaporte do Advogado** (opcional — ou `pular`):")
            if padv_raw is None: return
            pass_adv_txt = None if padv_raw.lower() == "pular" else padv_raw

            # ---- Fiança ----
            fianca_resp = await ask("Houve **Fiança**? (Sim/Não):")
            if fianca_resp is None: return
            fianca_tem  = fianca_resp.strip().lower() in ("sim", "s")
            fianca_txt  = "Sim" if fianca_tem else "Não"

            valor_fianca_txt = "Não houve"
            if fianca_tem:
                vf = await ask("Valor da fiança:")
                if vf is None: return
                valor_fianca_txt = vf

            # ---- Provas (imagens) ----
            await channel.send(
                "📌 Agora envie os prints: **mochila do preso**, **registro do tablet** e **identificação do preso**."
            )

            imagens_bytes: list[tuple[str, bytes]] = []  # (filename, bytes)
            tentativas = 0

            while not imagens_bytes:
                tentativas += 1
                if tentativas > MAX_TENTATIVAS_IMG:
                    await fechar_canal(
                        f"❌ Limite de {MAX_TENTATIVAS_IMG} tentativas atingido. O canal será fechado."
                    )
                    return

                await channel.send(
                    "📸 Envie as **fotos/provas da prisão**.\n"
                    "✔ Formatos aceitos: **PNG ou JPG**\n"
                    "⚠️ Mínimo: 1 imagem | Máximo: 5 imagens\n"
                    "💡 Envie todas as imagens em **uma única mensagem**."
                )

                def check(m: discord.Message) -> bool:
                    return m.author == user and m.channel == channel

                try:
                    msg_img = await self.bot.wait_for("message", check=check, timeout=TIMEOUT_POR_PERGUNTA)
                except asyncio.TimeoutError:
                    await fechar_canal("⏳ **Tempo esgotado!** Você demorou demais para enviar as imagens.")
                    return

                validas = [a for a in msg_img.attachments if a.filename.lower().endswith(EXTENSOES_VALIDAS)]

                if not validas:
                    await channel.send("❌ Nenhuma imagem válida detectada. Use apenas **PNG ou JPG**.")
                    continue

                if len(validas) > 5:
                    await channel.send("❌ Você enviou mais de **5 imagens**. Envie no máximo 5.")
                    continue

                # ---- FIX PRINCIPAL: baixa as imagens ANTES de deletar o canal ----
                await channel.send("⏳ Processando imagens, aguarde...")
                for anexo in validas:
                    dados = await baixar_imagem(anexo.url)
                    if dados:
                        imagens_bytes.append((anexo.filename, dados))

                if not imagens_bytes:
                    await channel.send("❌ Falha ao processar as imagens. Tente novamente.")
                    continue  # permite nova tentativa

            # ==========================================
            # MONTAGEM DO EMBED
            # ==========================================
            embed = ui.build_embed(
                title="📚 Registro de Prisão",
                color=ui.UI_COLOR_WARNING,
            )
            embed.add_field(name="QRA dos Oficiais da Penal",    value=qra_oficiais,            inline=False)
            embed.add_field(name="Passaporte dos Oficiais",      value=pass_oficiais,           inline=False)
            embed.add_field(name="QRA da Primária",              value=qra,                     inline=False)
            embed.add_field(name="Passaporte da Primária",       value=pass_primaria,           inline=False)
            embed.add_field(name="Nome do Preso",                value=nome_preso,              inline=False)
            embed.add_field(name="Passaporte do Preso",          value=pass_preso,              inline=False)
            embed.add_field(name="Artigos Violados",             value=artigos,                 inline=False)
            embed.add_field(name="Tempo de Prisão (meses)",      value=meses,                   inline=False)
            embed.add_field(name="Houve Multa?",                 value=multa_txt,               inline=True)
            embed.add_field(name="Valor da Multa",               value=valor_multa_txt,         inline=True)
            embed.add_field(name="\u200b",                       value="\u200b",                inline=False) # separador visual
            embed.add_field(name="Advogado",                     value=advogado_txt or "Não informado", inline=True)
            embed.add_field(name="Passaporte do Advogado",       value=pass_adv_txt or "Não informado", inline=True)
            embed.add_field(name="\u200b",                       value="\u200b",                inline=False)
            embed.add_field(name="Houve Fiança?",                value=fianca_txt,              inline=True)
            embed.add_field(name="Valor da Fiança",              value=valor_fianca_txt,        inline=True)

            embed.set_footer(text=f"{ui.FOOTER_TEXT} • Prisão registrada em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
            embed.set_author(name=f"Registrado por: {user.display_name}")

            # ---- Primeira imagem como thumbnail no embed (via attachment local) ----
            nome_principal, bytes_principal = imagens_bytes[0]
            arquivo_principal = discord.File(io.BytesIO(bytes_principal), filename=nome_principal)
            embed.set_image(url=f"attachment://{nome_principal}")

            # ---- Imagens extras como arquivos adicionais ----
            arquivos_extras: list[discord.File] = []
            for nome, dados in imagens_bytes[1:]:
                arquivos_extras.append(discord.File(io.BytesIO(dados), filename=nome))

            # ---- Envio para o canal de registro ----
            canal_registro: discord.TextChannel | None = channel.guild.get_channel(CANAL_REGISTRO)

            if canal_registro is None:
                await fechar_canal(
                    "🚨 Canal de registro oficial não encontrado. Contate a administração."
                )
                return

            # Envia embed com imagem principal
            await canal_registro.send(file=arquivo_principal, embed=embed)

            # Envia imagens extras separadamente (se houver)
            if arquivos_extras:
                await canal_registro.send(
                    content=f"📎 **Provas adicionais** — Registro de {user.display_name}:",
                    files=arquivos_extras,
                )

            await fechar_canal("✅ Prisão registrada com sucesso! Este canal será fechado em 5 segundos...")

        except Exception as e:
            logger.error(f"[RegistroPrisao] Erro inesperado no formulário: {e}", exc_info=True)
            await fechar_canal("🚨 Ocorreu um erro interno. O canal será fechado...")


# ==========================================
# SETUP
# ==========================================
async def setup(bot: commands.Bot):
    await bot.add_cog(RegistroPrisao(bot))
    bot.add_view(PrisaoView(bot))
