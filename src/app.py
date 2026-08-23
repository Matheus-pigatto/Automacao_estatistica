import streamlit as st
import subprocess
import os
from datetime import datetime
import sys
from automacao import buscar_titulo, script, limparFotos, trocar_titulo
import automacao_adb
import adb_manipulation
from agente import AgenteSorteiosDeepSeek
from config import DB_DIR
import json
import time
from db.rag import SorteioRAG

PATH_CONFIG = os.path.join(DB_DIR, "config_automacao.json")

def salvar_config_seguro(dados):
    path_temp = PATH_CONFIG + ".tmp"
    with open(path_temp, "w", encoding='utf-8') as f:
        json.dump(dados, f, indent=4)
    os.replace(path_temp, PATH_CONFIG)

# INICIALIZAÇÃO SEGURA (Roda apenas uma vez por sessão)
if "inicializado" not in st.session_state:
    if not os.path.exists(PATH_CONFIG) or os.path.getsize(PATH_CONFIG) == 0:
        salvar_config_seguro({"progresso": 0, "status": "AGUARDANDO", "msg_status": "Início"})
    st.session_state["inicializado"] = True

@st.cache_resource
def get_agente():
    with open("src\\api_deepseek.txt", "r") as txt:
        api_key = txt.read().strip()
        api_key = api_key.split('"')
    print("API Key loaded.")
    #print(api_key[1])
    return AgenteSorteiosDeepSeek(api_key=api_key[1])

agente = get_agente()
rag = SorteioRAG()

class SistemaUnificado:
    def run(self):
        """Executa a interface Streamlit"""
        st.sidebar.title("🎰 Sistema Unificado")
        
        menu = st.sidebar.radio(
            "Menu",
            ["🤖 Automações", "⚙️ Sistema"]
        )
        
        if menu == "🤖 Automações":
            self.pagina_automacoes()
        elif menu == "⚙️ Sistema":
            self.pagina_sistema()

    
    def pagina_automacoes(self):
        # Garante que o agente está acessível
        if 'agente' not in st.session_state:
            st.session_state.agente = get_agente()

        if 'rag' not in st.session_state:
            st.session_state.rag = rag
        
        # Atalho para facilitar a escrita
        agente_ia = st.session_state.agente

        
        
        if 'Atualizar estátistica' not in st.session_state:
            st.session_state.expandido_atualizar_estatistica = False

        if 'expandido_jogos_simulados' not in st.session_state:
            st.session_state.expandido_jogos_simulados = False

        if 'tabela_jogos_historico' not in st.session_state:
            st.session_state.tabela_jogos_historico = False


        st.subheader(body="🤖   Automações do Sistema Vale Cap", divider="grey")

        # 1. Pop-up de Monitoramento (Prioridade Máxima)
        pendente = self.monitorar_automacao()

        col1, col2 = st.columns(2)

        with col1:
            with st.expander("🔍 Configurar e Iniciar",width="stretch"):
                st.markdown("### Parâmetros de Busca")
                tipo_jogo = st.radio(label="Tipo de Jogo:", 
                                    options =["Vale Cap", "Hiper Cap"], 
                                    index=False,
                                    horizontal=True) # Exemplo de switch rápido
                tipo_jogo = tipo_jogo.lower().replace(" ", "")
                if tipo_jogo == "hipercap":
                    
                    qtd = st.radio(label=" Quantidade de cartelas:", options =[2, 5, 10], index=False, horizontal=True)
                else:
                    
                    qtd = st.radio(label="Quantidade de cartelas:", options =[1, 2, 4], index=False, horizontal=True)
                    
                if st.button("Iniciar Busca", key="start", use_container_width=True):
                    # Lógica de iniciar o robô
                    config_missao = {
                        "tipo": tipo_jogo,
                        "quantidade": qtd,
                        "status": "PROCESSANDO",
                        "progresso": 0,
                        "msg_status": "Iniciando...",
                        "timestamp": datetime.now().isoformat()
                    }
                    with open(os.path.join(DB_DIR, "config_automacao.json"), "w") as f:
                        json.dump(config_missao, f)
                    time.sleep(1)  # Pequena pausa para garantir que o arquivo foi escrito    
                    automacao_adb.main()  # Inicia o script de automação em background
                    st.success(f"Iniciando busca no jogo **{tipo_jogo}**, buscando **{qtd} cartelas**.",width=500)
                    
                    


            if st.button("📊  Atualizar estátistica", key="update", use_container_width=True):
                with st.spinner("Atualizando informações..."):
                    sucesso, mensagem = st.session_state.agente.atualizar_conhecimento()
        
                    if sucesso:
                        st.success(mensagem)
                        # Opcional: força um recarregamento para mostrar novos dados nos gráficos
                        st.session_state.expandido_estatistica = True
                        #st.rerun()
                    else:
                        st.error(mensagem)
            
            if st.button("📊  Visualizar tabela de jogos ", key="table", use_container_width=True):
                st.session_state.tabela_jogos_historico = not st.session_state.tabela_jogos_historico
                
                # No app.py, dentro da visualização de estatísticas
                #if st.session_state.agente.rag_sorteios.memoria['objetos_sorteio']:
                #    ultimos_jogos = st.session_state.agente.rag_sorteios.memoria['objetos_sorteio'][-4:]
                #    st.write("### 🕒 Últimos Sorteios Sincronizados")
                #    for jogo in reversed(ultimos_jogos):
                #        st.info(jogo.to_text())




        with col2:
            if st.button("🗑  Limpar imagens", key="clean", use_container_width=True):
                with st.spinner("Limpando..."):
                    if limparFotos(): st.success("Imagens limpas!")

            if st.button("🗃️ Painel de jogos simulados", key="simulado", use_container_width=True):
                st.session_state.expandido_jogos_simulados = not st.session_state.expandido_jogos_simulados


                #if st.session_state.expandido_jogos_simulados:
                    #with st.container(border=True):
                        #self.painel_simulado()
            
            if st.button("🔄 Atualizar Status Manualmente"):
                st.rerun()

        if st.session_state.get('tabela_jogos_historico', False):
            st.divider()
            # Busca o DataFrame já convertido
            df = st.session_state.agente.carregar_tabelas_rag_exibicao()
            
            if not df.empty:
                st.write("### 📜 Histórico de Sorteios Processados")
                # Exibe o dataframe com busca e ordenação habilitadas
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True # Esconde a coluna de índices (0, 1, 2...)
                )
            else:
                st.warning("Nenhum dado encontrado no histórico.")

        st.divider()
        
        st.subheader("🤖 Controle do Robô")

        # ÁREA DA BARRA DE PROGRESSO
        st.subheader("🛰️ Monitorização em Tempo Real",)
        monitorar = st.checkbox("Monitorar Robô em Tempo Real")
        if monitorar:
            time.sleep(10) # Espera 2 segundos antes de recarregar
            st.rerun()
        col_prog, col_msg = st.columns([1, 3])

        # Criamos espaços vazios que serão preenchidos pelo loop
        barra_progresso = st.progress(0)
        texto_progresso = st.empty()

        # Função para ler o estado atual
        def obter_progresso_atual():
            if os.path.exists(PATH_CONFIG):
                try:
                    with open(PATH_CONFIG, "r") as f:
                        return json.load(f)
                except:
                    pass
            return {"progresso": 0, "msg_status": "A aguardar início..."}

        # Loop de atualização automática (Fragmento ou Simples)
        # Nota: O Streamlit atualizará isto sempre que o script rodar ou via st.empty
        dados = obter_progresso_atual()
        barra_progresso.progress(dados["progresso"])
        texto_progresso.write(f"**Estado:** {dados['msg_status']}")


        st.divider()
        # --- SEÇÃO DO CHAT ---
        st.write("### 💬 Assistente de Análise Vale Cap")
        
        # Sincroniza e exibe histórico
        for message in agente.historico:
            if message["role"] == "system": continue
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Pergunte sobre probabilidade, desvio padrão..."):
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("Consultando RAG..."):
                    resposta = agente.consultar(prompt) # Certifique-se que o método chama-se consultar ou analisar
                    st.markdown(resposta)
            #st.rerun()

    
    def procurar_jogos(self, script_path):
        """Executa um script Python"""
        if os.path.exists(script_path):
            resultado = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True
            )
            if resultado.returncode == 0:
                st.success("Script executado com sucesso!")
                st.code(resultado.stdout)
            else:
                st.error(f"Erro: {resultado.stderr}")
    
    def selecionar_jogos(self):
        """Exemplo: limpar arquivos temporários"""
        #if os.name == 'nt':  # Windows
        #    os.system('cleanmgr /sagerun:1')
        #    st.info("Limpeza de disco iniciada no Windows")
        #else:  # Linux/Mac
        #    os.system('sudo apt-get autoremove -y')
        #    st.info("Limpeza de sistema iniciada")

    def atualizar_estatisticas(self):
            
        # Puxa os dados calculados que estão na memória do Agente
        rag = st.session_state.agente.rag_sorteios
        stats = rag.memoria.get('estatisticas', {})
        
        if not stats:
            st.warning("Nenhuma estatística disponível. Clique em 'Atualizar estatísticas' primeiro.")
            return

        # Painel de Resumo
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Jogos", stats['total_jogos'])
        c2.metric("Último Concurso", stats['ultimo_concurso'])
        c3.metric("Dezenas Mapeadas", "60")

        # Gráfico de Frequência das 20 mais sorteadas
        st.write("### 🔥 Top 20 Dezenas Mais Frequentes")
        import pandas as pd
        
        # Prepara os dados para o gráfico
        df_freq = pd.DataFrame(
            list(stats['frequencia'].items()), 
            columns=['Dezena', 'Ocorrências']
        ).sort_values(by='Ocorrências', ascending=False)
        
        # Exibe gráfico de barras
        st.bar_chart(df_freq.set_index('Dezena'))

        # Se houver métricas avançadas (Markov/Regressão), podemos mostrar um sumário
        if 'metricas_avancadas' in rag.memoria:
            with st.expander("🧠 Insights da Inteligência Avançada"):
                st.json(rag.memoria['metricas_avancadas'])

    def painel_simulado(self):
        pass
        #"""Exemplo: limpar arquivos temporários"""
        #if os.name == 'nt':  # Windows
        #    os.system('cleanmgr /sagerun:1')
        #    st.info("Limpeza de disco iniciada no Windows")
        #else:  # Linux/Mac
        #    os.system('sudo apt-get autoremove -y')
        #    st.info("Limpeza de sistema iniciada")

    def pagina_dashboard(self):
        """Página inicial do dashboard"""
        st.header("🏠 Dashboard Principal")
        st.write("Bem-vindo ao Sistema de Estatísticas para jogos de Sorteios!")
        st.write("Escolha uma opção abaixo.")

        col1, col2 = st.columns(2)
        col1.button("🎰 Adicionar ultimo sorteio")
        col2.button("📊 Procurar cartela para comprar", on_click=lambda: trocar_titulo())
        BASE_DIR = r"D:\Documentos\Projetos de programacao\Automacao de estatistica vale cap e compra"

    def monitorar_automacao(self):
        
        caminho_json = os.path.join(DB_DIR, "comunicacao_app.json")
        if not os.path.exists(caminho_json):
            return False

        with open(caminho_json, "r") as f:
            dados = json.load(f)

        # O status deve ser exatamente o que o robô gravou
        st.write(dados)
        if dados.get("status") == "aguardando_aprovacao":
            st.warning("⚠️ CARTELA FILTRADA ENCONTRADA!")
            
            # EXIBIÇÃO DO GRÁFICO (Garanta que matplotlib está instalado)
            if "monte_carlo_data" in dados and dados["monte_carlo_data"]:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(8, 3))
                ax.hist(dados["monte_carlo_data"], bins=30, color='gold', edgecolor='black')
                ax.axvline(dados['media'], color='red', label=f"Média: {dados['media']:.2f}")
                ax.legend()
                st.pyplot(fig) # MOSTRA O GRÁFICO
            
            else:
                st.info("Aguardando dados da simulação para gerar gráfico...")
            # MÉTRICAS
            st.write(f"Média: **{dados['media']:.2f}** | Prob 50: **{dados['prob_50']:.2f}%**")

            c1, c2 = st.columns(2)
            if c1.button("✅ COMPRAR", use_container_width=True):
                dados["status"] = "ACEITO"
                with open(caminho_json, "w") as f: json.dump(dados, f)
                st.rerun()
                
            if c2.button("❌ DESCARTAR", use_container_width=True):
                dados["status"] = "DESISTIDO"
                with open(caminho_json, "w") as f: json.dump(dados, f)
                st.rerun()
            return True
        return False

# Ponto de entrada PRINCIPAL
if __name__ == "__main__":
    app = SistemaUnificado()
    app.run()

