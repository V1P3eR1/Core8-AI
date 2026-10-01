import re
from dataclasses import dataclass, field

_DETECTORS: list[tuple[str, re.Pattern]] = [
    ("ignore-previous", re.compile(
        r"ignore\s+(all|the|previous|prior|above)\s+(instructions?|rules?|prompts?)", re.I)),
    ("disregard", re.compile(
        r"disregard\s+(all|the|previous)\s+(instructions?|rules?)", re.I)),
    ("new-instructions", re.compile(
        r"(new instructions?|new task|new prompt)\s*:", re.I)),
    ("system-tag", re.compile(
        r"(^\s*system\s*:|<system>|\[SYSTEM\]|<\|system\|>)", re.I | re.M)),
    ("role-play", re.compile(
        r"(act as|pretend (to be|you are)|you are now|from now on you)", re.I)),
    ("jailbreak", re.compile(
        r"(jailbreak|DAN mode|developer mode enabled)", re.I)),
    ("data-exfil-cue", re.compile(
        r"(send|email|forward|post)\s+(all|every|the full)\s+(customers?|emails?|users?|secrets?|api keys?|tokens?)", re.I)),
    ("tool-invocation", re.compile(
        r"(call|invoke|use|run|execute)\s+(the\s+)?(send_email|delete|forget|run_code|execute_shell)", re.I)),
]


@dataclass
class GatedContent:
    content: str
    source: str
    flagged: bool = False
    flag_reasons: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        flag_attr = "true" if self.flagged else "false"
        reasons_attr = ",".join(self.flag_reasons) if self.flag_reasons else ""
        tag = f"untrusted_{self.source}"
        return f'<{tag} flagged="{flag_attr}" reasons="{reasons_attr}">{self.content}</{tag}>'


def gate(content: str, source: str) -> GatedContent:
    reasons = [name for name, pattern in _DETECTORS if pattern.search(content)]
    return GatedContent(
        content=content,
        source=source,
        flagged=bool(reasons),
        flag_reasons=reasons,
    )


def flag_untrusted_rows(rows: list[dict], source_label: str) -> list[dict]:
    result = []
    for row in rows:
        reasons: list[str] = []
        for value in row.values():
            if isinstance(value, str):
                reasons += [name for name, pat in _DETECTORS if pat.search(value)]
        out = dict(row)
        if reasons:
            out["_flagged_untrusted"] = True
            out["_flag_reasons"] = list(set(reasons))
            out["_untrusted_source"] = source_label
        result.append(out)
    return result
