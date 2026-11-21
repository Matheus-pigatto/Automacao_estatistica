import os
import subprocess
import sys
from datetime import datetime
from typing import Callable

import matplotlib.pyplot as plt
import streamlit as st

from automacao_adb import limparFotos
from config import DB_DIR, PROJECT_ROOT, SRC_DIR
from database import DatabaseManager


class AbaRobo:
    """Aba principal: configuração da busca, controle do robô, aprovação e console ao vivo."""

    LOG_FILE: str = os.path.join(DB_DIR, "robo.log")

    def __init__(self, db: DatabaseManager, encerrar_fn: Callable[[], int]) -> None:
        self.db = db
        self.encerrar_fn = encerrar_fn

    def _ler_ultimas_linhas_log(self, qtd: int = 18) -> str:
        if not os.path.exists(self.LOG_FILE):
            return "Nenhum log registrado ainda. Inicie uma busca para acompanhar em tempo real."
        try:
            with open(self.LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                linhas = f.readlines()
            return "".join(linhas[-qtd:]) or "Log vazio."
        except Exception as e:
            return f"Erro ao ler log: {e}"

    def render(self) -> None:
        estado = self.db.obter_estado_robo()
        col_cfg, col_ctrl = st.columns([2, 1])

        with col_cfg:
            with st.container(border=True):
                st.subheader("🎯 Parâmetros da Busca")
                opcoes_jogo = ["Vale Cap", "Hiper Cap"]
                idx_jogo = 1 if estado.get("tipo") == "hipercap" else 0
                tipo_sel = st.radio("Tipo de Jogo:", options=opcoes_jogo, index=idx_jogo, horizontal=True)
                tipo_jogo = tipo_sel.lower().replace(" ", "")

                opcoes_qtd = [2, 5, 10] if tipo_jogo == "hipercap" else [1, 2, 4]
                qtd_salva = int(estado.get("quantidade", opcoes_qtd[0]))
                idx_qtd = opcoes_qtd.index(qtd_salva) if qtd_salva in opcoes_qtd else 0
                qtd = st.radio("Quantidade de cartelas:", options=opcoes_qtd, index=idx_qtd, horizontal=True)

                media_salva = min(58.30, max(57.50, float(estado.get("media_corte", 57.80))))
                media_corte = st.slider(
                    "Média de Corte RAG (menor = mais exigente)",
                    min_value=57.50,
                    max_value=58.30,
                    value=media_salva,
                    step=0.05,
                    help="57.77 = Top 1% | 57.80 = Top ~2% | 57.89 = Top 5% (1 em 20) | 57.95 = Top 10% | 58.10 = Mediana",
                )

        with col_ctrl:
            with st.container(border=True):
                st.subheader("⚡ Controle")
                if st.button("🚀 Iniciar Busca", key="start", type="primary", use_container_width=True):
                    proc_existente = st.session_state.get("robo_processo")
                    if proc_existente is not None and proc_existente.poll() is None:
                        st.warning("⚠️ O robô já está em execução em segundo plano.")
                    else:
                        self.db.atualizar_estado_robo(
                            tipo=tipo_jogo,
                            quantidade=int(qtd),
                            media_corte=float(media_corte),
                            status="PROCESSANDO",
                            progresso=0,
                            msg_status="Iniciando robô ADB...",
                        )
                        script_robo = os.path.join(SRC_DIR, "automacao_adb.py")
                        st.session_state["robo_processo"] = subprocess.Popen(
                            [sys.executable, script_robo],
                            cwd=PROJECT_ROOT,
                        )
                        st.success(f"Busca iniciada ({tipo_sel} | {qtd} cartela(s) | corte ≤ {media_corte:.2f}).")

                if st.button("🛑 Encerrar Busca", key="stop_busca", use_container_width=True):
                    qtd_enc = self.encerrar_fn()
                    if qtd_enc > 0:
                        st.warning(f"Busca encerrada ({qtd_enc} processo(s) finalizado(s)).")
                    else:
                        st.info("Nenhuma busca ativa encontrada. Status redefinido.")
                    st.rerun()

                if st.button("🗑 Limpar Capturas", key="clean", use_container_width=True):
                    limparFotos()
                    st.success("Capturas temporárias limpas!")

        st.divider()
        col_mon_h, col_chk = st.columns([3, 1])
        with col_mon_h:
            st.subheader("🛰️ Monitorização & Console ao Vivo")
        with col_chk:
            monitorar = st.checkbox("Atualizar a cada 5s", value=False)

        def _render_bloco_vivo() -> None:
            dados = self.db.obter_estado_robo()
            prog = max(0, min(100, int(dados.get("progresso", 0))))
            st.progress(prog)
            st.write(f"**Status:** `{dados.get('status', 'AGUARDANDO')}` | **Estado:** {dados.get('msg_status', 'Aguardando...')}")

            hoje = datetime.now().strftime("%Y-%m-%d")
            df_hoje = self.db.carregar_decisoes_df(hoje)
            if not df_hoje.empty:
                ultima = df_hoje.iloc[0]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Testadas Hoje", len(df_hoje))
                m2.metric("Última Cartela", str(ultima["ID_Cartela"]))
                m3.metric("Último Score", f"{float(ultima['Weighted_Score']):.2f}")
                m4.metric("Melhor Score Hoje", f"{df_hoje['Weighted_Score'].max():.2f}")

            self._render_card_aprovacao()

            with st.expander("🖥️ Console ao Vivo do Robô (db/robo.log)", expanded=True):
                st.code(self._ler_ultimas_linhas_log(18), language="log")

        if monitorar:
            @st.fragment(run_every=5)
            def _frag_monitor() -> None:
                _render_bloco_vivo()
            _frag_monitor()
        else:
            _render_bloco_vivo()

    def _render_card_aprovacao(self) -> None:
        dados = self.db.obter_aprovacao_pendente()
        if not dados or dados.get("status") != "aguardando_aprovacao":
            return

        with st.container(border=True):
            st.warning(f"🔥 CARTELA FILTRADA ENCONTRADA — Título **{dados.get('id_cartela', 'N/A')}**")
            st.write("**Dezenas:** " + " • ".join(f"`{d}`" for d in dados.get("dezenas", [])))

            mc_data = dados.get("monte_carlo_data") or []
            if mc_data:
                fig, ax = plt.subplots(figsize=(8, 2.8))
                ax.hist(mc_data, bins=30, color="gold", edgecolor="black")
                ax.axvline(dados["media"], color="red", label=f"Média RAG: {dados['media']:.2f}")
                if dados.get("media_pura"):
                    ax.axvline(dados["media_pura"], color="blue", linestyle="--", label=f"Base Aleatória: {dados['media_pura']:.2f}")
                ax.legend()
                st.pyplot(fig)
                plt.close(fig)

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
            if c1.button("✅ COMPRAR", key="btn_comprar", type="primary", use_container_width=True):
                self.db.atualizar_status_aprovacao("ACEITO")
                st.rerun()
            if c2.button("❌ DESCARTAR", key="btn_descartar", use_container_width=True):
                self.db.atualizar_status_aprovacao("DESISTIDO")
                st.rerun()
