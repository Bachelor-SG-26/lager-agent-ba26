"""Tests für Bestell-Tools: Bestellung erstellen und Bestellhistorie."""
import pytest
import sqlite3
from unittest.mock import patch
from agent.tools.bestellungen import (
    erstelle_bestellung,
    erstelle_bestellung_batch,
    check_bestellhistorie,
)


class TestErstelleBestellung:
    """Tests für die Bestellerstellung mit Budget- und Bestandsprüfung."""

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_erfolgreiche_bestellung(self, mock_telegram):
        """Eine gültige Bestellung sollte angelegt werden."""
        result = erstelle_bestellung.invoke({"produkt_id": 1, "menge": 10})
        assert "erfolgreich angelegt" in result
        assert "Stück" in result

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_bestand_wird_erhoeht(self, mock_telegram):
        """Nach Bestellung sollte der Bestand gestiegen sein."""
        from database.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bestand FROM produkte WHERE id = 1")
        alter_bestand = cursor.fetchone()[0]
        conn.close()

        erstelle_bestellung.invoke({"produkt_id": 1, "menge": 10})

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bestand FROM produkte WHERE id = 1")
        neuer_bestand = cursor.fetchone()[0]
        conn.close()

        assert neuer_bestand == alter_bestand + 10

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_budget_wird_reduziert(self, mock_telegram):
        """Nach Bestellung sollte das verbrauchte Budget gestiegen sein."""
        from database.database import get_connection
        from datetime import datetime

        jetzt = datetime.now()
        quartal = (jetzt.month - 1) // 3 + 1

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT verbrauchtes_budget FROM budget WHERE quartal = ? AND jahr = ?",
            (quartal, jetzt.year),
        )
        altes_budget = cursor.fetchone()[0]
        conn.close()

        erstelle_bestellung.invoke({"produkt_id": 1, "menge": 10})

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT verbrauchtes_budget FROM budget WHERE quartal = ? AND jahr = ?",
            (quartal, jetzt.year),
        )
        neues_budget = cursor.fetchone()[0]
        conn.close()

        assert neues_budget > altes_budget

    def test_ungueltige_produkt_id(self):
        """Eine nicht existierende Produkt-ID sollte einen Fehler liefern."""
        result = erstelle_bestellung.invoke({"produkt_id": 9999, "menge": 10})
        assert "Fehler" in result
        assert "nicht gefunden" in result

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_budget_ueberschreitung(self, mock_telegram):
        """Eine Bestellung die das Budget übersteigt sollte abgelehnt werden."""
        result = erstelle_bestellung.invoke({"produkt_id": 1, "menge": 99999999})
        assert "BUDGET ÜBERSCHRITTEN" in result
        assert "NICHT angelegt" in result

    @patch("agent.tools.bestellungen._telegram_batch_senden")
    def test_telegram_batch_wird_befuellt(self, mock_senden):
        """Bei erfolgreicher Bestellung sollte der Telegram-Batch befuellt werden."""
        from agent.tools.bestellungen import _telegram_batch, _telegram_batch_lock
        erstelle_bestellung.invoke({"produkt_id": 1, "menge": 5})
        with _telegram_batch_lock:
            assert len(_telegram_batch) >= 1
            letzter = _telegram_batch[-1]
            assert "bestell_nr" in letzter
            assert letzter["menge"] == 5
            _telegram_batch.clear()


    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_bestell_nr_im_ergebnis(self, mock_telegram):
        """Die Bestellnummer im Format BEST-YYYY-NNNN sollte im Ergebnis stehen."""
        result = erstelle_bestellung.invoke({"produkt_id": 1, "menge": 5})
        assert "BEST-" in result
        import re
        assert re.search(r"BEST-\d{4}-\d{4}", result)

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_nutzt_ausgewaehlten_lieferanten(self, mock_telegram):
        """Eine Lieferantenwahl sollte in Bestellung und Kosten uebernommen werden."""
        from database.database import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pl.lieferant_id, l.name, pl.preis
            FROM produkt_lieferanten pl
            JOIN produkte p ON pl.produkt_id = p.id
            JOIN lieferanten l ON pl.lieferant_id = l.id
            WHERE pl.produkt_id = 1
              AND pl.lieferant_id != p.standard_lieferant_id
            ORDER BY pl.preis ASC
            LIMIT 1
        """)
        lieferant_id, lieferant_name, preis = cursor.fetchone()
        conn.close()

        result = erstelle_bestellung.invoke({
            "produkt_id": 1,
            "menge": 10,
            "lieferant_id": lieferant_id,
        })

        assert "erfolgreich angelegt" in result
        assert lieferant_name in result
        assert f"ID: {lieferant_id}" in result

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lieferant_id, gesamtkosten
            FROM bestellungen
            ORDER BY id DESC
            LIMIT 1
        """)
        gespeicherter_lieferant, gesamtkosten = cursor.fetchone()
        conn.close()

        assert gespeicherter_lieferant == lieferant_id
        assert gesamtkosten == pytest.approx(preis * 10)

    def test_unhinterlegter_lieferant_wird_abgelehnt(self):
        result = erstelle_bestellung.invoke({
            "produkt_id": 1,
            "menge": 10,
            "lieferant_id": 9999,
        })
        assert "Fehler" in result
        assert "nicht hinterlegt" in result


class TestCheckBestellhistorie:
    """Tests für die Bestellhistorie."""

    def test_zeigt_bestellungen(self):
        """Bestellhistorie sollte die Seed-Bestellungen auflisten."""
        result = check_bestellhistorie.invoke({})
        assert "Bestellhistorie" in result
        assert "Gesamtausgaben" in result

    def test_zeigt_lieferant_und_kosten(self):
        """Jeder Eintrag sollte Lieferant und Kosten enthalten."""
        result = check_bestellhistorie.invoke({})
        assert "Euro" in result
        assert "Stück" in result


class TestErstelleBestellungBatch:
    """Tests für die Sammelbestellung."""

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_sammelbestellung_erfolgreich(self, mock_telegram):
        result = erstelle_bestellung_batch.invoke({
            "positionen": [
                {"produkt_id": 1, "menge": 5},
                {"produkt_id": 2, "menge": 3},
            ]
        })
        assert "Sammelbestellung abgeschlossen" in result
        assert "Erfolgreich:" in result

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_sammelbestellung_mit_lieferantenwahl(self, mock_telegram):
        from database.database import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pl.lieferant_id
            FROM produkt_lieferanten pl
            JOIN produkte p ON pl.produkt_id = p.id
            WHERE pl.produkt_id = 1
              AND pl.lieferant_id != p.standard_lieferant_id
            LIMIT 1
        """)
        lieferant_id = cursor.fetchone()[0]
        conn.close()

        result = erstelle_bestellung_batch.invoke({
            "positionen": [
                {"produkt_id": 1, "menge": 5, "lieferant_id": lieferant_id},
            ]
        })
        assert "Sammelbestellung abgeschlossen" in result
        assert f"ID: {lieferant_id}" in result

    def test_leere_positionen(self):
        result = erstelle_bestellung_batch.invoke({"positionen": []})
        assert "Fehler" in result
