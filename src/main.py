import sys
from time import sleep
from openai import api_key
import pyautogui
import src.agente as agente
import image_read

historico = []
#menssagem = "Você poderiam e me ajudar com estatística?"    
#historico = agent.mensagem_multitarn(menssagem, historico)
#print(historico[-1].content)



def main():
    
    with open("src\\api_deepseek.txt", "r") as txt:
        api_key = txt.read().strip()
        api_key = api_key.split('"')
        print("API Key loaded.")

    messages = []
    agente = agente.AgenteSorteiosDeepSeek(api_key=api_key)
    while True:
        pergunta = input("Digite sua pergunta (ou 'sair' para encerrar): ")
        if pergunta.lower() == 'sair':
            print("Encerrando o programa.")
            break
        messages = agente.mensagem_multitarn(pergunta, messages)
        print("Resposta:", messages[-1].content)



if __name__ == "__main__":
    main()


#image_read.imagem_ajuste()