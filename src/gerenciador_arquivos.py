import os
from pathlib import Path
from src.config import PROJECT_ROOT, DB_DIR, SRC_DIR, SS_DIR

def arquivos_na_pasta(pasta: str) -> list:
    match pasta.lower():
            case 'projeto':
                caminho_pasta = PROJECT_ROOT
            case 'src':
                caminho_pasta = SRC_DIR
            case 'db':
                caminho_pasta = DB_DIR
            case 'ss':
                caminho_pasta = SS_DIR
            case _:
                print(f"Pasta desconhecida: {pasta}")
    """Retorna uma lista de arquivos na pasta especificada"""
    arquivos_na_pasta = Path(__file__).parent
    if not arquivos_na_pasta.exists() or not arquivos_na_pasta.is_dir():
        print(f"A pasta especificada não existe ou não é um diretório: {arquivos_na_pasta}")
        return []
    print("Arquivos na pasta:")
    return [str(arquivo) for arquivo in arquivos_na_pasta.iterdir()]

def deletar_arquivo(caminho_arquivo: str) -> None:
    """Deleta o arquivo no caminho especificado"""
    try:
        os.remove(caminho_arquivo)
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {caminho_arquivo}")
    except Exception as e:
        print(f"Erro ao deletar o arquivo {caminho_arquivo}: {e}")

def manter_arquivo(caminho_arquivo: str, arquivos: list) -> None:
    """Mantém o arquivo no caminho especificado (função placeholder)"""
    print(f"Arquivo mantido: {caminho_arquivo}")
    for arquivo in arquivos:
        if arquivo != caminho_arquivo:
            deletar_arquivo(arquivo)

