import base64
import json
import os
import re
import sys
from datetime import datetime
from time import sleep

import pandas as pd
import pypdf
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_DIR, PDF_DIR, PROJECT_ROOT, RAG_DIR
from db.rag import SorteioRAG

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}
CSV_PATH = os.path.join(PROJECT_ROOT, "historico_vale_cap.csv")


def _decodificar_pdfemb_urls(html: str) -> list[str]:
    """Extrai URLs de PDF embutidas no parâmetro base64 ?pdfemb-data=..."""
    urls = []
    for b64 in re.findall(r"pdfemb-data=([A-Za-z0-9+/=_-]+)", html):
        try:
            pad = "=" * (-len(b64) % 4)
            decoded = base64.b64decode(b64 + pad).decode("utf-8", errors="ignore")
            data = json.loads(decoded)
            u = data.get("url", "").strip()
            if u and u.lower().endswith(".pdf"):
                urls.append(u)
        except Exception:
            continue
    return list(dict.fromkeys(urls))


def extrair_sorteios_do_pdf(caminho_pdf: str, data_fallback: str | None = None) -> list[dict]:
    """Extrai os 4 sorteios (data + dezenas) de um PDF oficial do Vale Cap."""
    texto_completo = ""
    try:
        with open(caminho_pdf, "rb") as f:
            leitor = pypdf.PdfReader(f)
            for pag in leitor.pages:
                texto_completo += (pag.extract_text() or "") + "\n"
    except Exception as e:
        print(f"⚠️ Erro ao ler PDF {os.path.basename(caminho_pdf)}: {e}")
        return []

    if not texto_completo.strip():
        return []

    # 1. Data do sorteio
    data_sorteio = data_fallback
    m_data = re.search(r"(\d{2}/\d{2}/\d{4})", texto_completo[:400])
    if m_data:
        data_sorteio = m_data.group(1)
    if not data_sorteio:
        return []

    # 2. Localiza cada sorteio (1º, 2º, 3º, 4º) e suas linhas de dezenas (1..60)
    # Usa a mesma lógica estrutural do PDF do Vale Cap: 4 blocos sequenciais de números
    linhas = [l.strip() for l in texto_completo.splitlines() if l.strip()]
    blocos_sorteio: list[list[int]] = []
    atual: list[int] = []

    for linha in linhas:
        tokens = linha.split()
        if tokens and all(t.isdigit() and 1 <= int(t) <= 60 for t in tokens):
            nums = [int(t) for t in tokens]
            atual.extend(nums)
            # Nos PDFs do Vale Cap, cada linha cheia tem ~12-15 números; a última linha de um sorteio é mais curta
            if len(linha) < 32 and len(atual) >= 25:
                blocos_sorteio.append(atual)
                atual = []
                if len(blocos_sorteio) == 4:
                    break
        else:
            if len(atual) >= 25:
                blocos_sorteio.append(atual)
                atual = []
                if len(blocos_sorteio) == 4:
                    break
            elif atual:
                atual = []

    if len(atual) >= 25 and len(blocos_sorteio) < 4:
        blocos_sorteio.append(atual)

    if len(blocos_sorteio) != 4:
        return []

    registros = []
    for idx, dezenas in enumerate(blocos_sorteio, 1):
        registros.append({
            "Data": data_sorteio,
            "Sorteio": f"{idx}o Sorteio",
            "Dezenas": " ".join(map(str, dezenas)),
            "Total_Numeros": len(dezenas),
        })
    return registros


def atualizar_base_portal_r3(max_paginas: int = 8, data_minima: str = "01/05/2025") -> dict:
    """
    Baixa novos PDFs do Portal R3 até `data_minima` (parando quando já estiverem no CSV),
    extrai os 4 sorteios, ordena o CSV cronologicamente e sincroniza o RAG local.
    """
    os.makedirs(PDF_DIR, exist_ok=True)
    dt_limite = datetime.strptime(data_minima, "%d/%m/%Y")

    if os.path.exists(CSV_PATH):
        df_existente = pd.read_csv(CSV_PATH, sep=";", encoding="utf-8-sig")
    else:
        df_existente = pd.DataFrame(columns=["Data", "Sorteio", "Dezenas", "Total_Numeros"])

    datas_existentes = set(df_existente["Data"].astype(str).unique())
    novos_registros = []
    pdfs_baixados = 0
    posts_verificados = 0
    parar = False

    for pag in range(1, max_paginas + 1):
        if parar:
            break
        url_pag = (
            "https://www.portalr3.com.br/editoria/vale-cap/"
            if pag == 1
            else f"https://www.portalr3.com.br/editoria/vale-cap/page/{pag}/"
        )
        print(f"🔎 Varrendo página {pag}: {url_pag}")
        try:
            resp = requests.get(url_pag, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"⚠️ HTTP {resp.status_code} na página {pag}. Encerrando.")
                break
        except Exception as e:
            print(f"⚠️ Erro ao acessar página {pag}: {e}")
            break

        links = re.findall(r'<h2[^>]*>.*?<a[^>]+href=["\']([^"\']+)["\']', resp.text, re.S | re.I)
        links = list(dict.fromkeys(links))
        if not links:
            break

        for link in links:
            m_url_dt = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", link)
            data_url_str = None
            if m_url_dt:
                dt_post = datetime(int(m_url_dt.group(1)), int(m_url_dt.group(2)), int(m_url_dt.group(3)))
                data_url_str = dt_post.strftime("%d/%m/%Y")
                if dt_post < dt_limite:
                    parar = True
                    break
                if data_url_str in datas_existentes:
                    continue

            posts_verificados += 1
            try:
                r_post = requests.get(link, headers=HEADERS, timeout=20)
                if r_post.status_code != 200:
                    continue
                pdf_urls = _decodificar_pdfemb_urls(r_post.text)
                if not pdf_urls:
                    continue

                slug = link.rstrip("/").split("/")[-1]
                caminho_pdf = os.path.join(PDF_DIR, f"{slug}.pdf")
                if not os.path.exists(caminho_pdf):
                    r_pdf = requests.get(pdf_urls[0], headers=HEADERS, timeout=30)
                    if r_pdf.status_code == 200 and r_pdf.content.startswith(b"%PDF"):
                        with open(caminho_pdf, "wb") as f:
                            f.write(r_pdf.content)
                        pdfs_baixados += 1
                        print(f"  📥 Baixado: {slug}.pdf")
                    else:
                        continue

                regs = extrair_sorteios_do_pdf(caminho_pdf, data_fallback=data_url_str)
                if regs:
                    data_real = regs[0]["Data"]
                    if data_real not in datas_existentes:
                        novos_registros.extend(regs)
                        datas_existentes.add(data_real)
                        print(f"  ✅ Extraído: {data_real} (4 sorteios)")
                sleep(0.3)
            except Exception as e:
                print(f"  ⚠️ Erro no post {link}: {e}")
                continue

    if novos_registros:
        df_novos = pd.DataFrame(novos_registros)
        df_final = pd.concat([df_existente, df_novos], ignore_index=True)
    else:
        df_final = df_existente.copy()

    # Remove duplicatas e ordena cronologicamente (mais antigo -> mais recente)
    df_final = df_final.drop_duplicates(subset=["Data", "Sorteio"], keep="last")
    df_final["_dt"] = pd.to_datetime(df_final["Data"], format="%d/%m/%Y", errors="coerce")
    df_final = df_final.sort_values(by=["_dt", "Sorteio"]).drop(columns=["_dt"]).reset_index(drop=True)
    df_final.to_csv(CSV_PATH, index=False, sep=";", encoding="utf-8-sig")

    # Sincroniza o RAG local
    rag = SorteioRAG(caminho_base=RAG_DIR)
    qtd_rag = rag.sincronizar_com_csv(CSV_PATH) or 0
    rag._recalcular_e_salvar()

    ultima_data = df_final["Data"].iloc[-1] if not df_final.empty else "N/A"
    resumo = {
        "posts_verificados": posts_verificados,
        "pdfs_baixados": pdfs_baixados,
        "novos_sorteios_csv": len(novos_registros),
        "novos_sorteios_rag": qtd_rag,
        "total_sorteios": len(df_final),
        "ultima_data": ultima_data,
    }
    print("\n🏁 ATUALIZAÇÃO CONCLUÍDA:", resumo)
    return resumo


if __name__ == "__main__":
    atualizar_base_portal_r3()
