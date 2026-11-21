try:
    import faiss
except ImportError:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

import numpy as np
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
    def __init__(self, model_name='all-MiniLM-L6-v2', caminho_base=None, usar_embeddings=False):
        self.embedder = SentenceTransformer(model_name) if (usar_embeddings and SentenceTransformer is not None) else None
        if caminho_base is None:
            caminho_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "RAG")
        self.caminho_base = caminho_base
        os.makedirs(self.caminho_base, exist_ok=True)
        
        # Estado Interno Único
        self.memoria = {
            'objetos_sorteio': [], 
            'textos': [],
            'estatisticas': {},
            'metricas_avancadas': {} # <--- ADICIONADO PARA GUARDAR MARKOV/ERLANG
        }
        
        self.index = faiss.IndexFlatL2(self.embedder.get_sentence_embedding_dimension()) if (self.embedder is not None and faiss is not None) else None
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
                
                # Adiciona ao FAISS (se embeddings estiverem habilitados)
                if self.embedder is not None and self.index is not None:
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

        def _chave_data(s):
            try:
                return (datetime.strptime(str(s.data), "%d/%m/%Y"), str(s.concurso))
            except Exception:
                return (datetime.min, str(s.concurso))

        sorteios_ordenados = sorted(sorteios, key=_chave_data)
        self.memoria['objetos_sorteio'] = sorteios_ordenados
        todos_numeros = [n for s in sorteios_ordenados for n in s.numeros]
        
        # 1. Estatísticas Básicas
        self.memoria['estatisticas'] = {
            'frequencia': dict(Counter(todos_numeros).most_common(20)),
            'total_jogos': len(sorteios_ordenados),
            'ultimo_concurso': sorteios_ordenados[-1].concurso
        }

        # 2. Métricas Avançadas (Markov, Erlang, Regressão)
        # Movido para cá para ser calculado apenas uma vez na sincronização
        self.memoria['metricas_avancadas'] = self._processar_inteligencia_avancada()

        try:
            with open(caminho_arquivo, 'wb') as f:
                # Protocolo 4 ou superior é mais estável para objetos grandes
                pickle.dump(self.memoria, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Salva o FAISS separadamente se estiver habilitado
            if faiss is not None and self.index is not None:
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
            tipo = getattr(s, 'tipo', None)
            if not tipo and isinstance(s.concurso, str) and " - " in s.concurso:
                tipo = s.concurso.split(" - ")[-1].strip()
            if tipo:
                sorteios_por_tipo[tipo].append(len(s.numeros))
        
        if len(sorteios_por_tipo) > 1:
            f_stat, anova_p = stats.f_oneway(*sorteios_por_tipo.values())
        else:
            anova_p = 1.0

        # 5. K-MEANS / QUARTIS (Clusterização de Números)
        # Divide os números em 3 grupos: Elite, Médio, Inerte
        frequencia_completa = {n: contagem_real.get(n, 0) for n in range(1, 61)}
        dados_cluster = np.array([frequencia_completa[i] for i in range(1, 61)]).reshape(-1, 1)
        limiar_elite = np.percentile(dados_cluster, 75)
        limiar_inerte = np.percentile(dados_cluster, 25)
        
        clusters = {}
        for n in range(1, 61):
            freq = frequencia_completa[n]
            if freq >= limiar_elite: clusters[n] = "Elite"
            elif freq <= limiar_inerte: clusters[n] = "Inerte"
            else: clusters[n] = "Médio"

        # 6. TENDÊNCIA RECENTE (Últimos 20 sorteios vs média histórica)
        janela_recente = sorteios[-20:]
        contagem_recente = Counter(n for s in janela_recente for n in s.numeros)
        media_recente = sum(contagem_recente.values()) / 60.0 if janela_recente else 1.0
        tendencias = {
            n: round((contagem_recente.get(n, 0) - media_recente) / max(media_recente, 1e-6), 4)
            for n in range(1, 61)
        }

        # 7. ERLANG / ATRASO (Tempo de Espera)
        atrasos = {}
        for n in range(1, 61):
            distancia = 0
            for s in reversed(sorteios):
                if n in s.numeros: break
                distancia += 1
            atrasos[n] = distancia

        # 8. MARKOV (Transição)
        transicoes = Counter()
        for i in range(len(sorteios)-1):
            for n1 in sorteios[i].numeros:
                for n2 in sorteios[i+1].numeros:
                    transicoes[(n1, n2)] += 1

        return {
            "chi_score": float(chi_stat),
            "p_value": float(p_value),
            "status": "Aleatório" if p_value > 0.05 else "Tendencioso",
            'entropia_alvo': float(media_entropia_ganhadora),
            'anova_p_valor': float(anova_p),
            'frequencia_completa': frequencia_completa,
            'tendencias': tendencias,
            'clusters': clusters,             # Dicionário {número: categoria}
            'atrasos': atrasos,               # Dicionário {número: sorteios_sem_sair}
            'transicoes': dict(transicoes.most_common(100)),
            'timestamp_analise': datetime.now().isoformat()
        }

    def _calcular_pesos_rag(self) -> np.ndarray:
        """
        Gera vetor de probabilidades (tamanho 60, índices 0..59 -> dezenas 1..60)
        combinando frequência histórica, tendência recente e atraso do RAG.
        """
        avancadas = self.memoria.get('metricas_avancadas', {})
        if not avancadas:
            return np.full(60, 1.0 / 60.0, dtype=np.float64)

        freq_raw = avancadas.get('frequencia_completa', {})
        tend_raw = avancadas.get('tendencias', {})
        atrasos_raw = avancadas.get('atrasos', {})

        freqs = np.array([float(freq_raw.get(n, freq_raw.get(str(n), 0))) for n in range(1, 61)], dtype=np.float64)
        media_freq = np.mean(freqs) if np.sum(freqs) > 0 else 1.0
        fator_freq = (freqs / media_freq) if np.sum(freqs) > 0 else np.ones(60, dtype=np.float64)

        tends = np.array([float(tend_raw.get(n, tend_raw.get(str(n), 0.0))) for n in range(1, 61)], dtype=np.float64)
        atrasos = np.array([float(atrasos_raw.get(n, atrasos_raw.get(str(n), 0.0))) for n in range(1, 61)], dtype=np.float64)
        media_atraso = max(float(np.mean(atrasos)), 1.0)
        fator_atraso = np.clip((atrasos - media_atraso) / media_atraso, -0.5, 1.0)

        # Combinação balanceada e estável: base histórica + tendência recente + pressão de atraso
        pesos = np.clip(fator_freq + 0.25 * tends + 0.15 * fator_atraso, 0.25, None)
        return pesos / np.sum(pesos)

    def _rodar_simulacao_vetorizada(self, indices_cartela: np.ndarray, pesos: np.ndarray, num_simulacoes: int) -> np.ndarray:
        """
        Simulação exata de sorteio sem reposição ponderado via estatísticas de ordem
        Exponenciais: Exp(rate = peso_i) -> ordem crescente equivale a sorteio sem reposição com pesos.
        Retorna a bola (20..60) em que a cartela fecha em cada simulação.
        """
        tempos = np.random.exponential(scale=1.0 / pesos, size=(num_simulacoes, 60))
        tempo_fechamento = tempos[:, indices_cartela].max(axis=1, keepdims=True)
        return np.sum(tempos <= tempo_fechamento, axis=1)

    def simular_comparativo(self, dezenas_cartela, num_simulacoes=5000):
        """Mantém compatibilidade retornando scores puro e ponderado pelo RAG."""
        res = self.simular_monte_carlo(dezenas_cartela, num_simulacoes=num_simulacoes, usar_pesos_rag=True)
        return {
            "pure_score": res["pure_score"],
            "weighted_score": res["weighted_score"],
            "media_bolas_viciado": round(res["media"], 2),
            "media_bolas_puro": round(res["media_pura"], 2),
            "ganho_rag": res["ganho_rag"],
        }

    def simular_monte_carlo(self, dezenas_cartela, num_simulacoes=10000, usar_pesos_rag=True):
        """
        Simulação de Monte Carlo vetorizada usando os pesos estatísticos do RAG
        (frequência, tendência recente e atraso) comparada à linha de base uniforme.
        """
        try:
            dezenas_int = sorted(set(int(d) for d in dezenas_cartela))
        except Exception as e:
            print(f"Erro ao converter dezenas: {e}")
            return {
                "media": 60.0, "media_pura": 58.1, "ganho_rag": 0.0,
                "prob_50": 0.0, "prob_55": 0.0,
                "pure_score": 0.0, "weighted_score": 0.0,
                "resumo_dezenas": {}, "monte_carlo_data": []
            }

        if len(dezenas_int) != 20 or any(d < 1 or d > 60 for d in dezenas_int):
            print(f"Cartela inválida para simulação ({len(dezenas_int)} dezenas): {dezenas_int}")
            return {
                "media": 60.0, "media_pura": 58.1, "ganho_rag": 0.0,
                "prob_50": 0.0, "prob_55": 0.0,
                "pure_score": 0.0, "weighted_score": 0.0,
                "resumo_dezenas": {}, "monte_carlo_data": []
            }

        indices = np.array([d - 1 for d in dezenas_int], dtype=np.int64)
        pesos_uniforme = np.full(60, 1.0 / 60.0, dtype=np.float64)
        pesos_rag = self._calcular_pesos_rag() if usar_pesos_rag else pesos_uniforme

        resultados_rag = self._rodar_simulacao_vetorizada(indices, pesos_rag, num_simulacoes)
        resultados_puro = self._rodar_simulacao_vetorizada(indices, pesos_uniforme, min(num_simulacoes, 3000))

        media_rag = float(np.mean(resultados_rag))
        media_pura = float(np.mean(resultados_puro))
        ganho_rag = round(media_pura - media_rag, 2)

        prob_50 = float((np.sum(resultados_rag <= 50) / len(resultados_rag)) * 100.0)
        prob_55 = float((np.sum(resultados_rag <= 55) / len(resultados_rag)) * 100.0)

        # Escala 0..100 centrada na média teórica uniforme (~58.10 = 50 pts; cada 1 bola mais rápido soma ~15 pts)
        pure_score = round(float(np.clip(50.0 + (58.10 - media_pura) * 15.0, 0.0, 100.0)), 2)
        weighted_score = round(float(np.clip(50.0 + (58.10 - media_rag) * 15.0, 0.0, 100.0)), 2)

        # Resumo qualitativo da cartela segundo os clusters/atrasos do RAG
        avancadas = self.memoria.get('metricas_avancadas', {})
        clusters = avancadas.get('clusters', {})
        atrasos = avancadas.get('atrasos', {})
        contagem_clusters = Counter(clusters.get(d, clusters.get(str(d), "Médio")) for d in dezenas_int)
        atraso_medio = float(np.mean([atrasos.get(d, atrasos.get(str(d), 0)) for d in dezenas_int])) if atrasos else 0.0

        resumo_dezenas = {
            "elite": contagem_clusters.get("Elite", 0),
            "medio": contagem_clusters.get("Médio", 0),
            "inerte": contagem_clusters.get("Inerte", 0),
            "atraso_medio": round(atraso_medio, 2),
        }

        print(f"--- Monte Carlo RAG ({num_simulacoes} sims) ---")
        print(f"Média RAG: {media_rag:.2f} | Média Pura: {media_pura:.2f} | Ganho: {ganho_rag:+.2f} bolas")
        print(f"Prob <=50: {prob_50:.2f}% | Prob <=55: {prob_55:.2f}% | Score RAG: {weighted_score:.1f}/100")
        print(f"Clusters: {resumo_dezenas}")

        return {
            "media": round(media_rag, 2),
            "media_pura": round(media_pura, 2),
            "ganho_rag": ganho_rag,
            "prob_50": round(prob_50, 2),
            "prob_55": round(prob_55, 2),
            "pure_score": pure_score,
            "weighted_score": weighted_score,
            "resumo_dezenas": resumo_dezenas,
            "monte_carlo_data": resultados_rag.astype(int).tolist()
        }

    def preparar_contexto_agente(self, pergunta: str) -> str:
        # Entrega estatísticas se a pergunta sugerir análise
        if any(p in pergunta.lower() for p in ['chance', 'probabilidade', 'frequência', 'estatística']):
            return f"Dados Estatísticos: {json.dumps(self.memoria['estatisticas'])}"
        
        # Busca por similaridade (quando FAISS/embeddings estiverem ativos)
        if self.embedder is not None and self.index is not None:
            emb = self.embedder.encode([pergunta])
            _, indices = self.index.search(emb.astype('float32'), 3)
            return "\n".join([self.memoria['textos'][i] for i in indices[0] if i != -1])
        return f"Dados Estatísticos: {json.dumps(self.memoria.get('estatisticas', {}))}"

    def _carregar_estado(self):
        caminho_pkl = os.path.join(self.caminho_base, "jogos.pkl")
        caminho_index = os.path.join(self.caminho_base, "jogos.index")
        if os.path.exists(caminho_pkl):
            with open(caminho_pkl, 'rb') as f:
                self.memoria = pickle.load(f)
            if faiss is not None and self.embedder is not None and os.path.exists(caminho_index):
                self.index = faiss.read_index(caminho_index)

    