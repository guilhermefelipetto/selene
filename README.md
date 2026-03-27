# Selene Server

Assistente para Discord com personalidade própria, memória vetorial, execução de comandos em sandbox Docker, suporte a visão (Gemini) e troca dinâmica de modelos LLM.

## O que este projeto faz

O `selene_server` conecta um bot Discord a um “cérebro” de IA que pode:

- conversar em contexto de canal;
- lembrar informações relevantes via ChromaDB;
- usar ferramentas (ler/escrever arquivos, terminal, web, análise de imagem);
- executar tarefas recorrentes agendadas;
- alternar entre DeepSeek e modelos OpenAI em tempo real.

## Principais recursos

- Bot Discord com comandos administrativos e de conversa.
- Histórico passivo por canal para contexto recente.
- Memória vetorial local (`quarto_da_selene/vetor_db`).
- Sandbox Docker para execução isolada de comandos.
- Ferramentas de busca web e leitura de links.
- Análise de imagens via Gemini.
- Scheduler simples para notificações automáticas no canal.

## Stack

- Python 3.10+
- `discord.py`
- `openai` (AsyncOpenAI)
- `chromadb` + `sentence-transformers`
- Docker
- `google-genai`

## Estrutura do projeto

```txt
.
├── main.py                  # Entrada do bot Discord
├── selene_brain.py          # Orquestração de LLM + tool calls
├── ferramentas.py           # Implementação das ferramentas
├── requirements.txt
├── quarto_da_selene/        # Estado local (plano, tarefas, vetor_db, uploads)
└── README.md
```

## Pré-requisitos

- Python 3.10 ou superior
- Docker instalado e rodando
- Token de bot no Discord
- Chaves de API

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração (.env)

Crie um arquivo `.env` na raiz com:

```env
DISCORD_TOKEN=seu_token_do_discord
OWNER_ID=123456789012345678

# LLMs
DEEPSEEK_API_KEY=sua_chave_deepseek
OPENAI_API_KEY=sua_chave_openai

# Visão (opcional)
GEMINI_API_KEY=sua_chave_gemini
```

### Observações importantes

- `DISCORD_TOKEN` é obrigatório para o bot iniciar.
- `OWNER_ID` controla quem pode usar comandos administrativos como `!setllm`.
- Sem `GEMINI_API_KEY`, a ferramenta de análise de imagem fica indisponível.

## Executando

```bash
python main.py
```

Ao subir, o sistema inicializa automaticamente o container Docker de sandbox e o loop de tarefas agendadas.

## Comandos do bot

- `!s <mensagem>`: envia uma solicitação para a Selene.
- `!setllm [modelo]`: troca o modelo ativo (somente `OWNER_ID`).
- `!csm`: limpa memória de curto prazo da conversa.
- `!docker_reset`: recria o container de sandbox.

### Modelos suportados em `!setllm`

- `deepseek`
- `gpt-5.4`
- `gpt-5.4-mini`
- `gpt-5.4-nano`
- `gpt-5.3-codex`
- `gpt-5.3-chat-latest`

## Persistência local

Dados gerados em runtime ficam em `quarto_da_selene/`:

- `plano_de_acao.md`
- `tarefas.json`
- `vetor_db/`
- uploads e artefatos temporários

Esse diretório está no `.gitignore`.

## Segurança e operação

- A execução de comandos ocorre em container Docker dedicado.
- O bot usa permissões de `message_content` no Discord; configure no painel de aplicações.
- Revise o prompt de sistema e ferramentas antes de uso em produção pública.

## Próximos passos sugeridos

- [ ] Adicionar logs estruturados e níveis de logging.
- [ ] Criar testes para funções de ferramenta e scheduler.
- [ ] Adicionar `docker-compose.yml` para setup mais simples.
- [ ] Dinamização de Chaves API via Discord (com Mensagem Privada)
- [ ] Adicionar funções de gerenciamento do servidor no discord

## Licença

Defina a licença do projeto: MIT
