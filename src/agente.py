import datetime
from enum import auto
from openai import OpenAI
import json
from typing import List, Dict, Any
import automacao
from db.estrutura_de_dados import Sorteio
from db.rag import SorteioRAG
from time import sleep
import os

class AgenteSorteiosDeepSeek:
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        """
        Agente especializado em análise de sorteios com RAG
        """
        self.api_key = api_key
        self.model = model
        print(self.api_key)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"  # Verifique o endpoint
        )
        
        # Sistema RAG
        self.rag_sorteios = SorteioRAG()
        
        # Histórico de conversa
        self.caminho_base = r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\RAG\\"
        self.historico = self._carregar_historico()
        self._atualizar_dados_background()
   
  
    def _carregar_historico(self):
        caminho = f"{self.caminho_base}_historico.json"
        if os.path.exists(caminho):
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        return [{"role": "system", "content": "Você é um especialista em estatística de sorteios."}]

    def _atualizar_dados_background(self):
        """Carrega os sorteios salvos e recalcula estatísticas sem intervenção"""
        if os.path.exists(f"{self.caminho_base}_rag"):
            self.rag_sorteios.carregar(f"{self.caminho_base}_rag")
        # Aqui você pode disparar scripts de scraping ou atualização de DB
        self.estatisticas_atuais = self.rag_sorteios._recalcular_e_salvar()


    def consultar(self, pergunta: str, contexto_extra: str = ""):
        
        # 1. Pega os 3-5 sorteios similares (RAG padrão)
        contexto_rag = self.rag_sorteios.preparar_contexto_agente(pergunta)
        
        # 2. PEGA AS ESTATÍSTICAS GLOBAIS (O pulo do gato)
        # Isso garante que ele saiba o total de jogos e as dezenas frequentes sem precisar ler tudo
        stats_globais = self.rag_sorteios.memoria.get('estatisticas', {})
        
        resumo_estatistico = f"""
        ESTATÍSTICAS GLOBAIS DO SISTEMA:
        - Total de sorteios carregados: {stats_globais.get('total_jogos')}
        - Último sorteio: {stats_globais.get('ultimo_concurso')}
        - Top 10 dezenas mais frequentes: {stats_globais.get('frequencia')}
        """

        # 3. Monta o prompt com o resumo fixo + o contexto variável do RAG
        prompt_completo = f"""
        [ESTATÍSTICAS GERAIS]: {resumo_estatistico}
        [DADOS ESPECÍFICOS DO RAG]: {contexto_rag}
        [PERGUNTA]: {pergunta}
        """

        # 3. Adiciona a nova pergunta ao histórico
        self.historico.append({"role": "user", "content": prompt_completo})
        
        # --- LÓGICA DA JANELA DESLIZANTE (Manter 15 mensagens + System Prompt) ---
        # Se o histórico passar de 16 (1 System + 15 conversas)
        if len(self.historico) > 16:
            # Mantém o índice 0 (System) e pega os últimos 15 itens
            self.historico = [self.historico[0]] + self.historico[-15:]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.historico,
                temperature=0.3
            )
            resposta = response.choices[0].message.content
            
            # 4. Adiciona a resposta e salva
            self.historico.append({"role": "assistant", "content": resposta})
            self._salvar_estado()
            return resposta
            
        except Exception as e:
            return f"Erro: {str(e)}"

    def _salvar_estado(self):
        with open(f"{self.caminho_base}_historico.json", 'w', encoding='utf-8') as f:
            json.dump(self.historico, f, indent=2, ensure_ascii=False)

    def analisar_cartela_viva(self, dezenas_lidas):
        """Analisa a cartela oferecida pelo Vale Cap em tempo real"""
        
        # 1. Roda o Monte Carlo (35% de vantagem está aqui)
        score = self.rag_sorteios.simular_monte_carlo(dezenas_lidas)

        # 2. Gera o veredito
        if score >= 75:
            veredito = "🔥 COMPRA IMEDIATA! Estatisticamente superior."
        elif score >= 50:
            veredito = "✅ BOA. Está dentro da média competitiva."
        else:
            veredito = "❌ PASSE. Esta cartela tende a ser lenta."
            
        return {
            "score": score,
            "veredito": veredito,
            "media_projetada": "37 bolas"
        }
    
    def atualizar_conhecimento(self):
        try:
            # Caminho do CSV na raiz
            caminho_csv = os.path.join(os.getcwd(), "historico_vale_cap.csv") 
            if not os.path.exists(caminho_csv):
                return False, "Arquivo 'base_sorteios.csv' não encontrado na raiz."

            # Chama a função que você apresentou
            qtd_novos = self.rag_sorteios.sincronizar_com_csv(caminho_csv)
            if qtd_novos > 0:
                return True, f"Sucesso! {qtd_novos} novos sorteios foram integrados e as estatísticas foram atualizadas."
            else:
                return True, "A base já estava atualizada. Nenhuma mudança necessária."
            
        
        except Exception as e:
        # Captura qualquer erro (erro de leitura, erro no FAISS, etc)
            return False, f"Erro ao atualizar conhecimento: {str(e)}"
    
    def carregar_tabelas_rag_exibicao(self):
        import pickle
        import pandas as pd
        # Carrega o dicionário do Pickle
        with open(r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra\db\RAG\jogos.pkl", 'rb') as f:
            dados_pkl = pickle.load(f)
        
        # Extrai a lista de objetos 'Sorteio'
        objetos = dados_pkl.get('objetos_sorteio', [])
        
        # Converte a lista de objetos em uma lista de dicionários simples
        lista_para_tabela = []
        for obj in objetos:
            lista_para_tabela.append({
                "Concurso/Sorteio": obj.concurso,
                "Data": obj.data,
                "Dezenas": ", ".join(map(str, obj.numeros)),
                "Qtd": len(obj.numeros)
            })
        
        # Retorna um DataFrame formatado
        return pd.DataFrame(lista_para_tabela)
    
    def testar_rag(self, titulo, dezenas: List[int]):
        """Testa o RAG com um conjunto de dezenas fornecido"""
        print("Testando o titulo:", titulo)
        print("Testando RAG com dezenas:", dezenas)
        return self.rag_sorteios.simular_monte_carlo(dezenas_cartela=dezenas)