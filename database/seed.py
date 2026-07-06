from datetime import datetime, timedelta
import random
from config import SEED_BUDGET_BETRAG, SEED_VORQUARTAL_VERBRAUCHT

LIEFERANTEN = [
    # Schrauben/Befestigungen Spezialisten
    ("Würth", "bestellung@wuerth.de", 2, 4.5),
    ("Bossard", "order@bossard.com", 3, 4.0),
    ("Arnold", "vertrieb@arnold.de", 4, 3.8),
    ("Fabory", "order@fabory.com", 3, 3.5),
    ("Schrauben Jäger", "info@schrauben-jaeger.de", 2, 4.3),
    ("Norelem", "order@norelem.de", 3, 4.1),
    # Dübel/Befestigungstechnik
    ("Fischer", "info@fischer.de", 2, 4.2),
    ("TOX", "vertrieb@tox-duebel.de", 3, 3.9),
    ("Hilti", "order@hilti.de", 1, 4.7),
    # Nieten/Verbindungstechnik
    ("Gesipa", "order@gesipa.de", 3, 3.5),
    ("Bralo", "info@bralo.de", 4, 3.6),
    ("RIBE", "vertrieb@ribe.de", 5, 3.4),
    # Klebstoffe/Dichtungen
    ("Loctite", "b2b@loctite.com", 5, 4.0),
    ("Soudal", "order@soudal.de", 4, 3.7),
    ("Simrit", "info@simrit.de", 3, 4.1),
    ("Weicon", "order@weicon.de", 3, 4.2),
    ("Pattex", "industrie@pattex.de", 4, 3.8),
    # Werkzeug/Verbrauchsmaterial
    ("3M", "industrie@3m.de", 2, 4.6),
    ("Bosch", "profi@bosch.de", 3, 4.8),
    ("Liqui Moly", "industrie@liquimoly.de", 5, 4.0),
    ("WD-40", "order@wd40.de", 4, 3.9),
    ("Hellermann", "vertrieb@hellermann.de", 3, 4.0),
    ("Metabo", "industrie@metabo.de", 3, 4.4),
    ("Klingspor", "order@klingspor.de", 2, 4.5),
    # Große Industriehändler (breites Sortiment)
    ("RS Components", "sales@rs-components.de", 2, 4.3),
    ("Misumi", "order@misumi.de", 3, 4.1),
    ("Conrad", "b2b@conrad.de", 1, 4.0),
    ("Mercateo", "order@mercateo.de", 2, 3.9),
    ("Haberkorn", "vertrieb@haberkorn.at", 4, 3.7),
    ("Keller & Kalmbach", "order@kk-group.de", 3, 4.2),
]

# (name, bestand, mindestbestand, preis, lieferant_name)
PRODUKTE = [
    # Schrauben & Befestigungen (20 Produkte)
    ("Schrauben M4x10",         3,  50,  0.05, "Würth"),
    ("Schrauben M4x20",        80,  50,  0.06, "Würth"),
    ("Schrauben M6x12",        12,  40,  0.08, "Würth"),
    ("Schrauben M6x30",        45,  40,  0.10, "Würth"),
    ("Schrauben M8x20",         2,  30,  0.12, "Würth"),
    ("Schrauben M8x40",        60,  30,  0.15, "Würth"),
    ("Schrauben M10x50",       18,  25,  0.20, "Würth"),
    ("Schrauben M10x80",       90,  25,  0.25, "Würth"),
    ("Schrauben M12x60",        5,  20,  0.30, "Würth"),
    ("Schrauben M12x100",      35,  20,  0.40, "Würth"),
    ("Senkkopfschraube M4x20", 40,  30,  0.07, "Schrauben Jäger"),
    ("Senkkopfschraube M6x30", 25,  30,  0.11, "Schrauben Jäger"),
    ("Senkkopfschraube M8x40", 10,  25,  0.16, "Schrauben Jäger"),
    ("Senkkopfschraube M10x60",15,  20,  0.24, "Norelem"),
    ("Senkkopfschraube M12x60",  5,  20,  0.30, "Norelem"),
    ("Gewindestange M8x1000",   8,  10,  2.50, "Würth"),
    ("Gewindestange M10x1000", 12,  10,  3.20, "Arnold"),
    ("Gewindestange M12x1000",  4,   8,  4.00, "Arnold"),
    ("Fluegelschraube M6x20",  30,  20,  0.18, "Norelem"),
    ("Fluegelschraube M8x30",  15,  15,  0.25, "Norelem"),
    # Muttern (10 Produkte)
    ("Sechskantmutter M4",     15,  60,  0.04, "Bossard"),
    ("Sechskantmutter M6",    120,  60,  0.06, "Bossard"),
    ("Sechskantmutter M8",      8,  50,  0.08, "Bossard"),
    ("Sechskantmutter M10",    75,  50,  0.10, "Bossard"),
    ("Sechskantmutter M12",     3,  40,  0.12, "Bossard"),
    ("Flanschmutter M6",       40,  30,  0.09, "Norelem"),
    ("Flanschmutter M8",       20,  25,  0.12, "Norelem"),
    ("Hutmutter M6 verzinkt",  50,  30,  0.08, "Fabory"),
    ("Hutmutter M8 verzinkt",  25,  25,  0.11, "Fabory"),
    ("Hutmutter M10 verzinkt", 10,  20,  0.14, "Fabory"),
    # Unterlegscheiben (10 Produkte)
    ("Unterlegscheibe M4 verzinkt",    20,  80,  0.03, "Bossard"),
    ("Unterlegscheibe M6 verzinkt",   200,  80,  0.04, "Bossard"),
    ("Unterlegscheibe M8 verzinkt",     9,  60,  0.05, "Bossard"),
    ("Unterlegscheibe M10 verzinkt",   55,  60,  0.06, "Bossard"),
    ("Unterlegscheibe M12 verzinkt",    4,  40,  0.08, "Bossard"),
    ("Federring M6",                   60,  50,  0.05, "Norelem"),
    ("Federring M8",                   35,  40,  0.06, "Norelem"),
    ("Federring M10",                  20,  30,  0.07, "Norelem"),
    ("Zahnscheibe M6",                 45,  40,  0.04, "Fabory"),
    ("Zahnscheibe M8",                 30,  30,  0.05, "Fabory"),
    # Dübel (10 Produkte)
    ("Spreizdübel 6mm",                10,  40,  0.15, "Fischer"),
    ("Spreizdübel 8mm",                25,  40,  0.20, "Fischer"),
    ("Spreizdübel 10mm",                6,  30,  0.25, "Fischer"),
    ("Spreizdübel 12mm",               45,  30,  0.30, "Fischer"),
    ("Spreizdübel 14mm",                2,  20,  0.40, "Fischer"),
    ("Hohlraumdübel 8mm",              15,  20,  0.35, "TOX"),
    ("Hohlraumdübel 10mm",              8,  15,  0.45, "TOX"),
    ("Schwerlastanker M8x80",           6,  10,  1.80, "Hilti"),
    ("Schwerlastanker M10x100",          4,   8,  2.50, "Hilti"),
    ("Schwerlastanker M12x120",          3,   6,  3.20, "Hilti"),
    # Bolzen (10 Produkte)
    ("Bolzen M6x40",                   30,  25,  0.35, "Arnold"),
    ("Bolzen M8x50",                    4,  25,  0.45, "Arnold"),
    ("Bolzen M8x80",                   40,  20,  0.55, "Arnold"),
    ("Bolzen M10x60",                   7,  20,  0.65, "Arnold"),
    ("Bolzen M10x100",                 25,  15,  0.80, "Arnold"),
    ("Passstift 6x30",                 20,  15,  0.40, "Norelem"),
    ("Passstift 8x40",                 12,  12,  0.55, "Norelem"),
    ("Passstift 10x50",                 8,  10,  0.70, "Norelem"),
    ("Spannstift 4x30",                35,  20,  0.25, "Misumi"),
    ("Spannstift 6x40",                20,  15,  0.35, "Misumi"),
    # Nieten (10 Produkte)
    ("Blindniete 3.2mm Alu",           60,  50,  0.05, "Gesipa"),
    ("Blindniete 4.0mm Alu",            8,  50,  0.06, "Gesipa"),
    ("Blindniete 4.8mm Alu",           90,  40,  0.08, "Gesipa"),
    ("Blindniete 5.0mm Stahl",          3,  40,  0.10, "Gesipa"),
    ("Blindniete 6.4mm Stahl",         45,  30,  0.12, "Gesipa"),
    ("Gewindeniete M4",                20,  20,  0.25, "Bralo"),
    ("Gewindeniete M5",                15,  20,  0.30, "Bralo"),
    ("Gewindeniete M6",                10,  15,  0.35, "Bralo"),
    ("Gewindeniete M8",                 5,  10,  0.50, "RIBE"),
    ("Gewindeniete M10",                3,   8,  0.70, "RIBE"),
    # Klebstoffe & Dichtungen (15 Produkte)
    ("Sekundenkleber 20g",              2,  15,  2.50, "Loctite"),
    ("Schraubensicherung mittelfest 50ml", 5, 8,  12.50, "Loctite"),
    ("Schraubensicherung hochfest 50ml",  3,  6,  14.80, "Loctite"),
    ("Epoxidharz 50ml",                12,  10,  8.90, "Loctite"),
    ("Silikon transparent 310ml",       5,  10,  4.50, "Soudal"),
    ("Silikon schwarz 310ml",          18,  10,  4.50, "Soudal"),
    ("Silikon weiß 310ml",             8,  10,  4.50, "Soudal"),
    ("Montagekleber 310ml",            10,   8,  5.80, "Pattex"),
    ("Dichtungsring 10mm NBR",          6,  30,  0.30, "Simrit"),
    ("Dichtungsring 15mm NBR",         12,  25,  0.35, "Simrit"),
    ("Dichtungsring 20mm NBR",          8,  20,  0.40, "Simrit"),
    ("O-Ring 12mm Viton",               4,  15,  0.80, "Simrit"),
    ("Metallkleber 2K 25ml",            6,  10,  6.50, "Weicon"),
    ("Dichtmasse 310ml",                5,   8,  7.20, "Weicon"),
    ("Gewindedichtband 12mm",          20,  15,  1.20, "Würth"),
    # Werkzeug Verbrauchsmaterial (15 Produkte)
    ("Schleifpapier K80",               3,  20,  0.80, "Klingspor"),
    ("Schleifpapier K120",             25,  20,  0.80, "Klingspor"),
    ("Schleifpapier K240",              8,  20,  0.80, "Klingspor"),
    ("Schleifscheibe 125mm K40",       10,  15,  1.20, "Klingspor"),
    ("Schleifscheibe 125mm K80",       15,  15,  1.20, "Klingspor"),
    ("Bohrer 4mm HSS",                  2,  10,  1.20, "Bosch"),
    ("Bohrer 6mm HSS",                  5,  10,  1.80, "Bosch"),
    ("Bohrer 8mm HSS",                  1,  10,  2.50, "Bosch"),
    ("Bohrer 10mm HSS",                 7,  10,  3.20, "Bosch"),
    ("Bohrer 12mm HSS",                 3,   8,  4.50, "Bosch"),
    ("Schneidoel 500ml",                2,   5, 12.90, "Liqui Moly"),
    ("Reinigungsspray 400ml",           4,   8,  5.90, "WD-40"),
    ("Kabelbinder 200mm 100er Pack",    3,  10,  3.50, "Hellermann"),
    ("Kabelbinder 300mm 100er Pack",    5,  10,  4.20, "Hellermann"),
    ("Schrumpfschlauch-Set 100-tlg",    2,   5,  8.90, "Hellermann"),
]

# (produkt_index, lieferant_name, preis, lieferzeit_tage)
# Jedes Produkt soll mindestens 3 Lieferanten haben (1 Standard + 2 Alternative)
ALTERNATIVE_LIEFERANTEN = [
    # Schrauben M4-M12: Standard=Würth, Alternativen aus Fabory, RS Components, Bossard, Schrauben Jäger, Keller & Kalmbach
    (0,  "Fabory",             0.06, 4),  (0,  "RS Components",     0.04, 2),  (0,  "Schrauben Jäger",  0.05, 2),
    (1,  "Fabory",             0.07, 4),  (1,  "Bossard",           0.06, 3),  (1,  "Schrauben Jäger",  0.06, 2),
    (2,  "Fabory",             0.09, 4),  (2,  "RS Components",     0.07, 2),  (2,  "Bossard",          0.08, 3),
    (3,  "Bossard",            0.11, 3),  (3,  "Schrauben Jäger",   0.09, 2),  (3,  "Keller & Kalmbach",0.10, 3),
    (4,  "Fabory",             0.14, 4),  (4,  "RS Components",     0.11, 2),  (4,  "Keller & Kalmbach",0.13, 3),
    (5,  "Bossard",            0.16, 3),  (5,  "Schrauben Jäger",   0.14, 2),  (5,  "Mercateo",         0.15, 2),
    (6,  "RS Components",      0.19, 2),  (6,  "Fabory",            0.22, 4),  (6,  "Keller & Kalmbach",0.21, 3),
    (7,  "Bossard",            0.26, 3),  (7,  "Schrauben Jäger",   0.24, 2),  (7,  "Mercateo",         0.25, 2),
    (8,  "Fabory",             0.33, 4),  (8,  "RS Components",     0.28, 2),  (8,  "Keller & Kalmbach",0.31, 3),
    (9,  "Bossard",            0.42, 3),  (9,  "Schrauben Jäger",   0.38, 2),  (9,  "Mercateo",         0.40, 2),
    # Senkkopfschrauben: Standard=Schrauben Jäger/Norelem
    (10, "Würth",              0.07, 2),  (10, "Fabory",            0.08, 4),  (10, "RS Components",    0.06, 2),
    (11, "Würth",              0.11, 2),  (11, "Bossard",           0.12, 3),  (11, "Mercateo",         0.10, 2),
    (12, "Würth",              0.16, 2),  (12, "Fabory",            0.18, 4),  (12, "Keller & Kalmbach",0.17, 3),
    (13, "Würth",              0.24, 2),  (13, "Schrauben Jäger",   0.23, 2),  (13, "RS Components",    0.22, 2),
    (14, "Würth",              0.30, 2),  (14, "Schrauben Jäger",   0.29, 2),  (14, "Fabory",           0.33, 4),
    # Gewindestangen
    (15, "Arnold",             2.60, 4),  (15, "RS Components",     2.40, 2),  (15, "Keller & Kalmbach",2.55, 3),
    (16, "Würth",              3.30, 2),  (16, "RS Components",     3.10, 2),  (16, "Fabory",           3.40, 4),
    (17, "Würth",              4.10, 2),  (17, "RS Components",     3.90, 2),  (17, "Fabory",           4.20, 4),
    # Fluegelschrauben
    (18, "Würth",              0.19, 2),  (18, "Misumi",            0.17, 3),  (18, "Mercateo",         0.18, 2),
    (19, "Würth",              0.26, 2),  (19, "Misumi",            0.24, 3),  (19, "RS Components",    0.25, 2),
    # Sechskantmuttern: Standard=Bossard
    (20, "Würth",              0.05, 2),  (20, "Fabory",            0.04, 3),  (20, "Keller & Kalmbach",0.04, 3),
    (21, "Würth",              0.06, 2),  (21, "Schrauben Jäger",   0.06, 2),  (21, "Mercateo",         0.06, 2),
    (22, "Würth",              0.09, 2),  (22, "Fabory",            0.08, 3),  (22, "RS Components",    0.08, 2),
    (23, "Würth",              0.11, 2),  (23, "Schrauben Jäger",   0.10, 2),  (23, "Keller & Kalmbach",0.10, 3),
    (24, "Würth",              0.13, 2),  (24, "Fabory",            0.12, 3),  (24, "Mercateo",         0.12, 2),
    # Flanschmuttern
    (25, "Bossard",            0.10, 3),  (25, "Würth",             0.09, 2),  (25, "Keller & Kalmbach",0.10, 3),
    (26, "Bossard",            0.13, 3),  (26, "Würth",             0.12, 2),  (26, "RS Components",    0.12, 2),
    # Hutmuttern
    (27, "Bossard",            0.09, 3),  (27, "Würth",             0.08, 2),  (27, "Keller & Kalmbach",0.09, 3),
    (28, "Bossard",            0.12, 3),  (28, "Würth",             0.11, 2),  (28, "RS Components",    0.11, 2),
    (29, "Bossard",            0.15, 3),  (29, "Würth",             0.14, 2),  (29, "Mercateo",         0.14, 2),
    # Unterlegscheiben: Standard=Bossard
    (30, "Würth",              0.04, 2),  (30, "Fabory",            0.03, 3),  (30, "Mercateo",         0.03, 2),
    (31, "Würth",              0.04, 2),  (31, "Fabory",            0.04, 3),  (31, "Keller & Kalmbach",0.04, 3),
    (32, "Würth",              0.05, 2),  (32, "RS Components",     0.05, 2),  (32, "Fabory",           0.06, 3),
    (33, "Würth",              0.07, 2),  (33, "Fabory",            0.06, 3),  (33, "Mercateo",         0.06, 2),
    (34, "Würth",              0.09, 2),  (34, "Fabory",            0.08, 3),  (34, "RS Components",    0.08, 2),
    # Federringe/Zahnscheiben
    (35, "Bossard",            0.05, 3),  (35, "Würth",             0.05, 2),  (35, "Fabory",           0.06, 3),
    (36, "Bossard",            0.07, 3),  (36, "Würth",             0.06, 2),  (36, "Keller & Kalmbach",0.07, 3),
    (37, "Bossard",            0.08, 3),  (37, "Würth",             0.07, 2),  (37, "RS Components",    0.07, 2),
    (38, "Bossard",            0.04, 3),  (38, "Würth",             0.04, 2),  (38, "Mercateo",         0.04, 2),
    (39, "Bossard",            0.06, 3),  (39, "Würth",             0.05, 2),  (39, "RS Components",    0.05, 2),
    # Dübel: Standard=Fischer/TOX/Hilti
    (40, "TOX",                0.17, 3),  (40, "Hilti",             0.20, 1),  (40, "RS Components",    0.16, 2),
    (41, "TOX",                0.22, 3),  (41, "Hilti",             0.26, 1),  (41, "Haberkorn",        0.21, 4),
    (42, "TOX",                0.28, 3),  (42, "Hilti",             0.32, 1),  (42, "RS Components",    0.26, 2),
    (43, "TOX",                0.33, 3),  (43, "Hilti",             0.38, 1),  (43, "Mercateo",         0.31, 2),
    (44, "TOX",                0.44, 3),  (44, "Hilti",             0.52, 1),  (44, "Haberkorn",        0.42, 4),
    (45, "Fischer",            0.38, 2),  (45, "Hilti",             0.42, 1),  (45, "RS Components",    0.36, 2),
    (46, "Fischer",            0.48, 2),  (46, "Hilti",             0.55, 1),  (46, "Mercateo",         0.46, 2),
    (47, "Fischer",            1.90, 2),  (47, "TOX",               1.95, 3),  (47, "Haberkorn",        1.85, 4),
    (48, "Fischer",            2.60, 2),  (48, "TOX",               2.70, 3),  (48, "RS Components",    2.45, 2),
    (49, "Fischer",            3.30, 2),  (49, "TOX",               3.40, 3),  (49, "Haberkorn",        3.15, 4),
    # Bolzen/Stifte: Standard=Arnold/Norelem/Misumi
    (50, "Würth",              0.37, 2),  (50, "Fabory",            0.38, 3),  (50, "Keller & Kalmbach",0.36, 3),
    (51, "Würth",              0.47, 2),  (51, "RS Components",     0.44, 2),  (51, "Fabory",           0.48, 3),
    (52, "Würth",              0.57, 2),  (52, "Fabory",            0.58, 3),  (52, "Keller & Kalmbach",0.56, 3),
    (53, "Würth",              0.67, 2),  (53, "RS Components",     0.63, 2),  (53, "Mercateo",         0.66, 2),
    (54, "Würth",              0.82, 2),  (54, "Fabory",            0.84, 3),  (54, "RS Components",    0.78, 2),
    (55, "Misumi",             0.42, 3),  (55, "Arnold",            0.43, 4),  (55, "RS Components",    0.40, 2),
    (56, "Misumi",             0.57, 3),  (56, "Arnold",            0.58, 4),  (56, "Keller & Kalmbach",0.56, 3),
    (57, "Misumi",             0.72, 3),  (57, "Arnold",            0.74, 4),  (57, "RS Components",    0.68, 2),
    (58, "Arnold",             0.27, 4),  (58, "Norelem",           0.26, 3),  (58, "RS Components",    0.24, 2),
    (59, "Arnold",             0.37, 4),  (59, "Norelem",           0.36, 3),  (59, "Mercateo",         0.34, 2),
    # Nieten: Standard=Gesipa/Bralo/RIBE
    (60, "Bralo",              0.06, 4),  (60, "RS Components",     0.05, 2),  (60, "Mercateo",         0.05, 2),
    (61, "Bralo",              0.07, 4),  (61, "RS Components",     0.06, 2),  (61, "Haberkorn",        0.06, 4),
    (62, "Bralo",              0.09, 4),  (62, "RS Components",     0.08, 2),  (62, "Mercateo",         0.08, 2),
    (63, "Bralo",              0.11, 4),  (63, "RS Components",     0.10, 2),  (63, "Keller & Kalmbach",0.10, 3),
    (64, "Bralo",              0.13, 4),  (64, "RS Components",     0.12, 2),  (64, "Haberkorn",        0.12, 4),
    (65, "Gesipa",             0.27, 3),  (65, "RS Components",     0.24, 2),  (65, "Mercateo",         0.26, 2),
    (66, "Gesipa",             0.32, 3),  (66, "RS Components",     0.29, 2),  (66, "Haberkorn",        0.31, 4),
    (67, "Gesipa",             0.37, 3),  (67, "RS Components",     0.34, 2),  (67, "Mercateo",         0.36, 2),
    (68, "Bralo",              0.52, 4),  (68, "Gesipa",            0.48, 3),  (68, "RS Components",    0.50, 2),
    (69, "Bralo",              0.72, 4),  (69, "Gesipa",            0.68, 3),  (69, "RS Components",    0.70, 2),
    # Klebstoffe/Dichtungen: Standard=Loctite/Soudal/Simrit/Pattex/Weicon
    (70, "Weicon",             2.60, 3),  (70, "Pattex",            2.40, 4),  (70, "RS Components",    2.70, 2),
    (71, "Weicon",            13.00, 3),  (71, "RS Components",    12.80, 2),  (71, "Mercateo",        12.90, 2),
    (72, "Weicon",            15.00, 3),  (72, "RS Components",    14.50, 2),  (72, "Mercateo",        15.20, 2),
    (73, "Weicon",             9.20, 3),  (73, "Pattex",            8.80, 4),  (73, "RS Components",    9.50, 2),
    (74, "Weicon",             4.80, 3),  (74, "Pattex",            4.40, 4),  (74, "RS Components",    4.90, 2),
    (75, "Weicon",             4.80, 3),  (75, "Pattex",            4.40, 4),  (75, "Mercateo",         4.60, 2),
    (76, "Weicon",             4.80, 3),  (76, "Loctite",           4.70, 5),  (76, "RS Components",    4.90, 2),
    (77, "Soudal",             6.00, 4),  (77, "Loctite",           5.90, 5),  (77, "Mercateo",         5.80, 2),
    (78, "Weicon",             0.32, 3),  (78, "RS Components",     0.31, 2),  (78, "Mercateo",         0.30, 2),
    (79, "Weicon",             0.37, 3),  (79, "RS Components",     0.36, 2),  (79, "Haberkorn",        0.36, 4),
    (80, "Weicon",             0.42, 3),  (80, "RS Components",     0.41, 2),  (80, "Mercateo",         0.40, 2),
    (81, "Weicon",             0.85, 3),  (81, "RS Components",     0.82, 2),  (81, "Mercateo",         0.80, 2),
    (82, "Loctite",            6.80, 5),  (82, "Pattex",            6.30, 4),  (82, "RS Components",    6.70, 2),
    (83, "Soudal",             7.50, 4),  (83, "Loctite",           7.40, 5),  (83, "RS Components",    7.30, 2),
    (84, "Loctite",            1.30, 5),  (84, "RS Components",     1.20, 2),  (84, "Mercateo",         1.25, 2),
    # Werkzeug Verbrauchsmaterial: Standard=Klingspor/Bosch/etc.
    (85, "3M",                 0.85, 2),  (85, "Bosch",             0.90, 3),  (85, "RS Components",    0.82, 2),
    (86, "3M",                 0.85, 2),  (86, "Bosch",             0.90, 3),  (86, "Mercateo",         0.82, 2),
    (87, "3M",                 0.85, 2),  (87, "Bosch",             0.90, 3),  (87, "RS Components",    0.82, 2),
    (88, "3M",                 1.25, 2),  (88, "Bosch",             1.30, 3),  (88, "Mercateo",         1.22, 2),
    (89, "3M",                 1.25, 2),  (89, "Bosch",             1.30, 3),  (89, "RS Components",    1.22, 2),
    (90, "Metabo",             1.30, 3),  (90, "RS Components",     1.15, 2),  (90, "Mercateo",         1.22, 2),
    (91, "Metabo",             1.90, 3),  (91, "RS Components",     1.75, 2),  (91, "Conrad",           1.80, 1),
    (92, "Metabo",             2.60, 3),  (92, "RS Components",     2.45, 2),  (92, "Conrad",           2.50, 1),
    (93, "Metabo",             3.30, 3),  (93, "RS Components",     3.10, 2),  (93, "Conrad",           3.15, 1),
    (94, "Metabo",             4.60, 3),  (94, "RS Components",     4.40, 2),  (94, "Conrad",           4.45, 1),
    (95, "WD-40",             13.20, 4),  (95, "RS Components",    12.50, 2),  (95, "Mercateo",        13.00, 2),
    (96, "Liqui Moly",         6.10, 5),  (96, "RS Components",     5.80, 2),  (96, "Conrad",           5.90, 1),
    (97, "RS Components",      3.60, 2),  (97, "Conrad",            3.40, 1),  (97, "Mercateo",         3.55, 2),
    (98, "RS Components",      4.30, 2),  (98, "Conrad",            4.10, 1),  (98, "Mercateo",         4.25, 2),
    (99, "RS Components",      9.10, 2),  (99, "Conrad",            8.80, 1),  (99, "Mercateo",         9.00, 2),
]


def _seed_lieferanten(cursor):
    """Fuegt alle Lieferanten ein und gibt die Name-zu-ID Zuordnung zurück."""
    cursor.executemany("""
        INSERT INTO lieferanten (name, kontakt, lieferzeit_tage, bewertung)
        VALUES (?, ?, ?, ?)
    """, LIEFERANTEN)

    cursor.execute("SELECT id, name FROM lieferanten")
    return {name: lid for lid, name in cursor.fetchall()}


def _seed_produkte(cursor, lief_map):
    """Fuegt alle Produkte ein und gibt die Produkt-IDs zurück."""
    for p in PRODUKTE:
        cursor.execute("""
            INSERT INTO produkte (name, bestand, mindestbestand, preis_pro_einheit, standard_lieferant_id)
            VALUES (?, ?, ?, ?, ?)
        """, (p[0], p[1], p[2], p[3], lief_map[p[4]]))

    cursor.execute("SELECT id FROM produkte ORDER BY id")
    return [row[0] for row in cursor.fetchall()]


def _seed_lieferanten_zuordnungen(cursor, produkt_ids, lief_map):
    """Verknuepft Produkte mit Standard- und Alternativ-Lieferanten."""
    for i, p in enumerate(PRODUKTE):
        cursor.execute("""
            INSERT INTO produkt_lieferanten (produkt_id, lieferant_id, preis, lieferzeit_tage)
            VALUES (?, ?, ?, ?)
        """, (produkt_ids[i], lief_map[p[4]], p[3], None))

    for prod_idx, lief_name, preis, lieferzeit in ALTERNATIVE_LIEFERANTEN:
        cursor.execute("""
            INSERT INTO produkt_lieferanten (produkt_id, lieferant_id, preis, lieferzeit_tage)
            VALUES (?, ?, ?, ?)
        """, (produkt_ids[prod_idx], lief_map[lief_name], preis, lieferzeit))


def _seed_budget(cursor):
    """Legt aktuelles und vorheriges Quartalsbudget an."""
    jetzt = datetime.now()
    quartal = (jetzt.month - 1) // 3 + 1

    cursor.execute("""
        INSERT INTO budget (quartal, jahr, gesamtbudget, verbrauchtes_budget)
        VALUES (?, ?, ?, ?)
    """, (quartal, jetzt.year, SEED_BUDGET_BETRAG, 0.00))

    prev_q = quartal - 1 if quartal > 1 else 4
    prev_year = jetzt.year if quartal > 1 else jetzt.year - 1
    cursor.execute("""
        INSERT INTO budget (quartal, jahr, gesamtbudget, verbrauchtes_budget)
        VALUES (?, ?, ?, ?)
    """, (prev_q, prev_year, SEED_BUDGET_BETRAG, SEED_VORQUARTAL_VERBRAUCHT))


def _seed_verbrauch(cursor, produkt_ids):
    """Erzeugt historische Verbrauchsdaten der letzten 90 Tage."""
    random.seed(42)
    jetzt = datetime.now()
    gruende = ["Produktion", "Wartung", "Montage", "Reparatur", "Prototyp"]

    for tage_zurueck in range(90, 0, -1):
        datum = (jetzt - timedelta(days=tage_zurueck)).strftime("%Y-%m-%d")
        for i, pid in enumerate(produkt_ids):
            if random.random() < 0.15:
                menge = random.randint(1, max(3, PRODUKTE[i][2] // 10))
                grund = random.choice(gruende)
                cursor.execute("""
                    INSERT INTO verbrauch (produkt_id, menge, grund, datum)
                    VALUES (?, ?, ?, ?)
                """, (pid, menge, grund, datum))


def _seed_bestellungen(cursor, produkt_ids, lief_map):
    """Erzeugt historische Bestellungen der letzten 60 Tage."""
    jetzt = datetime.now()
    bestell_nr_counter = 1
    for tage_zurueck in range(60, 0, -5):
        datum_obj = jetzt - timedelta(days=tage_zurueck)
        datum = datum_obj.strftime("%Y-%m-%d %H:%M:%S")
        for _ in range(random.randint(1, 3)):
            i = random.randint(0, len(PRODUKTE) - 1)
            pid = produkt_ids[i]
            menge = random.randint(10, 100)
            kosten = menge * PRODUKTE[i][3]
            lief_id = lief_map[PRODUKTE[i][4]]
            bestell_nr = f"BEST-{datum_obj.year}-{bestell_nr_counter:04d}"
            cursor.execute("""
                INSERT INTO bestellungen (bestell_nr, produkt_id, lieferant_id, menge, gesamtkosten, datum)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (bestell_nr, pid, lief_id, menge, kosten, datum))
            bestell_nr_counter += 1


def seed_data(cursor):
    """Fuellt die Datenbank mit Beispieldaten."""
    cursor.execute("SELECT COUNT(*) FROM lieferanten")
    if cursor.fetchone()[0] > 0:
        return

    lief_map = _seed_lieferanten(cursor)
    produkt_ids = _seed_produkte(cursor, lief_map)
    _seed_lieferanten_zuordnungen(cursor, produkt_ids, lief_map)
    _seed_budget(cursor)
    _seed_verbrauch(cursor, produkt_ids)
    _seed_bestellungen(cursor, produkt_ids, lief_map)
