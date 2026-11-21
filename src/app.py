import streamlit as st
import subprocess
import os
from datetime import datetime
import sys
import pandas as pd
import automacao_adb
from automacao_adb import limparFotos
import adb_manipulation
from config import PROJECT_ROOT, SRC_DIR, DB_DIR, RAG_DIR, SS_DIR, MOLDES_DIR
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
def get_rag():
    rag_inst = SorteioRAG(caminho_base=RAG_DIR)
    avancadas = rag_inst.memoria.get('metricas_avancadas', {})
    if rag_inst.memoria.get('objetos_sorteio') and 'tendencias' not in avancadas:
        rag_inst._recalcular_e_salvar()
    return rag_inst

rag = get_rag()

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
        if 'rag' not in st.session_state:
            st.session_state.rag = get_rag()

        
        
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
                    proc_existente = st.session_state.get("robo_processo")
                    if proc_existente is not None and proc_existente.poll() is None:
                        st.warning("⚠️ O robô já está em execução em segundo plano.")
                    else:
                        # Lógica de iniciar o robô em processo separado (não trava o Streamlit)
                        config_missao = {
                            "tipo": tipo_jogo,
                            "quantidade": qtd,
                            "status": "PROCESSANDO",
                            "progresso": 0,
                            "msg_status": "Iniciando...",
                            "timestamp": datetime.now().isoformat()
                        }
                        salvar_config_seguro(config_missao)
                        script_robo = os.path.join(SRC_DIR, "automacao_adb.py")
                        st.session_state["robo_processo"] = subprocess.Popen(
                            [sys.executable, script_robo],
                            cwd=PROJECT_ROOT
                        )
                        st.success(f"Robô iniciado em segundo plano para **{tipo_jogo}**, buscando **{qtd} cartelas**.")
                    
                    


            if st.button("📊  Atualizar estatísticas", key="update", use_container_width=True):
                with st.spinner("Atualizando informações..."):
                    caminho_csv = os.path.join(PROJECT_ROOT, "historico_vale_cap.csv")
                    if not os.path.exists(caminho_csv):
                        st.error(f"Arquivo '{caminho_csv}' não encontrado.")
                    else:
                        qtd_novos = st.session_state.rag.sincronizar_com_csv(caminho_csv) or 0
                        if qtd_novos > 0:
                            st.success(f"Sucesso! {qtd_novos} novos sorteios integrados e estatísticas recalculadas.")
                        else:
                            st.info("A base já estava atualizada.")
                        st.session_state.expandido_estatistica = True
            
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
            objetos = st.session_state.rag.memoria.get('objetos_sorteio', [])
            df = pd.DataFrame([
                {
                    "Concurso/Sorteio": obj.concurso,
                    "Data": obj.data,
                    "Dezenas": ", ".join(map(str, obj.numeros)),
                    "Qtd": len(obj.numeros),
                }
                for obj in objetos
            ])
            
            if not df.empty:
                st.write("### 📜 Histórico de Sorteios Processados")
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True
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
        # --- SEÇÃO DE ESTATÍSTICAS LOCAIS (SEM API EXTERNA) ---
        st.write("### 📊 Estatísticas da Base RAG (100% Local)")
        self.atualizar_estatisticas()
        st.caption("💡 Gestão e análises aprofundadas sobre logs e estratégias são feitas diretamente pelo chat do Antigravity (sem custo de API).")

    
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
            
        # Puxa os dados calculados diretamente do RAG local
        rag_local = st.session_state.rag
        stats = rag_local.memoria.get('estatisticas', {})
        
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
        
        # Prepara os dados para o gráfico
        df_freq = pd.DataFrame(
            list(stats['frequencia'].items()), 
            columns=['Dezena', 'Ocorrências']
        ).sort_values(by='Ocorrências', ascending=False)
        
        # Exibe gráfico de barras
        st.bar_chart(df_freq.set_index('Dezena'))

        # Se houver métricas avançadas (Markov/Regressão), podemos mostrar um sumário
        if 'metricas_avancadas' in rag_local.memoria:
            with st.expander("🧠 Insights da Inteligência Avançada"):
                st.json(rag_local.memoria['metricas_avancadas'])

    def painel_simulado(self):
        pass
        #"""Exemplo: limpar arquivos temporários"""
        #if os.name == 'nt':  # Windows
        #    os.system('cleanmgr /sagerun:1')
        #    st.info("Limpeza de disco iniciada no Windows")
        #else:  # Linux/Mac
        #    os.system('sudo apt-get autoremove -y')
        #    st.info("Limpeza de sistema iniciada")

    def pagina_sistema(self):
        """Página de status e controle de processo do sistema"""
        st.subheader("⚙️ Configurações e Status do Sistema", divider="grey")
        proc = st.session_state.get("robo_processo")
        em_execucao = proc is not None and proc.poll() is None

        if em_execucao:
            st.success(f"🟢 Robô ADB em execução (PID: {proc.pid})")
            if st.button("🛑 Parar Robô", type="primary"):
                proc.terminate()
                st.session_state["robo_processo"] = None
                salvar_config_seguro({"progresso": 0, "status": "AGUARDANDO", "msg_status": "Parado pelo usuário"})
                st.rerun()
        else:
            st.info("⚪ Nenhum processo de robô em execução.")

        with st.expander("📁 Diretórios Configurados"):
            st.json({
                "PROJECT_ROOT": PROJECT_ROOT,
                "SRC_DIR": SRC_DIR,
                "DB_DIR": DB_DIR,
                "RAG_DIR": RAG_DIR,
                "SS_DIR": SS_DIR,
                "MOLDES_DIR": MOLDES_DIR,
            })

    def pagina_dashboard(self):
        """Página inicial do dashboard"""
        st.header("🏠 Dashboard Principal")
        st.write("Bem-vindo ao Sistema de Estatísticas para jogos de Sorteios!")
        st.write("Escolha uma opção abaixo.")

        col1, col2 = st.columns(2)
        col1.button("🎰 Adicionar ultimo sorteio")
        col2.button("📊 Procurar cartela para comprar")
        BASE_DIR = PROJECT_ROOT

    def monitorar_automacao(self):
        
        caminho_json = os.path.join(DB_DIR, "comunicacao_app.json")
        if not os.path.exists(caminho_json):
            return False

        with open(caminho_json, "r") as f:
            dados = json.load(f)

        # O status deve ser exatamente o que o robô gravou
        if dados.get("status") == "aguardando_aprovacao":
            st.warning(f"⚠️ CARTELA FILTRADA ENCONTRADA! (Título: {dados.get('id_cartela', 'N/A')})")
            
            # EXIBIÇÃO DO GRÁFICO (Garanta que matplotlib está instalado)
            if "monte_carlo_data" in dados and dados["monte_carlo_data"]:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(8, 3))
                ax.hist(dados["monte_carlo_data"], bins=30, color='gold', edgecolor='black')
                ax.axvline(dados['media'], color='red', label=f"Média RAG: {dados['media']:.2f}")
                if dados.get("media_pura"):
                    ax.axvline(dados['media_pura'], color='blue', linestyle='--', label=f"Base Aleatória: {dados['media_pura']:.2f}")
                ax.legend()
                st.pyplot(fig) # MOSTRA O GRÁFICO
            
            else:
                st.info("Aguardando dados da simulação para gerar gráfico...")

            # MÉTRICAS
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Média RAG", f"{dados.get('media', 0):.2f}", delta=f"{dados.get('ganho_rag', 0):+.2f} bolas")
            m2.metric("Score RAG", f"{dados.get('weighted_score', 0):.1f}/100")
            m3.metric("Prob ≤ 50", f"{dados.get('prob_50', 0):.2f}%")
            m4.metric("Prob ≤ 55", f"{dados.get('prob_55', 0):.2f}%")

            resumo = dados.get("resumo_dezenas", {})
            if resumo:
                st.caption(
                    f"Clusters: **Elite:** {resumo.get('elite', 0)} | "
                    f"**Médio:** {resumo.get('medio', 0)} | "
                    f"**Inerte:** {resumo.get('inerte', 0)} | "
                    f"**Atraso médio:** {resumo.get('atraso_medio', 0)} sorteios"
                )

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

