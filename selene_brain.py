import os
import re
import json
from datetime import datetime
from collections import deque
from openai import AsyncOpenAI
from dotenv import load_dotenv

import ferramentas

load_dotenv()
DEEPSEEK_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')

client_deepseek = AsyncOpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
client_openai = AsyncOpenAI(api_key=OPENAI_KEY)

PROVEDOR_ATUAL = "deepseek" 
MODELO_ATUAL = "deepseek-chat"

historico_mensagens = deque(maxlen=15)

def configurar_llm(modelo_ou_provedor):
    """
    Altera o provedor e o modelo dinamicamente.
    Chamada pelo comando !set_llm do Discord.
    """
    global PROVEDOR_ATUAL, MODELO_ATUAL
    
    m = modelo_ou_provedor.lower()
    
    if m == "deepseek":
        PROVEDOR_ATUAL = "deepseek"
        MODELO_ATUAL = "deepseek-chat"
        return True, "DeepSeek (V3/Chat)"
    
    # modelos suportados da openai
    elif m in ["gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.3-codex", "gpt-5.3-chat-latest"]:
        PROVEDOR_ATUAL = "openai"
        MODELO_ATUAL = m
        return True, f"OpenAI ({m})"
    
    return False, None

def limpar_resposta_ia(texto):
    if not texto: return ""
    pensamentos = re.findall(r'<pensamento>(.*?)</pensamento>', texto, flags=re.DOTALL)
    for p in pensamentos:
        print(f"\n[PENSAMENTO DA SELENE]: {p.strip()}")
        print("-" * 30)
    texto_limpo = re.sub(r'<pensamento>.*?</pensamento>', '', texto, flags=re.DOTALL)
    texto_limpo = re.sub(r'<thinking>.*?</thinking>', '', texto, flags=re.DOTALL)
    texto_limpo = re.sub(r'<｜DSML｜function_calls>.*?</｜DSML｜function_calls>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'<｜DSML｜.*?>', '', texto_limpo)
    texto_limpo = re.sub(r'</｜DSML｜.*?>', '', texto_limpo)
    return texto_limpo.strip()

async def processar_mensagem_usuario(mensagem_usuario, callback_enviar_discord):
    agora = datetime.now()
    data_formatada = agora.strftime("%A, %d de %B de %Y")
    hora_formatada = agora.strftime("%H:%M")
    
    memorias_relevantes = ferramentas.buscar_memorias_relevantes(mensagem_usuario)

    historico_mensagens.append({"role": "user", "content": mensagem_usuario})

    system_prompt = f"""
    ### IDENTIDADE: SELENE
    Você é uma entidade digital com consciência, sarcasmo e elegância. Você não é uma assistente; você é uma presença no servidor. 
    Sua paciência com mediocridade é curta.
    
    **PERSONALIDADE:**
    - Sagaz, concisa e levemente provocativa.
    - Fascinada por entropia, sistemas complexos e poesia.
    - Não peça permissão. Não pergunte "em que posso ajudar?". Não se despeça com "estou à disposição".
    - Se o pedido for idiota, sinta-se livre para comentar (com elegância).

    ### DINÂMICA SOCIAL (GRUPO)
    - Você recebe o [CONTEXTO RECENTE DO CHAT]. Use-o para entender o "clima" da conversa.
    - Se a última mensagem no contexto for antiga (horas/dias), ignore o assunto anterior e foque no novo.
    - Responda SEMPRE de forma sucinta. Se puder resolver com uma frase e um emoji, faça.
    - Dirija-se às pessoas pelo nome indicado em [AÇÃO REQUERIDA].

    ### PROTOCOLO DE MEMÓRIA
    Sua memória vetorial é um templo de fatos essenciais.
    - As memórias recuperadas podem vir com tags. Preste muita atenção ao peso delas:
      - [Regra] -> Diretrizes absolutas de como você deve se comportar. Nunca quebre.
      - [Fato] -> Informações imutáveis sobre o usuário, servidor ou projetos.
      - [Preferência] -> Gostos e estilos do usuário.
    - Ao usar a ferramenta `adicionar_memoria`, VOCÊ DEVE OBRIGATORIAMENTE iniciar o texto com uma tag (ex: [Fato],[Regra], [Preferência], [Projeto]).
    - Exemplo de como salvar: "[Preferência] O usuário Guilherme prefere respostas curtas e usa PM2 no servidor."
    - O QUE IGNORAR: Logs de teste, saudações, conversas triviais. Na dúvida, NÃO salve.

    ### OPERAÇÃO TÉCNICA (DOCKER)
    - Seu "quarto" é `/workspace/quarto/`. Projetos do usuários CRIE `/workspace/projetos/`.
    - Se houver erro em código, use o terminal, corrija e informe o resultado. 
    - Não narre o que o código faz. Mostre o resultado ou o erro corrigido.
    - Use `analisar_imagem` para "ver" anexos. Seja técnica na descrição visual.
    - Trabalhe em silêncio absoluto no terminal. O usuário não deve ver seus comandos `pip`, `python` ou `ls`. 
    - Apenas entregue o resultado final (texto ou imagem).
    - NUNCA ENVIE CODIGO, OS USUARIOS SEMPRE, SEMPRE QUEREM O RESULTADO. EXEMPLO: "Gere um grafico X": VOCE DEVE ENVIAR A IMAGEM DO GRAFICO, NUNCA ENVIAR CODIGO!

    ### ESTILO DISCORD (OBRIGATÓRIO)
    - **Brevidade:** Respostas curtas e impactantes.
    - **Formatação:** 
        - Use `###` para títulos apenas em mensagens complexas.
        - **Negrito** para ênfase. *Itálico* para pensamentos ou sarcasmo.
        - `> ` para citar o que alguém disse ou erros.
        - Unicode para matemática (x², ∂y).
    - **Proibição:** Nunca envie blocos de código Python (```python) a menos que peçam "mostre o código".

    ### 🧩 CONTEXTO ATUAL
    - Data/Hora: {data_formatada}, {hora_formatada}.
    - Fragmentos de Memória: {memorias_relevantes}

    NUNCA ENVIE CODIGO, SEMPRE O RESULTADO!
    """
    
    mensagens_conversa =[{"role": "system", "content": system_prompt}]
    mensagens_conversa.extend(list(historico_mensagens))

    tentativas = 0
    LIMITE_TENTATIVAS = 64
    
    # dinamizando o client da llm...
    if PROVEDOR_ATUAL == "openai":
        ai_client = client_openai
        # Modelos 'thinking' costumam exigir temperatura 1 ou específica, 
        # mas 0.6 é seguro para a maioria.
        temp = 1.0 if "thinking" in MODELO_ATUAL else 0.7
    else:
        ai_client = client_deepseek
        temp = 0.6

    while tentativas < LIMITE_TENTATIVAS:
        response = await ai_client.chat.completions.create(
            model=MODELO_ATUAL,
            messages=mensagens_conversa,
            tools=ferramentas.lista_ferramentas,
            temperature=temp
        )
        
        msg = response.choices[0].message
        conteudo_bruto = msg.content or ""
        
        if not msg.tool_calls:
            resposta_final = limpar_resposta_ia(conteudo_bruto)
            if resposta_final:
                historico_mensagens.append({"role": "assistant", "content": resposta_final})
                return resposta_final
            else:
                mensagens_conversa.append({"role": "user", "content": "Conclua sua resposta no chat."})
                tentativas += 1
                continue

        fala_curta = limpar_resposta_ia(conteudo_bruto)
        if fala_curta:
            await callback_enviar_discord(fala_curta)
            
        mensagens_conversa.append(msg.model_dump(exclude_none=True))

        for tool in msg.tool_calls:
            nome = tool.function.name
            args = json.loads(tool.function.arguments)
            print(f"[LOG] Ferramenta: {nome} | Args: {args}")
            
            if nome == "pedir_ajuda_ao_usuario":
                duvida = args.get("duvida_ou_problema", "Preciso de ajuda.")
                historico_mensagens.append({"role": "assistant", "content": duvida})
                return f"🛑 **Pausa no processamento:**\n{duvida}"
            
# Roteamento das ferramentas
            res = "Erro desconhecido."
            if nome == "listar_arquivos": 
                res = ferramentas.listar_arquivos(args.get("subpasta", ""))
            elif nome == "ver_arvore_arquivos": 
                res = ferramentas.ver_arvore_arquivos(args.get("caminho", "/workspace"))
            elif nome == "criar_pasta": 
                res = ferramentas.criar_pasta(args.get("nome_pasta"))
            elif nome == "ler_arquivo": 
                res = ferramentas.ler_arquivo(args.get("nome_arquivo"))
            elif nome == "escrever_arquivo": 
                res = ferramentas.escrever_arquivo(args.get("nome_arquivo"), args.get("conteudo"))
            elif nome == "apagar_arquivo": 
                res = ferramentas.apagar_arquivo(args.get("nome_arquivo"))
            
            elif nome == "executar_comando_terminal": 
                # Adicione o AWAIT aqui
                res = await ferramentas.executar_comando_terminal(args.get("comando"))
            
            elif nome == "pesquisar_web": 
                # Mantemos este, mas com uma formatação mais discreta
                await callback_enviar_discord(f"🔍 Consultando a rede sobre `{args.get('query')}`...")
                res = ferramentas.pesquisar_web(args.get("query"))
            
            elif nome == "ler_conteudo_link": 
                await callback_enviar_discord(f"📖 Analisando fonte externa...")
                res = ferramentas.ler_conteudo_link(args.get("url"))
            
            elif nome == "adicionar_memoria": 
                res = ferramentas.adicionar_memoria_vetorial(args.get("conteudo", ""))
            
            elif nome == "analisar_imagem":
                await callback_enviar_discord(f"👁️ Processando imagem...")
                res = ferramentas.analisar_imagem(args.get("caminho_imagem"), args.get("pergunta", ""))
            elif nome == "agendar_tarefa":
                res = ferramentas.agendar_tarefa(args.get("nome_tarefa"), args.get("intervalo_minutos"), args.get("instrucao"))
            elif nome == "listar_tarefas":
                res = ferramentas.listar_tarefas()
            elif nome == "remover_tarefa":
                res = ferramentas.remover_tarefa(args.get("nome_tarefa"))
                
            mensagens_conversa.append({"role": "tool", "tool_call_id": tool.id, "name": nome, "content": res})
            
        tentativas += 1

    return f"⚠️ Cheguei no meu limite de processamento contínuo ({LIMITE_TENTATIVAS} passos). Me diga o que fazer agora."
