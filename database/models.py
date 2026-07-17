def create_tables(cursor):
    """Erstellt alle Tabellen."""

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lieferanten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kontakt TEXT,
            lieferzeit_tage INTEGER NOT NULL DEFAULT 3,
            bewertung REAL NOT NULL DEFAULT 3.0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produkte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bestand INTEGER NOT NULL,
            mindestbestand INTEGER NOT NULL,
            preis_pro_einheit REAL NOT NULL,
            standard_lieferant_id INTEGER,
            FOREIGN KEY (standard_lieferant_id) REFERENCES lieferanten(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produkt_lieferanten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produkt_id INTEGER NOT NULL,
            lieferant_id INTEGER NOT NULL,
            preis REAL NOT NULL,
            lieferzeit_tage INTEGER,
            FOREIGN KEY (produkt_id) REFERENCES produkte(id),
            FOREIGN KEY (lieferant_id) REFERENCES lieferanten(id),
            UNIQUE(produkt_id, lieferant_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bestellungen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bestell_nr TEXT NOT NULL UNIQUE,
            produkt_id INTEGER NOT NULL,
            lieferant_id INTEGER,
            menge INTEGER NOT NULL,
            gesamtkosten REAL NOT NULL,
            datum TEXT NOT NULL,
            FOREIGN KEY (produkt_id) REFERENCES produkte(id),
            FOREIGN KEY (lieferant_id) REFERENCES lieferanten(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quartal INTEGER NOT NULL,
            jahr INTEGER NOT NULL,
            gesamtbudget REAL NOT NULL,
            verbrauchtes_budget REAL NOT NULL DEFAULT 0,
            UNIQUE(quartal, jahr)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verbrauch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produkt_id INTEGER NOT NULL,
            menge INTEGER NOT NULL,
            grund TEXT,
            datum TEXT NOT NULL,
            FOREIGN KEY (produkt_id) REFERENCES produkte(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_call_id TEXT,
            tool_name TEXT NOT NULL,
            tool_args TEXT,
            status TEXT NOT NULL,
            datum TEXT NOT NULL,
            duration_ms INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL UNIQUE,
            titel TEXT NOT NULL DEFAULT 'Neues Gespraech',
            erstellt_am TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_nachrichten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tools_used TEXT,
            erstellt_am TEXT NOT NULL,
            FOREIGN KEY (thread_id) REFERENCES chat_sessions(thread_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_teilnehmende (
            teilnehmer_code TEXT PRIMARY KEY,
            einwilligung_am TEXT NOT NULL,
            altersgruppe TEXT,
            berufsbereich TEXT,
            lager_erfahrung TEXT,
            digitale_kenntnisse INTEGER,
            ki_erfahrung TEXT,
            vorherige_kenntnis INTEGER,
            bevorzugter_modus TEXT,
            abschluss_kommentar TEXT,
            abgeschlossen_am TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_durchlaeufe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teilnehmer_code TEXT NOT NULL,
            position INTEGER NOT NULL,
            modus TEXT NOT NULL,
            szenario TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'offen',
            gestartet_am TEXT,
            abgeschlossen_am TEXT,
            modell_id TEXT,
            sus_antworten TEXT,
            sus_score REAL,
            feedback TEXT,
            FOREIGN KEY (teilnehmer_code)
                REFERENCES evaluation_teilnehmende(teilnehmer_code),
            UNIQUE(teilnehmer_code, position)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_aufgaben (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            durchlauf_id INTEGER NOT NULL,
            aufgabe_code TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'offen',
            gestartet_am TEXT,
            abgeschlossen_am TEXT,
            dauer_ms INTEGER,
            erwartung_json TEXT,
            antwort_json TEXT,
            erfolgreich INTEGER,
            validierung_json TEXT,
            schwierigkeit INTEGER,
            kommentar TEXT,
            chat_thread_id TEXT,
            FOREIGN KEY (durchlauf_id) REFERENCES evaluation_durchlaeufe(id),
            UNIQUE(durchlauf_id, aufgabe_code)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_ereignisse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aufgabe_id INTEGER NOT NULL,
            quelle TEXT NOT NULL,
            ereignis_id TEXT,
            aktion TEXT NOT NULL,
            argumente_json TEXT,
            status TEXT NOT NULL,
            dauer_ms INTEGER,
            erstellt_am TEXT NOT NULL,
            FOREIGN KEY (aufgabe_id) REFERENCES evaluation_aufgaben(id)
        )
    """)
