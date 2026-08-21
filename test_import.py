# test_import.py
import sys
import os
import src.gerenciador_arquivos as ga
import src.image_read as ir

def test_arquivos_na_pasta() -> None:
    arquivos = ga.arquivos_na_pasta('db')
    assert isinstance(arquivos, list)
    return arquivos


image_text = ir.ler_imagem(imagem='db\\ss\\2025-12-12_23-08-17cartela.png')
print("Texto extraído da imagem de teste:") 
print(image_text)
print(len(image_text))
print(type(image_text))

#12 letra