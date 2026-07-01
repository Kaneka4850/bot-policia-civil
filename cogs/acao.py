import discord
from discord.ext import commands
from discord import app_commands
import re

import utils.ui as ui

# ──────────────────────────────────────────────
# 📋 CANAIS QUE RECEBERÃO O RELATÓRIO
# ──────────────────────────────────────────────
CANAIS_ENVIO: list[int] = [] # Insira o id do canal 

# ──────────────────────────────────────────────
# CONSTANTES DOS FIELD NAMES (evita typos)
# ──────────────────────────────────────────────
FIELD_MEMBROS   = "👥 Membros Confirmados"
FIELD_LIMITE    = "🔢 Vagas"        # guarda "confirmados/limite" no embed


# ══════════════════════════════════════════════
# VIEW DE PARTICIPAÇÃO  (persistente)
# ══════════════════════════════════════════════
class ViewParticipacao(discord.ui.View):
    """
    View anexada ao relatório de ação.

    Botões:
    • ✋ Confirmar Participação  → verde
    • ❌ Cancelar Confirmação   → vermelho

    Lógica de limite:
    O embed guarda o campo FIELD_LIMITE com o formato "X/Y"
    onde X = confirmados e Y = máximo. O botão de confirmar bloqueia
    quando X >= Y.
    """

    def __init__(self) -> None:
        super().__init__(timeout=None)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _get_field_index(embed: discord.Embed, name: str) -> int | None:
        """Retorna o índice do field cujo nome contenha `name`, ou None."""
        for i, field in enumerate(embed.fields):
            if name in field.name:
                return i
        return None

    @staticmethod
    def _parse_limite(embed: discord.Embed) -> tuple[int, int]:
        """
        Lê o campo FIELD_LIMITE e retorna (confirmados, limite).
        Retorna (0, 0) se o campo não existir (sem limite definido).
        """
        for field in embed.fields:
            if FIELD_LIMITE in field.name:
                partes = field.value.split("/")
                if len(partes) == 2:
                    try:
                        return int(partes[0].strip()), int(partes[1].strip())
                    except ValueError:
                        return 0, 0
        return 0, 0  # sem limite → sem restrição

    @staticmethod
    def _count_members(membros_value: str) -> int:
        """Conta quantas menções existem no value do field de membros."""
        return len(re.findall(r"<@\d+>", membros_value))

    # ------------------------------------------------------------------
    # BOTÃO: CONFIRMAR PARTICIPAÇÃO
    # ------------------------------------------------------------------

    @discord.ui.button(
        label="Confirmar Participação",
        style=discord.ButtonStyle.success,
        custom_id="btn_confirmar_participacao",
        emoji="✋",
        row=0,
    )
    async def btn_participar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Deferir imediatamente para evitar "Unknown interaction" (token expira em 3s)
        await interaction.response.defer(ephemeral=True)

        embed = interaction.message.embeds[0]
        user_mention = interaction.user.mention

        idx_membros = self._get_field_index(embed, FIELD_MEMBROS)
        if idx_membros is None:
            await interaction.followup.send(
                embed=ui.build_warn_embed("Não foi possível encontrar o campo de membros no relatório."), ephemeral=True
            )
            return

        membros_atuais = embed.fields[idx_membros].value

        # Duplicata
        if user_mention in membros_atuais:
            await interaction.followup.send(
                embed=ui.build_warn_embed("Você já confirmou participação nesta ação!"), ephemeral=True
            )
            return

        # Verificação de limite
        confirmados, limite = self._parse_limite(embed)
        if limite > 0 and confirmados >= limite:
            await interaction.followup.send(
                embed=ui.build_error_embed(f"Limite de **{limite} membros** atingido. Não há mais vagas nesta ação."),
                ephemeral=True,
            )
            return

        # Adiciona o membro
        if membros_atuais.strip() == "Nenhum membro confirmado ainda.":
            novo_valor = user_mention
        else:
            novo_valor = f"{membros_atuais}, {user_mention}"

        embed.set_field_at(idx_membros, name=FIELD_MEMBROS, value=novo_valor, inline=False)

        # Atualiza o contador de vagas
        if limite > 0:
            novo_confirmados = self._count_members(novo_valor)
            idx_limite = self._get_field_index(embed, FIELD_LIMITE)
            if idx_limite is not None:
                embed.set_field_at(
                    idx_limite,
                    name=FIELD_LIMITE,
                    value=f"{novo_confirmados}/{limite}",
                    inline=True,
                )

        await interaction.message.edit(embed=embed)
        await interaction.followup.send(
            embed=ui.build_success_embed("Sua participação foi confirmada com sucesso!"), ephemeral=True
        )

    # ------------------------------------------------------------------
    # BOTÃO: CANCELAR CONFIRMAÇÃO
    # ------------------------------------------------------------------

    @discord.ui.button(
        label="Cancelar Confirmação",
        style=discord.ButtonStyle.danger,
        custom_id="btn_cancelar_participacao",
        emoji="❌",
        row=0,
    )
    async def btn_cancelar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Deferir imediatamente para evitar "Unknown interaction" (token expira em 3s)
        await interaction.response.defer(ephemeral=True)

        embed = interaction.message.embeds[0]
        user_mention = interaction.user.mention

        idx_membros = self._get_field_index(embed, FIELD_MEMBROS)
        if idx_membros is None:
            await interaction.followup.send(
                embed=ui.build_warn_embed("Não foi possível encontrar o campo de membros no relatório."), ephemeral=True
            )
            return

        membros_atuais = embed.fields[idx_membros].value

        if user_mention not in membros_atuais:
            await interaction.followup.send(
                embed=ui.build_warn_embed("Você não está na lista de participantes desta ação."), ephemeral=True
            )
            return

        # Remove a menção do usuário
        # Cobre tanto o caso de estar no meio (",  <@ID>") quanto no início
        novo_valor = re.sub(rf",?\s*{re.escape(user_mention)}", "", membros_atuais).strip()
        novo_valor = re.sub(r"^,\s*", "", novo_valor).strip()  # vírgula solta no início

        if not novo_valor:
            novo_valor = "Nenhum membro confirmado ainda."

        embed.set_field_at(idx_membros, name=FIELD_MEMBROS, value=novo_valor, inline=False)

        # Atualiza contador de vagas
        _, limite = self._parse_limite(embed)
        if limite > 0:
            novo_confirmados = self._count_members(novo_valor)
            idx_limite = self._get_field_index(embed, FIELD_LIMITE)
            if idx_limite is not None:
                embed.set_field_at(
                    idx_limite,
                    name=FIELD_LIMITE,
                    value=f"{novo_confirmados}/{limite}",
                    inline=True,
                )

        await interaction.message.edit(embed=embed)
        await interaction.followup.send(
            embed=ui.build_success_embed("Sua participação foi cancelada."), ephemeral=True
        )


# ══════════════════════════════════════════════
# MODAL DE REGISTRO DE AÇÃO
# ══════════════════════════════════════════════
# ⚠️  Discord limita modais a 5 campos (TextInput).
#     Campos originais: qual_acao | org_envolvida | negociador |
#                       call_p1_p2 | resultado | itens_apreendidos  → 6 ❌
#
#     Solução: "resultado" e "itens_apreendidos" foram unidos em um
#     único campo com instrução clara, liberando espaço para
#     "num_membros".  Total: 5 ✅
# ──────────────────────────────────────────────
class ModalAcao(discord.ui.Modal, title="Registro de Ação"):

    # 1. Ação
    qual_acao = discord.ui.TextInput(
        label="1. Qual a ação?",
        style=discord.TextStyle.short,
        placeholder="Ex: Açougue, Banco Central, etc.",
        max_length=100,
        required=True,
    )

    # 2. Oponente
    org_envolvida = discord.ui.TextInput(
        label="2. Oponente Envolvida",
        style=discord.TextStyle.short,
        placeholder="Ex: França, Inglaterra, etc.",
        max_length=100,
        required=True,
    )

    # 3. Negociador e Call P1/P2 — consolidados para abrir espaço
    negociador_e_call = discord.ui.TextInput(
        label="3. Negociador (ID) | P1 (ID) | P2 (ID)",
        style=discord.TextStyle.short,
        placeholder="IDs separados por espaço: 111... 222... 333...",
        required=True,
    )

    # 4. Resultado + Itens Apreendidos — separados por espaço simples
    resultado_e_itens = discord.ui.TextInput(
        label="4. Resultado + Itens",
        style=discord.TextStyle.short,
        placeholder="Ex: Win 8 SMG 2 AR    |    Loss",
        required=True,
    )

    # 5. Número de Membros (limite de vagas)
    num_membros = discord.ui.TextInput(
        label="5. Nº máximo de membros",
        style=discord.TextStyle.short,
        placeholder="Ex: 12  (0 = sem limite)",
        max_length=3,
        required=True,
    )

    # ------------------------------------------------------------------

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # ── Parsear resultado + itens ──────────────────────────────────
        partes_resultado = self.resultado_e_itens.value.strip().split(" ", 1)
        # A primeira palavra é o resultado; o restante são os itens.
        palavra_chave = partes_resultado[0].lower()

        is_win = palavra_chave in ("win", "vitória", "vitoria")
        cor = ui.UI_COLOR_SUCCESS if is_win else ui.UI_COLOR_ERROR
        descricao = (
            "**Ação finalizada com vitória** 🏆"
            if is_win
            else "**Ação finalizada com derrota** 💀"
        )
        texto_resultado = "Win ✅" if is_win else "Loss ❌"

        if is_win:
            texto_itens = partes_resultado[1].strip() if len(partes_resultado) > 1 else "Nenhum item registrado."
        else:
            texto_itens = "Ação perdida — nenhum item apreendido."

        # ── Parsear negociador e call ──────────────────────────────────
        ids_encontrados = re.findall(r"\d{17,19}", self.negociador_e_call.value)

        if len(ids_encontrados) >= 1:
            negociador_mention = f"<@{ids_encontrados[0]}>"
        else:
            negociador_mention = self.negociador_e_call.value  # fallback

        if len(ids_encontrados) >= 3:
            call_text = (
                f"**P1:** <@{ids_encontrados[1]}>\n"
                f"**P2:** <@{ids_encontrados[2]}>"
            )
        elif len(ids_encontrados) == 2:
            call_text = (
                f"**P1:** <@{ids_encontrados[1]}>\n"
                f"**P2:** Não informado"
            )
        else:
            call_text = "P1/P2 não informados"

        # ── Parsear limite de membros ──────────────────────────────────
        try:
            limite = max(0, int(self.num_membros.value.strip()))
        except ValueError:
            limite = 0  # valor inválido → sem limite

        vagas_valor = f"0/{limite}" if limite > 0 else "Sem limite"

        # ── Pré-popular membros com negociador, P1 e P2 ───────────────
        membros_iniciais: list[str] = []

        # Negociador
        if ids_encontrados:
            membros_iniciais.append(f"<@{ids_encontrados[0]}>")

        # P1
        if len(ids_encontrados) >= 2:
            p1_mention = f"<@{ids_encontrados[1]}>"
            if p1_mention not in membros_iniciais:
                membros_iniciais.append(p1_mention)

        # P2
        if len(ids_encontrados) >= 3:
            p2_mention = f"<@{ids_encontrados[2]}>"
            if p2_mention not in membros_iniciais:
                membros_iniciais.append(p2_mention)

        valor_membros_inicial = (
            ", ".join(membros_iniciais)
            if membros_iniciais
            else "Nenhum membro confirmado ainda."
        )

        # Ajusta contador de vagas se membros iniciais já foram adicionados
        if limite > 0 and membros_iniciais:
            vagas_valor = f"{len(membros_iniciais)}/{limite}"

        # ── Montar Embed ───────────────────────────────────────────────
        embed = ui.build_embed(
            title="📝 RELATÓRIO DE AÇÃO",
            description=descricao,
            color=cor,
        )

        # Thumbnail = foto de perfil do bot (logo da polícia)
        if interaction.client.user and interaction.client.user.display_avatar:
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)

        embed.add_field(name="1️⃣ AÇÃO",             value=self.qual_acao.value.capitalize(),  inline=False)
        embed.add_field(name="2️⃣ OPONENTE",         value=self.org_envolvida.value.capitalize(), inline=False)
        embed.add_field(name="3️⃣ NEGOCIADOR",       value=negociador_mention,                  inline=False)
        embed.add_field(name="4️⃣ CALL P1/P2",       value=call_text,                           inline=False)
        embed.add_field(name="5️⃣ RESULTADO",        value=texto_resultado,                     inline=False)
        embed.add_field(name="6️⃣ ITENS APREENDIDOS",value=texto_itens,                         inline=False)
        embed.add_field(name=FIELD_LIMITE,           value=vagas_valor,                         inline=True)
        embed.add_field(name=FIELD_MEMBROS,          value=valor_membros_inicial,                inline=False)

        view = ViewParticipacao()

        # ── Enviar nos canais ──────────────────────────────────────────
        enviados = 0
        for canal_id in CANAIS_ENVIO:
            canal = interaction.client.get_channel(canal_id)
            if isinstance(canal, discord.TextChannel):
                await canal.send(embed=embed, view=view)
                enviados += 1

        if enviados > 0:
            await interaction.response.send_message(
                embed=ui.build_success_embed("Relatório de ação registrado e enviado com sucesso!"), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=ui.build_warn_embed(
                    "Relatório gerado, mas não encontrei os canais de envio. "
                    "Verifique os IDs em `CANAIS_ENVIO`."
                ),
                ephemeral=True,
            )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            embed=ui.build_error_embed("Ocorreu um erro ao processar o formulário. Tente novamente."), ephemeral=True
        )
        raise error  # propaga para o log do bot


# ══════════════════════════════════════════════
# VIEW DO PAINEL (botão que abre o modal)
# ══════════════════════════════════════════════
class ViewAcao(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Registrar Ação",
        style=discord.ButtonStyle.primary,
        custom_id="botao_registro_acao_permanente",
        emoji="📝",
    )
    async def botao_registrar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(ModalAcao())


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════
class AcaoCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._views_registered = False

    async def cog_load(self) -> None:
        """
        Chamado UMA vez pelo discord.py quando o cog é carregado via add_cog.
        É o local correto para registrar views persistentes — não on_ready,
        que pode disparar múltiplas vezes em reconexões e gerar duplicatas.
        """
        if not self._views_registered:
            self.bot.add_view(ViewAcao())
            self.bot.add_view(ViewParticipacao())
            self._views_registered = True

    # ------------------------------------------------------------------
    # COMANDO: setup do painel
    # ------------------------------------------------------------------

    @app_commands.command(name="painel_acao", description="Envia o painel de registro de ações no canal atual.")
    @app_commands.default_permissions(administrator=True)
    async def setup_painel(self, interaction: discord.Interaction) -> None:
        """Envia o painel de registro de ações no canal atual."""
        embed = ui.build_embed(
            title="🚓 Central de Registros de Ações",
            description=(
                "Clique no botão abaixo para preencher o relatório da operação.\n\n"
                "📌 **Instruções rápidas:**\n"
                "• Informe os IDs do Negociador, P1 e P2 separados por espaço\n"
                "• No campo Resultado, escreva **Win** ou **Loss** na primeira linha\n"
                "  e os itens apreendidos nas linhas seguintes (apenas para Win)\n"
                "• Defina o número máximo de membros (0 = sem limite)"
            )
        )
        await interaction.channel.send(embed=embed, view=ViewAcao())
        await interaction.response.send_message(
            embed=ui.build_success_embed("Painel de ação enviado com sucesso!"), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AcaoCog(bot))
