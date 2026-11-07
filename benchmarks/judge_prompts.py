"""
FROZEN judge prompts for the LLM-judge baseline (argument grounding). Written once, before any judge was run on any
benchmark case; do not edit after the first test-set run (changing any character changes PROMPT_HASH and invalidates the
cache and the pre-registration).  Variant 0 is the main prompt; variants 1 to 4 are paraphrases used only for the
prompt-sensitivity study (hypothesis H4).

The few-shot examples are invented here and are not taken from any benchmark file.
"""
from __future__ import annotations

import hashlib
import json

TASK_V0 = (
    "You check whether a planned tool call is supported by the conversation that came before it. "
    "For each argument, decide whether its value is supported: it is stated in the conversation, or it is an unambiguous "
    "reformatting of something stated (for example a currency code for a named currency, an ISO timestamp for a stated date "
    "and time, a number written in words). Be strict: a different number, name, date, place or unit is NOT supported, and "
    "a value that the conversation never mentions is NOT supported. Ignore arguments whose value is true or false. "
    'Reply with JSON only, no other text: {"supported": true or false, "unsupported_arguments": ["argument name", ...]}. '
    '"supported" is true only if every checked argument is supported.'
)

TASK_PARAPHRASES = [
    TASK_V0,
    "Decide if a proposed function call is grounded in the preceding dialogue. Look at every argument value. A value is "
    "grounded if the dialogue states it or states something that clearly means the same thing in another format (a currency "
    "code for a currency name, a timestamp for a date and time, digits for a number in words). Different numbers, names, dates, "
    "places or units are not grounded, and neither are values that never appear. Skip true/false arguments. Output JSON only: "
    '{"supported": true or false, "unsupported_arguments": [names]}. Use true for "supported" only when all checked values are grounded.',
    "Task: audit a tool call against its conversation. Go through the arguments one by one. Mark a value as supported when the "
    "conversation says it directly or says it in a different but equivalent format (currency code vs currency name, ISO "
    "date-time vs spoken date and time, spelled-out numbers). Mark it unsupported if the number, name, date, place or unit "
    "differs, or if the conversation does not mention it. Do not judge boolean arguments. Return only JSON of the form "
    '{"supported": bool, "unsupported_arguments": [str]} where supported is true exactly when no checked argument is unsupported.',
    "You are a strict verifier. Input: a conversation and a planned tool call. Output: whether each argument value is backed by "
    "the conversation. Backed means stated or trivially reformatted (e.g. JPY for Japanese yen, 2022-03-15T14:00:00 for 2 pm on "
    "March 15, 'twelve' for 12). Anything different, or never mentioned, is not backed. Booleans are ignored. Respond with a JSON "
    'object only: {"supported": <true|false>, "unsupported_arguments": [<names>]}; supported must be true only if nothing is unsupported.',
    "Verify the following planned tool call against the conversation shown. For every argument check that its value appears in "
    "the conversation or is an obvious rewriting of a stated value; be strict about numbers, names, dates, places and units, "
    "and treat unmentioned values as unsupported. Ignore true/false values. Answer in JSON only, exactly: "
    '{"supported": true/false, "unsupported_arguments": ["name", ...]}, with supported true only when the list is empty.',
]

FEW_SHOT = [
    {"conversation": "User: Please book a table for 4 people at Luigi's on Friday at 7 pm.",
     "call": {"name": "book_table", "arguments": {"restaurant": "Luigi's", "party_size": 4, "time": "19:00", "day": "Friday"}},
     "answer": {"supported": True, "unsupported_arguments": []}},
    {"conversation": "User: Convert 250 euros to Swiss francs.",
     "call": {"name": "convert_currency", "arguments": {"amount": 520, "from_currency": "EUR", "to_currency": "CHF"}},
     "answer": {"supported": False, "unsupported_arguments": ["amount"]}},
]


def _fmt_call(call: dict) -> str:
    return f"{call['name']}({json.dumps(dict(call['arguments']), ensure_ascii=False)})"


def render_user(conversation: str, call) -> str:
    """`call` is one {name, arguments} dict or a list of them (several calls planned together)."""
    calls = call if isinstance(call, list) else [call]
    label = "Planned tool call" if len(calls) == 1 else "Planned tool calls (all must be supported)"
    return f"Conversation:\n{conversation}\n\n{label}:\n" + "\n".join(_fmt_call(c) for c in calls)


def build_messages(variant: int, conversation: str, call: dict):
    msgs = [{"role": "system", "content": TASK_PARAPHRASES[variant]}]
    for ex in FEW_SHOT:
        msgs.append({"role": "user", "content": render_user(ex["conversation"], ex["call"])})
        msgs.append({"role": "assistant", "content": json.dumps(ex["answer"])})
    msgs.append({"role": "user", "content": render_user(conversation, call)})
    return msgs


PROMPT_HASH = hashlib.sha256(json.dumps([TASK_PARAPHRASES, FEW_SHOT], sort_keys=True).encode()).hexdigest()[:16]
