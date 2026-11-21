import logging
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from time import sleep, time

import numpy as np

from config import ADB_BIN, ADB_DEVICE, ANDROID_APP_PACKAGE, SS_DIR


class ADBController:
    """Controlador ADB orientado a objetos para interação headless e leitura XML no Android."""

    def __init__(
        self,
        adb_bin: str = ADB_BIN,
        device: str = ADB_DEVICE,
        app_package: str = ANDROID_APP_PACKAGE,
        ss_dir: str = SS_DIR,
    ) -> None:
        self.adb_bin: str = adb_bin
        self.device: str = device
        self.device_ativo: str = device
        self.app_package: str = app_package
        self.ss_dir: str = ss_dir

    def _run_adb(self, args: list[str], usar_device: bool = True, check: bool = False) -> subprocess.CompletedProcess[str]:
        cmd: list[str] = [self.adb_bin]
        if usar_device:
            cmd.extend(["-s", self.device_ativo])
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def listar_dispositivos_online(self) -> list[str]:
        """Retorna lista de dispositivos ADB atualmente online (estado 'device')."""
        try:
            res = self._run_adb(["devices"], usar_device=False)
            dispositivos: list[str] = []
            for linha in res.stdout.splitlines()[1:]:
                partes = linha.strip().split()
                if len(partes) >= 2 and partes[1] == "device":
                    dispositivos.append(partes[0])
            return dispositivos
        except Exception as e:
            logging.error(f"Erro ao listar dispositivos ADB: {e}")
            return []

    def garantir_conexao_adb(self, timeout: int = 60) -> bool:
        """Garante conexão ADB ativa com o BlueStacks/Android em segundo plano."""
        inicio = time()
        while time() - inicio < timeout:
            if ":" in self.device:
                self._run_adb(["connect", self.device], usar_device=False)

            online = self.listar_dispositivos_online()
            if self.device in online:
                self.device_ativo = self.device
                logging.info(f"✅ Dispositivo ADB conectado: {self.device_ativo}")
                return True
            if online:
                self.device_ativo = online[0]
                logging.info(f"✅ Dispositivo ADB autodetectado: {self.device_ativo}")
                return True

            logging.info(f"⏳ Aguardando dispositivo ADB ({self.device})...")
            sleep(3)

        logging.error(f"❌ Timeout ao conectar via ADB ({self.device}).")
        return False

    def abrir_app_android(self, package_name: str | None = None, espera_segundos: int = 15) -> bool:
        """Abre o aplicativo alvo via ADB e aguarda até `espera_segundos` para carregar."""
        pkg = (package_name or self.app_package).strip()
        if not pkg:
            logging.info("ℹ️ ANDROID_APP_PACKAGE não definido — assumindo que o app já está aberto.")
            return True

        try:
            res = self._run_adb(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
            if res.returncode == 0:
                logging.info(f"📱 App '{pkg}' iniciado via ADB. Aguardando até {espera_segundos}s...")
                inicio = time()
                while time() - inicio < espera_segundos:
                    sleep(3)
                    tree = self.dump_ui_xml(tentativas=1)
                    if self.existe_texto_na_tela(
                        ["Seu saldo", "Olá ", "Acessar conta", "Participe e Concorra", "Escolher o titulo"],
                        tree=tree,
                        contem=True,
                    ):
                        logging.info(f"✅ App '{pkg}' carregado em {int(time() - inicio)}s.")
                        return True
                return True
            logging.warning(f"⚠️ Não foi possível abrir '{pkg}' via ADB: {res.stderr.strip()}")
            return False
        except Exception as e:
            logging.error(f"Erro ao abrir app via ADB: {e}")
            return False

    def tap_adb(self, x: int, y: int, random_offset: int = 0) -> tuple[bool, int, int]:
        """Executa um toque direto nas coordenadas (x, y) via ADB."""
        ox = int(np.random.randint(-random_offset, random_offset + 1)) if random_offset > 0 else 0
        oy = int(np.random.randint(-random_offset, random_offset + 1)) if random_offset > 0 else 0
        tx, ty = int(x) + ox, int(y) + oy
        try:
            self._run_adb(["shell", "input", "tap", str(tx), str(ty)], check=True)
            return True, tx, ty
        except Exception as e:
            logging.error(f"Erro ao executar clique ADB em ({tx}, {ty}): {e}")
            return False, 0, 0

    def clicar_adb(
        self,
        x_ini: float,
        y_ini: float,
        w: float,
        h: float,
        random_offset: int = 0,
        centro: bool = False,
    ) -> tuple[bool, int, int]:
        """Clica no centro do retângulo informado."""
        cx = int(x_ini + (w / 2))
        cy = int(y_ini + (h / 2))
        return self.tap_adb(cx, cy, random_offset=0 if centro else random_offset)

    def escrever_texto_adb(self, texto: str) -> bool:
        """Envia texto para o campo focado via ADB."""
        try:
            texto_seguro = str(texto).replace(" ", "%s")
            self._run_adb(["shell", "input", "text", texto_seguro], check=True)
            sleep(0.8)
            return True
        except Exception as e:
            logging.error(f"Erro ao enviar texto via ADB: {e}")
            return False

    def swipe_adb(self, x1: int, y1: int, x2: int, y2: int, duracao: int) -> bool:
        """Executa gesto de arrastar (swipe) diretamente via ADB."""
        try:
            self._run_adb(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duracao)], check=True)
            return True
        except Exception as e:
            logging.error(f"Erro ao executar swipe ADB: {e}")
            return False

    def capturar_cartela_android(self) -> str:
        """Captura screenshot atual do Android e retorna o caminho local."""
        os.makedirs(self.ss_dir, exist_ok=True)
        caminho_completo = os.path.join(self.ss_dir, "print.PNG")
        self._run_adb(["shell", "screencap", "-p", "/sdcard/screen.png"], check=True)
        self._run_adb(["pull", "/sdcard/screen.png", caminho_completo], check=True)
        return caminho_completo

    @staticmethod
    def parse_bounds(bounds_str: str) -> tuple[int, int, int, int, int, int]:
        """Converte '[x1,y1][x2,y2]' em (x1, y1, x2, y2, cx, cy)."""
        nums = list(map(int, re.findall(r"\d+", bounds_str)))
        if len(nums) != 4:
            return 0, 0, 0, 0, 0, 0
        x1, y1, x2, y2 = nums
        return x1, y1, x2, y2, (x1 + x2) // 2, (y1 + y2) // 2

    def dump_ui_xml(self, tentativas: int = 3) -> ET.ElementTree | None:
        """Extrai a árvore de UI XML do Android via uiautomator dump."""
        os.makedirs(self.ss_dir, exist_ok=True)
        caminho_xml = os.path.join(self.ss_dir, "ui.xml")
        for _ in range(tentativas):
            try:
                res = self._run_adb(["shell", "uiautomator", "dump", "/sdcard/ui.xml"])
                if res.returncode == 0:
                    self._run_adb(["pull", "/sdcard/ui.xml", caminho_xml], check=True)
                    return ET.parse(caminho_xml)
            except Exception as e:
                logging.warning(f"⚠️ Falha temporária no dump XML: {e}")
            sleep(0.5)
        return None

    def encontrar_no_xml(
        self,
        tree: ET.ElementTree | None,
        textos: str | list[str],
        classe: str | None = None,
        contem: bool = False,
        min_y: int | None = None,
        max_y: int | None = None,
    ) -> ET.Element | None:
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

            match = any(
                (alvo in t or alvo in d) if contem else (alvo == t or alvo == d)
                for alvo in alvos_lower
            )
            if not match:
                continue

            _, y1, _, y2, _, cy = self.parse_bounds(el.attrib.get("bounds", ""))
            if y2 <= y1:
                continue
            if min_y is not None and cy < min_y:
                continue
            if max_y is not None and cy > max_y:
                continue
            return el

        return None

    def existe_texto_na_tela(
        self,
        textos: str | list[str],
        tree: ET.ElementTree | None = None,
        contem: bool = True,
    ) -> bool:
        """Verifica se algum dos textos está presente na árvore XML atual."""
        arvore = tree if tree is not None else self.dump_ui_xml()
        return self.encontrar_no_xml(arvore, textos, contem=contem) is not None

    def clicar_por_texto(
        self,
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
            tree = self.dump_ui_xml()
            no = self.encontrar_no_xml(tree, textos, classe=classe, contem=contem, min_y=min_y, max_y=max_y)
            if no is not None:
                _, _, _, _, cx, cy = self.parse_bounds(no.attrib.get("bounds", ""))
                rotulo = no.attrib.get("text") or no.attrib.get("content-desc") or str(textos)
                logging.info(f"✅ XML encontrado: '{rotulo}' -> clicando em ({cx}, {cy})")
                ok, _, _ = self.tap_adb(cx, cy, random_offset=random_offset)
                if ok:
                    sleep(delay_pos)
                    return True
            sleep(0.8)

        logging.warning(f"❌ Timeout XML: não encontrado {textos}")
        return False

    def extrair_cartela_xml(self, tree: ET.ElementTree | None = None) -> dict[str, object]:
        """Lê o número do título e as 20 dezenas diretamente da árvore XML da cartela."""
        arvore = tree if tree is not None else self.dump_ui_xml()
        if arvore is None:
            return {"titulo": "", "dezenas": [], "status": "alerta_falha_leitura"}

        titulo = ""
        dezenas: list[str] = []
        vistas: set[str] = set()

        for el in arvore.iter("node"):
            if "TextView" not in el.attrib.get("class", ""):
                continue
            txt = el.attrib.get("text", "").strip()
            if not txt:
                continue

            _, y1, _, y2, _, cy = self.parse_bounds(el.attrib.get("bounds", ""))
            if y2 <= y1:
                continue

            if not titulo and re.fullmatch(r"\d{1,3}\.\d{3}", txt) and 300 <= cy <= 800:
                titulo = txt
                continue

            if re.fullmatch(r"\d{2}", txt) and 500 <= cy <= 1350:
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

    def clicar_atualizar_cartela(self, tree: ET.ElementTree | None = None, duplo_clique: bool = True) -> bool:
        """Clica no botão circular azul de atualizar (↻) ao lado do número do título."""
        cx, cy = 856, 443
        arvore = tree if tree is not None else self.dump_ui_xml(tentativas=1)
        if arvore is not None:
            for el in arvore.iter("node"):
                t = el.attrib.get("text", "").strip()
                if t == "\ue5d5":
                    _, _, _, _, nx, ny = self.parse_bounds(el.attrib.get("bounds", ""))
                    if 780 <= nx <= 1100 and 350 <= ny <= 750:
                        cx, cy = nx, ny
                        break

        ok, _, _ = self.tap_adb(cx, cy, random_offset=3)
        if duplo_clique and ok:
            sleep(0.5)
            ok, _, _ = self.tap_adb(cx, cy, random_offset=3)
        return ok


def random_offset(valor_maximo: int) -> int:
    return int(np.random.randint(-valor_maximo, valor_maximo + 1))


# Instância padrão + wrappers para compatibilidade
adb_controller = ADBController()
_run_adb = adb_controller._run_adb
listar_dispositivos_online = adb_controller.listar_dispositivos_online
garantir_conexao_adb = adb_controller.garantir_conexao_adb
abrir_app_android = adb_controller.abrir_app_android
tap_adb = adb_controller.tap_adb
clicar_adb = adb_controller.clicar_adb
escrever_texto_adb = adb_controller.escrever_texto_adb
swipe_adb = adb_controller.swipe_adb
capturar_cartela_android = adb_controller.capturar_cartela_android
parse_bounds = ADBController.parse_bounds
dump_ui_xml = adb_controller.dump_ui_xml
encontrar_no_xml = adb_controller.encontrar_no_xml
existe_texto_na_tela = adb_controller.existe_texto_na_tela
clicar_por_texto = adb_controller.clicar_por_texto
extrair_cartela_xml = adb_controller.extrair_cartela_xml
clicar_atualizar_cartela = adb_controller.clicar_atualizar_cartela
