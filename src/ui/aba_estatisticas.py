from typing import Callable

import pandas as pd
import streamlit as st

from db.rag import SorteioRAG


class AbaEstatisticas:
    """Aba de base histórica, atualização via Portal R3, Qui-Quadrado e atrasos."""

    def __init__(self, rag: SorteioRAG, limpar_cache_fn: Callable[[], None]) -> None:
        self.rag = rag
        self.limpar_cache_fn = limpar_cache_fn

    def render(self) -> None:
        st.subheader("📊 Base Histórica & Estatísticas RAG")

        col_btn1, _ = st.columns([1, 3])
        with col_btn1:
            if st.button("🌐 Atualizar Base (Portal R3)", use_container_width=True):
                with st.spinner("Buscando novos sorteios no Portal R3 e recalculando RAG..."):
                    from webScrapy import atualizar_base_portal_r3
                    resumo = atualizar_base_portal_r3(max_paginas=2)
                    self.limpar_cache_fn()
                    st.session_state.pop("rag", None)
                    st.success(
                        f"Base atualizada até **{resumo['ultima_data']}**! "
                        f"Total: **{resumo['total_sorteios']}** sorteios (+{resumo['novos_sorteios_csv']} novos)."
                    )
                    st.rerun()

        stats = self.rag.memoria.get("estatisticas", {})
        avancadas = self.rag.memoria.get("metricas_avancadas", {})

        if not stats:
            st.warning("Nenhuma estatística disponível. Clique em 'Atualizar Base (Portal R3)'.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total de Sorteios", stats.get("total_jogos", 0))
        c2.metric("Último Concurso", stats.get("ultimo_concurso", "-"))
        c3.metric("Qui-Quadrado", f"{avancadas.get('chi_score', 0):.2f}")
        c4.metric("Status do Globo", f"{avancadas.get('status', '-')} (p={avancadas.get('p_value', 1):.2f})")

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("#### 🔥 Top 20 Dezenas Mais Frequentes")
            df_freq = pd.DataFrame(
                list(stats["frequencia"].items()),
                columns=["Dezena", "Ocorrências"],
            ).sort_values(by="Ocorrências", ascending=False)
            st.bar_chart(df_freq.set_index("Dezena"))

        with col_g2:
            st.write("#### ⏱️ Top 15 Dezenas Mais Atrasadas")
            atrasos = avancadas.get("atrasos", {})
            clusters = avancadas.get("clusters", {})
            if atrasos:
                df_atr = pd.DataFrame([
                    {
                        "Dezena": str(int(k)).zfill(2),
                        "Sorteios sem sair": int(v),
                        "Cluster": clusters.get(int(k), clusters.get(str(k), "-")),
                    }
                    for k, v in atrasos.items()
                ]).sort_values(by="Sorteios sem sair", ascending=False).head(15)
                st.dataframe(df_atr, use_container_width=True, hide_index=True)

        with st.expander("📜 Tabela Completa de Sorteios"):
            objetos = self.rag.memoria.get("objetos_sorteio", [])
            df_hist = pd.DataFrame([
                {
                    "Concurso/Sorteio": obj.concurso,
                    "Data": obj.data,
                    "Dezenas": ", ".join(map(str, obj.numeros)),
                    "Qtd": len(obj.numeros),
                }
                for obj in reversed(objetos)
            ])
            st.dataframe(df_hist, use_container_width=True, hide_index=True)

        if avancadas:
            with st.expander("🧠 Insights da Inteligência Avançada (JSON)"):
                st.json(avancadas)
