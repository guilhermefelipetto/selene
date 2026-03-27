import glob
import json
import os
from collections import deque
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

import selene_brain
from ferramentas import PASTA_QUARTO

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', 0))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

canal_ativo = None 
ARQUIVO_TAREFAS = os.path.join(PASTA_QUARTO, "tarefas.json")

@bot.event
async def on_ready():
    print(f'🌙 {bot.user.name} 3.5 online! Proatividade ativada.')
    verificador_de_tarefas.start()

historico_passivo = {} 

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    canal_id = message.channel.id
    if canal_id not in historico_passivo:
        historico_passivo[canal_id] = deque(maxlen=40)

    texto = message.content[:600]
    autor = message.author.display_name
    hora_str = message.created_at.strftime("%H:%M")

    if texto and not message.content.startswith('!'):
        historico_passivo[canal_id].append(f"[{hora_str}] {autor}: {texto}")

    await bot.process_commands(message)

@bot.command(name='setllm')
async def alterar_llm(ctx, escolha: str = ""):
    """Troca o modelo de IA em tempo real. Uso: !set_llm gpt-5.4"""

    if ctx.author.id != OWNER_ID:
        await ctx.send(f"❌ Desculpe, {ctx.author.display_name}, mas apenas o meu criador pode alterar meus parâmetros neurais.\nUsando o modelo: {selene_brain.MODELO_ATUAL}")
        return
    
    if not escolha:
        msg = (
            "### 🧠 Gestão de Modelos (LLM)\n"
            "Atualmente estou usando: **" + selene_brain.MODELO_ATUAL + "**\n\n"
            "**Opções disponíveis:**\n"
            "- `deepseek`\n"
            "- `gpt-5.4`\n"
            "- `gpt-5.4-mini`\n"
            "- `gpt-5.4-nano`\n"
            "- `gpt-5.3-codex`\n"
            "- `gpt-5.3-chat-latest`\n\n"
            "*Exemplo: !setllm gpt-5.4*"
        )
        await ctx.send(msg)
        return

    sucesso, nome_formatado = selene_brain.configurar_llm(escolha)
    
    if sucesso:
        await ctx.send(f"✅ **Cérebro Atualizado!**\nProvedor alterado para: **{nome_formatado}**. *Minha percepção parece... diferente agora.*")
    else:
        await ctx.send(f"❌ O modelo `{escolha}` não está na minha lista de compatibilidade.")

@bot.command(name='docker_reset')
async def reset_docker_selene(ctx):
    """Destrói o container atual e cria um novo, limpando bibliotecas instaladas."""
    await ctx.send("🛠️ Entrando no quarto para uma limpeza pesada... (Isso pode levar alguns segundos)")
    
    try:
        import subprocess
        subprocess.run("docker rm -f selene_sandbox", shell=True, check=True)
        
        import ferramentas
        ferramentas.iniciar_docker()
        
        await ctx.send("✨ Quarto limpo! O container foi resetado e o ambiente Python está como novo.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao tentar limpar o quarto: {e}")

@bot.command(name='csm')
async def limpar_memoria_curto_prazo(ctx):
    selene_brain.historico_mensagens.clear()
    await ctx.send("🧹 Memória de curto prazo limpa! Cérebro resetado.")

@bot.command(name='s')
async def falar_com_selene(ctx, *, mensagem: str = ""):
    global canal_ativo
    canal_ativo = ctx.channel

    async with ctx.typing():
        try:
            canal_id = ctx.channel.id
            contexto_chat = "\n".join(historico_passivo.get(canal_id,[]))
            
            if historico_passivo.get(canal_id):
                historico_passivo[canal_id].pop()

            autor_comando = ctx.author.display_name

            info_anexos = ""
            if ctx.message.attachments:
                pasta_uploads = os.path.join(PASTA_QUARTO, "uploads")
                os.makedirs(pasta_uploads, exist_ok=True)
                
                nomes_arquivos = []
                for anexo in ctx.message.attachments:
                    caminho_local = os.path.join(pasta_uploads, anexo.filename)
                    await anexo.save(caminho_local)
                    nomes_arquivos.append(f"/workspace/quarto/uploads/{anexo.filename}")
                
                extensoes_imagem = ['.png', '.jpg', '.jpeg', '.webp']
                info_anexos = "\n[O usuário enviou arquivos/imagens. Estão no /workspace/quarto/uploads/]"

            mensagem_injetada = (
                f"[CONTEXTO RECENTE DO CHAT]\n"
                f"{contexto_chat if contexto_chat else 'Sem histórico recente.'}\n\n"
                f"---\n"
                f"[AÇÃO REQUERIDA]\n"
                f"Usuário {autor_comando} disse: \"{mensagem}\"\n"
                f"{info_anexos}"
            )

            async def enviar_status(texto):
                await ctx.send(f"*{texto}*", delete_after=10)

            resposta_final = await selene_brain.processar_mensagem_usuario(mensagem_injetada, enviar_status)
            
            if resposta_final:
                for i in range(0, len(resposta_final), 1900):
                    await ctx.send(resposta_final[i:i+1900])

            imagens = glob.glob(os.path.join(PASTA_QUARTO, "*.png")) + glob.glob(os.path.join(PASTA_QUARTO, "*.jpg"))
            for img_path in imagens:
                await ctx.send(file=discord.File(img_path))
                os.remove(img_path)

        except Exception as e:
            print(f"ERRO CRÍTICO: {e}")
            await ctx.send(f"Tive um curto-circuito cerebral: {e}")

@tasks.loop(minutes=1)
async def verificador_de_tarefas():
    global canal_ativo
    if not canal_ativo:
        return

    try:
        if not os.path.exists(ARQUIVO_TAREFAS): return
        
        with open(ARQUIVO_TAREFAS, "r", encoding="utf-8") as f:
            tarefas = json.load(f)
            
        agora = datetime.now()
        tarefas_modificadas = False

        for dados in tarefas:
            nome = dados["nome_tarefa"]
            proxima_execucao = datetime.fromisoformat(dados["proxima_execucao"])
            
            if agora >= proxima_execucao:
                print(f"⏰[PROATIVIDADE] Acordando Selene para a tarefa: {nome}")
                
                nova_execucao = agora + timedelta(minutes=dados["intervalo_minutos"])
                dados["proxima_execucao"] = nova_execucao.isoformat()
                tarefas_modificadas = True
                
                prompt_invisivel = f"[SISTEMA - TAREFA AGENDADA: '{nome}']: {dados['instrucao']}. Responda de forma sucinta e humana no chat."
                
                async def enviar_status_background(texto): pass

                resposta_final = await selene_brain.processar_mensagem_usuario(prompt_invisivel, enviar_status_background)
                
                if resposta_final:
                    await canal_ativo.send(f"🔔 **Notificação Automática ({nome}):**\n{resposta_final}")
                
                imagens = glob.glob(os.path.join(PASTA_QUARTO, "*.png")) + glob.glob(os.path.join(PASTA_QUARTO, "*.jpg"))
                for img_path in imagens:
                    await canal_ativo.send(file=discord.File(img_path))
                    os.remove(img_path)

        if tarefas_modificadas:
            with open(ARQUIVO_TAREFAS, "w", encoding="utf-8") as f:
                json.dump(tarefas, f, indent=4)

    except Exception as e:
        print(f"Erro no verificador de tarefas: {e}")

if __name__ == '__main__':
    bot.run(TOKEN)
