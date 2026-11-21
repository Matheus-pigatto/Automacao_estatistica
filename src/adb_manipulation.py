import logging
import re
import os
import subprocess
import xml.etree.ElementTree as ET
from time import sleep, time
import numpy as np
from config import SS_DIR, ADB_BIN, ADB_DEVICE, ANDROID_APP_PACKAGE

_DEVICE_ATIVO = ADB_DEVICE


def _run_adb(args: list[str], usar_device: bool = True, check: bool = False) -> subprocess.CompletedProcess:
    cmd = [ADB_BIN]
    if usar_device:
        cmd.extend(["-s", _DEVICE_ATIVO])
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def listar_dispositivos_online() -> list[str]:
    """Retorna lista de dispositivos ADB atualmente online (estado 'device')."""
    try:
        res = _run_adb(["devices"], usar_device=False)
        dispositivos = []
        for linha in res.stdout.splitlines()[1:]:
            partes = linha.strip().split()
            if len(partes) >= 2 and partes[1] == "device":
                dispositivos.append(partes[0])
        return dispositivos
    except Exception as e:
        logging.error(f"Erro ao listar dispositivos ADB: {e}")
        return []


def garantir_conexao_adb(timeout: int = 60) -> bool:
    """
    Garante que o BlueStacks/Android esteja conectado via ADB (100% em segundo plano,
    sem precisar focar janela nem usar mouse).
    """
    global _DEVICE_ATIVO
    inicio = time()
    while time() - inicio < timeout:
        if ":" in ADB_DEVICE:
            _run_adb(["connect", ADB_DEVICE], usar_device=False)

        online = listar_dispositivos_online()
        if ADB_DEVICE in online:
            _DEVICE_ATIVO = ADB_DEVICE
            logging.info(f"✅ Dispositivo ADB conectado: {_DEVICE_ATIVO}")
            return True
        if online:
            _DEVICE_ATIVO = online[0]
            logging.info(f"✅ Dispositivo ADB autodetectado: {_DEVICE_ATIVO}")
            return True

        logging.info(f"⏳ Aguardando dispositivo ADB ({ADB_DEVICE})... Certifique-se de que o BlueStacks está aberto com ADB ativado.")
        sleep(3)

    logging.error(f"❌ Timeout ao conectar via ADB ({ADB_DEVICE}).")
    return False


def abrir_app_android(package_name: str | None = None) -> bool:
    """Abre o aplicativo alvo diretamente via ADB (sem clique de mouse)."""
    pkg = (package_name or ANDROID_APP_PACKAGE).strip()
    if not pkg:
        logging.info("ℹ️ ANDROID_APP_PACKAGE não definido no .env — assumindo que o app já está aberto.")
        return True

    try:
        res = _run_adb(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
        if res.returncode == 0:
            logging.info(f"📱 App '{pkg}' aberto/trazido para frente via ADB.")
            sleep(3)
            return True
        logging.warning(f"⚠️ Não foi possível abrir '{pkg}' via ADB: {res.stderr.strip()}")
        return False
    except Exception as e:
        logging.error(f"Erro ao abrir app via ADB: {e}")
        return False


def tap_adb(x: int, y: int, random_offset: int = 0) -> tuple[bool, int, int]:
    """Executa um toque direto nas coordenadas (x, y) via ADB."""
    ox = int(np.random.randint(-random_offset, random_offset + 1)) if random_offset > 0 else 0
    oy = int(np.random.randint(-random_offset, random_offset + 1)) if random_offset > 0 else 0
    tx, ty = int(x) + ox, int(y) + oy
    try:
        _run_adb(["shell", "input", "tap", str(tx), str(ty)], check=True)
        return True, tx, ty
    except Exception as e:
        logging.error(f"Erro ao executar clique ADB em ({tx}, {ty}): {e}")
        return False, 0, 0


def clicar_adb(x_ini, y_ini, w, h, random_offset: int = 0, centro: bool = False):
    """Compatibilidade com assinatura anterior (recebe retângulo e clica no centro)."""
    cx = int(x_ini + (w / 2))
    cy = int(y_ini + (h / 2))
    return tap_adb(cx, cy, random_offset=0 if centro else random_offset)


def escrever_texto_adb(texto: str) -> bool:
    """Envia texto para o campo focado via ADB (sem usar teclado do Windows)."""
    try:
        texto_seguro = str(texto).replace(" ", "%s")
        _run_adb(["shell", "input", "text", texto_seguro], check=True)
        sleep(0.8)
        return True
    except Exception as e:
        logging.error(f"Erro ao enviar texto via ADB: {e}")
        return False


def swipe_adb(x1, y1, x2, y2, duracao) -> bool:
    """Executa gesto de arrastar (swipe) diretamente via ADB."""
    try:
        _run_adb(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duracao)], check=True)
        return True
    except Exception as e:
        logging.error(f"Erro ao executar swipe ADB: {e}")
        return False


def capturar_cartela_android() -> str:
    """Captura screenshot atual do Android (útil para debug/auditoria)."""
    os.makedirs(SS_DIR, exist_ok=True)
    caminho_completo = os.path.join(SS_DIR, "print.PNG")
    _run_adb(["shell", "screencap", "-p", "/sdcard/screen.png"], check=True)
    _run_adb(["pull", "/sdcard/screen.png", caminho_completo], check=True)
    return caminho_completo


# =====================================================================
# NAVEGAÇÃO E LEITURA VIA XML (UIAutomator) - SEM MOLDES PNG E SEM OCR
# =====================================================================

def parse_bounds(bounds_str: str) -> tuple[int, int, int, int, int, int]:
    """Converte '[x1,y1][x2,y2]' em (x1, y1, x2, y2, cx, cy)."""
    nums = list(map(int, re.findall(r"\d+", bounds_str)))
    if len(nums) != 4:
        return 0, 0, 0, 0, 0, 0
    x1, y1, x2, y2 = nums
    return x1, y1, x2, y2, (x1 + x2) // 2, (y1 + y2) // 2


def dump_ui_xml(tentativas: int = 3) -> ET.ElementTree | None:
    """Extrai a árvore de UI XML do Android via uiautomator dump."""
    os.makedirs(SS_DIR, exist_ok=True)
    caminho_xml = os.path.join(SS_DIR, "ui.xml")
    for _ in range(tentativas):
        try:
            res = _run_adb(["shell", "uiautomator", "dump", "/sdcard/ui.xml"])
            if res.returncode == 0:
                _run_adb(["pull", "/sdcard/ui.xml", caminho_xml], check=True)
                return ET.parse(caminho_xml)
        except Exception as e:
            logging.warning(f"⚠️ Falha temporária no dump XML: {e}")
        sleep(0.5)
    return None


def encontrar_no_xml(
    tree: ET.ElementTree | None,
    textos: str | list[str],
    classe: str | None = None,
    contem: bool = False,
    min_y: int | None = None,
    max_y: int | None = None,
):
    """Procura o primeiro nó XML cujo text ou content-desc corresponda ao(s) texto(s)."""
    if tree is None:
        return None
    lista_alvos = [textos] if isinstance(textos, str) else list(textos)
    alvos_lower = [a.lower() for a in lista_alvos]

    for el in tree.iter("node"):
        c = el.attrib.get("class", "")
        if classe and classe not in c:
            continue

        t = el.attrib.get("text", "").strip().lower()
        d = el.attrib.get("content-desc", "").strip().lower()

        match = False
        for alvo in alvos_lower:
            if contem:
                if alvo in t or alvo in d:
                    match = True
                    break
            else:
                if alvo == t or alvo == d:
                    match = True
                    break

        if not match:
            continue

        _, y1, _, y2, _, cy = parse_bounds(el.attrib.get("bounds", ""))
        if y2 <= y1:
            continue
        if min_y is not None and cy < min_y:
            continue
        if max_y is not None and cy > max_y:
            continue
        return el

    return None


def existe_texto_na_tela(
    textos: str | list[str],
    tree: ET.ElementTree | None = None,
    contem: bool = True,
) -> bool:
    """Verifica se algum dos textos está presente na árvore XML atual."""
    arvore = tree if tree is not None else dump_ui_xml()
    return encontrar_no_xml(arvore, textos, contem=contem) is not None


def clicar_por_texto(
    textos: str | list[str],
    timeout: int = 10,
    contem: bool = False,
    classe: str | None = None,
    min_y: int | None = None,
    max_y: int | None = None,
    random_offset: int = 5,
    delay_pos: float = 1.5,
) -> bool:
    """Localiza elemento por texto/content-desc no XML e clica no seu centro via ADB."""
    inicio = time()
    while time() - inicio < timeout:
        tree = dump_ui_xml()
        no = encontrar_no_xml(tree, textos, classe=classe, contem=contem, min_y=min_y, max_y=max_y)
        if no is not None:
            _, _, _, _, cx, cy = parse_bounds(no.attrib.get("bounds", ""))
            rotulo = no.attrib.get("text") or no.attrib.get("content-desc") or str(textos)
            logging.info(f"✅ XML encontrado: '{rotulo}' -> clicando em ({cx}, {cy})")
            ok, _, _ = tap_adb(cx, cy, random_offset=random_offset)
            if ok:
                sleep(delay_pos)
                return True
        sleep(0.8)

    logging.warning(f"❌ Timeout XML: não encontrado {textos}")
    return False


def extrair_cartela_xml(tree: ET.ElementTree | None = None) -> dict:
    """
    Lê o número do título (ex: '918.614') e as 20 dezenas diretamente da árvore XML
    da tela da cartela — 100% exato e sem depender de OCR.
    """
    arvore = tree if tree is not None else dump_ui_xml()
    if arvore is None:
        return {"titulo": "", "dezenas": [], "status": "alerta_falha_leitura"}

    titulo = ""
    dezenas = []
    vistas = set()

    for el in arvore.iter("node"):
        if "TextView" not in el.attrib.get("class", ""):
            continue
        txt = el.attrib.get("text", "").strip()
        if not txt:
            continue

        _, y1, _, y2, _, cy = parse_bounds(el.attrib.get("bounds", ""))
        if y2 <= y1:
            continue

        # Número do título (ex: 918.614) na parte superior do card
        if not titulo and re.fullmatch(r"\d{1,3}\.\d{3}", txt) and 400 <= cy <= 800:
            titulo = txt
            continue

        # Dezenas (01..60) dentro da grade da cartela
        if re.fullmatch(r"\d{2}", txt) and 650 <= cy <= 1350:
            val = int(txt)
            if 1 <= val <= 60 and txt not in vistas:
                vistas.add(txt)
                dezenas.append(txt)
                if len(dezenas) == 20:
                    break

    status = "sucesso" if len(dezenas) == 20 else "alerta_falha_leitura"
    return {
        "titulo": titulo or "desconhecido",
        "dezenas": dezenas,
        "status": status,
    }


def clicar_atualizar_cartela(tree: ET.ElementTree | None = None) -> bool:
    """
    Clica no botão circular azul de atualizar (↻ / ícone '\ue5d5') ao lado do número do título
    para carregar uma nova cartela com 1 toque via ADB.
    """
    arvore = tree if tree is not None else dump_ui_xml()
    if arvore is not None:
        for el in arvore.iter("node"):
            t = el.attrib.get("text", "").strip()
            if t == "\ue5d5":
                x1, y1, x2, y2, cx, cy = parse_bounds(el.attrib.get("bounds", ""))
                if 800 <= cx <= 1100 and 450 <= cy <= 700:
                    ok, _, _ = tap_adb(cx, cy, random_offset=3)
                    return ok
    # Fallback na posição padrão do botão ↻ em 1440x2560
    ok, _, _ = tap_adb(898, 574, random_offset=3)
    return ok


def random_offset(valor_maximo: int) -> int:
    return int(np.random.randint(-valor_maximo, valor_maximo + 1))
