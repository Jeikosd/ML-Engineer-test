"""RAG: chunk text, and answer questions grounded in retrieved context.

Implement this. Reminders (graded): chunking must not cut words in half; the
LLM call needs a timeout and retries; the answer must be grounded in the
retrieved chunks and ``sources`` must reflect what was actually retrieved (no
fabricated sources); handle a missing/failing LLM cleanly.
"""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 60) -> list[str]:
    """Split text into whole-word chunks; each starts with the previous one's tail."""
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
    chunks, current = [], []
    for word in text.split():
        if current and len(" ".join([*current, word])) > chunk_size:
            chunks.append(" ".join(current))
            tail = []
            for previous in reversed(current):
                tail_len = len(" ".join([previous, *tail]))
                if tail_len > overlap or tail_len + 1 + len(word) > chunk_size:
                    break
                tail = [previous, *tail]
            current = tail
        current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def generate_answer(question: str) -> dict:
    """Retrieve context and return ``{"answer", "sources"}``."""
    raise NotImplementedError
