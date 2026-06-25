import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
import re

# ============================================================
#  CONSTANTES — ajuste conforme seu servidor
# ============================================================
CARGO_INSTRUTOR_ID    = # Cargo autorizado a passar os cursos
CARGO_POLICIA_ID      = # ID do cargo a ser mencionado no embed
CANAL_CURSOS_ID       = # ID do canal os cursos serão avisados
CURSOS_PENDENTES      = # Canal para solicitar aprovação do curso
# ============================================================

# ---------------------------------------------------------------------------
# Modal — preenchido pelo instrutor ao agendar um curso
# ---------------------------------------------------------------------------
class AgendarCursoModal(ui.Modal, title="Agendar Curso"):
    nome_curso = ui.TextInput(
        label="Nome do Curso",
        placeholder="Ex: Flagrante",
        max_length=50,
    )
    cargo_id = ui.TextInput(
        label="ID do Cargo do Curso",
        placeholder="Ex: 1394099683470606426",
        max_length=20,
    )
    data = ui.TextInput(
        label="Data",
        placeholder="DD/MM/AAAA",
        max_length=10,
    )
    hora = ui.TextInput(
        label="Hora",
        placeholder="18h00 ou 18:00",
        max_length=6,
    )

    local = ui.TextInput(
        label="Local",
        placeholder="Ex: DP da policia civil",
        max_length=100,
        default="DP da policia civil",
    )

    def __init__(self, criador_id: int):
        super().__init__()
        self.criador_id = criador_id

    async def on_submit(self, interaction: discord.Interaction):
        # ── validação data ──
        if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", self.data.value.strip()):
            await interaction.response.send_message(
                "❌ Data inválida. Use o formato **DD/MM/AAAA**.", ephemeral=True
            )
            return

        # ── validação hora ──
        hora_raw = self.hora.value.strip()
        if not re.fullmatch(r"\d{1,2}[h:]\d{2}", hora_raw):
            await interaction.response.send_message(
                "❌ Hora inválida. Use **18h00** ou **18:00**.", ephemeral=True
            )
            return

        # ── normaliza hora para exibição (ex: 18h00) ──
        hora_fmt = hora_raw.replace(":", "h") if ":" in hora_raw else hora_raw

        # ── valida cargo ──
        try:
            cargo_id_int = int(self.cargo_id.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ ID do cargo inválido. Deve ser um número.", ephemeral=True
            )
            return

        cargo_curso = interaction.guild.get_role(cargo_id_int)
        if cargo_curso is None:
            await interaction.response.send_message(
                "❌ Cargo não encontrado neste servidor. Verifique o ID.", ephemeral=True
            )
            return

        # ── validação hierárquica: cargo do curso deve estar ABAIXO do cargo Instrutor ──
        cargo_instrutor = interaction.guild.get_role(CARGO_INSTRUTOR_ID)
        if cargo_instrutor and cargo_curso.position >= cargo_instrutor.position:
            await interaction.response.send_message(
                f"🚫 O cargo **{cargo_curso.name}** está na mesma posição ou acima do cargo de "
                f"**Instrutor** na hierarquia do servidor.\n"
                f"Apenas cargos abaixo do Instrutor podem ser concedidos por cursos.",
                ephemeral=True,
            )
            return

        cargo_policia = interaction.guild.get_role(CARGO_POLICIA_ID)
        canal_cursos  = interaction.guild.get_channel(CANAL_CURSOS_ID)

        if canal_cursos is None:
            await interaction.response.send_message(
                "❌ Canal de cursos não encontrado. Verifique CANAL_CURSOS_ID.", ephemeral=True
            )
            return

        # ── avatar do bot ──
        bot_user   = interaction.client.user
        bot_avatar = bot_user.display_avatar.url if bot_user else None

        # ── embed de aviso ──
        embed = discord.Embed(
            title=f"📋 Curso: {self.nome_curso.value.strip()}",
            color=discord.Color.blue(),
        )
        if bot_avatar:
            embed.set_thumbnail(url=bot_avatar)
            embed.set_author(name=bot_user.display_name, icon_url=bot_avatar)
        embed.add_field(name="Curso",     value=f"@ ┊ {self.nome_curso.value.strip()}", inline=False)
        embed.add_field(name="Instrutor", value=interaction.user.mention,               inline=False)
        embed.add_field(name="Data",      value=self.data.value.strip(),                inline=True)
        embed.add_field(name="Hora",      value=f"{hora_fmt}h",                         inline=True)
        embed.add_field(name="Local",     value=self.local.value.strip(),               inline=False)
        embed.add_field(
            name="\u200b",
            value="Confirmar participação reagindo nesse aviso ✅",
            inline=False,
        )
        embed.add_field(
            name="\u200b",
            value="🔴 **Não entrem em QRU's faltando 15 minutos para a aplicação desse curso, evitem atrasos!**",
            inline=False,
        )

        mencoes = f"{cargo_policia.mention if cargo_policia else ''} {interaction.guild.default_role}"

        view = AvisoCursoView(
            criador_id=self.criador_id,
            cargo_curso_id=cargo_id_int,
            nome_curso=self.nome_curso.value.strip(),
        )

        msg = await canal_cursos.send(content=mencoes, embed=embed, view=view)
        view.message_id = msg.id

        await interaction.response.send_message(
            f"✅ Curso **{self.nome_curso.value.strip()}** agendado com sucesso!", ephemeral=True
        )


# ---------------------------------------------------------------------------
# View persistente — botão "Solicitar Curso" no embed de aviso
# ---------------------------------------------------------------------------
class AvisoCursoView(ui.View):
    def __init__(self, criador_id: int, cargo_curso_id: int, nome_curso: str):
        super().__init__(timeout=None)
        self.criador_id    = criador_id
        self.cargo_curso_id = cargo_curso_id
        self.nome_curso    = nome_curso
        self.message_id    = None

    @ui.button(label="Solicitar Curso", style=discord.ButtonStyle.primary, emoji="📩", custom_id="solicitar_curso")
    async def solicitar_curso(self, interaction: discord.Interaction, button: ui.Button):
        canal_pendentes = interaction.guild.get_channel(CURSOS_PENDENTES)
        if canal_pendentes is None:
            await interaction.response.send_message(
                "❌ Canal de pendências não encontrado.", ephemeral=True
            )
            return

        aluno_avatar = interaction.user.display_avatar.url

        embed = discord.Embed(
            title="🕐 Solicitação Pendente",
            description=f"**{interaction.user.mention}** solicitou aprovação no curso **{self.nome_curso}**.",
            color=discord.Color.yellow(),
        )
        embed.set_thumbnail(url=aluno_avatar)
        embed.set_author(name=interaction.user.display_name, icon_url=aluno_avatar)
        embed.add_field(name="Solicitante", value=interaction.user.mention,         inline=True)
        embed.add_field(name="Curso",       value=self.nome_curso,                  inline=True)
        embed.add_field(name="Aprovador",   value=f"<@{self.criador_id}>",          inline=False)
        embed.add_field(name="Status",      value="🟡 Aguardando avaliação",        inline=False)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        view = AvaliacaoView(
            criador_id=self.criador_id,
            aluno_id=interaction.user.id,
            cargo_curso_id=self.cargo_curso_id,
            nome_curso=self.nome_curso,
        )

        await canal_pendentes.send(embed=embed, view=view)
        await interaction.response.send_message(
            "✅ Sua solicitação foi enviada! Aguarde a avaliação do instrutor.", ephemeral=True
        )


# ---------------------------------------------------------------------------
# View de avaliação — botões Aprovar / Reprovar no embed de pendência
# ---------------------------------------------------------------------------
class AvaliacaoView(ui.View):
    def __init__(self, criador_id: int, aluno_id: int, cargo_curso_id: int, nome_curso: str):
        super().__init__(timeout=None)
        self.criador_id    = criador_id
        self.aluno_id      = aluno_id
        self.cargo_curso_id = cargo_curso_id
        self.nome_curso    = nome_curso

    def _somente_criador(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.criador_id

    @ui.button(label="Aprovar", style=discord.ButtonStyle.success, emoji="✅", custom_id="aprovar_curso")
    async def aprovar(self, interaction: discord.Interaction, button: ui.Button):
        if not self._somente_criador(interaction):
            await interaction.response.send_message(
                "❌ Apenas o instrutor que criou o curso pode aprovar/reprovar.", ephemeral=True
            )
            return

        cargo = interaction.guild.get_role(self.cargo_curso_id)
        aluno = interaction.guild.get_member(self.aluno_id)

        if aluno is None:
            await interaction.response.send_message(
                "❌ Aluno não encontrado no servidor.", ephemeral=True
            )
            return

        if cargo:
            await aluno.add_roles(cargo, reason=f"Aprovado no curso {self.nome_curso}")

        # ── desabilita os botões após decisão ──
        for item in self.children:
            item.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ Solicitação Aprovada"

        # atualiza campo Status
        fields_novos = [f for f in embed.fields if f.name != "Status"]
        embed.clear_fields()
        for f in fields_novos:
            embed.add_field(name=f.name, value=f.value, inline=f.inline)
        embed.add_field(name="Status", value="🟢 Aprovado", inline=False)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f"✅ {aluno.mention} aprovado(a) e cargo **{cargo.name if cargo else self.cargo_curso_id}** concedido.",
            ephemeral=True,
        )

    @ui.button(label="Reprovar", style=discord.ButtonStyle.danger, emoji="❌", custom_id="reprovar_curso")
    async def reprovar(self, interaction: discord.Interaction, button: ui.Button):
        if not self._somente_criador(interaction):
            await interaction.response.send_message(
                "❌ Apenas o instrutor que criou o curso pode aprovar/reprovar.", ephemeral=True
            )
            return

        aluno = interaction.guild.get_member(self.aluno_id)

        # ── DM ao aluno ──
        if aluno:
            try:
                await aluno.send(
                    f"❌ Você foi **reprovado(a)** no curso **{self.nome_curso}**.\n"
                    f"Não desanime! Estude o conteúdo e tente novamente na próxima aplicação. 💪"
                )
            except discord.Forbidden:
                pass  # DM bloqueada pelo usuário

        # ── desabilita os botões após decisão ──
        for item in self.children:
            item.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ Solicitação Reprovada"

        # atualiza campo Status
        fields_novos = [f for f in embed.fields if f.name != "Status"]
        embed.clear_fields()
        for f in fields_novos:
            embed.add_field(name=f.name, value=f.value, inline=f.inline)
        embed.add_field(name="Status", value="🔴 Reprovado", inline=False)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f"❌ {aluno.mention if aluno else self.aluno_id} reprovado(a). DM enviada.", ephemeral=True
        )


# ---------------------------------------------------------------------------
# View persistente do setup (botão "Agendar Curso")
# ---------------------------------------------------------------------------
class SetupCursosView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _tem_permissao(self, interaction: discord.Interaction) -> bool:
        cargo_instrutor = interaction.guild.get_role(CARGO_INSTRUTOR_ID)
        membro = interaction.user
        tem_instrutor = cargo_instrutor in membro.roles if cargo_instrutor else False
        tem_adm = membro.guild_permissions.administrator
        return tem_instrutor or tem_adm

    @ui.button(
        label="📅 Agendar Curso",
        style=discord.ButtonStyle.primary,
        custom_id="agendar_curso_btn",
    )
    async def agendar_curso(self, interaction: discord.Interaction, button: ui.Button):
        if not self._tem_permissao(interaction):
            await interaction.response.send_message(
                "❌ Você precisa ter o cargo de **Instrutor** ou ser **Administrador** para agendar cursos.",
                ephemeral=True,
            )
            return

        modal = AgendarCursoModal(criador_id=interaction.user.id)
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# Cog principal
# ---------------------------------------------------------------------------
class SetupCursos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(SetupCursosView())

    @app_commands.command(name="setup_cursos", description="Posta o embed persistente de agendamento de cursos.")
    @app_commands.default_permissions(administrator=True)
    async def setup_cursos(self, interaction: discord.Interaction):
        """Posta o embed persistente de agendamento de cursos."""
        bot_user   = interaction.client.user
        bot_avatar = bot_user.display_avatar.url if bot_user else None

        embed = discord.Embed(
            title="🎓 Sistema de Cursos",
            description=(
                "Bem-vindo ao sistema de cursos da corporação!\n\n"
                "Instrutores podem agendar novos cursos clicando no botão abaixo."
            ),
            color=discord.Color.blurple(),
        )
        if bot_avatar:
            embed.set_thumbnail(url=bot_avatar)
            embed.set_author(name=bot_user.display_name, icon_url=bot_avatar)
        embed.set_footer(text="Apenas instrutores e administradores podem agendar cursos.")

        await interaction.channel.send(embed=embed, view=SetupCursosView())
        await interaction.response.send_message("Painel de cursos enviado com sucesso!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCursos(bot))
