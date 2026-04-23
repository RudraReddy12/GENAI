"""
Minimal Streamlit UI for the CryptoMind chatbot.
Run: streamlit run app.py
"""

import streamlit as st
from dotenv import load_dotenv

from mcp_orchestrator import run_mcp

load_dotenv()

st.set_page_config(page_title="CryptoMind", layout="centered")

st.title("CryptoMind")
st.write("Ask about crypto prices, compare two coins, or explore crypto concepts.")

if "history" not in st.session_state:
    st.session_state.history = []

for message in st.session_state.history:
    with st.chat_message("user" if message["role"] == "user" else "assistant"):
        st.markdown(message["content"])

query = st.chat_input("Type your message")

if query:
    st.session_state.history.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                gemini_history = [
                    {
                        "role": "user" if message["role"] == "user" else "model",
                        "content": message["content"],
                    }
                    for message in st.session_state.history[:-1]
                ]
                answer = run_mcp(query, gemini_history)
            except Exception as error:
                error_message = str(error)
                if "GOOGLE_API_KEY is not set" in error_message:
                    answer = (
                        "Something went wrong: GOOGLE_API_KEY is not set in environment variables.\n\n"
                        "Make sure your GOOGLE_API_KEY is set in .env."
                    )
                else:
                    answer = f"Something went wrong: {error_message}"

            st.markdown(answer)

    st.session_state.history.append({"role": "model", "content": answer})
