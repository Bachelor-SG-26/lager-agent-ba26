import uuid

import streamlit as st

from agent.agent import AgentConfigurationError, is_agent_configured
from services.agent_runner import (
    build_agent_error_message,
    continue_after_tool_confirmation,
    get_pending_tool_calls,
    reject_pending_tool_calls,
    stream_agent_response,
)
from services.chat_session import (
    create_chat_session,
    get_latest_chat_session,
    list_chat_sessions,
    load_chat_messages,
    save_chat_message,
    update_chat_title_from_message,
)


_TOOL_DESCRIPTIONS = {
    "check_lagerbestand": lambda args: "Ruft den aktuellen Lagerbestand ab",
    "check_engpaesse": lambda args: "Prüft Produkte unter dem Mindestbestand",
    "check_lagerwert": lambda args: "Berechnet den aktuellen Lagerwert",
    "korrigiere_lagerbestand": lambda args: (
        f"Setzt Produkt #{args.get('produkt_id', '?')} auf "
        f"{args.get('neuer_bestand', '?')} Stück"
    ),
    "erfasse_entnahme": lambda args: (
        f"Entnimmt {args.get('menge', '?')} Stück von Produkt "
        f"#{args.get('produkt_id', '?')}"
    ),
    "check_budget": lambda args: "Ruft die aktuelle Budgetübersicht ab",
    "erstelle_budget": lambda args: (
        f"Legt ein Budget für Q{args.get('quartal', '?')}/"
        f"{args.get('jahr', '?')} an"
    ),
    "erstelle_bestellung": lambda args: (
        f"Legt eine Bestellung über {args.get('menge', '?')} Stück "
        f"für Produkt #{args.get('produkt_id', '?')} an"
    ),
    "check_bestellhistorie": lambda args: "Ruft die letzten Bestellungen ab",
    "check_bestellvorschlaege": lambda args: "Ermittelt Produkte mit Bestellbedarf",
    "check_offene_bestellungen": lambda args: "Ruft offene Bestellungen ab",
    "aktualisiere_bestellstatus": lambda args: (
        f"Setzt Bestellung {args.get('bestell_nr', '?')} auf "
        f"{args.get('status', '?')}"
    ),
    "vergleiche_lieferanten": lambda args: (
        f"Vergleicht Lieferanten für Produkt #{args.get('produkt_id', '?')}"
    ),
    "prognostiziere_bedarf": lambda args: (
        f"Erstellt eine Bedarfsprognose für Produkt "
        f"#{args.get('produkt_id', '?')}"
    ),
    "prognostiziere_bedarf_batch": lambda args: (
        f"Erstellt Bedarfsprognosen für {len(args.get('produkt_ids', []))} Produkte"
    ),
    "erstelle_lieferant": lambda args: (
        f"Legt Lieferant '{args.get('name', '?')}' an"
    ),
    "erstelle_produkt": lambda args: (
        f"Legt Produkt '{args.get('name', '?')}' an"
    ),
    "aktualisiere_lieferant": lambda args: (
        f"Aktualisiert Lieferant #{args.get('lieferant_id', '?')}"
    ),
    "aktualisiere_produkt": lambda args: (
        f"Aktualisiert Produkt #{args.get('produkt_id', '?')}"
    ),
}


def show_agent():
    """Rendert den Agenten-Chat mit persistenter Thread-ID."""
    st.title("Agent")
    st.caption("Lagerfragen stellen und operative Abläufe vorbereiten.")

    _ensure_chat_state()
    _render_session_controls()

    if not is_agent_configured():
        st.warning("Für den Agenten fehlt noch der NVIDIA API-Key.")
        return

    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending_tool_calls = _load_pending_tool_calls()
    if pending_tool_calls:
        _render_tool_confirmation(pending_tool_calls)
        return

    user_input = st.chat_input("Nachricht an den Agenten")
    if not user_input:
        return

    st.session_state.agent_messages.append({"role": "user", "content": user_input})
    save_chat_message(st.session_state.agent_thread_id, "user", user_input)
    update_chat_title_from_message(st.session_state.agent_thread_id, user_input)

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Agent arbeitet..."):
            has_error = False
            try:
                answer = _render_streaming_answer(user_input, st.session_state.agent_thread_id)
            except AgentConfigurationError as error:
                has_error = True
                answer = str(error)
                st.markdown(answer)
            except Exception as error:
                has_error = True
                answer = build_agent_error_message(
                    st.session_state.agent_thread_id,
                    error,
                )
                st.error(answer)

    pending_tool_calls = [] if has_error else _safe_get_pending_tool_calls()
    if pending_tool_calls:
        st.session_state.agent_pending_tool_calls = pending_tool_calls
        st.rerun()

    _store_assistant_answer(answer)


def _render_streaming_answer(message, thread_id):
    """Zeigt eine Agent-Antwort während des Streams an und gibt sie zurück."""
    placeholder = st.empty()
    chunks = []
    for chunk in stream_agent_response(message, thread_id):
        chunks.append(chunk)
        placeholder.markdown("".join(chunks))

    answer = "".join(chunks).strip()
    if answer:
        placeholder.markdown(answer)
        return answer

    if get_pending_tool_calls(thread_id):
        placeholder.empty()
        return ""

    answer = "Es wurde keine Antwort erzeugt."
    placeholder.markdown(answer)
    return answer


def _load_pending_tool_calls():
    """Lädt offene Tool-Aufrufe aus Session-State oder Graph-State."""
    pending_tool_calls = st.session_state.get("agent_pending_tool_calls")
    if pending_tool_calls:
        return pending_tool_calls

    pending_tool_calls = _safe_get_pending_tool_calls()
    if pending_tool_calls:
        st.session_state.agent_pending_tool_calls = pending_tool_calls
    return pending_tool_calls


def _render_tool_confirmation(tool_calls):
    """Zeigt vorbereitete Agent-Aktionen zur Bestätigung an."""
    with st.chat_message("assistant"):
        st.markdown("**Geplante Aktionen**")
        for tool_call in tool_calls:
            args = tool_call.get("args") or {}
            args_text = _format_tool_args(args)
            description = _describe_tool_call(tool_call.get("name"), args)
            with st.container(border=True):
                if description:
                    st.markdown(description)
                st.caption(f"{tool_call.get('name', 'tool')}({args_text})")

        col_run, col_cancel, _ = st.columns([1, 1, 3])
        with col_run:
            if st.button("Ausführen", type="primary", width="stretch"):
                _execute_pending_tools()
        with col_cancel:
            if st.button("Abbrechen", width="stretch"):
                _cancel_pending_tools()


def _execute_pending_tools():
    """Führt bestätigte Tool-Aufrufe aus und speichert die Agent-Antwort."""
    try:
        answer, next_tool_calls = continue_after_tool_confirmation(
            st.session_state.agent_thread_id
        )
    except Exception as error:
        answer = build_agent_error_message(st.session_state.agent_thread_id, error)
        next_tool_calls = []

    if next_tool_calls:
        st.session_state.agent_pending_tool_calls = next_tool_calls
        st.rerun()

    st.session_state.pop("agent_pending_tool_calls", None)
    _store_assistant_answer(answer)
    st.rerun()


def _cancel_pending_tools():
    """Bricht geplante Tool-Aufrufe ab und setzt den Chat-State zurück."""
    try:
        reject_pending_tool_calls(st.session_state.agent_thread_id)
        answer = "Aktion wurde abgebrochen."
    except Exception as error:
        answer = build_agent_error_message(st.session_state.agent_thread_id, error)

    st.session_state.pop("agent_pending_tool_calls", None)
    _store_assistant_answer(answer)
    st.rerun()


def _safe_get_pending_tool_calls():
    """Liest offene Tool-Aufrufe, ohne die Oberfläche bei State-Fehlern zu blockieren."""
    try:
        return get_pending_tool_calls(st.session_state.agent_thread_id)
    except Exception as error:
        answer = build_agent_error_message(st.session_state.agent_thread_id, error)
        st.session_state.pop("agent_pending_tool_calls", None)
        _store_assistant_answer(answer)
        return []


def _store_assistant_answer(answer):
    """Speichert eine Agent-Antwort einmalig in Session-State und Datenbank."""
    if not answer:
        return

    messages = st.session_state.agent_messages
    if (
        messages
        and messages[-1]["role"] == "assistant"
        and messages[-1]["content"] == answer
    ):
        return

    messages.append({"role": "assistant", "content": answer})
    save_chat_message(st.session_state.agent_thread_id, "assistant", answer)


def _describe_tool_call(name, args):
    """Erstellt eine kurze fachliche Beschreibung für eine geplante Aktion."""
    describer = _TOOL_DESCRIPTIONS.get(name)
    return describer(args) if describer else ""


def _format_tool_args(args):
    """Formatiert Tool-Parameter kompakt für die Detailanzeige."""
    return ", ".join(f"{key}={value}" for key, value in args.items())


def _clear_active_agent_action():
    """Entfernt laufende Aktionsdaten beim Wechsel der Chat-Session."""
    st.session_state.pop("agent_pending_tool_calls", None)


def _ensure_chat_state():
    """Initialisiert die aktive Chat-Session aus der Datenbank."""
    if "agent_thread_id" not in st.session_state:
        latest_session = get_latest_chat_session()
        if latest_session:
            st.session_state.agent_thread_id = latest_session["thread_id"]
        else:
            st.session_state.agent_thread_id = create_chat_session(str(uuid.uuid4()))

    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = load_chat_messages(st.session_state.agent_thread_id)


def _render_session_controls():
    """Rendert einfache Steuerung für neue und bestehende Agent-Gespräche."""
    col_new, col_history = st.columns([1, 3])
    with col_new:
        if st.button("Neues Gespräch", width="stretch"):
            _clear_active_agent_action()
            st.session_state.agent_thread_id = create_chat_session(str(uuid.uuid4()))
            st.session_state.agent_messages = []
            st.rerun()

    sessions = list_chat_sessions()
    if not sessions:
        return

    labels = {
        f"{session['titel']} ({session['erstellt_am']})": session
        for session in sessions
    }
    current_label = next(
        (
            label
            for label, session in labels.items()
            if session["thread_id"] == st.session_state.agent_thread_id
        ),
        next(iter(labels)),
    )
    with col_history:
        selected_label = st.selectbox(
            "Gespräch",
            list(labels.keys()),
            index=list(labels.keys()).index(current_label),
        )

    selected_session = labels[selected_label]
    if selected_session["thread_id"] != st.session_state.agent_thread_id:
        _clear_active_agent_action()
        st.session_state.agent_thread_id = selected_session["thread_id"]
        st.session_state.agent_messages = load_chat_messages(selected_session["thread_id"])
        st.rerun()
