import json
import os
import sqlite3
from datetime import datetime
from typing import Any

import pandas as pd

from config import DB_DIR

DB_PATH: str = os.path.join(DB_DIR, "valecap.db")


class DatabaseManager:
    """Gerenciador SQLite (modo WAL) para estado do robô, aprovações, decisões e limites."""

    def __init__(self, db_path: str = DB_PATH, migrar_csvs: bool = True) -> None:
        self.db_path = db_path
        self.migrar_csvs = migrar_csvs
        self._inicializado = False

    def get_conn(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def init_db(self) -> None:
        """Inicializa as tabelas no SQLite e importa logs CSV existentes caso ainda não estejam no banco."""
        if self._inicializado:
            return
        with self.get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS estado_robo (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    tipo TEXT DEFAULT 'valecap',
                    quantidade INTEGER DEFAULT 1,
                    media_corte REAL DEFAULT 57.80,
                    status TEXT DEFAULT 'AGUARDANDO',
                    progresso INTEGER DEFAULT 0,
                    msg_status TEXT DEFAULT 'Aguardando início...',
                    timestamp TEXT
                );

                CREATE TABLE IF NOT EXISTS aprovacao_pendente (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    id_cartela TEXT,
                    dezenas_json TEXT,
                    media REAL,
                    media_pura REAL,
                    ganho_rag REAL,
                    prob_50 REAL,
                    prob_55 REAL,
                    pure_score REAL,
                    weighted_score REAL,
                    resumo_json TEXT,
                    monte_carlo_json TEXT,
                    status TEXT,
                    timestamp TEXT
                );

                CREATE TABLE IF NOT EXISTS decisoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_dia TEXT,
                    hora TEXT,
                    id_cartela TEXT,
                    dezenas TEXT,
                    pure_score REAL,
                    weighted_score REAL,
                    decisao TEXT
                );

                CREATE TABLE IF NOT EXISTS limites_espera (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_aviso TEXT,
                    cartelas_ate_aviso INTEGER,
                    tempo_espera_segundos INTEGER,
                    tempo_espera_minutos REAL,
                    texto_aviso TEXT
                );
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO estado_robo (id, tipo, quantidade, media_corte, status, progresso, msg_status, timestamp)
                VALUES (1, 'valecap', 1, 57.80, 'AGUARDANDO', 0, 'Início', ?)
                """,
                (datetime.now().isoformat(),),
            )

            qtd_existente: int = conn.execute("SELECT COUNT(*) FROM decisoes").fetchone()[0]
            if self.migrar_csvs and qtd_existente == 0:
                self._migrar_csvs_legados(conn)
        self._inicializado = True

    def _migrar_csvs_legados(self, conn: sqlite3.Connection) -> None:
        if not os.path.exists(DB_DIR):
            return
        for nome in sorted(os.listdir(DB_DIR)):
            if nome.endswith("_log_decisoes.csv"):
                data_dia = nome.split("_log_decisoes.csv")[0]
                try:
                    df = pd.read_csv(os.path.join(DB_DIR, nome), sep=";")
                    for _, row in df.iterrows():
                        conn.execute(
                            """
                            INSERT INTO decisoes (data_dia, hora, id_cartela, dezenas, pure_score, weighted_score, decisao)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                data_dia,
                                str(row.get("Hora", "")),
                                str(row.get("ID_Cartela", "")),
                                str(row.get("Dezenas", "")),
                                float(row.get("Pure_Score", 0)),
                                float(row.get("Weighted_Score", 0)),
                                str(row.get("Decisao", "")),
                            ),
                        )
                except Exception:
                    pass

    def obter_estado_robo(self) -> dict[str, Any]:
        self.init_db()
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM estado_robo WHERE id = 1").fetchone()
            return dict(row) if row else {}

    def atualizar_estado_robo(self, **campos: Any) -> None:
        self.init_db()
        permitidos = {"tipo", "quantidade", "media_corte", "status", "progresso", "msg_status", "timestamp"}
        dados = {k: v for k, v in campos.items() if k in permitidos}
        if not dados:
            return
        dados.setdefault("timestamp", datetime.now().isoformat())
        sets = ", ".join(f"{k} = ?" for k in dados)
        valores = list(dados.values())
        with self.get_conn() as conn:
            conn.execute(f"UPDATE estado_robo SET {sets} WHERE id = 1", valores)

    def registrar_decisao(
        self,
        id_cartela: str,
        dezenas: list[Any],
        pure_score: float,
        weighted_score: float,
        decisao: str,
    ) -> None:
        self.init_db()
        agora = datetime.now()
        with self.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO decisoes (data_dia, hora, id_cartela, dezenas, pure_score, weighted_score, decisao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agora.strftime("%Y-%m-%d"),
                    agora.strftime("%H:%M:%S"),
                    str(id_cartela),
                    str(dezenas),
                    float(pure_score),
                    float(weighted_score),
                    str(decisao),
                ),
            )

    def listar_datas_decisoes(self) -> list[str]:
        self.init_db()
        with self.get_conn() as conn:
            rows = conn.execute("SELECT DISTINCT data_dia FROM decisoes ORDER BY data_dia DESC").fetchall()
            return [str(r[0]) for r in rows]

    def carregar_decisoes_df(self, data_dia: str | None = None) -> pd.DataFrame:
        self.init_db()
        with self.get_conn() as conn:
            if data_dia and data_dia != "Todas":
                rows = conn.execute(
                    "SELECT data_dia AS Data, hora AS Hora, id_cartela AS ID_Cartela, dezenas AS Dezenas, "
                    "pure_score AS Pure_Score, weighted_score AS Weighted_Score, decisao AS Decisao "
                    "FROM decisoes WHERE data_dia = ? ORDER BY id DESC",
                    (data_dia,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT data_dia AS Data, hora AS Hora, id_cartela AS ID_Cartela, dezenas AS Dezenas, "
                    "pure_score AS Pure_Score, weighted_score AS Weighted_Score, decisao AS Decisao "
                    "FROM decisoes ORDER BY id DESC"
                ).fetchall()
        return pd.DataFrame([dict(r) for r in rows])

    def registrar_limite_espera(
        self,
        timestamp_aviso: str,
        cartelas_ate_aviso: int,
        tempo_espera_s: int,
        texto_aviso: str,
    ) -> None:
        self.init_db()
        with self.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO limites_espera (timestamp_aviso, cartelas_ate_aviso, tempo_espera_segundos, tempo_espera_minutos, texto_aviso)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp_aviso, int(cartelas_ate_aviso), int(tempo_espera_s), round(tempo_espera_s / 60.0, 2), texto_aviso),
            )

    def carregar_limites_espera_df(self) -> pd.DataFrame:
        self.init_db()
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT timestamp_aviso AS Timestamp_Aviso, cartelas_ate_aviso AS Cartelas_Ate_Aviso, "
                "tempo_espera_segundos AS Tempo_Espera_Segundos, tempo_espera_minutos AS Tempo_Espera_Minutos, "
                "texto_aviso AS Texto_Aviso FROM limites_espera ORDER BY id DESC"
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows])

    def salvar_aprovacao_pendente(self, id_cartela: str, dezenas: list[Any], stats: dict[str, Any]) -> None:
        self.init_db()
        with self.get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO aprovacao_pendente (
                    id, id_cartela, dezenas_json, media, media_pura, ganho_rag,
                    prob_50, prob_55, pure_score, weighted_score, resumo_json,
                    monte_carlo_json, status, timestamp
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'aguardando_aprovacao', ?)
                """,
                (
                    str(id_cartela),
                    json.dumps(dezenas),
                    float(stats.get("media", 60.0)),
                    float(stats.get("media_pura", 58.1)),
                    float(stats.get("ganho_rag", 0.0)),
                    float(stats.get("prob_50", 0.0)),
                    float(stats.get("prob_55", 0.0)),
                    float(stats.get("pure_score", 0.0)),
                    float(stats.get("weighted_score", 0.0)),
                    json.dumps(stats.get("resumo_dezenas", {})),
                    json.dumps(stats.get("monte_carlo_data", [])),
                    datetime.now().isoformat(),
                ),
            )

    def obter_aprovacao_pendente(self) -> dict[str, Any] | None:
        self.init_db()
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM aprovacao_pendente WHERE id = 1").fetchone()
        if not row:
            return None
        d = dict(row)
        return {
            "id_cartela": d["id_cartela"],
            "dezenas": json.loads(d["dezenas_json"] or "[]"),
            "media": d["media"],
            "media_pura": d["media_pura"],
            "ganho_rag": d["ganho_rag"],
            "prob_50": d["prob_50"],
            "prob_55": d["prob_55"],
            "pure_score": d["pure_score"],
            "weighted_score": d["weighted_score"],
            "resumo_dezenas": json.loads(d["resumo_json"] or "{}"),
            "monte_carlo_data": json.loads(d["monte_carlo_json"] or "[]"),
            "status": d["status"],
            "timestamp": d["timestamp"],
        }

    def atualizar_status_aprovacao(self, novo_status: str) -> None:
        self.init_db()
        with self.get_conn() as conn:
            conn.execute("UPDATE aprovacao_pendente SET status = ? WHERE id = 1", (novo_status,))

    def limpar_aprovacao_pendente(self) -> None:
        self.init_db()
        with self.get_conn() as conn:
            conn.execute("DELETE FROM aprovacao_pendente WHERE id = 1")


# Instância padrão + wrappers tipados para compatibilidade
db = DatabaseManager()
get_conn = db.get_conn
init_db = db.init_db
obter_estado_robo = db.obter_estado_robo
atualizar_estado_robo = db.atualizar_estado_robo
registrar_decisao = db.registrar_decisao
listar_datas_decisoes = db.listar_datas_decisoes
carregar_decisoes_df = db.carregar_decisoes_df
registrar_limite_espera = db.registrar_limite_espera
carregar_limites_espera_df = db.carregar_limites_espera_df
salvar_aprovacao_pendente = db.salvar_aprovacao_pendente
obter_aprovacao_pendente = db.obter_aprovacao_pendente
atualizar_status_aprovacao = db.atualizar_status_aprovacao
limpar_aprovacao_pendente = db.limpar_aprovacao_pendente
