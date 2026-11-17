"""Reproduction and verification test for SQLite FTS5 unicode61 Indic tokenization.

Tests whether SQLite FTS5 unicode61 tokenizer splits Hindi, Kannada, Tamil, and Telugu
words around combining vowel signs (matras, Mn/Mc) and virama (halant), and verifies the fix.
"""

from __future__ import annotations

import sqlite3
import pytest

TEST_WORDS = {
    "hindi": ["नमस्ते", "भारत", "प्रौद्योगिकी"],
    "kannada": ["ಕನ್ನಡ", "ಬೆಂಗಳೂರು"],
    "tamil": ["தமிழ்", "சென்னை"],
    "telugu": ["తెలుగు", "హైదరాబాద్"],
}

# Generate tokenchars for Indic combining vowel signs, viramas, and marks
def get_indic_tokenchars() -> str:
    chars = []
    # Devanagari: 0x0901-0x0903, 0x093C, 0x093E-0x094F, 0x0951-0x0957, 0x0962-0x0963
    for cp in list(range(0x0901, 0x0904)) + [0x093C] + list(range(0x093E, 0x0950)) + list(range(0x0951, 0x0958)) + list(range(0x0962, 0x0964)):
        chars.append(chr(cp))
    # Tamil: 0x0B82, 0x0BBE-0x0BCD, 0x0BD7
    for cp in [0x0B82] + list(range(0x0BBE, 0x0BCE)) + [0x0BD7]:
        chars.append(chr(cp))
    # Telugu: 0x0C00-0x0C03, 0x0C3E-0x0C4D, 0x0C55-0x0C56, 0x0C62-0x0C63
    for cp in list(range(0x0C00, 0x0C04)) + list(range(0x0C3E, 0x0C4E)) + list(range(0x0C55, 0x0C57)) + list(range(0x0C62, 0x0C64)):
        chars.append(chr(cp))
    # Kannada: 0x0C81-0x0C83, 0x0CBC, 0x0CBE-0x0CCD, 0x0CD5-0x0CD6, 0x0CE2-0x0CE3
    for cp in list(range(0x0C81, 0x0C84)) + [0x0CBC] + list(range(0x0CBE, 0x0CCE)) + list(range(0x0CD5, 0x0CD7)) + list(range(0x0CE2, 0x0CE4)):
        chars.append(chr(cp))
    return "".join(chars)


def test_sqlite_fts5_unicode61_indic_tokenization_defect_reproduction():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()

    cur.execute("CREATE VIRTUAL TABLE default_fts USING fts5(content, tokenize='unicode61')")
    cur.execute("INSERT INTO default_fts(content) VALUES ('भारत')")

    cur.execute("CREATE VIRTUAL TABLE default_vocab USING fts5vocab(default_fts, 'row')")
    cur.execute("SELECT term FROM default_vocab")
    terms = [row[0] for row in cur.fetchall()]

    # Confirms reproduction: "भारत" is shattered into "भ" and "रत"
    assert "भारत" not in terms
    assert "भ" in terms
    assert "रत" in terms
    con.close()


def test_sqlite_fts5_indic_tokenchars_fix():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()

    indic_tokenchars = get_indic_tokenchars()
    # Escape quotes inside tokenizer argument
    safe_tokenchars = indic_tokenchars.replace("'", "''")
    tokenizer_sql = f"unicode61 tokenchars '{safe_tokenchars}'"

    cur.execute(f"CREATE VIRTUAL TABLE fixed_fts USING fts5(content, tokenize=\"{tokenizer_sql}\")")

    # Insert test sentences
    for lang, words in TEST_WORDS.items():
        sentence = " ".join(words)
        cur.execute("INSERT INTO fixed_fts(content) VALUES (?)", (sentence,))

    cur.execute("CREATE VIRTUAL TABLE fixed_vocab USING fts5vocab(fixed_fts, 'row')")
    cur.execute("SELECT term FROM fixed_vocab")
    terms = set(row[0] for row in cur.fetchall())

    # Verify that every test word is indexed as a complete intact token
    for lang, words in TEST_WORDS.items():
        for word in words:
            assert word in terms, f"Word '{word}' ({lang}) was not preserved as intact token. Tokens: {terms}"

    # Verify MATCH query on whole word
    for lang, words in TEST_WORDS.items():
        for word in words:
            cur.execute("SELECT count(*) FROM fixed_fts WHERE fixed_fts MATCH ?", (f'"{word}"',))
            count = cur.fetchone()[0]
            assert count >= 1, f"MATCH query failed for '{word}' ({lang})"

    con.close()
