import argparse
import os
import sys
import chromadb
from chromadb.utils import embedding_functions

PASTA_QUARTO = os.path.abspath("quarto_da_selene")
CHROMA_PATH = os.path.join(PASTA_QUARTO, "vetor_db")
MODELO_EMBEDDING = "all-MiniLM-L6-v2"

def obter_colecao():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODELO_EMBEDDING)
    return client.get_or_create_collection(name="memorias_selene", embedding_function=ef), client

def main():
    parser = argparse.ArgumentParser(description="🌙 Selene CLI - Gerenciador do Sistema")
    subparsers = parser.add_subparsers(dest="comando", help="Comandos disponíveis")

    subparsers.add_parser("list", help="Lista todas as memórias vetoriais cadastradas.")
    
    parser_search = subparsers.add_parser("search", help="Busca memórias por similaridade.")
    parser_search.add_argument("query", type=str, help="O texto que deseja buscar.")
    
    parser_delete = subparsers.add_parser("delete", help="Deleta uma memória específica pelo ID.")
    parser_delete.add_argument("id", type=str, help="O ID da memória (use 'list' para ver os IDs).")
    
    subparsers.add_parser("reset", help="Zera o banco vetorial e injeta o memorias_base.txt.")

    args = parser.parse_args()

    if not args.comando:
        parser.print_help()
        sys.exit(1)

    colecao, client = obter_colecao()

    if args.comando == "list":
        dados = colecao.get()
        if not dados['ids']:
            print("📭 O banco vetorial está vazio.")
            return
        print(f"🧠 Encontradas {len(dados['ids'])} memórias:\n")
        for i in range(len(dados['ids'])):
            print(f"ID: {dados['ids'][i]}")
            print(f"Conteúdo: {dados['documents'][i]}")
            print("-" * 50)

    elif args.comando == "search":
        res = colecao.query(query_texts=[args.query], n_results=3)
        print(f"🔍 Resultados para: '{args.query}'\n")
        if not res['documents'][0]:
            print("Nenhuma memória encontrada.")
        for i, doc in enumerate(res['documents'][0]):
            distancia = res['distances'][0][i]
            print(f"[{distancia:.4f}] {doc}")

    elif args.comando == "delete":
        try:
            colecao.delete(ids=[args.id])
            print(f"[OK] Memória {args.id} deletada com sucesso.")
        except Exception as e:
            print(f"[ERROR] Erro ao deletar: {e}")

    elif args.comando == "reset":
        confirmar = input("[WARN] PERIGO: Isso apagará TODAS as memórias. Confirmar? (s/N): ")
        if confirmar.lower() == 's':
            try:
                client.delete_collection("memorias_selene")
            except:
                pass
            
            colecao, _ = obter_colecao()
            base_file = "memorias_base.txt"
            
            if os.path.exists(base_file):
                import uuid
                with open(base_file, "r", encoding="utf-8") as f:
                    linhas = [linha.strip() for linha in f if linha.strip()]
                
                for linha in linhas:
                    colecao.add(documents=[linha], ids=[str(uuid.uuid4())])
                print(f"[OK] Banco resetado! {len(linhas)} memórias base injetadas.")
            else:
                print("[OK] Banco resetado! (Arquivo memorias_base.txt não encontrado).")

if __name__ == "__main__":
    main()