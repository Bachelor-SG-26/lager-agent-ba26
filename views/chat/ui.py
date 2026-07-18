"""UI-Rendering für den Chat: Nachrichten, Verlauf, Bestätigungen, Empty-State."""
import streamlit as st

from config import MAX_TOOL_CALLS_PRO_SCHRITT, BATCH_TRIGGER_ANZAHL
from views.chat.state import cancel_pending_tools


# ─────────────────────────────────────────
#  Tool-Beschreibungen
# ─────────────────────────────────────────


_TOOL_BESCHREIBUNGEN = {
    "erstelle_bestellung": lambda a: (
        f"Bestellt {a.get('menge', '?')} Stück von Produkt #{a.get('produkt_id', '?')}"
    ),
    "erfasse_entnahme": lambda a: (
        f"Entnimmt {a.get('menge', '?')} Stück von Produkt #{a.get('produkt_id', '?')} "
        f"(Grund: {a.get('grund', 'k.A.')})"
    ),
    "check_lagerbestand": lambda a: (
        f"Sucht im Lagerbestand nach '{a.get('suchbegriff', '')}'"
        if a.get("suchbegriff")
        else "Ruft den aktuellen Lagerbestand aller Produkte ab"
    ),
    "check_engpaesse": lambda a: "Prüft welche Produkte unter dem Mindestbestand liegen",
    "check_budget": lambda a: "Ruft die aktuelle Budget-Übersicht ab",
    "check_bestellhistorie": lambda a: "Ruft die bisherigen Bestellungen ab",
    "prognostiziere_bedarf": lambda a: (
        f"Erstellt eine Bedarfsprognose für Produkt #{a.get('produkt_id', '?')} "
        f"({a.get('tage_voraus', 30)} Tage voraus)"
    ),
    "prognostiziere_bedarf_batch": lambda a: (
        f"Erstellt Bedarfsprognosen für {len(a.get('produkt_ids', []))} Produkte "
        f"({a.get('tage_voraus', 30)} Tage voraus)"
    ),
    "check_lieferanten": lambda a: (
        f"Sucht vorhandene Lieferanten nach '{a.get('suchbegriff', '')}'"
        if a.get("suchbegriff")
        else "Ruft die vorhandenen Lieferanten ab"
    ),
    "vergleiche_lieferanten": lambda a: (
        f"Vergleicht alle Lieferanten für Produkt #{a.get('produkt_id', '?')}"
    ),
    "erstelle_bestellung_batch": lambda a: (
        f"Legt Sammelbestellung mit {len(a.get('positionen', []))} Positionen an"
    ),
    "erstelle_produkt": lambda a: (
        f"Legt neues Produkt '{a.get('name', '?')}' an "
        f"(Mindestbestand: {a.get('mindestbestand', '?')}, "
        f"Preis: {a.get('preis_pro_einheit', '?')} Euro)"
    ),
    "erstelle_lieferant": lambda a: (
        f"Legt neuen Lieferanten '{a.get('name', '?')}' an"
    ),
    "erstelle_budget": lambda a: (
        f"Legt Budget für Q{a.get('quartal', '?')}/{a.get('jahr', '?')} an "
        f"({a.get('gesamtbudget', '?')} Euro)"
    ),
    "aktualisiere_produkt": lambda a: (
        f"Aktualisiert Produkt #{a.get('produkt_id', '?')}"
    ),
    "aktualisiere_lieferant": lambda a: (
        f"Aktualisiert Lieferant #{a.get('lieferant_id', '?')}"
    ),
}


def beschreibe_tool_call(name, args):
    """Erzeugt eine verstaendliche Beschreibung für einen Tool-Call."""
    fn = _TOOL_BESCHREIBUNGEN.get(name)
    return fn(args) if fn else ""


# ─────────────────────────────────────────
#  Rendering
# ─────────────────────────────────────────


def render_message(message):
    """Rendert eine einzelne Chat-Nachricht mit optionaler Tool-Info."""
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("tools_used"):
            pills = " ".join(
                f"<span class='tool-pill'>{t}</span>" for t in message["tools_used"]
            )
            st.markdown(
                f"<div class='tools-used-row'>{pills}</div>",
                unsafe_allow_html=True,
            )


def render_empty_state():
    """Zeigt einen Willkommens-Hinweis bei leerem Chat."""
    st.markdown(
        """
        <div class='chat-empty-state'>
            <div class='chat-empty-title'>Lager-Agent bereit</div>
            <div class='chat-empty-sub'>
                Frage nach Lagerbestand, Engpässen oder Bestellungen.<br>
                Der Agent zeigt dir jede Aktion vor der Ausführung zur Bestätigung.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chat_history(container):
    """Zeigt den gesamten Chat-Verlauf im Container an."""
    with container:
        # Spacer drückt kurze Verläufe nach unten.
        st.markdown("<div class='chat-start-spacer'></div>", unsafe_allow_html=True)
        if not st.session_state.messages:
            render_empty_state()
            return
        for message in st.session_state.messages:
            render_message(message)


def render_confirmation(container):
    """Zeigt die Inline-Bestätigung für geplante Tool-Aufrufe."""
    with container:
        with st.chat_message("assistant"):
            anzahl = len(st.session_state.pending_tool_calls)
            if anzahl > MAX_TOOL_CALLS_PRO_SCHRITT:
                st.error(
                    f"Zu viele Tool-Calls in einem Schritt ({anzahl}). "
                    f"Maximal erlaubt: {MAX_TOOL_CALLS_PRO_SCHRITT}."
                )
                if st.button("Abbrechen", width="stretch"):
                    cancel_pending_tools(
                        reason=(
                            f"Zu viele Tool-Calls in einem Schritt ({anzahl}). "
                            f"Maximal erlaubt: {MAX_TOOL_CALLS_PRO_SCHRITT}."
                        ),
                        user_msg=(
                            f"Aktion abgebrochen: Der Agent hat {anzahl} Tool-Calls "
                            f"in einem Schritt geplant. Bitte Anfrage aufteilen oder ab "
                            f"{BATCH_TRIGGER_ANZAHL} ähnlichen Aktionen Batch-Tools nutzen."
                        ),
                    )
                return

            st.markdown("**Geplante Aktionen**")
            for tc in st.session_state.pending_tool_calls:
                args_str = ", ".join(f"{k}={v}" for k, v in tc["args"].items())
                beschreibung = beschreibe_tool_call(tc["name"], tc["args"])
                with st.container(border=True):
                    if beschreibung:
                        st.markdown(beschreibung)
                    st.caption(f"{tc['name']}({args_str})")

            col1, col2, _ = st.columns([1, 1, 3])
            with col1:
                if st.button("Ausführen", type="primary", width="stretch"):
                    st.session_state.tool_approved = True
                    st.rerun()
            with col2:
                if st.button("Abbrechen", width="stretch"):
                    st.session_state.tool_approved = False
                    st.rerun()
