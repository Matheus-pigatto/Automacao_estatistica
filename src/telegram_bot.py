import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramBot:
    """Bot leve para enviar cartelas promissoras e receber aprovação (COMPRAR/DESCARTAR) via Telegram."""

    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = (token if token is not None else TELEGRAM_BOT_TOKEN).strip()
        self.chat_id = str(chat_id if chat_id is not None else TELEGRAM_CHAT_ID).strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self._last_update_id = 0

    def esta_configurado(self) -> bool:
        return bool(self.token and self.chat_id)

    def _limpar_updates_antigos(self) -> None:
        if not self.esta_configurado():
            return
        try:
            r = requests.get(f"{self.base_url}/getUpdates", params={"timeout": 0}, timeout=5)
            data = r.json()
            if data.get("ok") and data.get("result"):
                self._last_update_id = data["result"][-1]["update_id"] + 1
        except Exception as e:
            logging.warning(f"⚠️ Telegram (limpar updates): {e}")

    def enviar_mensagem(self, texto: str) -> bool:
        if not self.esta_configurado():
            return False
        try:
            r = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": self.chat_id, "text": texto, "parse_mode": "HTML"},
                timeout=10,
            )
            return r.status_code == 200 and r.json().get("ok", False)
        except Exception as e:
            logging.warning(f"⚠️ Erro ao enviar mensagem Telegram: {e}")
            return False

    def enviar_cartela_aprovacao(self, titulo: str, dezenas: list, stats: dict) -> int | None:
        """Envia a cartela com botões inline ✅ COMPRAR e ❌ DESCARTAR."""
        if not self.esta_configurado():
            return None

        self._limpar_updates_antigos()
        resumo = stats.get("resumo_dezenas", {})
        dezenas_str = " ".join(str(d).zfill(2) for d in dezenas)
        texto = (
            f"🔥 <b>CARTELA PROMISSORA ENCONTRADA!</b>\n\n"
            f"🎫 <b>Título:</b> <code>{titulo}</code>\n"
            f"🔢 <b>Dezenas:</b>\n<code>{dezenas_str}</code>\n\n"
            f"📊 <b>Média RAG:</b> {stats.get('media', 0):.2f} bolas "
            f"(Base: {stats.get('media_pura', 58.1):.2f} | Ganho: {stats.get('ganho_rag', 0):+.2f})\n"
            f"⭐ <b>Score RAG:</b> {stats.get('weighted_score', 0):.1f}/100\n"
            f"🎯 <b>Prob ≤50:</b> {stats.get('prob_50', 0):.2f}% | <b>Prob ≤55:</b> {stats.get('prob_55', 0):.2f}%\n"
            f"🧩 <b>Clusters:</b> Elite {resumo.get('elite', 0)} | "
            f"Médio {resumo.get('medio', 0)} | Inerte {resumo.get('inerte', 0)}"
        )

        teclado = {
            "inline_keyboard": [[
                {"text": "✅ COMPRAR", "callback_data": f"ACEITO:{titulo}"},
                {"text": "❌ DESCARTAR", "callback_data": f"DESISTIDO:{titulo}"},
            ]]
        }

        try:
            r = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": texto,
                    "parse_mode": "HTML",
                    "reply_markup": teclado,
                },
                timeout=10,
            )
            data = r.json()
            if data.get("ok"):
                msg_id = data["result"]["message_id"]
                logging.info(f"📲 Cartela {titulo} enviada para o Telegram (msg_id={msg_id}).")
                return msg_id
            logging.warning(f"⚠️ Falha Telegram sendMessage: {data}")
        except Exception as e:
            logging.warning(f"⚠️ Erro ao enviar cartela no Telegram: {e}")
        return None

    def verificar_decisao(self, titulo_esperado: str) -> str | None:
        """
        Consulta (sem travar) se o usuário clicou em COMPRAR ou DESCARTAR no Telegram.
        Retorna 'ACEITO', 'DESISTIDO' ou None.
        """
        if not self.esta_configurado():
            return None

        try:
            params = {"timeout": 1}
            if self._last_update_id:
                params["offset"] = self._last_update_id
            r = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=5)
            data = r.json()
            if not data.get("ok"):
                return None

            for upd in data.get("result", []):
                self._last_update_id = upd["update_id"] + 1
                cb = upd.get("callback_query")
                if not cb:
                    continue

                chat_origem = str(cb.get("message", {}).get("chat", {}).get("id", ""))
                if chat_origem != self.chat_id:
                    continue

                payload = cb.get("data", "")
                if ":" not in payload:
                    continue
                acao, titulo_cb = payload.split(":", 1)
                if titulo_cb != str(titulo_esperado) or acao not in ("ACEITO", "DESISTIDO"):
                    continue

                # Confirma o clique no Telegram e remove os botões
                requests.post(
                    f"{self.base_url}/answerCallbackQuery",
                    json={"callback_query_id": cb["id"], "text": f"Decisão registrada: {acao}"},
                    timeout=5,
                )
                rotulo = "✅ APROVADA (COMPRAR)" if acao == "ACEITO" else "❌ DESCARTADA"
                msg = cb.get("message", {})
                if msg.get("message_id"):
                    requests.post(
                        f"{self.base_url}/editMessageReplyMarkup",
                        json={"chat_id": self.chat_id, "message_id": msg["message_id"], "reply_markup": {"inline_keyboard": []}},
                        timeout=5,
                    )
                self.enviar_mensagem(f"🎫 Título <code>{titulo_esperado}</code>: <b>{rotulo}</b>")
                return acao
        except Exception as e:
            logging.warning(f"⚠️ Erro ao consultar Telegram: {e}")

        return None
