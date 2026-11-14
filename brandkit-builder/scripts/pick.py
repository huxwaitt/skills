"""Pick a random asset brief from a brand kit, so "make me a random <brand> asset" is
actually random and reproducible.

    python pick.py brandkits/google [--seed 7]

Reads <kit>/regen.json if present: {"subjects": [...], "formats": [...], "compositions": [...]}.
Anything missing falls back to the defaults below. Prints one JSON brief.
"""
import argparse
import json
import os
import random

FORMATS = [
    {"name": "marketing landing page", "size": "1440xfull"},
    {"name": "product feature page", "size": "1440xfull"},
    {"name": "social share card", "size": "1200x630"},
    {"name": "blog key art", "size": "1300x731"},
    {"name": "keynote title slide", "size": "1920x1080"},
    {"name": "event poster", "size": "1080x1350"},
    {"name": "vertical story", "size": "1080x1920"},
    {"name": "display banner (medium rectangle)", "size": "300x250"},
    {"name": "leaderboard banner", "size": "728x90"},
]
COMPOSITIONS = [
    "centered lockup on a quiet field",
    "text left, hero visual right",
    "typographic only, one big statement",
    "product name lockup over abstract key art",
    "single data callout (one number, one line)",
    "two-up comparison with captions",
]
# Never picked, whatever regen.json says: these function as phishing or forgery.
FORBIDDEN = ("sign-in", "login", "password", "payment", "checkout", "invoice", "receipt",
             "security alert", "account", "verification", "2fa", "billing")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kit")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--kind", choices=["page", "graphic"], help="restrict to web pages or to fixed-size graphics")
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(1 << 30)
    rng = random.Random(seed)
    cfg_path = os.path.join(a.kit, "regen.json")
    cfg = json.load(open(cfg_path, encoding="utf-8")) if os.path.exists(cfg_path) else {}
    formats = [f for f in cfg.get("formats", FORMATS) if not any(x in f["name"].lower() for x in FORBIDDEN)]
    if a.kind:
        formats = [f for f in formats if f["size"].endswith("full") == (a.kind == "page")]
    subjects = [s for s in cfg.get("subjects", ["a product announcement"]) if not any(x in s.lower() for x in FORBIDDEN)]
    brief = {"seed": seed, "format": rng.choice(formats), "composition": rng.choice(cfg.get("compositions", COMPOSITIONS)),
             "subject": rng.choice(subjects), "scheme": rng.choice(cfg.get("schemes", ["light", "dark"])),
             "sample_to_match": None}
    samples_dir = os.path.join(a.kit, "assets", "samples")
    if os.path.isdir(samples_dir):
        files = sorted(os.listdir(samples_dir))
        if files:
            brief["sample_to_match"] = os.path.join("assets", "samples", rng.choice(files)).replace("\\", "/")
    print(json.dumps(brief, indent=1))


if __name__ == "__main__":
    main()
