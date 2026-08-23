import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import pickle
from collections import defaultdict, Counter
import json
import pandas as pd
from estrutura_de_dados import Sorteio
import os
from scipy import stats
from datetime import datetime

class SorteioRAG:
    def __init__(self, model_name='all-MiniLM-L6-v2', caminho_base=r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\RAG"):
        self.embedder = SentenceTransformer(model_name)
        self.caminho_base = caminho_base
        
        # Estado Interno Único
        self.memoria = {
            'objetos_sorteio': [], 
            'textos': [],
            'estatisticas': {},
            'metricas_avancadas': {} # <--- ADICIONADO PARA GUARDAR MARKOV/ERLANG
        }
        
        self.index = faiss.IndexFlatL2(self.embedder.get_sentence_embedding_dimension())
        self._carregar_estado()

    def sincronizar_com_csv(self, caminho_csv: str):
        if not os.path.exists(caminho_csv): return
        
        df = pd.read_csv(caminho_csv, sep=';', encoding='utf-8')
        # 2. Identifica o que já temos na memória
        concursos_existentes = [s.concurso for s in self.memoria['objetos_sorteio']]
        
        # 3. Cria a Chave Única Composta para a comparação
        # Exemplo: "04/02/2024 - 1o Sorteio"
        df['chave_composta'] = df['Data'].astype(str) + " - " + df['Sorteio'].astype(str)
        
        # 4. Filtra apenas o que é realmente novo
        novos_jogos = df[~df['chave_composta'].isin(concursos_existentes)]
        
        if not novos_jogos.empty:
            for _, linha in novos_jogos.iterrows():
                # Converte a string de dezenas "55 1 49..." em lista de inteiros
                lista_dezenas = [int(n) for n in str(linha['Dezenas']).split()]
                
                # Cria o objeto Sorteio com a nova chave
                sorteio = Sorteio({
                    'concurso': linha['chave_composta'],
                    'data': linha['Data'],
                    'numeros': lista_dezenas,
                    'total': linha['Total_Numeros']
                })
                
                self.memoria['objetos_sorteio'].append(sorteio)
                txt = sorteio.to_text()
                self.memoria['textos'].append(txt)
                
                # Adiciona ao FAISS
                embedding = self.embedder.encode(txt)
                self.index.add(np.array([embedding]).astype('float32'))
            
            # 5. Atualiza os PKLs e as estatísticas globais
            self._recalcular_e_salvar()
            return len(novos_jogos)
        
        return 0

    def _recalcular_e_salvar(self):
        caminho_arquivo = os.path.join(self.caminho_base, "jogos.pkl")
        """Manutenção de todos os cálculos estatísticos"""
        sorteios = self.memoria['objetos_sorteio']
        if not sorteios: return

        todos_numeros = [n for s in sorteios for n in s.numeros]
        
        # 1. Estatísticas Básicas
        self.memoria['estatisticas'] = {
            'frequencia': dict(Counter(todos_numeros).most_common(20)),
            'total_jogos': len(sorteios),
            'ultimo_concurso': sorteios[-1].concurso
        }

        # 2. Métricas Avançadas (Markov, Erlang, Regressão)
        # Movido para cá para ser calculado apenas uma vez na sincronização
        self.memoria['metricas_avancadas'] = self._processar_inteligencia_avancada()

        try:
            with open(caminho_arquivo, 'wb') as f:
                # Protocolo 4 ou superior é mais estável para objetos grandes
                pickle.dump(self.memoria, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Salva o FAISS separadamente como você já faz
            faiss.write_index(self.index, os.path.join(self.caminho_base, "jogos.index"))
            print("✅ Tudo salvo com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao salvar pkl: {e}")

    def _processar_inteligencia_avancada(self):
        """Cálculos Científicos: ANOVA, Qui-Quadrado, Entropia, Clusters e Erlang"""
        sorteios = self.memoria['objetos_sorteio']
        if len(sorteios) < 50: return {}

        # 1. PREPARAÇÃO DE DADOS
        todos_numeros = [n for s in sorteios for n in s.numeros]
        contagem_real = Counter(todos_numeros)
        df_jogos = pd.DataFrame([s.numeros for s in sorteios]) # Matriz de sorteios

        # 2. QUI-QUADRADO (Vício do Globo)
        # Compara a frequência real com a teórica (uniforme)
        # Supondo que 'f_obs' seja a lista de contagem de cada número (1 a 60)
        # Exemplo: f_obs = [10, 12, 8, ...] (tamanho 60)
        f_obs = []
        for i in range(1, 61):
            f_obs.append(contagem_real.get(i, 0))

        f_obs = np.array(f_obs)
        
        # 1. Calcula o total de bolas que realmente saíram no seu histórico
        total_observado = np.sum(f_obs)
        
        # 2. Calcula a frequência esperada de forma proporcional
        # Em vez de usar um número fixo (ex: 37), dividimos o total real por 60
        f_exp = np.full(shape=f_obs.shape, fill_value=total_observado / len(f_obs))
        
        # 3. TRUQUE DE MESTRE: Força a soma a ser idêntica para evitar o erro de precisão
        f_exp = f_exp * (total_observado / np.sum(f_exp))
        
        # 4. Agora o teste vai rodar sem erro
        chi_stat, p_value = stats.chisquare(f_obs, f_exp)

        # 3. ENTROPIA DE SHANNON (Complexidade média das ganhadoras)
        # Calculamos a entropia média das cartelas que já ganharam
        def calc_entropia(lista):
            pk = np.histogram(lista, bins=10)[0] / len(lista)
            return stats.entropy(pk) if sum(pk) > 0 else 0
        
        entropias = [calc_entropia(s.numeros) for s in sorteios]
        media_entropia_ganhadora = np.mean(entropias)

        # 4. ANOVA (Diferença entre sorteios 1, 2, 3 e 4)
        # Verifica se um sorteio específico da semana é mais 'difícil'
        sorteios_por_tipo = defaultdict(list)
        for s in sorteios:
            if hasattr(s, 'tipo'): # Ex: 1o sorteio, 2o sorteio...
                sorteios_por_tipo[s.tipo].append(len(s.numeros))
        
        if len(sorteios_por_tipo) > 1:
            f_stat, anova_p = stats.f_oneway(*sorteios_por_tipo.values())
        else:
            anova_p = 1.0

        # 5. K-MEANS (Clusterização de Números)
        # Divide os números em 3 grupos: Elite, Médio, Inerte
        dados_cluster = np.array([contagem_real.get(i, 0) for i in range(1, 61)]).reshape(-1, 1)
        # Simulação simples de cluster por quartis (mais rápido que sklearn para 60 números)
        limiar_elite = np.percentile(dados_cluster, 75)
        limiar_inerte = np.percentile(dados_cluster, 25)
        
        clusters = {}
        for n in range(1, 61):
            freq = contagem_real.get(n, 0)
            if freq >= limiar_elite: clusters[n] = "Elite"
            elif freq <= limiar_inerte: clusters[n] = "Inerte"
            else: clusters[n] = "Médio"

        # 6. ERLANG / ATRASO (Tempo de Espera)
        atrasos = {}
        for n in range(1, 61):
            distancia = 0
            for s in reversed(sorteios):
                if n in s.numeros: break
                distancia += 1
            atrasos[n] = distancia

        # 7. MARKOV (Transição)
        transicoes = Counter()
        for i in range(len(sorteios)-1):
            for n1 in sorteios[i].numeros:
                for n2 in sorteios[i+1].numeros:
                    transicoes[(n1, n2)] += 1

        return {
            "chi_score": float(chi_stat),
            "p_value": float(p_value),
            "status": "Aleatório" if p_value > 0.05 else "Tendencioso",
            'entropia_alvo': media_entropia_ganhadora,
            'anova_p_valor': anova_p,
            'clusters': clusters,             # Dicionário {número: categoria}
            'atrasos': atrasos,               # Dicionário {número: semanas_sem_sair}
            'transicoes': dict(transicoes.most_common(100)),
            'timestamp_analise': datetime.now().isoformat()
        }

    def simular_comparativo(self, dezenas_cartela, num_simulacoes=1000):
        # CORREÇÃO 1: Garantir que todas as dezenas da cartela sejam INTEIROS
        dezenas_cartela = [int(d) for d in dezenas_cartela]
        
        print("Iniciando simulação comparativa...")
        print(f"Dezenas da cartela: {dezenas_cartela}")

        media_vitoria = 37
        avancadas = self.memoria.get('metricas_avancadas', {})

        # Armazenaremos em qual bola a cartela fechou em cada simulação
        bolas_fechamento_puro = []
        bolas_fechamento_viciado = []
        #print("Métricas avançadas carregadas:", avancadas)
        
        # Pegar dados de atraso e tendência (garantindo que as chaves sejam ints)
        atrasos_raw = avancadas.get('atrasos', {})
        # Converter chaves de atraso para int caso estejam como string no PKL
        atrasos = {int(k): v for k, v in atrasos_raw.items()}
        
        # --- SIMULAÇÃO 1: PURA ---
        acertos_puros = 0
        for _ in range(num_simulacoes):
            globo = list(range(1, 61))
            np.random.shuffle(globo)
            contagem = 0
            for bola_num, n in enumerate(globo, 1):
                if n in dezenas_cartela: 
                    contagem += 1
                if contagem == 20:
                    if bola_num <= media_vitoria: 
                        acertos_puros += 1
                    break
        
        # --- SIMULAÇÃO 2: VICIADA ---
        pesos = []
        for n in range(1, 61):
            # Busca o peso. Se não existir o número no histórico, usa peso base 1.0
            w_atraso = atrasos.get(n, 0) * 0.5
            w_tendencia = avancadas.get('tendencias', {}).get(n, 0) * 10
            pesos.append(max(0.1, 1.0 + w_atraso + w_tendencia))
        
        pesos = np.array(pesos) / sum(pesos)
        
        acertos_viciados = 0
        for _ in range(num_simulacoes):
            # np.random.choice gera o sorteio baseado nos pesos de probabilidade
            globo_viciado = np.random.choice(range(1, 61), size=60, replace=False, p=pesos)
            contagem = 0
            for bola_num, n in enumerate(globo_viciado, 1):
                if n in dezenas_cartela: 
                    contagem += 1
                if contagem == 20:
                    if bola_num <= media_vitoria: 
                        acertos_viciados += 1
                    break

            # Pesos (Histórico)
        pesos = []
        atrasos = {int(k): v for k, v in avancadas.get('atrasos', {}).items()}
        for n in range(1, 61):
            w_atraso = atrasos.get(n, 0) * 0.5
            w_tendencia = avancadas.get('tendencias', {}).get(n, 0) * 10
            pesos.append(max(0.1, 1.0 + w_atraso + w_tendencia))
        pesos = np.array(pesos) / sum(pesos)

        for _ in range(num_simulacoes):
            # 1. Simulação Pura
            globo = list(range(1, 61))
            np.random.shuffle(globo)
            contagem = 0
            for bola_num, n in enumerate(globo, 1):
                if n in dezenas_cartela: contagem += 1
                if contagem == 20:
                    bolas_fechamento_puro.append(bola_num)
                    break

            # 2. Simulação Viciada (RAG/Histórico)
            globo_viciado = np.random.choice(range(1, 61), size=60, replace=False, p=pesos)
            contagem = 0
            for bola_num, n in enumerate(globo_viciado, 1):
                if n in dezenas_cartela: contagem += 1
                if contagem == 20:
                    bolas_fechamento_viciado.append(bola_num)
                    break

        # MÉTRICAS FINAIS
        # Média de bolas para fechar (Quanto menor, melhor a cartela)
        media_pura = np.mean(bolas_fechamento_puro)
        media_viciada = np.mean(bolas_fechamento_viciado)

        # Score de Eficiência (0 a 100)
        # 37 bolas é o "Ideal", 60 é o "Pior". Criamos uma escala:
        score_puro = max(0, min(100, (60 - media_pura) / (60 - 37) * 100))
        score_viciado = max(0, min(100, (60 - media_viciada) / (60 - 37) * 100))

                # No final da sua função simular_comparativo, antes do return, adicione:
        media_bolas_para_fechar = np.mean(bolas_fechamento_viciado) if bolas_fechamento_viciado else 60
        print(f"DEBUG: Esta cartela fecha, em média, na bola: {media_bolas_para_fechar}")

        return {
            "pure_score": round(score_puro, 2),
            "weighted_score": round(score_viciado, 2),
            "media_bolas_viciado": round(media_viciada, 1)
        }
        
    
    def simular_monte_carlo(self, dezenas_cartela, num_simulacoes=10000):
        """Versão com debug"""
        print(f"dezenas que entraram no simulador: {dezenas_cartela}")
        resultados_bola_fechamento = []
        try:
            dezenas_set = set([int(d) for d in dezenas_cartela])
        except Exception as e:
            print(f"Erro ao converter dezenas: {e}")
            return {"media": 0, "prob_50": 0, "prob_55": 0, "monte_carlo_data": []}
        
        # VALIDAÇÃO INICIAL
        print(f"Cartela: {sorted(dezenas_set)}")
        print(f"Quantidade de números: {len(dezenas_set)}")
        print(f"Números únicos: {len(dezenas_set)}")
        
        for sim in range(num_simulacoes):
            #print(f"simulação: {sim}")
            globo = np.random.permutation(np.arange(1, 61))
            acertos = 0
            numeros_acertados = []
            
            for bola_idx, numero_sorteado in enumerate(globo, 1):
                #print(f"valor do globo sorteado: \n{globo}")
                if numero_sorteado in dezenas_set:
                    acertos += 1
                    #print(f"A bola sorteada #:{bola_idx}")
                    #print(f"O numero sorteado foi: {numero_sorteado}")
                    #print(f"acertou")
                
                if acertos == 20:
                    #print(f"cartela premiada")
                    #print(f"Resultado: {resultados_bola_fechamento}")
                    resultados_bola_fechamento.append(bola_idx)
                   
        # 3. VALIDAÇÃO ANTES DO CÁLCULO
        if not resultados_bola_fechamento:
            return {"media": 0, "prob_50": 0, "prob_55": 0, "monte_carlo_data": []}            
        #print(f"o resultado foi:")
        resultados = np.array(resultados_bola_fechamento)
        #print(f"{resultados}")
        # 58.10 é a média de uma cartela aleatória. 
        # Queremos saber a chance dela fechar significativamente antes (ex: 50 ou 52 bolas)
        prob_50 = (np.sum(resultados <= 50) / len(resultados)) * 100
        prob_55 = (np.sum(resultados <= 55) / len(resultados)) * 100
        media = np.mean(resultados_bola_fechamento)
        print('')
        print('-'*30)
        print(f"\n--- Resultados ---")
        print(f"Média de fechamento: {media:.2f}")
        print(f"Mínimo: {min(resultados_bola_fechamento)}")
        print(f"Máximo: {max(resultados_bola_fechamento)}")
        print(f"Primeiros 10 resultados: {sorted(resultados_bola_fechamento)[:10]}")
        print(f"monte_carlo_data: {len(resultados.astype(int).tolist())} ")
        print('-'*30)
        print('')
        
        return {
        "media": float(media),
        "prob_50": float(prob_50),
        "prob_55": float(prob_55),
        "monte_carlo_data": resultados.astype(int).tolist()
    }

    def preparar_contexto_agente(self, pergunta: str) -> str:
        # Entrega estatísticas se a pergunta sugerir análise
        if any(p in pergunta.lower() for p in ['chance', 'probabilidade', 'frequência', 'estatística']):
            return f"Dados Estatísticos: {json.dumps(self.memoria['estatisticas'])}"
        
        # Busca por similaridade
        emb = self.embedder.encode([pergunta])
        _, indices = self.index.search(emb.astype('float32'), 3)
        return "\n".join([self.memoria['textos'][i] for i in indices[0] if i != -1])

    def _carregar_estado(self):
        if os.path.exists(f"{self.caminho_base}\\jogos.pkl"):
            with open(f"{self.caminho_base}\\jogos.pkl", 'rb') as f:
                self.memoria = pickle.load(f)
            if os.path.exists(f"{self.caminho_base}.index"):
                self.index = faiss.read_index(f"{self.caminho_base}.index")

    