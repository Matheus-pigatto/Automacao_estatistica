import subprocess

import streamlit as st

from adb_manipulation import adb_controller
from config import RAG_DIR
from database import db
from db.rag import SorteioRAG
from ui import AbaEstatisticas, AbaRobo, AbaSimuladas, AbaSistema

st.set_page_config(page_title="Sistema Vale Cap", page_icon="🎰", layout="wide")
db.init_db()


@st.cache_resource
def get_rag() -> SorteioRAG:
    rag_inst = SorteioRAG(caminho_base=RAG_DIR)
    avancadas = rag_inst.memoria.get("metricas_avancadas", {})
    if rag_inst.memoria.get("objetos_sorteio") and "tendencias" not in avancadas:
        rag_inst._recalcular_e_salvar()
    return rag_inst


class SistemaUnificado:
    """Orquestrador principal da interface Streamlit modularizada."""

    def __init__(self) -> None:
        if "rag" not in st.session_state:
            st.session_state.rag = get_rag()
        self.aba_robo = AbaRobo(db=db, encerrar_fn=self.encerrar_busca)
        self.aba_simuladas = AbaSimuladas(db=db)
        self.aba_estatisticas = AbaEstatisticas(rag=st.session_state.rag, limpar_cache_fn=get_rag.clear)
        self.aba_sistema = AbaSistema(adb=adb_controller, encerrar_fn=self.encerrar_busca)

    def encerrar_busca(self) -> int:
        encerrados = 0
        proc = st.session_state.get("robo_processo")
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            encerrados += 1
        st.session_state["robo_processo"] = None

        try:
            cmd = (
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
                "| Where-Object { $_.CommandLine -like '*automacao_adb.py*' } "
                "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $_.ProcessId }"
            )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=8)
            pids = [l.strip() for l in res.stdout.splitlines() if l.strip().isdigit()]
            encerrados += len(pids)
        except Exception:
            pass

        db.atualizar_estado_robo(progresso=0, status="PARADO", msg_status="Busca encerrada pelo usuário")
        return encerrados

    def run(self) -> None:
        st.title("🎰 Sistema Unificado Vale Cap")
        t1, t2, t3, t4 = st.tabs(
            ["🤖 Robô & Aprovação", "🗃️ Cartelas Simuladas", "📊 Base & Estatísticas", "⚙️ Sistema"]
        )
        with t1:
            self.aba_robo.render()
        with t2:
            self.aba_simuladas.render()
        with t3:
            self.aba_estatisticas.render()
        with t4:
            self.aba_sistema.render()


if __name__ == "__main__":
    app = SistemaUnificado()
    app.run()
