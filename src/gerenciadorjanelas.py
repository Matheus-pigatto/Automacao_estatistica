from numpy.random import f
import pyautogui
import pygetwindow as gw
import psutil
import time
from typing import Optional, List, Tuple

class GerenciadorJanelas:
    def __init__(self):
        self.ultima_janela_ativa = None
    
    def esperar_janela(self, titulo_ou_parte: str, timeout: int = 30, verificar_processo: bool = False) -> Tuple[bool, Optional[gw.Window]]:
        """
        Espera até que uma janela específica apareça
        
        Args:
            titulo_ou_parte: Parte do título da janela
            timeout: Tempo máximo de espera em segundos
            verificar_processo: Se True, também verifica se o processo está rodando
        
        Returns:
            (sucesso, janela)
        """
        inicio = time.time()
        
        while time.time() - inicio < timeout:
            # Verifica processo se necessário
            if verificar_processo:
                # Extrai possível nome do processo do título
                processo = self._extrair_nome_processo(titulo_ou_parte)
                if processo and not self._processo_esta_rodando(processo):
                    time.sleep(1)
                    continue
            
            # Procura a janela
            janelas = self.encontrar_janelas(titulo_ou_parte)
            
            if janelas:
                # Tenta trazer para frente
                for janela in janelas:
                    try:
                        if not janela.isActive:
                            janela.activate()
                            time.sleep(0.5)
                    except:
                        pass
                
                # Verifica se agora está ativa
                esta_ativa, janela = self.janela_esta_ativa(titulo_ou_parte)
                if esta_ativa:
                    return True, janela
            
            time.sleep(1)
        
        return False, None
    
    def janela_esta_ativa(self, titulo_ou_parte: str = None) -> Tuple[bool, Optional[gw.Window]]:
        """
        Verifica se uma janela específica está ativa (em primeiro plano)
        """
        try:
            janela_ativa = gw.getActiveWindow()
            
            if not janela_ativa:
                print("Nenhuma janela ativa encontrada.")
                return False, None
            
            # Se não especificou título, retorna qualquer janela ativa
            if not titulo_ou_parte:
                print("Janela ativa encontrada:", janela_ativa.title)
                return True, janela_ativa
            
            # Verifica se o título corresponde
            if titulo_ou_parte.lower() in janela_ativa.title.lower():
                print("Janela ativa corresponde ao título procurado:", janela_ativa.title)
                return True, janela_ativa
            
            return False, janela_ativa
            
        except Exception as e:
            print(f"Erro: {e}")
            return False, None
    
    def encontrar_janelas(self, titulo_ou_parte: str) -> List[gw.Window]:
        """
        Encontra todas as janelas que contêm o texto especificado
        """
        try:
            todas = gw.getAllWindows()
            return [j for j in todas if titulo_ou_parte.lower() in j.title.lower()]
        except Exception as e:
            print(f"Erro ao buscar janelas: {e}")
            return []
    
    def _processo_esta_rodando(self, nome_processo: str) -> bool:
        """
        Verifica se um processo está rodando
        """
        for proc in psutil.process_iter(['name']):
            try:
                if nome_processo.lower() in proc.info['name'].lower():
                    return True
            except:
                pass
        return False
    
    def _extrair_nome_processo(self, titulo_janela: str) -> Optional[str]:
        """
        Tenta extrair nome do processo do título da janela
        """
        mapeamento = {
            'bluestacks': 'hd-player.exe'
        
        }
        
        titulo_lower = titulo_janela.lower()
        for app, processo in mapeamento.items():
            if app in titulo_lower:
                return processo
        
        return None
    
    def executar_com_janela_ativa(self, titulo_janela: str, acao, *args, **kwargs):
        """
        Executa uma ação garantindo que a janela está ativa
        """
        # 1. Traz janela para frente
        sucesso, janela = self.esperar_janela(titulo_janela, timeout=10)
        
        if not sucesso:
            raise Exception(f"Janela '{titulo_janela}' não encontrada")
        
        # 2. Aguarda um pouco para garantir foco
        time.sleep(0.5)
        
        # 3. Executa a ação
        try:
            resultado = acao(*args, **kwargs)
            return resultado
        except Exception as e:
            print(f"Erro ao executar ação: {e}")
            raise
    
    def monitorar_mudancas(self, intervalo: float = 1.0):
        """
        Monitora mudanças na janela ativa
        """
        while True:
            esta_ativa, janela = self.janela_esta_ativa()
            
            if janela and janela != self.ultima_janela_ativa:
                print(f"[{time.strftime('%H:%M:%S')}] Janela mudou para: {janela.title}")
                self.ultima_janela_ativa = janela
            
            time.sleep(intervalo)

    def padronizar_janela(self, titulo, largura, altura, pos_x=0, pos_y=0) -> bool:
        try:
            janelas = self.encontrar_janelas(titulo)
            if janelas:
                print(f"🔍 Janela '{janelas[0]}' encontrada. Ajustando tamanho e posição...")
                win = janelas[0]
                if win.isMinimized:
                    win.restore() # Tira do minimizado
                
                tamanho = win.size
                posicao = win.topleft
                if tamanho.width != largura and tamanho.height != altura:
                    print(f"ℹ️ Janela '{titulo}' fora do tamanho {largura}x{altura}.")
                    win.resizeTo(largura, altura)
                
                if posicao.x != pos_x or posicao.y != pos_y:
                    print(f"ℹ️ Janela '{titulo}' fora da posição ({pos_x}, {pos_y}).")
                    win.moveTo(pos_x, pos_y)
                    
                print(f"✅ Janela '{titulo}' ajustada para {largura}x{altura}")
                return True
            else:
                print(f"❌ Janela '{titulo}' não encontrada.")
                return False
        except Exception as e:
            print(f"⚠️ Erro ao ajustar janela: {e}")
            return False