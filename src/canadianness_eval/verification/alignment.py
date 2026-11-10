"""Exact original context for atomic assertions sharing a grammatical subject."""

import re


def contextualize(claim, answer):
    if answer[claim.answer_start : claim.answer_end] != claim.text:
        raise ValueError("Cannot contextualize a claim whose offsets do not match the original")
    left = 0
    for match in re.finditer(r"[.!?](?=\s)", answer[: claim.answer_start]):
        left = match.end()
    while left < claim.answer_start and answer[left].isspace():
        left += 1
    right = claim.answer_end
    if not answer[:right].endswith((".", "!", "?")):
        match = re.search(r"[.!?](?=\s|$)", answer[right:])
        right = right + match.end() if match else len(answer)
    return claim.model_copy(
        update={"text": answer[left:right], "answer_start": left, "answer_end": right}
    )
