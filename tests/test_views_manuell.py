"""Tests für Datenzugriff und Abdeckung der manuellen Arbeitsoberfläche."""

from views.manuell import (
    MANUELLE_RECHTE,
    _ist_fehler,
    _lade_budgets,
    _lade_lieferanten_fuer_produkt,
    _lade_produkte,
    _pflege_widget_key,
    _produkte_dataframe,
)


ERWARTETE_RECHTE = {
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
}


def test_manuelle_oberflaeche_deckt_fachliche_rechte_ab():
    """Alle fachlichen Einzelaktionen des Agenten sind manuell erreichbar."""
    assert MANUELLE_RECHTE == ERWARTETE_RECHTE


def test_manuelle_produktansicht_nutzt_seed_daten():
    """Die Lageransicht zeigt den vollständigen reproduzierbaren Datenstand."""
    produkte = _lade_produkte()
    df = _produkte_dataframe(produkte)

    assert len(produkte) == 100
    assert len(df) == 100
    assert set(df["Status"]) <= {"Kritisch", "OK"}
    assert (df["Fehlmenge"] >= 0).all()


def test_lieferantenvergleich_liefert_bestellbare_zuordnungen():
    """Ein Produkt kann manuell mit seinen Lieferanten verglichen werden."""
    produkt_id = _lade_produkte()[0][0]
    lieferanten = _lade_lieferanten_fuer_produkt(produkt_id)

    assert lieferanten
    assert all(row[2] > 0 for row in lieferanten)
    assert all(1.0 <= row[4] <= 5.0 for row in lieferanten)


def test_budgetansicht_zeigt_seed_budgets():
    """Die manuelle Budgetansicht greift auf denselben Budgetbestand zu."""
    budgets = _lade_budgets()

    assert len(budgets) == 2
    assert all(row[2] > 0 for row in budgets)


def test_tool_ergebnisse_werden_richtig_eingeordnet():
    """Fachliche Ablehnungen erscheinen nicht als erfolgreiche Aktion."""
    assert _ist_fehler("Fehler: Produkt fehlt.") is True
    assert _ist_fehler("BUDGET ÜBERSCHRITTEN\nBestellung wurde nicht angelegt.") is True
    assert _ist_fehler("Nicht genug Bestand. Verfügbar: 2 Stück.") is True
    assert _ist_fehler("Keine Änderungen angegeben.") is True
    assert _ist_fehler("Bestellung erfolgreich angelegt.") is False


def test_pflegefelder_sind_an_den_gewaehlten_datensatz_gebunden():
    """Werte eines Produkts dürfen beim Auswahlwechsel nicht übernommen werden."""
    assert _pflege_widget_key("produkt", 1, "preis") != _pflege_widget_key(
        "produkt", 2, "preis"
    )
    assert _pflege_widget_key("produkt", 1, "preis").startswith(
        "manuell_pflege_produkt_1_"
    )
