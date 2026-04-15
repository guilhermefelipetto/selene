import asyncio
import json
import os
import subprocess
import time
from datetime import datetime, timedelta

import chromadb
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
from chromadb.utils import embedding_functions
from ddgs import DDGS
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

PASTA_QUARTO = os.path.abspath("quarto_da_selene")

os.makedirs(PASTA_QUARTO, exist_ok=True)

ARQUIVO_PLANO = os.path.join(PASTA_QUARTO, "plano_de_acao.md")
ARQUIVOS_PROTEGIDOS = ["plano_de_acao.md"]
ARQUIVO_TAREFAS = os.path.join(PASTA_QUARTO, "tarefas.json")

CHROMA_PATH = os.path.join(PASTA_QUARTO, "vetor_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

GEMINI_KEY = os.getenv('GEMINI_API_KEY')
vision_client = None
if GEMINI_KEY:
    vision_client = genai.Client(api_key=GEMINI_KEY)

default_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

if not os.path.exists(ARQUIVO_PLANO): 
    with open(ARQUIVO_PLANO, "w", encoding="utf-8") as f:
        f.write("# Meu Plano de Ação\n\nUse este arquivo para anotar passos de tarefas complexas.")

if not os.path.exists(ARQUIVO_TAREFAS):
    with open(ARQUIVO_TAREFAS, "w", encoding="utf-8") as f:
        json.dump([], f)

CONTAINER_NAME = "selene_sandbox_publica"

def iniciar_docker():
    """Inicia o container Docker em background se não estiver rodando."""
    res = subprocess.run(f"docker ps -q -f name={CONTAINER_NAME}", shell=True, capture_output=True, text=True)
    if not res.stdout.strip():
        print("🐳 [SISTEMA] Iniciando o container Docker da Selene...")
        subprocess.run(f"docker rm -f {CONTAINER_NAME}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        cmd = (
            f"docker run -d --name {CONTAINER_NAME} "
            f"-v {PASTA_QUARTO}:/workspace/quarto "
            f"-w /workspace/quarto "
            f"python:3.10-slim tail -f /dev/null"
        )
        subprocess.run(cmd, shell=True, check=True)
        
        print("📦[SISTEMA] Instalando utilitários básicos no Docker (tree)...")
        subprocess.run(f"docker exec {CONTAINER_NAME} apt-get update", shell=True, capture_output=True)
        subprocess.run(f"docker exec {CONTAINER_NAME} apt-get install -y tree git", shell=True, capture_output=True)

        subprocess.run(f"docker exec {CONTAINER_NAME} git config --global user.name 'Selene AI'", shell=True)
        subprocess.run(f"docker exec {CONTAINER_NAME} git config --global user.email 'selene@sandbox.local'", shell=True)
        subprocess.run(f"docker exec {CONTAINER_NAME} git config --global init.defaultBranch main", shell=True)
        print("✅ [SISTEMA] Docker da Selene pronto e rodando!")

iniciar_docker()

def traduzir_caminho(caminho_ia):
    """Permite que a IA use caminhos do Docker e traduz para o seu Ubuntu."""
    caminho_ia = caminho_ia.replace("\\", "/")
    if caminho_ia.startswith("/workspace/quarto"):
        relativo = caminho_ia.replace("/workspace/quarto", "").lstrip("/")
        return os.path.join(PASTA_QUARTO, relativo)
    else:
        # Se ela passar só o nome do arquivo, assume que é no quarto
        return os.path.join(PASTA_QUARTO, caminho_ia)

def listar_arquivos(subpasta=""):
    caminho = traduzir_caminho(subpasta) if subpasta else PASTA_QUARTO
    if not os.path.exists(caminho): return f"Erro: A pasta não existe."
    itens = os.listdir(caminho)
    if not itens: return f"A pasta está vazia."
    detalhes =[f"📁 {i}/" if os.path.isdir(os.path.join(caminho, i)) else f"📄 {i}" for i in itens]
    return f"Conteúdo: {', '.join(detalhes)}"

def ver_arvore_arquivos(caminho="/workspace"):
    """Roda o comando 'tree' no Docker para ela entender a estrutura de projetos grandes."""
    cmd = f'docker exec {CONTAINER_NAME} tree {caminho} -L 3'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout if res.stdout else res.stderr

def criar_pasta(nome_pasta):
    try:
        caminho = traduzir_caminho(nome_pasta)
        os.makedirs(caminho, exist_ok=True)
        return f"Pasta '{nome_pasta}' criada com sucesso."
    except Exception as e: return f"Erro ao criar pasta: {e}"

def ler_arquivo(nome_arquivo):
    try:
        caminho = traduzir_caminho(nome_arquivo)
        if not os.path.exists(caminho): return f"Erro: Arquivo não existe."
        with open(caminho, "r", encoding="utf-8") as f: return f.read()
    except Exception as e: return f"Erro ao ler: {e}"

def escrever_arquivo(nome_arquivo, conteudo):
    try:
        caminho = traduzir_caminho(nome_arquivo)
        with open(caminho, "w", encoding="utf-8") as f: f.write(conteudo)
        return f"Arquivo '{nome_arquivo}' salvo com sucesso."
    except Exception as e: return f"Erro ao escrever: {e}"

def apagar_arquivo(nome_arquivo):
    try:
        if nome_arquivo in ARQUIVOS_PROTEGIDOS: return f"Erro: Arquivo protegido."
        caminho = traduzir_caminho(nome_arquivo)
        if os.path.exists(caminho):
            os.remove(caminho)
            return f"Arquivo apagado."
        return "Arquivo não encontrado."
    except Exception as e: return f"Erro ao apagar: {e}"

async def executar_comando_terminal(comando):
    """Roda comandos bash no Docker de forma ASSÍNCRONA para não travar o bot."""
    try:
        cmd_docker = f'docker exec {CONTAINER_NAME} bash -c "{comando}"'
        
        # Cria o processo de forma assíncrona
        processo = await asyncio.create_subprocess_shell(
            cmd_docker,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            # Espera o resultado com timeout de 60s sem travar o resto do bot
            stdout, stderr = await asyncio.wait_for(processo.communicate(), timeout=60)
            
            saida = stdout.decode().strip()
            erros = stderr.decode().strip()
            
            resultado = saida + erros
            return resultado if resultado.strip() else "Comando executado com sucesso."
            
        except asyncio.TimeoutError:
            processo.kill()
            return "Erro: O comando demorou mais de 60 segundos e foi interrompido."
            
    except Exception as e:
        return f"Erro no terminal: {e}"

def agendar_tarefa(nome_tarefa, intervalo_minutos, instrucao):
    """Salva uma tarefa recorrente no JSON (agora usando LISTA)."""
    try:
        with open(ARQUIVO_TAREFAS, "r", encoding="utf-8") as f:
            tarefas = json.load(f)
        
        tarefas = [t for t in tarefas if t.get("nome_tarefa") != nome_tarefa]
        
        tarefas.append({
            "nome_tarefa": nome_tarefa,
            "intervalo_minutos": int(intervalo_minutos),
            "instrucao": instrucao,
            "proxima_execucao": (datetime.now() + timedelta(minutes=int(intervalo_minutos))).isoformat()
        })
        
        with open(ARQUIVO_TAREFAS, "w", encoding="utf-8") as f:
            json.dump(tarefas, f, indent=4, ensure_ascii=False)
            
        return f"Tarefa '{nome_tarefa}' agendada para rodar a cada {intervalo_minutos} minutos."
    except Exception as e:
        return f"Erro ao agendar: {e}"

def listar_tarefas():
    try:
        with open(ARQUIVO_TAREFAS, "r", encoding="utf-8") as f:
            tarefas = json.load(f)
        if not tarefas: return "Nenhuma tarefa agendada."
        
        lista = [f"- {t['nome_tarefa']} (A cada {t['intervalo_minutos']} min): {t['instrucao']}" for t in tarefas]
        return "\n".join(lista)
    except Exception as e: return f"Erro ao listar: {e}"

def remover_tarefa(nome_tarefa):
    """Remove uma tarefa do JSON (agora usando LISTA)."""
    try:
        with open(ARQUIVO_TAREFAS, "r", encoding="utf-8") as f:
            tarefas = json.load(f)
        
        tarefas_restantes = [t for t in tarefas if t.get("nome_tarefa") != nome_tarefa]
        
        if len(tarefas) == len(tarefas_restantes):
            return f"Tarefa '{nome_tarefa}' não encontrada."
        
        with open(ARQUIVO_TAREFAS, "w", encoding="utf-8") as f:
            json.dump(tarefas_restantes, f, indent=4, ensure_ascii=False)
        return f"Tarefa '{nome_tarefa}' removida com sucesso."
    except Exception as e: return f"Erro ao remover: {e}"

def analisar_imagem(caminho_imagem, pergunta="Descreva esta imagem detalhadamente para uma IA engenheira."):
    """Usa o Gemini 3 Flash Preview para analisar imagens."""
    global vision_client
    
    if not vision_client:
        return "Erro: Sistema de visão não configurado (Falta GEMINI_API_KEY)."

    try:
        caminho_real = traduzir_caminho(caminho_imagem)
        
        if not os.path.exists(caminho_real):
            return f"Erro: Imagem não encontrada no caminho real: {caminho_real}"

        with open(caminho_real, "rb") as f:
            image_bytes = f.read()
        
        response = vision_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                pergunta
            ]
        )
        
        return f"ANÁLISE VISUAL: {response.text}"
        
    except Exception as e:
        return f"Erro técnico na visão: {e}"

def pesquisar_web(query):
    try:
        with DDGS() as ddgs:
            results =[r for r in ddgs.text(query, max_results=3)]
            if not results: return "Sem resultados."
            return "\n".join([f"Título: {r['title']}\nLink: {r['href']}\nResumo: {r['body']}\n" for r in results])
    except Exception as e: return f"Erro na busca: {e}"

def ler_conteudo_link(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
        texto = soup.get_text(separator=' ', strip=True)
        return texto[:4000] + "..."
    except Exception as e: return f"Erro ao ler link: {e}"

def obter_colecao_memorias():
    """Garante que a coleção sempre exista e pega a referência atualizada."""
    return chroma_client.get_or_create_collection(
        name="memorias_selene", 
        embedding_function=default_ef
    )

def adicionar_memoria_vetorial(conteudo):
    try:
        colecao = obter_colecao_memorias()
        import uuid
        id_memoria = str(uuid.uuid4())
        colecao.add(documents=[conteudo], ids=[id_memoria])
        return "Memória guardada no meu banco vetorial."
    except Exception as e:
        return f"Erro ao salvar memória vetorial: {e}"

def buscar_memorias_relevantes(query, n_resultados=5):
    try:
        colecao = obter_colecao_memorias()
        if colecao.count() == 0:
            return "Nenhuma memória relevante encontrada."
            
        resultados = colecao.query(query_texts=[query], n_results=n_resultados)
        if resultados['documents'] and resultados['documents'][0]:
            return "\n".join(resultados['documents'][0])
        return "Nenhuma memória relevante encontrada."
    except Exception as e:
        print(f"Erro na busca vetorial: {e}")
        return ""

def resetar_memoria_vetorial():
    """Deleta o banco, recria e injeta as memórias base."""
    try:
        try:
            chroma_client.delete_collection("memorias_selene")
        except Exception:
            pass
            
        colecao = obter_colecao_memorias()
        
        # Pega o diretório exato onde o ferramentas.py está rodando
        DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
        base_file = os.path.join(DIRETORIO_ATUAL, "memorias_base.txt")
        
        count = 0
        
        if os.path.exists(base_file):
            with open(base_file, "r", encoding="utf-8") as f:
                linhas = f.readlines()
            
            import uuid
            for linha in linhas:
                linha = linha.strip()
                if linha:
                    colecao.add(documents=[linha], ids=[str(uuid.uuid4())])
                    count += 1
            return f"Banco vetorial resetado. {count} memórias base injetadas a partir do arquivo local."
        return f"Banco vetorial resetado. Arquivo 'memorias_base.txt' não encontrado no servidor (esperado em: {base_file})."
    except Exception as e:
        return f"❌ Erro ao resetar memória: {e}"

def limpar_quarto():
    """Limpa a pasta de trabalho, mantendo arquivos essenciais e reinicia o Docker."""
    import shutil
    protegidos =["vetor_db", "tarefas.json", "plano_de_acao.md"]
    apagados = 0
    
    try:
        for item in os.listdir(PASTA_QUARTO):
            if item not in protegidos:
                caminho = os.path.join(PASTA_QUARTO, item)
                if os.path.isdir(caminho):
                    shutil.rmtree(caminho)
                else:
                    os.remove(caminho)
                apagados += 1
        
        iniciar_docker()
        
        return f"Workspace limpo! {apagados} arquivos/pastas removidos. Container Docker reiniciado."
    except Exception as e:
        return f"❌ Erro ao limpar o workspace: {e}"


lista_ferramentas =[
    {
        "type": "function", "function": {
            "name": "listar_arquivos", "description": "Lista arquivos de uma pasta.",
            "parameters": {"type": "object", "properties": {"subpasta": {"type": "string"}}}
        }
    },
    {
        "type": "function", "function": {
            "name": "ver_arvore_arquivos", "description": "Usa o comando 'tree' para ver a estrutura completa de pastas e arquivos de um projeto sem precisar ler um por um.",
            "parameters": {"type": "object", "properties": {"caminho": {"type": "string", "description": "Ex: /workspace/quarto"}}}
        }
    },
    {
        "type": "function", "function": {
            "name": "criar_pasta", "description": "Cria uma nova pasta.",
            "parameters": {"type": "object", "properties": {"nome_pasta": {"type": "string"}}, "required":["nome_pasta"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "ler_arquivo", "description": "Lê o conteúdo de um arquivo de código ou texto.",
            "parameters": {"type": "object", "properties": {"nome_arquivo": {"type": "string"}}, "required": ["nome_arquivo"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "escrever_arquivo", "description": "Cria ou sobrescreve um arquivo.",
            "parameters": {"type": "object", "properties": {"nome_arquivo": {"type": "string"}, "conteudo": {"type": "string"}}, "required":["nome_arquivo", "conteudo"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "apagar_arquivo", "description": "Deleta um arquivo.",
            "parameters": {"type": "object", "properties": {"nome_arquivo": {"type": "string"}}, "required": ["nome_arquivo"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "executar_comando_terminal", "description": "Roda comandos bash no seu Docker. Ex: 'python script.py', 'pip install pandas', 'ls -la', 'curl ...'.",
            "parameters": {"type": "object", "properties": {"comando": {"type": "string"}}, "required": ["comando"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "pedir_ajuda_ao_usuario", "description": "Use se travar em um erro ou precisar de uma decisão humana.",
            "parameters": {"type": "object", "properties": {"duvida_ou_problema": {"type": "string"}}, "required":["duvida_ou_problema"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "pesquisar_web", "description": "Busca na internet.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required":["query"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "ler_conteudo_link", "description": "Lê o texto de um site.",
            "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "adicionar_memoria", 
            "description": "Salva fatos concretos no banco vetorial. OBRIGATÓRIO iniciar o conteúdo com uma tag como [Fato], [Regra], [Preferência] ou[Projeto]. Ex: '[Fato] O dev se chama Guilherme.'",
            "parameters": {"type": "object", "properties": {"conteudo": {"type": "string"}}, "required": ["conteudo"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "agendar_tarefa", "description": "Cria uma rotina em background. Você será acordada automaticamente para executar a instrução no intervalo definido.",
            "parameters": {"type": "object", "properties": {"nome_tarefa": {"type": "string"}, "intervalo_minutos": {"type": "integer"}, "instrucao": {"type": "string", "description": "O que você deve fazer quando acordar (ex: 'Olhe o preço do BTC e me avise se caiu')."}}, "required":["nome_tarefa", "intervalo_minutos", "instrucao"]}
        }
    },
    {
        "type": "function", "function": {
            "name": "listar_tarefas", "description": "Mostra todas as suas rotinas em background."
        }
    },
    {
        "type": "function", "function": {
            "name": "remover_tarefa", "description": "Cancela uma rotina em background.",
            "parameters": {"type": "object", "properties": {"nome_tarefa": {"type": "string"}}, "required":["nome_tarefa"]}
        }
    },
    {
    "type": "function", "function": {
        "name": "analisar_imagem", "description": "Usa seus olhos digitais para ver uma imagem que o usuário enviou.",
        "parameters": {
            "type": "object", 
            "properties": {
                "caminho_imagem": {"type": "string", "description": "Caminho do arquivo (ex: /workspace/quarto/uploads/imagem.png)"},
                "pergunta": {"type": "string", "description": "O que você quer saber sobre a imagem?"}
            }, 
            "required":["caminho_imagem"]
            }
        }
    },
]
