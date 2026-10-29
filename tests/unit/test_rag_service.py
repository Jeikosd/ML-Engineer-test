import random
import string

import pytest

from app.services.rag_service import chunk_text

SENTENCE = (
    "Richard Hernandez called the meeting to order. Jennifer Liu confirmed quorum."
)


def _random_text(rng):
    lengths = [rng.randint(1, 60) for _ in range(rng.randint(30, 80))]
    return " ".join("".join(rng.choices(string.ascii_lowercase, k=n)) for n in lengths)


def test_ac_chk_01_random_text_keeps_whole_words_in_order():
    rng = random.Random(0)
    for _ in range(200):
        text = _random_text(rng)
        words = text.split()
        start, end = -1, 0
        for chunk in chunk_text(text, chunk_size=50, overlap=20):
            piece = chunk.split()
            # a chunk starts inside the previous one (its overlap), never after it
            starts = [
                s
                for s in range(start + 1, end + 1)
                if words[s : s + len(piece)] == piece
            ]
            assert starts, (
                "chunk is not a contiguous slice that starts after the previous one"
            )
            start, end = starts[0], starts[0] + len(piece)
            assert len(chunk) <= 50 or any(len(w) > 50 for w in piece)
        assert end == len(words)


@pytest.mark.parametrize("overlap", [17, 20])  # "meeting to order." is exactly 17
def test_ac_chk_02_overlap_keeps_name_whole(overlap):
    assert chunk_text(SENTENCE, chunk_size=50, overlap=overlap) == [
        "Richard Hernandez called the meeting to order.",
        "meeting to order. Jennifer Liu confirmed quorum.",
    ]


@pytest.mark.parametrize(
    ("text", "expected"), [("", []), ("   \n ", []), ("x" * 600, ["x" * 600])]
)
def test_ac_chk_03_edge_cases(text, expected):
    assert chunk_text(text, chunk_size=50, overlap=20) == expected


@pytest.mark.parametrize("overlap", [50, -1])
def test_ac_chk_03_overlap_not_smaller_raises(overlap):
    with pytest.raises(ValueError):
        chunk_text(SENTENCE, chunk_size=50, overlap=overlap)
