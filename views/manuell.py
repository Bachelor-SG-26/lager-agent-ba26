"""Manuelle Arbeitsoberfläche für Lager- und Beschaffungsvorgänge."""

from datetime import datetime

import pandas as pd
import streamlit as st

from agent.tools.bestellungen import erstelle_bestellung
from agent.tools.budget import erstelle_budget
from agent.tools.entnahme import erfasse_entnahme
from agent.tools.lieferanten import (
    _berechne_beste_empfehlung,
    erstelle_lieferant,
)
from agent.tools.produkte import erstelle_produkt
from agent.tools.prognose import prognostiziere_bedarf
from agent.tools.update import aktualisiere_lieferant, aktualisiere_produkt
from database.database import db_connection


BEREICHE = ("Lager", "Beschaffung", "Entnahme", "Budget", "Stammdaten")

# Batch-Tools beschleunigen Agentenaufrufe, erweitern aber nicht die fachlichen Rechte.
MANUELLE_RECHTE = frozenset({
    "lagerbestand_anzeigen",
    "engpaesse_anzeigen",
    "budget_anzeigen",
    "budget_anlegen",
    "bestellung_anlegen",
    "bestellhistorie_anzeigen",
    "entnahme_erfassen",
    "bedarf_prognostizieren",
    "lieferanten_vergleichen",
    "produkt_anlegen",
    "lieferant_anlegen",
    "produkt_aktualisieren",
    "lieferant_aktualisieren",
})


# ─────────────────────────────────────────
#  Daten laden
# ─────────────────────────────────────────


def _lade_produkte():
    """Lädt Produkte mit Standardlieferant für Tabellen und Formulare."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT
                p.id,
                p.name,
                p.bestand,
                p.mindestbestand,
                p.preis_pro_einheit,
                p.standard_lieferant_id,
                l.name
            FROM produkte p
            LEFT JOIN lieferanten l ON p.standard_lieferant_id = l.id
            ORDER BY p.name
        """)
        return cursor.fetchall()


def _lade_lieferanten():
    """Lädt alle Lieferanten alphabetisch sortiert."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT id, name, kontakt, lieferzeit_tage, bewertung
            FROM lieferanten
            ORDER BY name
        """)
        return cursor.fetchall()


def _lade_lieferanten_fuer_produkt(produkt_id):
    """Lädt die bestellbaren Lieferanten eines Produkts."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT
                l.id,
                l.name,
                pl.preis,
                COALESCE(pl.lieferzeit_tage, l.lieferzeit_tage),
                l.bewertung,
                CASE WHEN p.standard_lieferant_id = l.id THEN 1 ELSE 0 END
            FROM produkt_lieferanten pl
            JOIN lieferanten l ON pl.lieferant_id = l.id
            JOIN produkte p ON pl.produkt_id = p.id
            WHERE pl.produkt_id = ?
            ORDER BY pl.preis, l.name
        """, (produkt_id,))
        return cursor.fetchall()


def _lade_budgets():
    """Lädt alle Quartalsbudgets absteigend nach Zeitraum."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT quartal, jahr, gesamtbudget, verbrauchtes_budget
            FROM budget
            ORDER BY jahr DESC, quartal DESC
        """)
        return cursor.fetchall()


def _lade_bestellungen(limit=20):
    """Lädt die letzten Bestellungen für den manuellen Arbeitsbereich."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT b.bestell_nr, p.name, l.name, b.menge, b.gesamtkosten, b.datum
            FROM bestellungen b
            JOIN produkte p ON b.produkt_id = p.id
            LEFT JOIN lieferanten l ON b.lieferant_id = l.id
            ORDER BY b.datum DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()


def _lade_entnahmen(limit=30):
    """Lädt die letzten Materialentnahmen."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT p.name, v.menge, v.grund, v.datum
            FROM verbrauch v
            JOIN produkte p ON v.produkt_id = p.id
            ORDER BY v.datum DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()


# ─────────────────────────────────────────
#  Gemeinsame UI-Helfer
# ─────────────────────────────────────────


def _produkt_optionen(produkte):
    """Erzeugt eindeutige Produktlabels für Auswahlfelder."""
    return {f"{produkt[1]} · ID {produkt[0]}": produkt for produkt in produkte}


def _lieferant_optionen(lieferanten):
    """Erzeugt eindeutige Lieferantenlabels für Auswahlfelder."""
    return {f"{lieferant[1]} · ID {lieferant[0]}": lieferant for lieferant in lieferanten}


def _ist_fehler(ergebnis):
    """Erkennt fachliche Fehlermeldungen aus den gemeinsamen Tool-Regeln."""
    text = str(ergebnis).strip()
    return (
        text.startswith(("Fehler:", "Nicht genug Bestand", "Keine Änderungen"))
        or "BUDGET ÜBERSCHRITTEN" in text
    )


def _zeige_ergebnis(ergebnis):
    """Zeigt ein Tool-Ergebnis passend als Erfolg oder Fehler an."""
    if _ist_fehler(ergebnis):
        st.error(ergebnis)
    else:
        st.success(ergebnis)


def _fuehre_aktion_aus(tool, argumente):
    """Führt eine manuelle Aktion über dieselbe Fachlogik wie der Agent aus."""
    try:
        ergebnis = tool.invoke(argumente)
    except Exception as exc:
        st.error(f"Aktion fehlgeschlagen: {exc}")
        return

    if _ist_fehler(ergebnis):
        st.error(ergebnis)
        return

    st.session_state._manuell_meldung = ergebnis
    st.rerun()


def _zeige_meldung():
    """Zeigt das Ergebnis der zuletzt abgeschlossenen manuellen Aktion."""
    ergebnis = st.session_state.pop("_manuell_meldung", None)
    if ergebnis:
        st.success(ergebnis)


def _produkte_dataframe(produkte):
    """Bereitet Produktdaten inklusive Status für die Anzeige auf."""
    df = pd.DataFrame(
        produkte,
        columns=[
            "ID",
            "Produkt",
            "Bestand",
            "Mindestbestand",
            "Preis (Euro)",
            "Lieferant-ID",
            "Standardlieferant",
        ],
    )
    if df.empty:
        return df
    df["Fehlmenge"] = (df["Mindestbestand"] - df["Bestand"]).clip(lower=0)
    df["Status"] = df["Fehlmenge"].apply(lambda wert: "Kritisch" if wert > 0 else "OK")
    return df


# ─────────────────────────────────────────
#  Lager
# ─────────────────────────────────────────


def _render_lager(produkte):
    """Rendert Lagerübersicht, Engpässe und Bedarfsprognose."""
    df = _produkte_dataframe(produkte)
    if df.empty:
        st.info("Noch keine Produkte vorhanden.")
        return

    kritisch = int((df["Status"] == "Kritisch").sum())
    lagerwert = float((df["Bestand"] * df["Preis (Euro)"]).sum())
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Produkte", len(df))
    col2.metric("Kritisch", kritisch)
    col3.metric("Bestand gesamt", int(df["Bestand"].sum()))
    col4.metric("Lagerwert", f"{lagerwert:,.2f} Euro")

    st.divider()
    filter_col, suche_col = st.columns([1, 2])
    with filter_col:
        status = st.selectbox("Status", ("Alle", "Kritisch", "OK"), key="manuell_lager_status")
    with suche_col:
        suche = st.text_input("Produkt suchen", key="manuell_lager_suche")

    gefiltert = df
    if status != "Alle":
        gefiltert = gefiltert[gefiltert["Status"] == status]
    if suche.strip():
        gefiltert = gefiltert[
            gefiltert["Produkt"].str.contains(suche.strip(), case=False, na=False)
        ]

    st.dataframe(
        gefiltert.drop(columns=["Lieferant-ID"]),
        width="stretch",
        hide_index=True,
        column_config={"Preis (Euro)": st.column_config.NumberColumn(format="%.2f Euro")},
    )

    st.divider()
    st.subheader("Bedarfsprognose")
    optionen = _produkt_optionen(produkte)
    with st.form("manuell_prognose_form"):
        col_produkt, col_tage = st.columns([2, 1])
        with col_produkt:
            auswahl = st.selectbox("Produkt", tuple(optionen), key="manuell_prognose_produkt")
        with col_tage:
            tage = st.number_input("Zeitraum in Tagen", min_value=1, max_value=365, value=30)
        submitted = st.form_submit_button(
            "Prognose berechnen",
            icon=":material/query_stats:",
            width="stretch",
        )

    if submitted:
        produkt = optionen[auswahl]
        ergebnis = prognostiziere_bedarf.invoke({"produkt_id": produkt[0], "tage_voraus": int(tage)})
        _zeige_ergebnis(ergebnis)


# ─────────────────────────────────────────
#  Beschaffung
# ─────────────────────────────────────────


def _render_beschaffung(produkte):
    """Rendert Lieferantenvergleich, Bestellung und jüngste Vorgänge."""
    if not produkte:
        st.info("Für Bestellungen muss zuerst ein Produkt angelegt werden.")
        return

    optionen = _produkt_optionen(produkte)
    auswahl = st.selectbox("Produkt", tuple(optionen), key="manuell_bestellung_produkt")
    produkt = optionen[auswahl]
    lieferanten = _lade_lieferanten_fuer_produkt(produkt[0])

    col1, col2, col3 = st.columns(3)
    col1.metric("Bestand", f"{produkt[2]} Stück")
    col2.metric("Mindestbestand", f"{produkt[3]} Stück")
    fehlmenge = max(0, produkt[3] - produkt[2])
    col3.metric("Fehlmenge", f"{fehlmenge} Stück")

    st.subheader("Lieferantenvergleich")
    if not lieferanten:
        st.warning("Für dieses Produkt ist kein bestellbarer Lieferant hinterlegt.")
        return

    vergleich = pd.DataFrame(
        lieferanten,
        columns=["ID", "Lieferant", "Preis (Euro)", "Lieferzeit (Tage)", "Bewertung", "Standard"],
    )
    vergleich["Standard"] = vergleich["Standard"].map({1: "Ja", 0: ""})
    st.dataframe(
        vergleich,
        width="stretch",
        hide_index=True,
        column_config={
            "Preis (Euro)": st.column_config.NumberColumn(format="%.2f Euro"),
            "Bewertung": st.column_config.NumberColumn(format="%.1f / 5"),
        },
    )

    bewertungszeilen = [(row[1], row[2], row[3], row[4], bool(row[5])) for row in lieferanten]
    empfehlung = _berechne_beste_empfehlung(bewertungszeilen)
    st.info(f"Empfehlung: {empfehlung}")

    st.subheader("Bestellung anlegen")
    lieferant_map = {
        f"{row[1]} · {row[2]:.2f} Euro · {row[3]} Tage": row for row in lieferanten
    }
    with st.form("manuell_bestellung_form"):
        col_lieferant, col_menge = st.columns([2, 1])
        with col_lieferant:
            lieferant_label = st.selectbox("Lieferant", tuple(lieferant_map))
        with col_menge:
            menge = st.number_input("Menge", min_value=1, value=max(1, fehlmenge))
        submitted = st.form_submit_button(
            "Bestellung anlegen",
            type="primary",
            icon=":material/add_shopping_cart:",
            width="stretch",
        )

    if submitted:
        lieferant = lieferant_map[lieferant_label]
        _fuehre_aktion_aus(
            erstelle_bestellung,
            {"produkt_id": produkt[0], "menge": int(menge), "lieferant_id": lieferant[0]},
        )

    bestellungen = _lade_bestellungen(limit=10)
    if bestellungen:
        st.divider()
        st.subheader("Letzte Bestellungen")
        df = pd.DataFrame(
            bestellungen,
            columns=["Bestell-Nr.", "Produkt", "Lieferant", "Menge", "Kosten (Euro)", "Datum"],
        )
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={"Kosten (Euro)": st.column_config.NumberColumn(format="%.2f Euro")},
        )


# ─────────────────────────────────────────
#  Entnahme
# ─────────────────────────────────────────


def _render_entnahme(produkte):
    """Rendert Materialentnahme und Verbrauchshistorie."""
    if not produkte:
        st.info("Für eine Entnahme muss zuerst ein Produkt angelegt werden.")
        return

    optionen = _produkt_optionen(produkte)
    auswahl = st.selectbox("Produkt", tuple(optionen), key="manuell_entnahme_produkt")
    produkt = optionen[auswahl]

    col1, col2 = st.columns(2)
    col1.metric("Verfügbarer Bestand", f"{produkt[2]} Stück")
    col2.metric("Mindestbestand", f"{produkt[3]} Stück")

    with st.form("manuell_entnahme_form"):
        col_menge, col_grund = st.columns([1, 2])
        with col_menge:
            menge = st.number_input("Menge", min_value=1, value=1)
        with col_grund:
            grund = st.selectbox(
                "Grund",
                ("Produktion", "Wartung", "Montage", "Reparatur", "Prototyp", "Sonstiges"),
            )
        submitted = st.form_submit_button(
            "Entnahme erfassen",
            type="primary",
            icon=":material/remove_circle_outline:",
            width="stretch",
        )

    if submitted:
        _fuehre_aktion_aus(
            erfasse_entnahme,
            {"produkt_id": produkt[0], "menge": int(menge), "grund": grund},
        )

    entnahmen = _lade_entnahmen()
    if entnahmen:
        st.divider()
        st.subheader("Letzte Entnahmen")
        df = pd.DataFrame(entnahmen, columns=["Produkt", "Menge", "Grund", "Datum"])
        st.dataframe(df, width="stretch", hide_index=True)


# ─────────────────────────────────────────
#  Budget
# ─────────────────────────────────────────


def _render_budget():
    """Rendert Budgetstatus und Formular für neue Quartalsbudgets."""
    budgets = _lade_budgets()
    jetzt = datetime.now()
    aktuelles_quartal = (jetzt.month - 1) // 3 + 1
    aktuelles = next(
        (row for row in budgets if row[0] == aktuelles_quartal and row[1] == jetzt.year),
        None,
    )

    if aktuelles:
        verbleibend = aktuelles[2] - aktuelles[3]
        auslastung = aktuelles[3] / aktuelles[2] * 100 if aktuelles[2] else 0
        col1, col2, col3 = st.columns(3)
        col1.metric("Gesamtbudget", f"{aktuelles[2]:,.2f} Euro")
        col2.metric("Verbraucht", f"{aktuelles[3]:,.2f} Euro")
        col3.metric("Verbleibend", f"{verbleibend:,.2f} Euro", f"{auslastung:.1f}% genutzt")
    else:
        st.warning(f"Für Q{aktuelles_quartal}/{jetzt.year} ist kein Budget vorhanden.")

    if budgets:
        df = pd.DataFrame(
            budgets,
            columns=["Quartal", "Jahr", "Gesamtbudget", "Verbraucht"],
        )
        df["Quartal"] = df["Quartal"].map(lambda wert: f"Q{wert}")
        df["Verbleibend"] = df["Gesamtbudget"] - df["Verbraucht"]
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                "Gesamtbudget": st.column_config.NumberColumn(format="%.2f Euro"),
                "Verbraucht": st.column_config.NumberColumn(format="%.2f Euro"),
                "Verbleibend": st.column_config.NumberColumn(format="%.2f Euro"),
            },
        )

    st.divider()
    st.subheader("Budget anlegen")
    with st.form("manuell_budget_form"):
        col_quartal, col_jahr, col_betrag = st.columns(3)
        with col_quartal:
            quartal = st.selectbox("Quartal", (1, 2, 3, 4), index=aktuelles_quartal - 1)
        with col_jahr:
            jahr = st.number_input("Jahr", min_value=2020, max_value=2100, value=jetzt.year)
        with col_betrag:
            betrag = st.number_input("Gesamtbudget (Euro)", min_value=0.01, value=10000.0, step=500.0)
        submitted = st.form_submit_button(
            "Budget anlegen",
            type="primary",
            icon=":material/add_card:",
            width="stretch",
        )

    if submitted:
        _fuehre_aktion_aus(
            erstelle_budget,
            {"quartal": quartal, "jahr": int(jahr), "gesamtbudget": float(betrag)},
        )


# ─────────────────────────────────────────
#  Stammdaten
# ─────────────────────────────────────────


def _render_produkt_stammdaten(produkte, lieferanten):
    """Rendert Produktanlage, Produktpflege und Produkttabelle."""
    if not lieferanten:
        st.warning("Vor dem ersten Produkt muss ein Lieferant angelegt werden.")
    else:
        lieferant_map = _lieferant_optionen(lieferanten)
        st.subheader("Produkt anlegen")
        with st.form("manuell_produkt_anlegen_form"):
            name = st.text_input("Produktname")
            col_min, col_preis = st.columns(2)
            with col_min:
                mindestbestand = st.number_input("Mindestbestand", min_value=0, value=0)
            with col_preis:
                preis = st.number_input("Preis pro Einheit (Euro)", min_value=0.01, value=1.0)
            lieferant_label = st.selectbox("Standardlieferant", tuple(lieferant_map))
            submitted = st.form_submit_button(
                "Produkt anlegen",
                type="primary",
                icon=":material/add_box:",
                width="stretch",
            )

        if submitted:
            lieferant = lieferant_map[lieferant_label]
            _fuehre_aktion_aus(
                erstelle_produkt,
                {
                    "name": name.strip(),
                    "mindestbestand": int(mindestbestand),
                    "preis_pro_einheit": float(preis),
                    "lieferant_id": lieferant[0],
                },
            )

    if produkte:
        st.divider()
        st.subheader("Produkt bearbeiten")
        produkt_map = _produkt_optionen(produkte)
        produkt_label = st.selectbox("Produkt", tuple(produkt_map), key="manuell_produkt_bearbeiten")
        produkt = produkt_map[produkt_label]

        with st.form("manuell_produkt_bearbeiten_form"):
            neuer_name = st.text_input("Produktname", value=produkt[1])
            col_bestand, col_min, col_preis = st.columns(3)
            with col_bestand:
                neuer_bestand = st.number_input("Bestand", min_value=0, value=produkt[2])
            with col_min:
                neuer_mindestbestand = st.number_input(
                    "Mindestbestand",
                    min_value=0,
                    value=produkt[3],
                    key="manuell_update_mindestbestand",
                )
            with col_preis:
                neuer_preis = st.number_input(
                    "Preis pro Einheit (Euro)",
                    min_value=0.01,
                    value=float(produkt[4]),
                    key="manuell_update_preis",
                )
            submitted = st.form_submit_button(
                "Änderungen speichern",
                icon=":material/save:",
                width="stretch",
            )

        if submitted:
            argumente = {"produkt_id": produkt[0]}
            if neuer_name.strip() != produkt[1]:
                argumente["name"] = neuer_name.strip()
            if int(neuer_bestand) != produkt[2]:
                argumente["bestand"] = int(neuer_bestand)
            if int(neuer_mindestbestand) != produkt[3]:
                argumente["mindestbestand"] = int(neuer_mindestbestand)
            if float(neuer_preis) != float(produkt[4]):
                argumente["preis_pro_einheit"] = float(neuer_preis)
            _fuehre_aktion_aus(aktualisiere_produkt, argumente)

        st.divider()
        df = _produkte_dataframe(produkte)
        st.dataframe(
            df.drop(columns=["Lieferant-ID"]),
            width="stretch",
            hide_index=True,
            column_config={"Preis (Euro)": st.column_config.NumberColumn(format="%.2f Euro")},
        )


def _render_lieferant_stammdaten(lieferanten):
    """Rendert Lieferantenanlage, Lieferantenpflege und Tabelle."""
    st.subheader("Lieferant anlegen")
    with st.form("manuell_lieferant_anlegen_form"):
        name = st.text_input("Lieferantenname")
        kontakt = st.text_input("Kontakt")
        col_zeit, col_bewertung = st.columns(2)
        with col_zeit:
            lieferzeit = st.number_input("Lieferzeit (Tage)", min_value=0, value=3)
        with col_bewertung:
            bewertung = st.number_input(
                "Bewertung",
                min_value=1.0,
                max_value=5.0,
                value=3.0,
                step=0.1,
            )
        submitted = st.form_submit_button(
            "Lieferant anlegen",
            type="primary",
            icon=":material/add_business:",
            width="stretch",
        )

    if submitted:
        _fuehre_aktion_aus(
            erstelle_lieferant,
            {
                "name": name.strip(),
                "kontakt": kontakt.strip(),
                "lieferzeit_tage": int(lieferzeit),
                "bewertung": float(bewertung),
            },
        )

    if lieferanten:
        st.divider()
        st.subheader("Lieferant bearbeiten")
        lieferant_map = _lieferant_optionen(lieferanten)
        lieferant_label = st.selectbox(
            "Lieferant",
            tuple(lieferant_map),
            key="manuell_lieferant_bearbeiten",
        )
        lieferant = lieferant_map[lieferant_label]

        with st.form("manuell_lieferant_bearbeiten_form"):
            neuer_name = st.text_input("Lieferantenname", value=lieferant[1])
            neuer_kontakt = st.text_input("Kontakt", value=lieferant[2] or "")
            col_zeit, col_bewertung = st.columns(2)
            with col_zeit:
                neue_lieferzeit = st.number_input(
                    "Lieferzeit (Tage)",
                    min_value=0,
                    value=lieferant[3],
                    key="manuell_update_lieferzeit",
                )
            with col_bewertung:
                neue_bewertung = st.number_input(
                    "Bewertung",
                    min_value=1.0,
                    max_value=5.0,
                    value=float(lieferant[4]),
                    step=0.1,
                    key="manuell_update_bewertung",
                )
            submitted = st.form_submit_button(
                "Änderungen speichern",
                icon=":material/save:",
                width="stretch",
            )

        if submitted:
            argumente = {"lieferant_id": lieferant[0]}
            if neuer_name.strip() != lieferant[1]:
                argumente["name"] = neuer_name.strip()
            if neuer_kontakt.strip() != (lieferant[2] or ""):
                argumente["kontakt"] = neuer_kontakt.strip()
            if int(neue_lieferzeit) != lieferant[3]:
                argumente["lieferzeit_tage"] = int(neue_lieferzeit)
            if float(neue_bewertung) != float(lieferant[4]):
                argumente["bewertung"] = float(neue_bewertung)
            _fuehre_aktion_aus(aktualisiere_lieferant, argumente)

        st.divider()
        df = pd.DataFrame(
            lieferanten,
            columns=["ID", "Lieferant", "Kontakt", "Lieferzeit (Tage)", "Bewertung"],
        )
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={"Bewertung": st.column_config.NumberColumn(format="%.1f / 5")},
        )


def _render_stammdaten(produkte):
    """Rendert die manuelle Produkt- und Lieferantenverwaltung."""
    lieferanten = _lade_lieferanten()
    produkt_tab, lieferant_tab = st.tabs(("Produkte", "Lieferanten"))
    with produkt_tab:
        _render_produkt_stammdaten(produkte, lieferanten)
    with lieferant_tab:
        _render_lieferant_stammdaten(lieferanten)


# ─────────────────────────────────────────
#  Hauptfunktion
# ─────────────────────────────────────────


def show_manuell():
    """Zeigt alle manuellen Lager- und Beschaffungsvorgänge auf einer Seite."""
    st.title("Manuelle Bearbeitung")
    _zeige_meldung()

    bereich = st.segmented_control(
        "Bereich",
        BEREICHE,
        default="Lager",
        key="manuell_bereich",
        label_visibility="collapsed",
        width="stretch",
    )
    st.divider()

    produkte = _lade_produkte()
    if bereich == "Beschaffung":
        _render_beschaffung(produkte)
    elif bereich == "Entnahme":
        _render_entnahme(produkte)
    elif bereich == "Budget":
        _render_budget()
    elif bereich == "Stammdaten":
        _render_stammdaten(produkte)
    else:
        _render_lager(produkte)
