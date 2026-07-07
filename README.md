# 🚔 Bot FBI — Miami City (GTA RP)

Bot de gerenciamento interno do **FBI** para servidores de GTA RP / FiveM, desenvolvido com **discord.py 2.x** e **Python 3.13**. Automatiza toda a burocracia administrativa da corporação diretamente pelo Discord: cadastro de agentes, ações táticas, sistema disciplinar, corregedoria, cursos, exonerações e muito mais.

> **Filosofia do projeto:** Eliminar processos manuais. Cada módulo (cog) é independente, utiliza **Views Persistentes** (botões que sobrevivem a reinicializações) e registra logs detalhados em canais dedicados.

---

## 📋 Índice

- [Funcionalidades](#-funcionalidades)
- [Arquitetura do Projeto](#-arquitetura-do-projeto)
- [Estrutura de Pastas](#-estrutura-de-pastas)
- [Requisitos](#-requisitos)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Configuração dos Canais](#-configuração-dos-canais)
- [Como Utilizar](#-como-utilizar)
- [Exemplos de Uso](#-exemplos-de-uso)
- [Troubleshooting](#-troubleshooting)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Melhorias Futuras](#-melhorias-futuras)

---

## 🧩 Funcionalidades

### 🪪 Cadastro de Agentes (`cadastro.py`)
- Painel permanente com botão **"Iniciar Meu Registro"**.
- Formulário via Modal (nome, passaporte, telefone).
- Proteção contra registros duplicados.
- Fluxo de aprovação com botões **Aceitar** / **Recusar** (persistentes).
- Atribuição automática de cargo do FBI e formatação do apelido no padrão `ID • Nome`.
- Log de aprovação/recusa enviado ao canal de registros.
- Notificação por DM ao candidato em caso de recusa.

### ❌ Exoneração de Agentes (`demitir.py`)
- Painel permanente com botão **"Iniciar Exoneração"**.
- Modal com ID do oficial, motivo e opção de blacklist (dias, permanente ou vazio).
- Verificação de hierarquia de cargos antes de exonerar.
- Confirmação obrigatória antes de executar (botões **Confirmar** / **Cancelar**).
- Remove todos os cargos do membro e aplica o cargo ADV4 (exonerado).
- Remove o registro do banco de dados.
- Embed detalhado enviado ao canal de exonerações.
- Embed de blacklist permanente enviado ao canal de blacklist (quando aplicável).

### ⚠️ Sistema de Advertências (`advertencia.py`)
- Painel permanente com botão **"Aplicar Advertência"**.
- Modal com ID do oficial, tipo (ADV1–ADV4), duração em dias (opcional) e motivo.
- Quatro níveis de advertência, cada um com cargo correspondente.
- Remove automaticamente o cargo de advertência anterior ao aplicar um novo.
- Verificação de hierarquia de cargos (bot e aplicador).
- Embed no canal de penalidades + log detalhado no canal de logs.
- Notificação por DM ao membro advertido.

### 🎯 Registro de Ações Táticas (`acao.py`)
- Painel permanente com botão **"Registrar Ação"**.
- Modal com 5 campos: ação, oponente, negociador + P1/P2, resultado + itens, nº máximo de membros.
- Geração automática de embed com detalhamento completo (cores dinâmicas Win/Loss).
- Pré-populamento automático dos membros (negociador, P1 e P2).
- Sistema de **Confirmação/Cancelamento de Participação** com controle de vagas (`X/Y`).
- Envio para canais configurados em `CANAIS_ENVIO`.

### 📊 Estatísticas de Ações (`status_acao.py`)
- Banco SQLite dedicado (`acoesmembros.db`) com registro automático de participações.
- **Sincronização automática**: captura embeds de ações em `on_message` e `on_message_edit`.
- `/status_acao` — Estatísticas globais com wins/losses por tipo de ação e winrate.
- `/status_membro` — Ranking top-15 ou ficha individual com histórico detalhado.
- `/setup_status` — Embed fixo de estatísticas globais em canal dedicado (atualiza automaticamente).
- `/sync_acoes` — Importação retroativa de histórico de mensagens.
- Cache limitado (2000 mensagens) para evitar crescimento de memória.
- Lista de ações canônicas: Nióbio, Banco Central, Banco Paleto, Porta Aviões, Joalheria, Galinheiro, Açougue, Cinema, Fleeca Praia, Fleeca Life Invader, Fleeca Rota 68.

### 🔒 Registro de Prisão (`registro_prisao.py`)
- Painel permanente com botão **"Registrar Prisão"**.
- Verificação de cargo obrigatório (Curso de Prisão).
- Proteção contra múltiplos formulários simultâneos por usuário.
- Criação de **canal temporário privado** para o fluxo guiado.
- Formulário com 12 perguntas sequenciais (QRA, oficiais, preso, artigos, multa, advogado, fiança).
- Upload de **provas fotográficas** (PNG/JPG) — 1 a 5 imagens por mensagem.
- **Download antecipado** das imagens (resolve o bug de URLs expiradas do Discord).
- Timeout de 10 minutos por pergunta + 1 hora global de segurança.
- Embed final detalhado com imagem principal + provas adicionais.
- Canal temporário deletado automaticamente após finalizar.

### 🕵️ Corregedoria (`corregedoria.py`)
- Painel permanente com **Select Menu** de categorias:
  - 🛡️ Ticket de Corregedoria
  - 🚫 Denúncia de Oficial contra Oficial
  - 🧾 Reversão de Punição
  - 🎧 Suporte
- Modal obrigatório com relato detalhado ao abrir ticket.
- Criação de canal privado com permissões configuradas (usuário + corregedoria).
- **4 botões de controle** no ticket:
  - 🛎️ **Solicitar Atendimento** — pinga a equipe novamente.
  - 📌 **Assumir Ticket** — renomeia o canal com emoji da categoria.
  - 👉 **Pokar Membro** — adiciona outro membro ao ticket via modal de ID.
  - 🔒 **Encerrar Ticket** — modal com motivo, veredito e punição aplicada.
- **Transcript HTML** gerado ao fechar via `chat_exporter` (enviado por DM ou canal de logs).
- Proteção contra tickets duplicados por usuário.
- Log estruturado de todas as ações no canal de logs.

### 📚 Sistema de Cursos (`cursos.py`)
- Painel permanente com botão **"📅 Agendar Curso"** (restrito a Instrutores/Admins).
- Modal com nome do curso, ID do cargo, data, hora e local.
- Validação de data (`DD/MM/AAAA`), hora (`18h00` ou `18:00`) e hierarquia de cargos.
- Proteção contra escalada de privilégios (cargo do curso deve estar abaixo do de Instrutor).
- Embed de aviso no canal de cursos com menção `@everyone`.
- Botão **"📩 Solicitar Curso"** no aviso para os alunos.
- Embed de solicitação pendente enviado ao canal de pendências.
- **Avaliação pelo instrutor** com botões **Aprovar** / **Reprovar**:
  - Aprovação: concede o cargo do curso automaticamente.
  - Reprovação: envia DM ao aluno com mensagem de incentivo.

### 🗓️ Convocação para Alinhamento (`alinhamento.py`)
- Painel permanente com botão **"📋 Preencher Convocação"**.
- Modal com ID do agente, data e horário.
- Validação de data (`DD/MM/AAAA`) e horário (`00h00` / `00:00`).
- Embed de convocação no canal de alinhamento com menção ao convocado.
- Link direto para a call de alinhamento.
- Log detalhado no canal de logs.

### 🚪 Registro de Ausência (`ausencia.py`)
- Painel permanente com botão **"Solicitar Ausência"**.
- Modal com QRA, data de início, data de término e motivo.
- Validação de datas no formato `DD/MM/YYYY`.
- Embed de registro no canal de logs com período formatado.

### 📂 Aba de Provas (`provas.py`)
- Painel permanente com botões **"📂 Crie seu chat"** e **"🗑️ Deletar Chat"**.
- Criação de **categoria privada** com o nome do oficial, contendo 4 canais:
  - `👤・identidade`
  - `🗯・chat`
  - `📸・provas`
  - `🎫・boletins-de-ocorrencia`
- Acesso restrito ao oficial e ao bot.
- Verificação de cargo FBI obrigatória.
- Proteção contra categorias duplicadas.
- Exclusão de categoria com **confirmação obrigatória** (apenas admins).
- Validação de padrão de canais antes de permitir exclusão.

### 🤖 Monitoramento e Infraestrutura
- Monitor de recursos a cada 30 segundos (memória, tasks asyncio, threads, latência).
- Alertas automáticos para uso de memória > 200MB ou > 50 tasks.
- Faulthandler habilitado para diagnóstico de crashes fatais.
- Signal handlers para SIGTERM/SIGINT (Docker).
- Exception handler global do asyncio.
- Logging completo em console + arquivo (`bot.log`).
- Sincronização global de Slash Commands no `setup_hook`.

---

## 🏗️ Arquitetura do Projeto

O projeto segue uma arquitetura **modular baseada em Cogs** do discord.py:

```
┌──────────────────────────────┐
│           main.py            │  ← Ponto de entrada, logging, monitor
│     (MyBot + setup_hook)     │
└──────────┬───────────────────┘
           │ carrega
           ▼
┌──────────────────────────────┐
│         cogs/                │  ← Módulos independentes (11 cogs)
│  cadastro, demitir, acao,    │
│  advertencia, corregedoria,  │
│  registro_prisao, provas,    │
│  status_acao, cursos,        │
│  alinhamento, ausencia       │
└──────────┬───────────────────┘
           │ utiliza
           ▼
┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐
│   utils/       │  │   services/      │  │     data/         │
│ ui.py          │  │ membro_service   │  │ db_setup, crud,   │
│ logger.py      │  │ (SQLAlchemy ORM) │  │ db_session        │
│ permissao.py   │  └──────────────────┘  └───────────────────┘
└────────────────┘
```

**Persistência de dados:**
- **SQLAlchemy + SQLite** (`oficiais-fbi.db`) — membros, advertências, prisões.
- **SQLite direto** (`acoesmembros.db`) — participações em ações táticas.
- **SQLite direto** (`eventos.db`) — log de eventos do sistema.
- **JSON** (`acoes_stats.json`) — cache de estatísticas globais de ações.

---

## 📁 Estrutura de Pastas

```
Bot civil meta city s6/
├── main.py                         # Ponto de entrada, classe MyBot, monitor de recursos
├── .env                            # Variáveis de ambiente (token, guild IDs)
├── requirements.txt                # Dependências Python
├── Dockerfile                      # Imagem Docker (Python 3.13-slim)
├── docker-compose.yml              # Orquestração com limites de memória e logging
├── .gitignore                      # Arquivos ignorados pelo Git
│
├── cogs/                           # Módulos de funcionalidades (11 cogs)
│   ├── __init__.py                 # Inicializador do pacote
│   ├── cadastro.py                 # Registro e aprovação de agentes
│   ├── demitir.py                  # Sistema de exoneração com blacklist
│   ├── advertencia.py              # Sistema disciplinar (ADV1–ADV4)
│   ├── acao.py                     # Registro de ações táticas com participação
│   ├── status_acao.py              # Estatísticas e ranking de ações
│   ├── registro_prisao.py          # Formulário guiado de registro de prisão
│   ├── corregedoria.py             # Sistema de tickets internos
│   ├── cursos.py                   # Agendamento e avaliação de cursos
│   ├── alinhamento.py              # Convocação para alinhamentos/reuniões
│   ├── ausencia.py                 # Solicitação de ausência
│   └── provas.py                   # Criação de categorias individuais de provas
│
├── services/                       # Serviços de domínio
│   └── membro_service.py           # CRUD de membros com SQLAlchemy ORM
│
├── data/                           # Camada de acesso a dados
│   ├── __init__.py                 # Inicializador do pacote
│   ├── db_setup.py                 # Setup do engine SQLAlchemy
│   ├── db_session.py               # Gerenciamento de sessões
│   └── crud.py                     # Operações CRUD genéricas
│
├── utils/                          # Utilitários compartilhados
│   ├── __init__.py                 # Inicializador do pacote
│   ├── ui.py                       # Design system (cores, embeds padrão, emojis)
│   ├── logger.py                   # Logger com persistência em SQLite (eventos.db)
│   └── permissao.py                # Helper de verificação de permissão admin
│
├── events/                         # Listeners de eventos (extensível)
│   └── __init__.py                 # Inicializador do pacote
│
├── teste/                          # Scripts de diagnóstico e teste
│   └── diagnostico_db.py           # Diagnóstico do banco de dados
│
├── oficiais-fbi.db                 # Banco SQLite de membros (gerado automaticamente)
├── eventos.db                      # Banco SQLite de log de eventos (gerado automaticamente)
└── bot.log                         # Arquivo de log do bot (gerado automaticamente)
```

---

## 📦 Requisitos

### Software necessário

| Requisito | Versão | Observação |
|---|---|---|
| **Python** | 3.10+ (recomendado 3.13) | O Dockerfile utiliza `python:3.13-slim` |
| **pip** | Última versão | Gerenciador de pacotes Python |
| **Git** | Qualquer versão | Para clonar o repositório |
| **Docker** *(opcional)* | 20.10+ | Para deploy em container |
| **Docker Compose** *(opcional)* | 2.x+ | Orquestração do container |

### Dependências Python

```
discord.py         # Framework principal do bot
python-dotenv      # Carregamento de variáveis de ambiente (.env)
sqlalchemy         # ORM para banco de dados SQLite
aiohttp            # Download assíncrono de imagens
chat-exporter      # Geração de transcript HTML para tickets
```

### Discord Developer Portal

Antes de iniciar, você precisa criar uma aplicação no [Discord Developer Portal](https://discord.com/developers/applications):

1. Acesse o portal e clique em **"New Application"**.
2. Dê um nome ao bot (ex: `FBI Miami City`).
3. Vá em **Bot** → clique em **"Add Bot"**.
4. Copie o **Token** (será usado no arquivo `.env`).
5. Em **Bot → Privileged Gateway Intents**, habilite:
   - ✅ **PRESENCE INTENT**
   - ✅ **SERVER MEMBERS INTENT**
   - ✅ **MESSAGE CONTENT INTENT**
6. Em **OAuth2 → URL Generator**, selecione os escopos:
   - ✅ `bot`
   - ✅ `applications.commands`
7. Em **Bot Permissions**, selecione:
   - ✅ Administrator *(recomendado)*

   Ou, para permissões granulares:

   | Permissão | Motivo |
   |---|---|
   | Manage Channels | Criar/deletar canais temporários |
   | Manage Roles | Atribuir/remover cargos |
   | Manage Nicknames | Formatar apelido dos agentes |
   | Send Messages | Enviar embeds e mensagens |
   | Embed Links | Enviar embeds ricos |
   | Attach Files | Enviar transcripts e imagens |
   | Read Message History | Sync retroativo de ações |
   | Use Slash Commands | Comandos slash |
   | Manage Messages | Gerenciar mensagens em tickets |

8. Copie o link gerado e convide o bot para o seu servidor.

---

## 🚀 Instalação

### Opção 1: Instalação Local

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/bot-fbi-miami-city.git

# 2. Entre na pasta do projeto
cd bot-fbi-miami-city

# 3. Crie um ambiente virtual
python -m venv venv

# 4. Ative o ambiente virtual
# Linux/macOS:
source venv/bin/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
venv\Scripts\activate.bat

# 5. Instale as dependências
pip install -r requirements.txt

# 6. Configure o arquivo .env (veja a seção Configuração)
cp .env.example .env
# Ou crie manualmente o arquivo .env

# 7. Execute o bot
python main.py
```

### Opção 2: Docker (Recomendado para produção)

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/bot-fbi-miami-city.git
cd bot-fbi-miami-city

# 2. Configure o arquivo .env
cp .env.example .env
# Edite o .env com seu token

# 3. Build e execute com Docker Compose
docker-compose up -d --build

# 4. Verificar os logs
docker-compose logs -f bot

# 5. Parar o bot
docker-compose down

# 6. Reiniciar após alterações
docker-compose up -d --build
```

O `docker-compose.yml` inclui:
- **Restart automático** (`unless-stopped`)
- **Limite de memória** de 512MB
- **Timezone** configurado para `America/Sao_Paulo`
- **Rotação de logs** do Docker (máx. 3 arquivos de 10MB)
- **Volume montado** (`.:/app`) para persistência de dados

---

## ⚙️ Configuração

### 1. Arquivo `.env`

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
DISCORD_TOKEN=SEU_TOKEN_AQUI
GUILD_IDS=ID_DO_SERVIDOR_AQUI
```

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DISCORD_TOKEN` | ✅ Sim | Token do bot obtido no Discord Developer Portal |
| `GUILD_IDS` | ✅ Sim | ID(s) do servidor separados por vírgula |

> ⚠️ **NUNCA suba o arquivo `.env` para o repositório.** Certifique-se de que `.env` está no `.gitignore`.

#### Como obter o Token:
1. Acesse o [Discord Developer Portal](https://discord.com/developers/applications).
2. Selecione sua aplicação → **Bot** → **Reset Token** → Copie o token.

#### Como obter o ID do servidor:
1. No Discord, ative o **Modo de Desenvolvedor** (Configurações → Avançado → Modo de Desenvolvedor).
2. Clique com o botão direito no ícone do servidor → **Copiar ID do Servidor**.

---

### 2. IDs de Cargos e Canais

Cada cog possui constantes no topo do arquivo que precisam ser configuradas com os IDs do seu servidor. Abaixo está o mapeamento completo:

#### `cogs/cadastro.py`

```python
Cargos_aprovadores = [SEU_CARGO_RECRUTAMENTO_ID]   # Cargo que pode aprovar registros
Cargo_membro       = SEU_CARGO_FBI_ID               # Cargo atribuído ao aprovar
Canal_logs         = SEU_CANAL_REGISTROS_ID          # Canal de log de registros
canal_aprovacao    = SEU_CANAL_APROVACAO_ID          # Canal onde ficam os registros pendentes
```

#### `cogs/demitir.py`

```python
CARGOS_PERMITIDOS    = [SEU_CARGO_PERMISSAO_ID]     # Cargo que pode exonerar
CARGO_EXONERADO_ID   = SEU_CARGO_ADV4_ID            # Cargo aplicado ao exonerado
CANAL_EXONERACAO_ID  = SEU_CANAL_EXONERACAO_ID      # Canal de log de exonerações
CANAL_BLACKLIST_ID   = SEU_CANAL_BLACKLIST_ID        # Canal de blacklist permanente
```

#### `cogs/advertencia.py`

```python
CARGOS_PERMITIDOS    = [SEU_CARGO_PERMISSAO_ADV_ID] # Cargo que pode aplicar advertências
CARGOS_ADVERTENCIA   = {
    "ADV1": SEU_CARGO_ADV1_ID,
    "ADV2": SEU_CARGO_ADV2_ID,
    "ADV3": SEU_CARGO_ADV3_ID,
    "ADV4": SEU_CARGO_ADV4_ID,
}
CANAL_PENALIDADES_ID = SEU_CANAL_PENALIDADES_ID     # Canal de penalidades
CANAL_LOG_ADV_ID     = SEU_CANAL_LOGS_BOT_ID        # Canal de logs do bot
```

#### `cogs/acao.py`

```python
CANAIS_ENVIO = [SEU_CANAL_ACOES_ID]                 # Canal(is) que recebem relatórios de ações
```

#### `cogs/status_acao.py`

```python
CANAL_STATUS_ID = SEU_CANAL_ACOES_ID                # Canal onde o embed global de estatísticas fica
```

#### `cogs/registro_prisao.py`

```python
CARGO_AUTORIZADO = SEU_CARGO_CURSO_PRISAO_ID        # Cargo obrigatório para registrar prisões
CANAL_REGISTRO   = SEU_CANAL_PAINEL_PRISOES_ID      # Canal que recebe os registros finais
```

#### `cogs/corregedoria.py`

```python
LOG_CHANNEL_ID       = SEU_CANAL_LOGS_BOT_ID        # Canal de logs
TICKET_CATEGORY_ID   = SEU_CATEGORIA_TICKETS_ID     # Categoria onde os tickets são criados
CORREGEDORIA_ROLE_ID = SEU_CARGO_CORREGEDORIA_ID    # Cargo da Corregedoria
```

#### `cogs/cursos.py`

```python
CARGO_INSTRUTOR_ID   = SEU_CARGO_INSTRUTOR_ID       # Cargo de Instrutor
CARGO_POLICIA_ID     = SEU_CARGO_FBI_ID             # Cargo FBI (para menção nos avisos)
CANAL_CURSOS_ID      = SEU_CANAL_AVISOS_CURSOS_ID   # Canal de avisos de cursos
CURSOS_PENDENTES     = SEU_CANAL_SOLICITAR_CURSO_ID # Canal de solicitações pendentes
```

#### `cogs/alinhamento.py`

```python
CARGO_PERMITIDO   = SEU_CARGO_PERMISSAO_ADV_ID     # Cargo que pode convocar
CANAL_ALINHAMENTO = SEU_CANAL_ALINHAMENTO_ID        # Canal de alinhamento
CANAL_LOGS        = SEU_CANAL_LOGS_BOT_ID           # Canal de logs
LINK_CALL         = "URL_DA_CALL_DE_ALINHAMENTO"    # Link direto para a call
```

#### `cogs/ausencia.py`

```python
ID_CANAL_LOGS = SEU_CANAL_LOGS_BOT_ID              # Canal de logs
```

#### `cogs/provas.py`

```python
# Dentro da função criar_ticket:
ID_CARGO_POLICIA = SEU_CARGO_FBI_ID                # Cargo FBI (verificação de permissão)
```

#### `utils/ui.py`

```python
FOOTER_TEXT = "FBI | Miami City"                    # Texto do rodapé de todos os embeds
```

> 💡 **Dica:** Use o **Modo de Desenvolvedor** do Discord para copiar os IDs. Clique com o botão direito em qualquer canal, cargo ou categoria → **Copiar ID**.

---

### 3. Banco de Dados

Os bancos de dados SQLite são criados **automaticamente** na primeira execução do bot:

| Banco | Criado por | Conteúdo |
|---|---|---|
| `oficiais-fbi.db` | `services/membro_service.py` | Membros, advertências, prisões (SQLAlchemy) |
| `acoesmembros.db` | `cogs/status_acao.py` | Participações em ações táticas (SQLite direto) |
| `eventos.db` | `utils/logger.py` | Log de eventos do sistema (SQLite direto) |

> ℹ️ Não é necessário criar os bancos manualmente. O bot inicializa as tabelas automaticamente.

---

## 📡 Configuração dos Canais

Para o funcionamento completo do bot, os seguintes canais precisam ser criados no seu servidor Discord. A tabela abaixo detalha cada canal, sua finalidade e onde configurar o ID:

### Canais Obrigatórios

| Canal | Finalidade | Onde configurar o ID | Sistemas que utilizam |
|---|---|---|---|
| `🔑・registros` | Log de aprovação/recusa de cadastros | `cadastro.py` → `Canal_logs` | Cadastro |
| `📁・aprovação-registro` | Registros pendentes aguardando aprovação | `cadastro.py` → `canal_aprovacao` | Cadastro |
| `🗂️・penalidades` | Embeds de advertências aplicadas | `advertencia.py` → `CANAL_PENALIDADES_ID` | Advertências |
| `🤖・logs-bot` | Logs gerais de todas as ações do bot | `advertencia.py`, `alinhamento.py`, `ausencia.py`, `corregedoria.py` → vários IDs de logs | Advertências, Alinhamento, Ausência, Corregedoria |
| `🔫・ações` | Relatórios de ações táticas e embed de estatísticas | `acao.py` → `CANAIS_ENVIO`, `status_acao.py` → `CANAL_STATUS_ID` | Ações, Status |
| `🦝・painel-prisões` | Registros finais de prisões | `registro_prisao.py` → `CANAL_REGISTRO` | Prisão |
| `📢・alinhamento` | Convocações para alinhamentos | `alinhamento.py` → `CANAL_ALINHAMENTO` | Alinhamento |
| `🚨・avisos-cursos` | Avisos de cursos agendados | `cursos.py` → `CANAL_CURSOS_ID` | Cursos |
| `📋・solicitar-curso` | Solicitações pendentes de cursos | `cursos.py` → `CURSOS_PENDENTES` | Cursos |
| `❌・exonerações` | Registros de exonerações | `demitir.py` → `CANAL_EXONERACAO_ID` | Exoneração |
| `💀・blacklist-permanente` | Registros de blacklist permanente | `demitir.py` → `CANAL_BLACKLIST_ID` | Exoneração |

### Categorias Obrigatórias

| Categoria | Finalidade | Onde configurar o ID |
|---|---|---|
| Categoria de Tickets | Onde os tickets da corregedoria são criados | `corregedoria.py` → `TICKET_CATEGORY_ID` |

### Canais de Voz

| Canal | Finalidade | Onde configurar |
|---|---|---|
| `👑・Aguardando AC` | Call de alinhamento | `alinhamento.py` → `LINK_CALL` (URL completa) |

### Cargos Obrigatórios

| Cargo | Finalidade | Onde configurar |
|---|---|---|
| Cargo FBI (membro) | Atribuído ao aprovar cadastro | `cadastro.py` → `Cargo_membro`, `cursos.py` → `CARGO_POLICIA_ID`, `provas.py` → `ID_CARGO_POLICIA` |
| Cargo de Recrutamento | Pode aprovar/recusar cadastros | `cadastro.py` → `Cargos_aprovadores` |
| Cargo Perm. Advertência | Pode advertir, convocar e exonerar | `advertencia.py` → `CARGOS_PERMITIDOS`, `alinhamento.py` → `CARGO_PERMITIDO`, `demitir.py` → `CARGOS_PERMITIDOS` |
| Cargos ADV1–ADV4 | Advertências de nível 1 a 4 | `advertencia.py` → `CARGOS_ADVERTENCIA` |
| Cargo Corregedoria | Pode gerenciar tickets | `corregedoria.py` → `CORREGEDORIA_ROLE_ID` |
| Cargo Instrutor | Pode agendar cursos | `cursos.py` → `CARGO_INSTRUTOR_ID` |
| Cargo Curso de Prisão | Pode registrar prisões | `registro_prisao.py` → `CARGO_AUTORIZADO` |

---

## 🎮 Como Utilizar

### Comandos de Setup (Administradores)

Esses comandos criam os **painéis permanentes** que ficam fixos nos canais. Precisam ser executados apenas **uma vez** por canal:

| Comando | Descrição | Canal recomendado |
|---|---|---|
| `/setup_registro` | Cria o painel de cadastro de agentes | Canal de cadastro |
| `/setup_demissao` | Cria o painel de exoneração | Canal de exonerações |
| `/setup_advertencia` | Cria o painel de advertências | Canal de penalidades |
| `/painel_acao` | Cria o painel de registro de ações | Canal de ações |
| `/setup_status` | Posta o embed global de estatísticas | Canal de ações |
| `/setup_prisao` | Cria o painel de registro de prisões | Canal de prisões |
| `/setup_corregedoria` | Cria o painel de tickets da corregedoria | Canal de corregedoria |
| `/setup_cursos` | Cria o painel de agendamento de cursos | Canal de cursos |
| `/setup_alinhamento` | Cria o painel de convocação para alinhamento | Canal de alinhamento |
| `/setup_ausencia` | Cria o painel de registro de ausência | Canal de ausência |
| `/setup_provas` | Cria o painel de criação de abas de provas | Canal de provas |

> ⚠️ **Importante:** Esses comandos enviam mensagens com **Views Persistentes**. Não é necessário executá-los novamente após reiniciar o bot — os botões continuam funcionando.

### Comandos Operacionais

| Comando | Permissão | Descrição |
|---|---|---|
| `/listar_registros` | Administrador | Lista todos os agentes aprovados |
| `/status_acao` | Todos | Exibe estatísticas globais de ações por tipo |
| `/status_membro` | Todos | Ranking top-15 (sem menção) ou ficha individual (com @menção) |
| `/sync_acoes [limite]` | Administrador | Importa histórico retroativo de ações (padrão: 200 mensagens) |
| `/comandos` | Todos | Lista todos os comandos disponíveis |

### Fluxos Principais

#### Fluxo de Cadastro
```
Usuário clica "Iniciar Meu Registro"
    → Preenche modal (nome, passaporte, telefone)
    → Embed enviado ao canal de aprovação
    → Aprovador clica "Aceitar" ou "Recusar"
    → Se aceito: cargo FBI atribuído + apelido formatado
    → Se recusado: DM de notificação ao candidato
```

#### Fluxo de Ação Tática
```
Membro clica "Registrar Ação"
    → Preenche modal (ação, oponente, negociador/P1/P2, resultado, vagas)
    → Embed de relatório enviado ao canal de ações
    → Membros clicam "Confirmar Participação" (controle de vagas)
    → Estatísticas atualizadas automaticamente em tempo real
```

#### Fluxo de Ticket (Corregedoria)
```
Usuário seleciona categoria no menu
    → Preenche modal com relato detalhado
    → Canal privado criado automaticamente
    → Staff assume o ticket (renomeia canal)
    → Staff pode pokar membros (adicionar ao ticket)
    → Staff encerra com motivo, veredito e punição
    → Transcript HTML gerado e enviado por DM
    → Canal deletado automaticamente
```

#### Fluxo de Prisão
```
Membro clica "Registrar Prisão"
    → Canal temporário privado criado
    → Bot faz 12 perguntas sequenciais
    → Membro envia fotos de provas (1-5 imagens)
    → Bot baixa as imagens antecipadamente
    → Embed final com todas as informações + fotos
    → Canal temporário deletado após 5 segundos
```

---

## 📝 Exemplos de Uso

### Exemplo: Configurar o bot pela primeira vez

```bash
# 1. Instalar e iniciar o bot
python main.py

# 2. No Discord, execute os setups nos canais corretos:
/setup_registro       # no canal de cadastro
/setup_demissao       # no canal de exonerações
/setup_advertencia    # no canal de penalidades
/painel_acao          # no canal de ações
/setup_status         # no canal de ações (embed fixo de estatísticas)
/setup_prisao         # no canal de prisões
/setup_corregedoria   # no canal de corregedoria
/setup_cursos         # no canal de cursos
/setup_alinhamento    # no canal de alinhamento
/setup_ausencia       # no canal de ausência
/setup_provas         # no canal de provas
```

### Exemplo: Registrar uma ação tática

1. Clique no botão **"📝 Registrar Ação"** no painel.
2. Preencha o modal:
   - **Ação:** `Banco Central`
   - **Oponente:** `França`
   - **Negociador | P1 | P2:** `123456789012345678 234567890123456789 345678901234567890`
   - **Resultado + Itens:** `Win 8 SMG 2 AR`
   - **Nº máximo de membros:** `12`
3. O embed será gerado automaticamente com cores (verde para Win, vermelho para Loss).
4. Os membros podem clicar em **"✋ Confirmar Participação"** para entrar na lista.

### Exemplo: Verificar estatísticas

```
/status_acao                    # Estatísticas globais de todas as ações
/status_membro                  # Ranking top-15 de participação
/status_membro @JogadorX        # Ficha individual do jogador
```

### Exemplo: Importar histórico de ações

```
/sync_acoes             # Importa as últimas 200 mensagens do canal
/sync_acoes limite:500  # Importa as últimas 500 mensagens do canal
```

---

## 🔧 Troubleshooting

### Token inválido

```
discord.errors.LoginFailure: Improper token has been passed.
```

**Solução:** Verifique se o token no arquivo `.env` está correto e sem espaços extras. Gere um novo token no [Discord Developer Portal](https://discord.com/developers/applications) se necessário.

---

### Bot sem permissões

```
discord.errors.Forbidden: 403 Forbidden (error code: 50013): Missing Permissions
```

**Solução:**
1. Verifique se o bot tem a permissão **Administrator** no servidor.
2. Ou conceda as permissões granulares listadas na seção [Requisitos](#-requisitos).
3. Certifique-se de que o cargo do bot está **acima** dos cargos que ele precisa gerenciar na hierarquia.

---

### IDs incorretos

```
Erro: "Canal de penalidades não encontrado" ou "Membro não encontrado neste servidor"
```

**Solução:**
1. Ative o **Modo de Desenvolvedor** (Configurações → Avançado → Modo de Desenvolvedor).
2. Copie os IDs clicando com o botão direito → **Copiar ID**.
3. Substitua os IDs nas constantes do arquivo de cada cog.

---

### Banco de dados não criado / corrompido

```
sqlalchemy.exc.OperationalError: unable to open database file
```

**Solução:**
1. Verifique se o bot tem permissão de escrita no diretório.
2. Em Docker, verifique se o volume está montado corretamente (`volumes: - .:/app`).
3. Exclua os arquivos `.db` e reinicie o bot — eles serão recriados automaticamente.

---

### Dependências ausentes

```
ModuleNotFoundError: No module named 'discord'
```

**Solução:**
```bash
pip install -r requirements.txt
```

Se estiver usando ambiente virtual, certifique-se de que ele está ativado:
```bash
# Linux/macOS:
source venv/bin/activate
# Windows:
.\venv\Scripts\Activate.ps1
```

---

### Intents não habilitadas

```
discord.errors.PrivilegedIntentsRequired: Shard ID None is requesting privileged intents...
```

**Solução:**
1. Acesse o [Discord Developer Portal](https://discord.com/developers/applications).
2. Selecione sua aplicação → **Bot**.
3. Habilite todos os **Privileged Gateway Intents**:
   - ✅ PRESENCE INTENT
   - ✅ SERVER MEMBERS INTENT
   - ✅ MESSAGE CONTENT INTENT

---

### Botões não funcionam após reiniciar

**Solução:** Isso geralmente não deveria acontecer, pois todas as Views são registradas com `custom_id` fixo no `cog_load()`. Verifique:
1. Se todas as cogs estão carregando sem erro nos logs.
2. Se o `custom_id` dos botões não foi alterado acidentalmente.
3. Execute os logs com `docker-compose logs -f bot` para verificar erros no carregamento.

---

### Chat exporter não funciona

```
⚠️ `chat_exporter` não está instalado.
```

**Solução:**
```bash
pip install chat-exporter
```

---

### Erro "Unknown interaction" nos botões

**Causa:** O Discord espera uma resposta em até 3 segundos. Se o bot demora mais, a interação expira.

**Solução:** Isso já é tratado no código com `interaction.response.defer()`. Se persistir:
1. Verifique a latência do bot nos logs (`Latência Gateway: XXms`).
2. Verifique se o servidor/VPS não está sobrecarregado.
3. Consulte os alertas no monitor de recursos (memória > 200MB, tasks > 50).

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Versão | Finalidade |
|---|---|---|
| **Python** | 3.13 | Linguagem principal |
| **discord.py** | 2.x | Framework do bot Discord |
| **SQLAlchemy** | 2.x | ORM para banco de dados |
| **SQLite** | 3 | Banco de dados embarcado |
| **aiohttp** | 3.x | Cliente HTTP assíncrono |
| **chat-exporter** | — | Geração de transcripts HTML |
| **python-dotenv** | — | Variáveis de ambiente |
| **Docker** | — | Containerização |
| **Docker Compose** | — | Orquestração de containers |

---

## 🔮 Melhorias Futuras

- [ ] **Dashboard Web** — Painel administrativo web para visualizar estatísticas e gerenciar membros.
- [ ] **Sistema de Promoções** — Fluxo automatizado de promoção de cargo com aprovação.
- [ ] **Backup automático** — Rotina de backup dos bancos SQLite com notificação.
- [ ] **Sistema de Pontuação** — Pontuação automática baseada em ações, prisões e cursos.
- [ ] **Relatórios periódicos** — Embeds semanais/mensais com resumo de atividades.
- [ ] **Migração para PostgreSQL** — Para maior robustez em produção de alto volume.
- [ ] **Testes automatizados** — Suite de testes unitários e de integração.
- [ ] **Configuração via `.env`** — Migrar todos os IDs hardcoded para variáveis de ambiente.
- [ ] **Internacionalização** — Suporte a múltiplos idiomas.
- [ ] **Rate limiting** — Controle de uso excessivo de comandos por usuário.

---

<div align="center">

**Desenvolvido com ❤️ para a comunidade GTA RP**

`FBI | Miami City`

</div>
