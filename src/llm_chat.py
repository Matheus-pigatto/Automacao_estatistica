import streamlit as st
import agente
import time 

class LLMChat:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.agente = agente.AgenteSorteiosDeepSeek(api_key=self.api_key)

    def chat(self, mensagem: str) -> str:
        """Envia uma mensagem para o agente e retorna a resposta"""
        if 'messages' not in st.session_state:
            st.session_state.messages  = [{"role": "assistant", "content": "Olá! Como posso ajudar você hoje?"}]

        # Display chat messages from history on app rerun
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Accept user input
        if prompt := st.chat_input("What is up?"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            # Display user message in chat message container
            with st.chat_message("user"):
                st.markdown(prompt)

            # Display assistant response in chat message container
            client = OpenAI(api_key=openai_api_key)
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            response = client.chat.completions.create(model="gpt-3.5-turbo", messages=st.session_state.messages)
            msg = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": msg})
            st.chat_message("assistant").write(msg)


        
