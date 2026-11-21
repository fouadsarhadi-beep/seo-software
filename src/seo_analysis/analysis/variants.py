"""Persian spelling-variant candidates. The tool only SUGGESTS; you approve each one.
Example: «نرمافزار» (joined) vs «نرم افزار» / «نرم‌افزار» (split); «میشود» vs «می‌شود»."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def find_candidates(token_lists, min_split: int = 2, min_len: int = 4):
    uni, bi = Counter(), Counter()
    for toks in token_lists:
        uni.update(toks)
        bi.update(zip(toks, toks[1:]))
    out = []
    for (a, b), c in bi.items():
        joined = a + b
        if c >= min_split and len(joined) >= min_len and len(b) >= 2 and joined in uni:
            out.append({"joined": joined, "split": f"{a} {b}", "joined_count": uni[joined], "split_count": c})
    out.sort(key=lambda x: -(x["joined_count"] + x["split_count"]))
    return out


def review(cands, path, input_fn=input, output_fn=print):
    """Ask the user to approve each candidate. Saves {joined: split} to `path`."""
    path = Path(path)
    approved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    yes_all = False
    for k, c in enumerate(cands, 1):
        if c["joined"] in approved:
            continue
        if not yes_all:
            output_fn(f"\n[{k}/{len(cands)}] '{c['joined']}' ({c['joined_count']}x) vs '{c['split']}' ({c['split_count']}x)")
            ans = input_fn("  Treat as the same word? [y]es / [n]o / [a]ll remaining yes / [q]uit: ").strip().lower()
            if ans == "q":
                break
            if ans == "a":
                yes_all = True
            elif ans != "y":
                continue
        approved[c["joined"]] = c["split"]
    path.write_text(json.dumps(approved, ensure_ascii=False, indent=2), encoding="utf-8")
    return approved
