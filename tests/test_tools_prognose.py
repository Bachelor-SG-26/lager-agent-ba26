"""Tests für Prognose-Tool: Bedarfsanalyse auf Basis historischer Daten."""
import pytest
from agent.tools.prognose import prognostiziere_bedarf, prognostiziere_bedarf_batch


class TestPrognostiziereBedarf:
    """Tests für die Bedarfsprognose."""

    def test_erstellt_prognose(self):
        """Für ein Produkt mit Verbrauchsdaten sollte eine Prognose erstellt werden."""
        result = prognostiziere_bedarf.invoke({"produkt_id": 1})
        assert "Bedarfsprognose" in result
        assert "Schrauben M4x10" in result

    def test_zeigt_verbrauchsanalyse(self):
        """Die Verbrauchsanalyse sollte Durchschnittswerte enthalten."""
        result = prognostiziere_bedarf.invoke({"produkt_id": 1})
        assert "Durchschnitt/Tag" in result
        assert "Durchschnitt/Woche" in result

    def test_zeigt_reichweite(self):
        """Die geschaetzte Reichweite des Bestands sollte angezeigt werden."""
        result = prognostiziere_bedarf.invoke({"produkt_id": 1})
        assert "Reichweite" in result
        assert "Tage" in result

    def test_zeigt_empfohlene_bestellung(self):
        """Es sollte eine empfohlene Bestellmenge und deren Kosten geben."""
        result = prognostiziere_bedarf.invoke({"produkt_id": 1})
        assert "Empfohlene Bestellung" in result
        assert "Geschätzte Kosten" in result

    def test_benutzerdefinierter_zeitraum(self):
        """Der Prognosezeitraum sollte anpassbar sein."""
        result = prognostiziere_bedarf.invoke({
            "produkt_id": 1,
            "tage_voraus": 60,
        })
        assert "60 Tage" in result

    def test_ungueltige_produkt_id(self):
        """Nicht existierendes Produkt sollte Fehler liefern."""
        result = prognostiziere_bedarf.invoke({"produkt_id": 9999})
        assert "Fehler" in result
        assert "nicht gefunden" in result

    def test_lehnt_nichtpositiven_zeitraum_ab(self):
        """Ein Prognosezeitraum muss mindestens einen Tag umfassen."""
        result = prognostiziere_bedarf.invoke({"produkt_id": 1, "tage_voraus": 0})

        assert "Fehler" in result
        assert "größer als 0" in result


class TestPrognostiziereBedarfBatch:
    """Tests für die Batch-Bedarfsprognose."""

    def test_batch_prognose(self):
        result = prognostiziere_bedarf_batch.invoke(
            {"produkt_ids": [1, 2], "tage_voraus": 45}
        )
        assert "Batch-Prognose abgeschlossen" in result
        assert "45 Tage" in result

    def test_leere_liste(self):
        result = prognostiziere_bedarf_batch.invoke({"produkt_ids": []})
        assert "Fehler" in result
