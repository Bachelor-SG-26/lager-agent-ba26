def create_tables(cursor):
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
            name TEXT NOT NULL UNIQUE,
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
            status TEXT NOT NULL DEFAULT 'angelegt',
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_produkte_bestand ON produkte(bestand)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bestellungen_datum ON bestellungen(datum)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_verbrauch_datum ON verbrauch(datum)")
