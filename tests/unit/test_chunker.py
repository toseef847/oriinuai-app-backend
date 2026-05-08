from app.services.rag.chunker import chunk_by_day


def test_chunk_by_day_splits_entries():
    sample_text = (
        "DAY 1 — LAW OF BEGINNINGS\n"
        "PROVERB\n"
        "\"First proverb\" (Yoruba)\n"
        "Translation\n"
        "TODAY'S WISDOM\n"
        "One-line principle\n"
        "SACRED INSIGHT\n"
        "Insight body\n"
        "REFLECTION\n"
        "Question\n"
        "AFFIRMATION\n"
        "Affirmation\n"
        "ORÍ DECREE\n"
        "Decree\n"
        "ACTION STEP\n"
        "Action\n"
        "DAY 2 — LAW OF CONTINUITY\n"
        "PROVERB\n"
        "\"Second proverb\" (Igbo)\n"
        "Translation\n"
    )

    chunks = chunk_by_day(sample_text)

    assert len(chunks) == 2
    assert chunks[0]["day_number"] == 1
    assert "LAW OF BEGINNINGS" in chunks[0]["law_name"]
    assert chunks[1]["day_number"] == 2
    assert "LAW OF CONTINUITY" in chunks[1]["law_name"]
