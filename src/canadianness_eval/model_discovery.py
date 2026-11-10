import re


def select_model(ids, override="auto"):
    if override != "auto":
        if override not in ids:
            raise ValueError("Explicit LLM_MODEL is not accessible in /models")
        return override
    matches = [
        m for m in ids if re.search(r"gptoss120b(?!\d)", re.sub(r"[^a-z0-9]", "", m.lower()))
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one GPT-OSS-120B match; found {len(matches)}. "
            "Set LLM_MODEL to an accessible deployment ID if necessary."
        )
    return matches[0]
