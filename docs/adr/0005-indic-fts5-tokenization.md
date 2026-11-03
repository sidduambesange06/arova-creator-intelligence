# ADR-0005: Indic-Safe Full-Text Search (FTS5) Tokenization Architecture

**Status:** Accepted  
**Date:** 2026-11-02  
**Author:** Principal AI & Database Engineer  
**Scope:** Search, FTS5 Tokenizer, Alembic Migrations, and Multilingual Creator Text Retrieval (Phase E)

---

## 1. Context and Problem Statement

Arova Creator Intelligence uses SQLite FTS5 for local-first lexical retrieval of video transcripts and OCR chunks (`transcript_chunks_fts`). The baseline schema created this virtual table using SQLite FTS5's default `unicode61` tokenizer without explicit token character configuration.

During Step 2 Phase E evaluation against official FLEURS benchmark references in Hindi, Kannada, Tamil, and Telugu, a critical tokenization defect was reproduced (`backend/tests/unit/test_indic_fts_tokenization.py`):
1. SQLite FTS5's default `unicode61` tokenizer treats only Unicode categories `L*` (Letters) and `N*` (Numbers) as alphanumeric token characters.
2. In Unicode standards, Indic combining vowel signs (matras, e.g. Devanagari `ा`, `े`, `ी`, Tamil `ி`, `ை`, Telugu `ె`, `ు`, Kannada `ೆ`, `ೂ`) are categorized as `Mn` (Mark, Nonspacing) or `Mc` (Mark, Spacing Combining).
3. Virama (halant, e.g. Devanagari `्`, Tamil `்`, Telugu `్`, Kannada `್`) is also categorized as `Mn`.
4. As a result, default `unicode61` treated combining vowel signs and viramas as word boundaries and delimiters, shattering whole words into meaningless consonant fragments:
   - Hindi `भारत` (`भ + ार + त`) was split into tokens `भ` and `रत`.
   - Hindi `नमस्ते` (`न + म + स + ् + त + े`) was split into tokens `नमस` and `त`.
   - Tamil `தமிழ்` (`த + ம + ி + ழ + ்`) was split into tokens `தம` and `ழ`.
   - Kannada `ಕನ್ನಡ` was split into tokens `ಕನ` and `ನಡ`.
   - Telugu `తెలుగు` was shattered into individual consonants `త`, `ల`, `గ`.
5. Exact word queries and inflected form matches failed to match correctly in SQLite FTS5 lexical ranking.
6. Furthermore, Python `re.findall(r"\w+", query)` in `_sanitize_fts_query` suffered from an identical splitting bug because standard Python `\w` does not include `Mn`/`Mc` combining marks.

---

## 2. Decision and Architecture Override

Pursuant to explicit Program v2 authorization (Phase E2 override to previous general instruction to leave FTS5 unchanged), we adopt the following changes:

1. **Explicit Alembic Migration (`0003_indic_fts5_tokenization`):**
   - Drops and recreates `transcript_chunks_fts` with `tokenize="unicode61 tokenchars '...'"` specifying all Unicode `Mn`, `Mc`, virama, nukta, and anusvara/visarga code points for:
     - Devanagari: `0x0901-0x0903`, `0x093C`, `0x093E-0x094F`, `0x0951-0x0957`, `0x0962-0x0963`
     - Tamil: `0x0B82`, `0x0BBE-0x0BCD`, `0x0BD7`
     - Telugu: `0x0C00-0x0C03`, `0x0C3E-0x0C4D`, `0x0C55-0x0C56`, `0x0C62-0x0C63`
     - Kannada: `0x0C81-0x0C83`, `0x0CBC`, `0x0CBE-0x0CCD`, `0x0CD5-0x0CD6`, `0x0CE2-0x0CE3`
   - Rebuilds index contents from authoritative `embedding_records` source table.
   - Fully reversible in `downgrade()`.

2. **Query Sanitization Guard (`_sanitize_fts_query`):**
   - Replaced `re.findall(r"\w+", query)` with explicit punctuation stripping (`[!"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~।॥]`), preserving whole Indic words and combining marks.

3. **Database Migration Matrix Integration:**
   - Updated `backend/app/database/migrator.py` to recognize `0003_indic_fts5_tokenization` as current head revision.
   - Updated `_ensure_fts5_table` in `backend/app/ai/providers/embeddings.py` to ensure runtime table creation also applies the Indic tokenchars tokenizer.

---

## 3. Verification and Evidence

Automated tests in `backend/tests/unit/test_indic_fts_tokenization.py`:
- `test_sqlite_fts5_unicode61_indic_tokenization_defect_reproduction`: PASS (reproduces word shattering under default unicode61).
- `test_sqlite_fts5_indic_tokenchars_fix`: PASS (asserts `नमस्ते`, `भारत`, `प्रौद्योगिकी`, `ಕನ್ನಡ`, `ಬೆಂಗಳೂರು`, `தமிழ்`, `சென்னை`, `తెలుగు`, `హైదరాబాద్` index as complete, intact tokens and return valid MATCH hits).

