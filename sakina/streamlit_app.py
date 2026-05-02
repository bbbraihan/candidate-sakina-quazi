#!/usr/bin/env python3
"""
Sakina Health Streamlit Chat Interface — voice + text chat UI backed by hybrid RAG
and a local LLM, with real-time citation display.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
import time
from sakina import config
from sakina.search import search_hybrid
from sakina.chat import generate_response_with_citations
from sakina.voice import transcribe, synthesize, _get_whisper


@st.cache_resource(show_spinner="Loading speech model...")
def _warm_whisper() -> Any:
    """Pre-load faster-whisper once per session so the first recording isn't slow."""
    return _get_whisper()

# Page config
st.set_page_config(
    page_title="Sakina Health - Islamic Spiritual Guidance",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def format_citations(cited_ids: list[str], passages_by_id: dict[str, dict[str, Any]]) -> str:
    """Render only the IDs the LLM actually cited, using their reference text."""
    if not cited_ids:
        return ""

    parts = []
    for doc_id in cited_ids:
        passage = passages_by_id.get(doc_id, {})
        reference = passage.get('reference', doc_id)
        parts.append(f"**[{doc_id}]** {reference}")
    return "**Citations:** " + " | ".join(parts)


def get_response_with_citations(user_query: str) -> tuple[str, str]:
    """Run retrieval + structured generation through the shared chat pipeline."""
    search_results = search_hybrid(user_query, n_results=10)

    if not isinstance(search_results, list):
        search_results = []

    if not search_results:
        return "I couldn't find relevant guidance for your question. Please try rephrasing.", ""

    result = generate_response_with_citations(user_query, search_results)
    if not result:
        return "I apologize, I'm having trouble generating a response right now.", ""

    passages_by_id = {p.get('id'): p for p in search_results if p.get('id')}
    citations = format_citations(result.get('citations', []), passages_by_id)
    return result.get('response', ''), citations

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_mic_id" not in st.session_state:
    st.session_state.last_mic_id = None
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "pending_speak" not in st.session_state:
    st.session_state.pending_speak = False


def render_assistant_turn(prompt: str, speak: bool) -> float:
    """Run the RAG pipeline for prompt, render the response in the chat, and optionally play TTS audio."""
    with st.chat_message("assistant"):
        with st.spinner("Searching for guidance..."):
            t0 = time.time()
            response, citations = get_response_with_citations(prompt)
            gen_latency = time.time() - t0

        st.write(response)
        if citations:
            st.markdown(f"*{citations}*")

        if speak:
            with st.spinner("Generating voice..."):
                audio_bytes, tts_err = synthesize(response)
            if audio_bytes:
                st.audio(audio_bytes, format="audio/wav", autoplay=True)
            elif tts_err:
                st.caption(f"(voice unavailable: {tts_err})")

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "citations": citations,
    })
    return gen_latency

# Title and description
st.title("Sakina Health")


# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message["role"] == "assistant" and message.get("citations"):
            st.markdown(f"*{message['citations']}*")

# Process any pending prompt (from voice or text) before rendering input widgets
# so the assistant turn appears in the natural chat flow above the mic/input.
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    speak = st.session_state.pending_speak
    st.session_state.pending_prompt = None
    st.session_state.pending_speak = False
    render_assistant_turn(prompt, speak)

# Voice input (always available)
_warm_whisper()
try:
    from streamlit_mic_recorder import mic_recorder
    audio = mic_recorder(
        start_prompt="🎙️ Start",
        stop_prompt="⏹ Stop",
        just_once=False,
        use_container_width=False,
        format="wav",
        key="mic",
    )
    if audio and audio.get("id") != st.session_state.last_mic_id:
        st.session_state.last_mic_id = audio.get("id")
        with st.spinner("Transcribing..."):
            text, stt_err = transcribe(audio["bytes"])
        if text:
            st.session_state.messages.append({"role": "user", "content": text})
            st.session_state.pending_prompt = text
            st.session_state.pending_speak = True
            st.rerun()
        else:
            st.warning(f"Didn't catch that ({stt_err}). Please try again.")
except ImportError:
    st.error("streamlit-mic-recorder not installed. Run: pip install streamlit-mic-recorder")

# Text input
if prompt := st.chat_input("Ask about any spiritual struggle or question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.pending_prompt = prompt
    st.session_state.pending_speak = False
    st.rerun()

# Sidebar with information
with st.sidebar:
    st.markdown("### About Sakina Health")
    st.markdown("""
    This interface provides Islamic spiritual guidance by:
    - Searching through Quranic verses, hadith, and articles
    - Generating empathetic responses grounded in Islamic teachings
    - Providing proper citations for all references

    **Note:** This is not a substitute for professional mental health care or religious rulings (fatwa).
    """)

    st.markdown("### Model Information")
    st.markdown(f"**Chat Model:** {config.CHAT_MODEL}")
    st.markdown("**Embedding Model:** BGE-small-en-v1.5")
    st.markdown("**Vector Store:** ChromaDB")
    st.markdown(f"**STT:** faster-whisper ({config.WHISPER_MODEL})")
    st.markdown("**TTS:** pyttsx3 (local)")

    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Footer
st.markdown("---")
