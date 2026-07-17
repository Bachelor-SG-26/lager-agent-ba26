"""Geführte Oberfläche für die vergleichende Evaluation beider Bedienmodi."""

import uuid

import streamlit as st

from services.evaluation import (
    ALTERSGRUPPEN,
    AUFGABEN_CODES,
    BERUFSBEREICHE,
    KI_ERFAHRUNGEN,
    LAGER_ERFAHRUNGEN,
    SUS_AUSSAGEN,
    TEILNEHMER_CODES,
    WIEDERHOLUNGSGRUENDE,
    brich_aufgabe_ab,
    exportiere_aufgaben_csv,
    exportiere_ereignisse_csv,
    exportiere_teilnehmerbericht_html,
    hole_aktive_aufgabe,
    hole_aktuellen_durchlauf,
    hole_aufgabeninfo,
    hole_aufgabenstatus,
    hole_durchlaeufe,
    hole_laufende_aufgabe_fuer_teilnehmer,
    hole_offenes_aufgabenfeedback,
    hole_teilnehmerabschluss,
    hole_teilnehmerprofil,
    naechste_aufgabe,
    registriere_teilnehmer,
    schliesse_aufgabe_ab,
    speichere_abschlussfeedback,
    speichere_aufgabenfeedback,
    speichere_teilnehmerprofil,
    speichere_sus,
    starte_aufgabe,
    starte_aufgabe_neu,
    setze_teilnehmer_evaluation_zurueck,
    teilnehmer_existiert,
    teilnehmerprofil_vollstaendig,
    wiederhole_aufgabe,
)
from services.session import erstelle_session, lade_nachrichten
from views.chat.state import reset_state


QUERY_TASK_KEY = "evaluation_task"
QUERY_PARTICIPANT_KEY = "evaluation_participant"
STUDIENLEITUNG_EMAIL = "sefa.guer@iu-study.org"


def _query_wert(name):
    """Liest einen einzelnen Query-Parameter unabhängig von der Streamlit-Version."""
    wert = st.query_params.get(name)
    if isinstance(wert, list):
        return wert[0] if wert else None
    return wert


def _setze_aktiven_kontext(aufgabe):
    """Hält die aktive Aufgabe auch über einen Browser-Reload hinweg verfügbar."""
    st.session_state._evaluation_task_id = aufgabe["id"]
    st.session_state._evaluation_teilnehmer = aufgabe["teilnehmer_code"]
    st.query_params[QUERY_TASK_KEY] = str(aufgabe["id"])
    st.query_params[QUERY_PARTICIPANT_KEY] = aufgabe["teilnehmer_code"]


def _setze_teilnehmerkontext(teilnehmer_code):
    """Speichert den gewählten Teilnehmercode in Sitzung und Browseradresse."""
    st.session_state._evaluation_teilnehmer = teilnehmer_code
    st.query_params[QUERY_PARTICIPANT_KEY] = teilnehmer_code


def _aktiviere_agentensitzung(aufgabe, erzwingen=False):
    """Bindet den Chat ausschließlich an die Sitzung der aktuellen Aufgabe."""
    thread_id = aufgabe.get("chat_thread_id")
    if aufgabe["modus"] != "Agent" or not thread_id:
        return

    aktuelle_thread_id = st.session_state.get("config", {}).get(
        "configurable", {}
    ).get("thread_id")
    bisherige_aufgabe = st.session_state.get("_evaluation_chat_task_id")
    if erzwingen or aktuelle_thread_id != thread_id or bisherige_aufgabe != aufgabe["id"]:
        st.session_state.config = {"configurable": {"thread_id": thread_id}}
        st.session_state.messages = lade_nachrichten(thread_id)
        reset_state()
    st.session_state._evaluation_chat_task_id = aufgabe["id"]


def _loesche_aktiven_kontext():
    """Entfernt den temporären Aufgabenbezug nach Abschluss oder Abbruch."""
    st.session_state.pop("_evaluation_task_id", None)
    st.session_state.pop("_evaluation_chat_task_id", None)
    st.session_state.pop("_evaluation_resume_notice", None)
    if QUERY_TASK_KEY in st.query_params:
        del st.query_params[QUERY_TASK_KEY]


def _optionsindex(optionen, wert):
    """Liefert den passenden Formularindex oder eine leere Vorauswahl."""
    return optionen.index(wert) if wert in optionen else None


def _render_teilnehmerprofil(teilnehmer_code, registrierung):
    """Erfasst sechs anonyme Kontextmerkmale vollständig und validiert."""
    vorhandenes_profil = (
        {} if registrierung else hole_teilnehmerprofil(teilnehmer_code) or {}
    )
    st.subheader("Angaben zur Person")
    st.caption(
        "Die Angaben dienen ausschließlich der Einordnung der Ergebnisse. "
        "Name, Arbeitgeber und genaues Alter werden nicht erfasst."
    )
    with st.form(f"evaluation_profil_{teilnehmer_code}"):
        altersgruppe = st.selectbox(
            "Altersgruppe",
            ALTERSGRUPPEN,
            index=_optionsindex(
                ALTERSGRUPPEN, vorhandenes_profil.get("altersgruppe")
            ),
            placeholder="Bitte auswählen",
        )
        berufsbereich = st.selectbox(
            "Beruflicher Bereich",
            BERUFSBEREICHE,
            index=_optionsindex(
                BERUFSBEREICHE, vorhandenes_profil.get("berufsbereich")
            ),
            placeholder="Bitte auswählen",
        )
        lager_erfahrung = st.selectbox(
            "Erfahrung mit Lager, Logistik oder Beschaffung",
            LAGER_ERFAHRUNGEN,
            index=_optionsindex(
                LAGER_ERFAHRUNGEN, vorhandenes_profil.get("lager_erfahrung")
            ),
            placeholder="Bitte auswählen",
        )
        st.markdown("**Wie schätzen Sie Ihre allgemeinen digitalen Kenntnisse ein?**")
        st.caption("Bewertungsskala: 1 = sehr gering · 5 = sehr hoch")
        digitale_kenntnisse = st.radio(
            "Digitale Kenntnisse",
            (1, 2, 3, 4, 5),
            index=_optionsindex(
                (1, 2, 3, 4, 5), vorhandenes_profil.get("digitale_kenntnisse")
            ),
            horizontal=True,
            label_visibility="collapsed",
        )
        ki_erfahrung = st.selectbox(
            "Wie häufig nutzen Sie KI-Chatbots?",
            KI_ERFAHRUNGEN,
            index=_optionsindex(
                KI_ERFAHRUNGEN, vorhandenes_profil.get("ki_erfahrung")
            ),
            placeholder="Bitte auswählen",
        )
        kenntnis_optionen = ("Nein", "Ja")
        kenntnis_wert = vorhandenes_profil.get("vorherige_kenntnis")
        st.markdown("**Kannten Sie den Lager-Agenten bereits vor dieser Evaluation?**")
        vorherige_kenntnis = st.radio(
            "Vorherige Kenntnis",
            kenntnis_optionen,
            index=(
                1
                if kenntnis_wert == 1
                else 0
                if kenntnis_wert == 0
                else None
            ),
            horizontal=True,
            label_visibility="collapsed",
        )
        einwilligung = True
        if registrierung:
            einwilligung = st.checkbox(
                "Ich wurde über den Ablauf informiert und nehme freiwillig teil."
            )
        speichern = st.form_submit_button(
            "Evaluation beginnen" if registrierung else "Angaben speichern",
            type="primary",
            width="stretch",
        )

    if not speichern:
        return False
    profil = {
        "altersgruppe": altersgruppe,
        "berufsbereich": berufsbereich,
        "lager_erfahrung": lager_erfahrung,
        "digitale_kenntnisse": digitale_kenntnisse,
        "ki_erfahrung": ki_erfahrung,
        "vorherige_kenntnis": (
            vorherige_kenntnis == "Ja"
            if vorherige_kenntnis is not None
            else None
        ),
    }
    try:
        if registrierung:
            registriere_teilnehmer(teilnehmer_code, einwilligung, profil)
        else:
            speichere_teilnehmerprofil(teilnehmer_code, profil)
    except ValueError as exc:
        st.error(str(exc))
        return False
    return True


def _fuehre_hard_reset_aus(teilnehmer_code):
    """Setzt einen Teilnehmerlauf, seine Chats und den lokalen UI-Zustand zurück."""
    setze_teilnehmer_evaluation_zurueck(teilnehmer_code)
    _loesche_aktiven_kontext()
    for schluessel in list(st.session_state):
        if str(schluessel).startswith(
            ("evaluation_antwort_", "evaluation_auswahl_", "sus_")
        ):
            st.session_state.pop(schluessel, None)
    thread_id = str(uuid.uuid4())
    erstelle_session(thread_id)
    st.session_state.config = {"configurable": {"thread_id": thread_id}}
    st.session_state.messages = []
    reset_state()
    _setze_teilnehmerkontext(teilnehmer_code)
    st.session_state.seite = "Evaluation"
    st.session_state._letzte_seite = "Evaluation"
    st.rerun()


def _render_hard_reset(teilnehmer_code, bereich, disabled=False):
    """Bietet einen absichtlich zweistufig bestätigten vollständigen Neustart an."""
    with st.expander("Evaluation vollständig neu starten", icon=":material/restart_alt:"):
        st.warning(
            "Dabei werden alle Aufgaben, Zeiten, Rückmeldungen und Aufgaben-Chats "
            f"von {teilnehmer_code} gelöscht. Die Testdaten werden zurückgesetzt."
        )
        bestaetigung = st.text_input(
            f"Zur Bestätigung {teilnehmer_code} eingeben",
            key=f"evaluation_reset_code_{bereich}_{teilnehmer_code}",
        )
        if st.button(
            "Alle Evaluationsdaten dieser Person löschen",
            key=f"evaluation_reset_{bereich}_{teilnehmer_code}",
            type="primary",
            icon=":material/delete_forever:",
            disabled=disabled or bestaetigung.strip() != teilnehmer_code,
            width="stretch",
        ):
            _fuehre_hard_reset_aus(teilnehmer_code)


def restore_evaluation_context():
    """Rekonstruiert eine laufende Aufgabe nach einem Browser-Reload."""
    hatte_aufgabenkontext = bool(st.session_state.get("_evaluation_task_id"))
    aufgabe_id = _query_wert(QUERY_TASK_KEY) or st.session_state.get(
        "_evaluation_task_id"
    )
    try:
        aufgabe = hole_aktive_aufgabe(int(aufgabe_id)) if aufgabe_id else None
    except (TypeError, ValueError):
        aufgabe = None

    teilnehmer_code = (
        _query_wert(QUERY_PARTICIPANT_KEY)
        or st.session_state.get("_evaluation_teilnehmer")
    )
    if not aufgabe and teilnehmer_code in TEILNEHMER_CODES:
        aufgabe = hole_laufende_aufgabe_fuer_teilnehmer(teilnehmer_code)

    if not aufgabe:
        _loesche_aktiven_kontext()
        if teilnehmer_code in TEILNEHMER_CODES and teilnehmer_existiert(teilnehmer_code):
            _setze_teilnehmerkontext(teilnehmer_code)
            st.session_state.seite = "Evaluation"
        return None

    _setze_aktiven_kontext(aufgabe)
    st.session_state.seite = aufgabe["modus"]
    st.session_state._letzte_seite = aufgabe["modus"]
    _aktiviere_agentensitzung(aufgabe)
    if not hatte_aufgabenkontext:
        st.session_state._evaluation_resume_notice = aufgabe["id"]
    return aufgabe


def _starte_ausgewaehlte_aufgabe(durchlauf, aufgabe_code):
    """Startet die Aufgabe und wechselt in den automatisch zugewiesenen Modus."""
    thread_id = str(uuid.uuid4()) if durchlauf["modus"] == "Agent" else None
    aufgabe = starte_aufgabe(durchlauf["id"], aufgabe_code, thread_id)
    if thread_id:
        erstelle_session(thread_id)
        _aktiviere_agentensitzung(aufgabe, erzwingen=True)

    _setze_aktiven_kontext(aufgabe)
    st.session_state.seite = durchlauf["modus"]
    st.session_state._letzte_seite = durchlauf["modus"]
    st.rerun()


def _starte_aktive_aufgabe_neu(aufgabe):
    """Startet nach einer Unterbrechung Daten, Timer und Agentensitzung neu."""
    thread_id = str(uuid.uuid4()) if aufgabe["modus"] == "Agent" else None
    if thread_id:
        erstelle_session(thread_id)
    neu = starte_aufgabe_neu(aufgabe["id"], thread_id)
    if thread_id:
        _aktiviere_agentensitzung(neu, erzwingen=True)
    _setze_aktiven_kontext(neu)
    st.session_state.pop("_evaluation_resume_notice", None)
    st.session_state.seite = neu["modus"]
    st.session_state._letzte_seite = neu["modus"]
    st.rerun()


def _bereinige_wiederholungszustand(aufgabe_id):
    """Entfernt alte Formularwerte, damit der neue Versuch unabhängig beginnt."""
    praefixe = (
        f"evaluation_antwort_{aufgabe_id}_",
        "manuell_pflege_",
    )
    for schluessel in list(st.session_state):
        if str(schluessel).startswith(praefixe):
            st.session_state.pop(schluessel, None)
    st.session_state.pop("manuell_produkt_bearbeiten", None)


def _starte_einzelwiederholung(durchlauf, aufgabe_code, grund):
    """Startet den ausgewählten Versuch mit frischen Daten und eigener Sitzung."""
    thread_id = str(uuid.uuid4()) if durchlauf["modus"] == "Agent" else None
    neu = wiederhole_aufgabe(
        durchlauf["id"],
        aufgabe_code,
        grund,
        thread_id,
    )
    _bereinige_wiederholungszustand(neu["id"])
    if thread_id:
        erstelle_session(thread_id)
        _aktiviere_agentensitzung(neu, erzwingen=True)
    _setze_aktiven_kontext(neu)
    st.session_state.seite = neu["modus"]
    st.session_state._letzte_seite = neu["modus"]
    st.rerun()


def render_active_evaluation_task():
    """Zeigt den Arbeitsauftrag und stoppt den Timer direkt im Zielbereich."""
    aufgabe = hole_aktive_aufgabe(st.session_state.get("_evaluation_task_id"))
    if not aufgabe:
        return

    info = aufgabe["info"]
    busy = bool(
        st.session_state.get("agent_arbeitet")
        or st.session_state.get("warte_auf_bestaetigung")
        or st.session_state.get("pending_input")
    )

    if st.session_state.get("_evaluation_resume_notice") == aufgabe["id"]:
        st.warning(
            "Eine laufende Aufgabe wurde nach dem Neuladen wiederhergestellt. "
            "Für eine unverfälschte Zeitmessung wird ein Neustart empfohlen."
        )
        fortsetzen, neu_starten = st.columns(2)
        with fortsetzen:
            if st.button(
                "Aufgabe fortsetzen",
                key=f"evaluation_fortsetzen_{aufgabe['id']}",
                width="stretch",
            ):
                st.session_state.pop("_evaluation_resume_notice", None)
                st.rerun()
        with neu_starten:
            if st.button(
                "Aufgabe neu starten",
                key=f"evaluation_neustart_{aufgabe['id']}",
                type="primary",
                width="stretch",
            ):
                _starte_aktive_aufgabe_neu(aufgabe)

    antworten = {}
    fertig = False
    technischer_abbruch = False
    with st.container(border=True):
        st.markdown(
            "<span class='evaluation-task-marker' aria-hidden='true'>.</span>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"{aufgabe['teilnehmer_code']} · Durchgang {aufgabe['position']} · "
            f"{aufgabe['modus']} · Szenario {aufgabe['szenario']}"
        )
        st.markdown(
            f"<div class='evaluation-task-title'>{info['code']} · {info['titel']}</div>",
            unsafe_allow_html=True,
        )
        st.caption(info["anweisung"].replace("**", ""))

        with st.expander(
            "Ergebnis erfassen und Aufgabe beenden",
            expanded=False,
            icon=":material/task_alt:",
        ):
            with st.form(f"evaluation_abschluss_{aufgabe['id']}"):
                if info["antwortfelder"]:
                    spalten = st.columns(len(info["antwortfelder"]))
                    for spalte, (schluessel, label) in zip(
                        spalten, info["antwortfelder"]
                    ):
                        with spalte:
                            antworten[schluessel] = st.number_input(
                                label,
                                min_value=0,
                                step=1,
                                value=None,
                                key=(
                                    f"evaluation_antwort_{aufgabe['id']}_{schluessel}"
                                ),
                            )

                fertig = st.form_submit_button(
                    "Aufgabe abschließen",
                    type="primary",
                    icon=":material/task_alt:",
                    disabled=busy,
                    width="stretch",
                )
                technischer_abbruch = st.form_submit_button(
                    "Technischen Abbruch erfassen",
                    icon=":material/report:",
                    disabled=busy,
                    width="stretch",
                )

        if busy:
            st.caption("Die Aufgabe kann abgeschlossen werden, sobald der laufende Vorgang beendet ist.")

    _render_hard_reset(
        aufgabe["teilnehmer_code"],
        f"aufgabe_{aufgabe['id']}",
        disabled=busy,
    )

    if fertig:
        if any(wert is None for wert in antworten.values()):
            st.error("Bitte tragen Sie zuerst alle geforderten Ergebnisse ein.")
            return
        schliesse_aufgabe_ab(aufgabe["id"], antworten)
        st.session_state._evaluation_teilnehmer = aufgabe["teilnehmer_code"]
        _loesche_aktiven_kontext()
        st.session_state.seite = "Evaluation"
        st.rerun()

    if technischer_abbruch:
        brich_aufgabe_ab(aufgabe["id"])
        st.session_state._evaluation_teilnehmer = aufgabe["teilnehmer_code"]
        _loesche_aktiven_kontext()
        st.session_state.seite = "Evaluation"
        st.rerun()


def _render_datenexport():
    """Bietet der Studienleitung zwei direkt auswertbare CSV-Dateien an."""
    with st.sidebar.expander("Evaluationsdaten", expanded=False):
        st.download_button(
            "Aufgaben exportieren",
            data=exportiere_aufgaben_csv(),
            file_name="evaluation_aufgaben.csv",
            mime="text/csv",
            width="stretch",
        )
        st.download_button(
            "Ereignisse exportieren",
            data=exportiere_ereignisse_csv(),
            file_name="evaluation_ereignisse.csv",
            mime="text/csv",
            width="stretch",
        )


def _render_teilnehmerbericht_download(teilnehmer_code):
    """Stellt den lesbaren Einzelbericht nach vollständigem Abschluss bereit."""
    st.download_button(
        "Teilnehmerbericht herunterladen",
        data=exportiere_teilnehmerbericht_html(teilnehmer_code),
        file_name=f"evaluation_{teilnehmer_code}_abschlussbericht.html",
        mime="text/html",
        icon=":material/download:",
        type="primary",
        width="stretch",
    )
    st.caption(
        "Die Datei bündelt Zeiten, Ergebnisse, Voraussetzungen, Prüfkriterien, "
        "Feedback und Ereignisprotokolle."
    )


def _render_aufgabenfeedback(teilnehmer_code, feedback):
    """Erfasst die Schwierigkeit erst nach dem Stoppen der Bearbeitungszeit."""
    info = hole_aufgabeninfo(feedback["aufgabe_code"], feedback["szenario"])
    st.subheader(f"Rückmeldung zu {feedback['aufgabe_code']}")
    st.caption(f"Bearbeitungszeit: {feedback['dauer_ms'] / 1000:.1f} Sekunden")
    with st.form(f"evaluation_feedback_{feedback['id']}"):
        st.markdown("**Wie schwierig war diese Aufgabe?**")
        st.caption("Bewertungsskala: 1 = sehr leicht · 7 = sehr schwer")
        schwierigkeit = st.radio(
            "Aufgabenschwierigkeit",
            options=(1, 2, 3, 4, 5, 6, 7),
            index=None,
            horizontal=True,
            label_visibility="collapsed",
        )
        kommentar = st.text_area(
            "Was war unklar oder unerwartet?",
            placeholder=f"Optionale Rückmeldung zu {info['titel']}",
        )
        speichern = st.form_submit_button(
            "Rückmeldung speichern",
            type="primary",
            width="stretch",
        )
    if speichern:
        if schwierigkeit is None:
            st.error("Bitte wählen Sie eine Schwierigkeit aus.")
            return
        speichere_aufgabenfeedback(feedback["id"], schwierigkeit, kommentar)
        st.session_state._evaluation_teilnehmer = teilnehmer_code
        st.rerun()


def _render_sus(durchlauf):
    """Erfasst den standardisierten Usability-Fragebogen für einen Bedienmodus."""
    st.subheader(f"Bewertung des Modus {durchlauf['modus']}")
    st.caption(
        "Bewertungsskala für alle Aussagen: "
        "1 = stimme überhaupt nicht zu · 5 = stimme vollständig zu"
    )
    with st.form(f"evaluation_sus_{durchlauf['id']}"):
        antworten = []
        for index, aussage in enumerate(SUS_AUSSAGEN, start=1):
            antworten.append(
                st.radio(
                    f"{index}. {aussage}",
                    options=(1, 2, 3, 4, 5),
                    index=None,
                    horizontal=True,
                    key=f"sus_{durchlauf['id']}_{index}",
                )
            )
        feedback = st.text_area(
            "Was hat in diesem Bedienmodus besonders gut oder schlecht funktioniert?"
        )
        speichern = st.form_submit_button(
            "Modusbewertung speichern",
            type="primary",
            width="stretch",
        )
    if speichern:
        if any(wert is None for wert in antworten):
            st.error("Bitte beantworten Sie alle zehn Aussagen.")
            return
        speichere_sus(durchlauf["id"], antworten, feedback)
        st.rerun()


def _render_abschluss(teilnehmer_code):
    """Erfasst die Präferenz nach dem vollständigen Vergleich."""
    abschluss = hole_teilnehmerabschluss(teilnehmer_code)
    if abschluss and abschluss["abgeschlossen_am"]:
        st.success("Die Evaluation ist vollständig abgeschlossen. Vielen Dank für die Teilnahme.")
        _render_teilnehmerbericht_download(teilnehmer_code)
        st.info(
            "Bitte senden Sie den heruntergeladenen Teilnehmerbericht an "
            f"**{STUDIENLEITUNG_EMAIL}**."
        )
        st.link_button(
            "E-Mail mit Bericht vorbereiten",
            (
                f"mailto:{STUDIENLEITUNG_EMAIL}"
                f"?subject=Evaluation%20Lager-Agent%20{teilnehmer_code}"
            ),
            icon=":material/mail:",
            width="stretch",
        )
        return

    st.subheader("Abschließender Vergleich")
    with st.form(f"evaluation_abschluss_{teilnehmer_code}"):
        st.markdown("**Welchen Bedienmodus würden Sie bevorzugen?**")
        praferenz = st.radio(
            "Bevorzugter Bedienmodus",
            ("Agent", "Manuell", "Kein Unterschied"),
            index=None,
            horizontal=True,
            label_visibility="collapsed",
        )
        kommentar = st.text_area(
            "Welche Unterschiede waren für Ihre Entscheidung ausschlaggebend?"
        )
        speichern = st.form_submit_button(
            "Evaluation abschließen",
            type="primary",
            width="stretch",
        )
    if speichern:
        if praferenz is None:
            st.error("Bitte wählen Sie eine Präferenz aus.")
            return
        speichere_abschlussfeedback(teilnehmer_code, praferenz, kommentar)
        st.rerun()


def _render_einzelwiederholung(teilnehmer_code, durchlaeufe):
    """Bietet eine nachvollziehbare Wiederholung genau einer beendeten Aufgabe an."""
    wiederholbare_durchlaeufe = []
    for durchlauf in durchlaeufe:
        status = hole_aufgabenstatus(durchlauf["id"])
        codes = tuple(
            code
            for code in AUFGABEN_CODES
            if code in status
            and status[code]["status"] in ("abgeschlossen", "abgebrochen")
        )
        if codes:
            wiederholbare_durchlaeufe.append((durchlauf, status, codes))

    if not wiederholbare_durchlaeufe:
        return

    with st.expander(
        "Einzelne Aufgabe wiederholen",
        icon=":material/replay:",
    ):
        st.caption(
            "Nur der ausgewählte Versuch wird neu gemessen. Alle anderen Aufgaben "
            "bleiben unverändert; der vorherige Versuch und der Grund bleiben im Bericht erhalten."
        )
        modus_optionen = tuple(
            eintrag[0]["modus"] for eintrag in wiederholbare_durchlaeufe
        )
        modus = st.selectbox(
            "Bedienmodus",
            modus_optionen,
            key=f"evaluation_wiederholung_modus_{teilnehmer_code}",
        )
        durchlauf, status, codes = next(
            eintrag
            for eintrag in wiederholbare_durchlaeufe
            if eintrag[0]["modus"] == modus
        )
        aufgabe_code = st.selectbox(
            "Aufgabe",
            codes,
            format_func=lambda code: f"{code} · {hole_aufgabeninfo(code, durchlauf['szenario'])['titel']}",
            key=f"evaluation_wiederholung_aufgabe_{teilnehmer_code}_{durchlauf['id']}",
        )
        bisher = status[aufgabe_code]
        ergebnis = (
            "erfüllt"
            if bisher["erfolgreich"] == 1
            else "nicht erfüllt"
            if bisher["erfolgreich"] == 0
            else bisher["status"]
        )
        dauer = (
            f"{bisher['dauer_ms'] / 1000:.1f} Sekunden"
            if bisher["dauer_ms"] is not None
            else "nicht verfügbar"
        )
        st.info(
            f"Bisheriges Ergebnis: {ergebnis} · Bearbeitungszeit: {dauer}"
        )

        grundauswahl = st.selectbox(
            "Grund für die Wiederholung",
            WIEDERHOLUNGSGRUENDE,
            index=None,
            placeholder="Bitte auswählen",
            key=f"evaluation_wiederholung_grund_{teilnehmer_code}",
        )
        grund = grundauswahl or ""
        if grundauswahl == "Anderer nachvollziehbarer Grund":
            grund = st.text_input(
                "Kurze Begründung",
                key=f"evaluation_wiederholung_freitext_{teilnehmer_code}",
            ).strip()
        bestaetigt = st.checkbox(
            f"Nur {modus} · {aufgabe_code} neu starten",
            key=(
                f"evaluation_wiederholung_bestaetigt_{teilnehmer_code}_"
                f"{durchlauf['id']}_{aufgabe_code}"
            ),
        )
        if st.button(
            "Ausgewählte Aufgabe wiederholen",
            type="primary",
            icon=":material/replay:",
            disabled=not grund or not bestaetigt,
            width="stretch",
            key=(
                f"evaluation_wiederholung_start_{teilnehmer_code}_"
                f"{durchlauf['id']}_{aufgabe_code}"
            ),
        ):
            try:
                _starte_einzelwiederholung(durchlauf, aufgabe_code, grund)
            except ValueError as exc:
                st.error(str(exc))


def _render_durchlauf(teilnehmer_code, durchlauf):
    """Zeigt Fortschritt, Aufgabenreiter und den kontrollierten Startknopf."""
    status = hole_aufgabenstatus(durchlauf["id"])
    erledigt = len(status)
    naechste = naechste_aufgabe(durchlauf["id"])

    st.subheader(
        f"Durchgang {durchlauf['position']} · {durchlauf['modus']} · Szenario {durchlauf['szenario']}"
    )
    st.progress(erledigt / len(AUFGABEN_CODES), text=f"{erledigt} von 5 Aufgaben beendet")

    auswahl = st.segmented_control(
        "Aufgabe",
        AUFGABEN_CODES,
        default=naechste or AUFGABEN_CODES[-1],
        key=f"evaluation_auswahl_{durchlauf['id']}",
        width="stretch",
    )
    info = hole_aufgabeninfo(auswahl, durchlauf["szenario"])
    st.markdown(f"### {info['code']} · {info['titel']}")
    st.markdown(info["anweisung"])

    if auswahl in status:
        aufgabe = status[auswahl]
        ergebnis = "Abgeschlossen" if aufgabe["status"] == "abgeschlossen" else "Abgebrochen"
        st.info(f"{ergebnis} · Bearbeitungszeit {aufgabe['dauer_ms'] / 1000:.1f} Sekunden")
        return

    if auswahl != naechste:
        st.warning(f"Zur Vergleichbarkeit muss zuerst {naechste} bearbeitet werden.")
        return

    st.caption(
        "Mit dem Start werden die benötigten Testdaten vorbereitet und der serverseitige Timer aktiviert."
    )
    if st.button(
        f"{auswahl} starten",
        type="primary",
        icon=":material/play_arrow:",
        width="stretch",
    ):
        _starte_ausgewaehlte_aufgabe(durchlauf, auswahl)


def show_evaluation():
    """Rendert den vollständigen, automatisierten Evaluationsablauf."""
    st.title("Evaluation")
    st.caption("Vergleich der manuellen Bearbeitung mit dem Agenten")
    _render_datenexport()

    vorauswahl = (
        st.session_state.get("_evaluation_teilnehmer")
        or _query_wert(QUERY_PARTICIPANT_KEY)
        or TEILNEHMER_CODES[0]
    )
    if vorauswahl not in TEILNEHMER_CODES:
        vorauswahl = TEILNEHMER_CODES[0]
    teilnehmer_code = st.selectbox(
        "Teilnehmercode",
        TEILNEHMER_CODES,
        index=TEILNEHMER_CODES.index(vorauswahl),
    )
    _setze_teilnehmerkontext(teilnehmer_code)

    if not teilnehmer_existiert(teilnehmer_code):
        st.info(
            "Der zugeteilte Teilnehmercode wird ohne Namen gespeichert. "
            "Für jede Aufgabe wird ein kontrollierter Testdatenstand geladen und "
            "nach dem Abschluss automatisch zurückgesetzt."
        )
        if _render_teilnehmerprofil(teilnehmer_code, registrierung=True):
            st.rerun()
        return

    _render_hard_reset(teilnehmer_code, "uebersicht")
    if not teilnehmerprofil_vollstaendig(teilnehmer_code):
        st.info(
            "Bitte ergänzen Sie vor der nächsten Aufgabe die Angaben zur Person. "
            "Bereits erfasste Aufgaben bleiben erhalten."
        )
        if _render_teilnehmerprofil(teilnehmer_code, registrierung=False):
            st.rerun()
        return

    laufende_aufgabe = hole_laufende_aufgabe_fuer_teilnehmer(teilnehmer_code)
    if laufende_aufgabe:
        _setze_aktiven_kontext(laufende_aufgabe)
        _aktiviere_agentensitzung(laufende_aufgabe)
        st.session_state.seite = laufende_aufgabe["modus"]
        st.session_state._letzte_seite = laufende_aufgabe["modus"]
        st.rerun()

    feedback = hole_offenes_aufgabenfeedback(teilnehmer_code)
    if feedback:
        _render_aufgabenfeedback(teilnehmer_code, feedback)
        return

    durchlaeufe = hole_durchlaeufe(teilnehmer_code)
    _render_einzelwiederholung(teilnehmer_code, durchlaeufe)
    aktueller_durchlauf = hole_aktuellen_durchlauf(teilnehmer_code)
    if not aktueller_durchlauf:
        _render_abschluss(teilnehmer_code)
        return

    aufgabenstatus = hole_aufgabenstatus(aktueller_durchlauf["id"])
    if len(aufgabenstatus) == len(AUFGABEN_CODES):
        _render_sus(aktueller_durchlauf)
        return

    col1, col2 = st.columns(2)
    for spalte, durchlauf in zip((col1, col2), durchlaeufe):
        with spalte:
            label = "Aktuell" if durchlauf["id"] == aktueller_durchlauf["id"] else durchlauf["status"].title()
            st.metric(
                f"Durchgang {durchlauf['position']}",
                durchlauf["modus"],
                f"Szenario {durchlauf['szenario']} · {label}",
            )

    st.divider()
    _render_durchlauf(teilnehmer_code, aktueller_durchlauf)
