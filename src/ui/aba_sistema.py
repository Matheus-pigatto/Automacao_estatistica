import os
from typing import Callable

import streamlit as st

from adb_manipulation import ADBController
from config import (
    ADB_DEVICE,
    DB_DIR,
    MOLDES_DIR,
    PDF_DIR,
    PROJECT_ROOT,
    RAG_DIR,
    SRC_DIR,
    SS_DIR,
)
from telegram_bot import TelegramBot


class AbaSistema:
    """Aba de diagnóstico de conexões (ADB BlueStacks, Telegram), processos e diretórios."""

    def __init__(self, adb: ADBController, encerrar_fn: Callable[[], int]) -> None:
        self.adb = adb
        self.encerrar_fn = encerrar_fn

    def render(self) -> None:
        st.subheader("⚙️ Sistema & Testes de Conexão")

        proc = st.session_state.get("robo_processo")
        em_execucao = proc is not None and proc.poll() is None
        if em_execucao:
            st.success(f"🟢 Robô ADB em execução (PID: {proc.pid})")
            if st.button("🛑 Encerrar Busca", key="stop_sys", type="primary"):
                self.encerrar_fn()
                st.rerun()
        else:
            st.info("⚪ Nenhum processo de robô iniciado por esta sessão.")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            with st.container(border=True):
                st.write("#### 📱 BlueStacks / ADB")
                st.caption(f"Alvo configurado: `{ADB_DEVICE}`")
                if st.button("🔌 Testar Conexão ADB", use_container_width=True):
                    with st.spinner("Conectando via ADB..."):
                        ok = self.adb.garantir_conexao_adb(timeout=10)
                        devs = self.adb.listar_dispositivos_online()
                        if ok and devs:
                            st.success(f"✅ Conectado! Dispositivos online: {', '.join(devs)}")
                        else:
                            st.error("❌ Nenhum dispositivo ADB respondeu. Verifique se o BlueStacks está aberto com ADB ativado.")

        with col_t2:
            with st.container(border=True):
                st.write("#### 📲 Bot Telegram")
                bot = TelegramBot()
                st.caption("Configurado no `.env`" if bot.esta_configurado() else "Aguardando `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env`")
                if st.button("✉️ Enviar Mensagem de Teste", use_container_width=True):
                    if not bot.esta_configurado():
                        st.warning("⚠️ Preencha `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no arquivo `.env` primeiro.")
                    else:
                        ok = bot.enviar_mensagem("🎰 <b>Teste do Sistema Vale Cap:</b> Bot conectado e pronto para aprovações!")
                        if ok:
                            st.success("✅ Mensagem enviada! Confira seu Telegram.")
                        else:
                            st.error("❌ Falha ao enviar mensagem. Verifique o token e o chat_id no `.env`.")

        with st.expander("📁 Diretórios & Banco de Dados"):
            st.json({
                "PROJECT_ROOT": PROJECT_ROOT,
                "SRC_DIR": SRC_DIR,
                "DB_DIR": DB_DIR,
                "SQLITE_DB": os.path.join(DB_DIR, "valecap.db"),
                "ROBO_LOG": os.path.join(DB_DIR, "robo.log"),
                "RAG_DIR": RAG_DIR,
                "PDF_DIR": PDF_DIR,
                "SS_DIR": SS_DIR,
                "MOLDES_DIR": MOLDES_DIR,
            })
