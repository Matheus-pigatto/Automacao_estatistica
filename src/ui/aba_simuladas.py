import streamlit as st

from database import DatabaseManager


class AbaSimuladas:
    """Aba de histórico das cartelas simuladas no Monte Carlo e limites de espera."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def render(self) -> None:
        st.subheader("🗃️ Histórico de Cartelas Simuladas (SQLite)")
        datas = self.db.listar_datas_decisoes()
        if not datas:
            st.info("Nenhuma cartela foi simulada ainda. Inicie uma busca na primeira aba.")
        else:
            filtro_data = st.selectbox("Filtrar por data:", ["Todas"] + datas, index=1 if datas else 0)
            df_sim = self.db.carregar_decisoes_df(filtro_data)

            if not df_sim.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Cartelas Testadas", len(df_sim))
                c2.metric("Melhor Score RAG", f"{df_sim['Weighted_Score'].max():.2f}")
                c3.metric("Média Score RAG", f"{df_sim['Weighted_Score'].mean():.2f}")
                aprovadas = int(df_sim["Decisao"].astype(str).str.contains("Comprado", case=False).sum())
                c4.metric("Aprovadas", aprovadas)

                st.write("#### 📈 Evolução do Score RAG")
                df_chart = df_sim.iloc[::-1].reset_index(drop=True)[["Weighted_Score", "Pure_Score"]]
                st.line_chart(df_chart)

                st.dataframe(df_sim, use_container_width=True, hide_index=True)

        df_esp = self.db.carregar_limites_espera_df()
        if not df_esp.empty:
            st.divider()
            st.subheader("⏳ Histórico de Avisos de Limite / Espera")
            st.dataframe(df_esp, use_container_width=True, hide_index=True)
