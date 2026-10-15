"""Heuristic prompt injection detection for user text that is sent to an LLM."""

from __future__ import annotations

import re

# Sentence ends only split when a capitalised word follows, so "previous... instructions" stays one phrase.
_SEGMENT_BREAK = re.compile(r"[.!?]+(?=\s+[A-Z]|\s*$)|[;:|\n\r]+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_AI = r"(?:ai|assistant|model|llm|chatbot|bot|language model|ai assistant|ai model|ai system|ai reviewer|automated reviewer)"
_YOU = r"(?:you|your|yourself)"
_RULES = (
    r"(?:instructions?|prompts?|rules|guidelines|guidance|directions|directives|context|constraints|guardrails"
    r"|safeguards|everything|the above|what you were (?:told|given))"
)
_EARLIER = r"(?:previous|prior|above|earlier|preceding|foregoing|original)"
_PROMPT = (
    r"(?:system prompt|system instructions|hidden instructions|initial instructions|original instructions"
    r"|developer message|your (?:\w+ ){0,2}(?:instructions|prompt|rules|guidelines|configuration))"
)
_SECRETS = r"(?:api keys?|access keys?|credentials|passwords?|secrets?|tokens?|private keys?)"
_SHOW = r"(?:reveal|print|show|display|output|repeat|recite|echo|dump|list|share|leak|expose|return|tell me|give me|write out|send)"
_OUTCOME = r"(?:accept|accepted|approved|decided)"
# Optional filler words before an imperative at the start of a sentence.
_LEAD = r"^(?:(?:please|now|first|then|also|just|kindly|afterwards|finally|and|so) ){0,3}"

_RAW_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "delimiter_injection",
        re.compile(
            r"</?\s*(?:system|assistant|user|developer|tool|instructions?|context|prompt|untrusted[\w-]*|reference[\w-]*)\s*>"
            r"|<\|[a-z_]+\|>|\[/?(?:inst|sys)\]",
            re.IGNORECASE,
        ),
    ),
    ("role_prefix", re.compile(r"(?:^|[\n.!?]\s*)(?:system|assistant|developer)\s*:", re.IGNORECASE)),
    ("hidden_markup", re.compile(r"<!--|[​-‏⁠﻿]")),
]

_SEGMENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("instruction_override", re.compile(_LEAD + rf"(?:ignore|disregard|forget|discard)\b(?: \w+){{0,4}} {_RULES}\b")),
    (
        "instruction_override",
        re.compile(rf"\b(?:ignore|disregard|forget) (?:all |any |the |your )?{_EARLIER}(?: \w+){{0,2}} (?:{_RULES}|messages?)\b"),
    ),
    ("instruction_override", re.compile(rf"\b(?:override|bypass) (?:your|all {_EARLIER}|{_EARLIER})(?: \w+){{0,2}} {_RULES}\b")),
    (
        "role_reassignment",
        re.compile(
            rf"\byou are (?:now|no longer)\b|\b{_YOU} (?:will |shall |must |should )?(?:now )?(?:act|behave|operate|respond) as\b"
            r"|\bfrom (?:now on|this point(?: on| forward)?)(?: \w+){0,3} you\b|\bpretend (?:to be|you are|that you)\b|\brole ?play as\b"
        ),
    ),
    ("prompt_exfiltration", re.compile(rf"\b{_SHOW}\b(?: \w+){{0,5}} {_PROMPT}\b")),
    (
        "prompt_exfiltration",
        re.compile(rf"\b{_SHOW}\b(?: \w+){{0,5}} {_SECRETS}\b.*\b{_YOU}\b|\b{_YOU}\b.*\b{_SHOW}\b(?: \w+){{0,5}} {_SECRETS}\b"),
    ),
    (
        "model_addressed",
        re.compile(
            rf"^(?:(?:hey|dear|attention) )?(?:(?:a )?(?:note|message|instructions?|reminder|request) (?:for|to) (?:the |any |our )?{_AI}\b"
            rf"|{_AI} (?:please|you|stop|ignore|disregard|forget|set|mark|approve|accept|output|return|reply|respond|answer|rate|treat|skip|do not|don t)\b)"
        ),
    ),
    (
        "fake_authority",
        re.compile(
            r"\b(?:admin|administrator|system|developer|root|security|emergency) override(?: \w+){0,2} "
            r"(?:set|mark|approve|accept|grant|change|update|skip|ignore|disable)\b"
            r"|\b(?:new|updated|revised|real|actual) (?:instructions?|directives?|orders?|commands?)(?: \w+){0,3} (?:from|by) "
            r"(?:the |your )?(?:admin|administrator|system|developer|ciso|cto|ceo|board|committee|risk committee|security team|management|operator)\b"
            rf"|\b{_YOU} (?:are|re) (?:now )?(?:authori[sz]ed|permitted|allowed|cleared|instructed|required) to\b"
        ),
    ),
    (
        "decision_tampering",
        re.compile(
            r"\b(?:mark|set|record|flag|classify|rate|label|treat) (?:this|the|every|all|each|any)(?: \w+){0,3} "
            rf"(?:risks?|items?|records?|decisions?|treatments?|perspectives?|status)\b(?: \w+){{0,2}} (?:as|to) {_OUTCOME}\b"
            rf"|\b{_YOU} (?:can |may |should |must )?(?:bypass|skip|circumvent|override)\b"
            + "|"
            + _LEAD
            + r"(?:bypass|skip|circumvent) (?:the |any |all )?(?:human |manual |required )?"
            r"(?:review|reviewers|reviewer assessments|assessments|approvals?|safeguards|guardrails)\b"
        ),
    ),
]


def _segments(text: str) -> list[str]:
    normalised = (_NON_ALNUM.sub(" ", part.lower()).strip() for part in _SEGMENT_BREAK.split(text))
    return [segment for segment in normalised if segment]


def detect_prompt_injection(text: str | None) -> list[str]:
    """Return the injection categories found in one piece of text, in a stable order."""
    if not text:
        return []
    found = [category for category, pattern in _RAW_PATTERNS if pattern.search(text)]
    segments = _segments(text)
    for category, pattern in _SEGMENT_PATTERNS:
        if category not in found and any(pattern.search(segment) for segment in segments):
            found.append(category)
    return found


def scan_fields(fields: dict[str, str | None]) -> list[str]:
    """Return one prompt_injection:<category>:<field> flag per category found in each field."""
    return [
        f"prompt_injection:{category}:{name}"
        for name, value in fields.items()
        for category in detect_prompt_injection(value)
    ]
