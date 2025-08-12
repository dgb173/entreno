# Fichero: modules/kimi_chat.py

import streamlit as st
import requests
import json

# --- Función para llamar a la API de Kimi ---
def get_kimi_response(prompt: str):
    """
    Envía un prompt a la API de Kimi K2 a través de OpenRouter y devuelve la respuesta.
    """
    # Carga la API Key desde los secretos de Streamlit
    api_key = st.secrets.get("KIMI_API_KEY")

    if not api_key:
        return "Error: La clave KIMI_API_KEY no se encontró en los secretos. Por favor, configúrala en el fichero .streamlit/secrets.toml"

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "moonshotai/kimi-k2:free",
                "messages": [{"role": "user", "content": prompt}]
            }),
            timeout=30 # Tiempo de espera de 30 segundos
        )

        response.raise_for_status() # Lanza un error si la respuesta no es 2xx

        response_data = response.json()
        return response_data['choices'][0]['message']['content'].strip()

    except requests.exceptions.RequestException as e:
        return f"Error de conexión al llamar a la API: {e}"
    except (KeyError, IndexError):
        return "Error: La respuesta de la API no tuvo el formato esperado."

# --- Función que dibuja la interfaz de usuario en Streamlit ---
def display_kimi_chat_ui():
    """
    Crea la interfaz de usuario para interactuar con el chat de Kimi.
    """
    st.header("🤖 Chat con Kimi K2")
    st.info("Hazle una pregunta al modelo de lenguaje Kimi K2 (1 billón de parámetros).")

    user_prompt = st.text_area("Escribe tu pregunta aquí:", height=150, key="kimi_prompt")

    if st.button("Enviar Pregunta", key="kimi_submit"):
        if user_prompt:
            with st.spinner("Pensando... 🧠"):
                kimi_answer = get_kimi_response(user_prompt)
                st.markdown("### Respuesta:")
                st.success(kimi_answer) # Usamos st.success para que la respuesta resalte en verde
        else:
            st.warning("Por favor, escribe una pregunta antes de enviar.")