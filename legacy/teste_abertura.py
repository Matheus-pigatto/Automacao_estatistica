import pickle
import os
from rag import SorteioRAG

caminho_base=r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\RAG"
caminho_arquivo = os.path.join(caminho_base, "jogos.pkl")
# Teste de leitura
with open(caminho_arquivo, 'rb') as f:
    dados = pickle.load(f)

print("Chaves encontradas:", dados.keys())
if 'estatisticas' in dados:
    print("ok")
    #print("Estatísticas:", dados['estatisticas'])
    #print("Estatísticas: Avançadas:", dados['metricas_avancadas'])
else:
    print("🚨 A chave 'estatisticas' REALMENTE não foi salva!")

rag_sorteios = SorteioRAG()
dezenas_teste = ['02', '06', '08', '09', '11', '19', '20', '22', '26', '29', '31', '37', '39', '44', '45', '47', '49', '52', '54', '55']

scores = rag_sorteios.simular_comparativo(  dezenas_teste,num_simulacoes=20000)
print("Scores obtidos no teste:", scores)