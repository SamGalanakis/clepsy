# typable_password.py
from __future__ import annotations

from math import log2
import secrets
from typing import List, Sequence, Tuple


# Avoid visually ambiguous / awkward chars for typability
_AMBIG: set[str] = set("Il1O0|`'\"/\\,;:()[]{}<>")

# Short, easy words (3–5 letters). Extend as needed.
_SMALL_WORDS: Tuple[str, ...] = (
    "able",
    "acid",
    "acid",
    "arch",
    "area",
    "aqua",
    "apex",
    "axis",
    "bake",
    "band",
    "bank",
    "base",
    "beam",
    "bell",
    "best",
    "beta",
    "blue",
    "blink",
    "bold",
    "born",
    "brim",
    "brave",
    "bulk",
    "calm",
    "camp",
    "acid",
    "arch",
    "area",
    "aqua",
    "apex",
    "axis",
    "bake",
    "band",
    "bank",
    "base",
    "beam",
    "bell",
    "best",
    "beta",
    "blue",
    "blink",
    "bold",
    "born",
    "brim",
    "brave",
    "bulk",
    "calm",
    "camp",
    "arch",
    "area",
    "aqua",
    "apex",
    "axis",
    "bake",
    "band",
    "bank",
    "base",
    "beam",
    "bell",
    "best",
    "beta",
    "blue",
    "blink",
    "bold",
    "born",
    "brim",
    "brave",
    "bulk",
    "calm",
    "camp",
    "care",
    "cast",
    "chop",
    "city",
    "clay",
    "clip",
    "climb",
    "cool",
    "core",
    "craft",
    "crew",
    "crop",
    "cube",
    "dawn",
    "deal",
    "deep",
    "dock",
    "down",
    "draw",
    "drum",
    "dusk",
    "east",
    "easy",
    "edge",
    "epic",
    "even",
    "fair",
    "fast",
    "feed",
    "fine",
    "firm",
    "fish",
    "flat",
    "flow",
    "fold",
    "form",
    "free",
    "from",
    "gain",
    "gate",
    "gear",
    "gent",
    "glad",
    "glow",
    "gold",
    "good",
    "grid",
    "grow",
    "gust",
    "half",
    "hand",
    "hard",
    "harm",
    "hawk",
    "hear",
    "help",
    "hike",
    "hill",
    "hold",
    "home",
    "hood",
    "hope",
    "host",
    "hush",
    "idea",
    "idle",
    "inch",
    "iron",
    "item",
    "jazz",
    "join",
    "jump",
    "just",
    "keen",
    "keep",
    "kelp",
    "kind",
    "king",
    "kite",
    "lake",
    "lamp",
    "land",
    "lane",
    "last",
    "leaf",
    "left",
    "lift",
    "line",
    "link",
    "list",
    "live",
    "loft",
    "long",
    "look",
    "luck",
    "made",
    "main",
    "make",
    "mark",
    "mass",
    "meal",
    "mild",
    "mint",
    "mist",
    "muse",
    "mono",
    "near",
    "nest",
    "next",
    "noble",
    "note",
    "open",
    "pack",
    "pair",
    "path",
    "peak",
    "peer",
    "perk",
    "palm",
    "park",
    "pass",
    "past",
    "pine",
    "plan",
    "play",
    "plot",
    "plum",
    "plus",
    "pure",
    "push",
    "quad",
    "quick",
    "quiet",
    "rain",
    "rank",
    "real",
    "reed",
    "rest",
    "ring",
    "road",
    "rock",
    "root",
    "rose",
    "rule",
    "rush",
    "sage",
    "salt",
    "sand",
    "seat",
    "seed",
    "send",
    "ship",
    "shop",
    "shot",
    "show",
    "side",
    "sign",
    "silk",
    "sing",
    "site",
    "size",
    "slim",
    "slow",
    "soft",
    "soil",
    "solo",
    "soar",
    "song",
    "soul",
    "spin",
    "star",
    "stay",
    "step",
    "stone",
    "straw",
    "suit",
    "sure",
    "swim",
    "tale",
    "tall",
    "task",
    "team",
    "tell",
    "tide",
    "time",
    "town",
    "tree",
    "trail",
    "true",
    "tune",
    "turn",
    "twin",
    "unit",
    "vale",
    "vast",
    "verb",
    "view",
    "vine",
    "warm",
    "wave",
    "weak",
    "west",
    "whim",
    "wide",
    "wild",
    "wind",
    "wing",
    "wise",
    "wood",
    "yard",
    "year",
    "yarn",
    "yell",
    "young",
    "zeal",
    "zest",
    "zone",
)

# Pronounceable pseudo-word parts
_ONSETS: Tuple[str, ...] = (
    "b",
    "c",
    "d",
    "f",
    "g",
    "h",
    "j",
    "k",
    "l",
    "m",
    "n",
    "p",
    "r",
    "s",
    "t",
    "v",
    "w",
    "y",
    "z",
    "br",
    "cr",
    "dr",
    "fr",
    "gr",
    "pr",
    "tr",
    "st",
    "sp",
    "sk",
    "pl",
    "gl",
    "cl",
    "sl",
    "sn",
    "sm",
    "sw",
)
_VOWELS: Tuple[str, ...] = ("a", "e", "i", "o", "u")
_CODAS: Tuple[str, ...] = ("", "n", "m", "r", "l", "s", "t")


def _rand_choice(seq: Sequence[str]) -> str:
    return seq[secrets.randbelow(len(seq))]


def _rand_digit() -> str:
    # Exclude 0/1 to avoid confusion with O/l
    digit_pool = "23456789"
    return digit_pool[secrets.randbelow(len(digit_pool))]


def _make_pseudoword(min_len: int = 3, max_len: int = 5) -> str:
    # Try structured onset+vowel+coda a few times, then fallback to simple CVC
    for _ in range(32):
        w = _rand_choice(_ONSETS) + _rand_choice(_VOWELS) + _rand_choice(_CODAS)
        if min_len <= len(w) <= max_len:
            return w
    consonants = "bcdfghjklmnpqrstvwxyz"
    return (
        _rand_choice(tuple(consonants))
        + _rand_choice(_VOWELS)
        + _rand_choice(tuple(consonants))
    )


def _entropy_words_pool_size() -> int:
    pseudo_space = len(_ONSETS) * len(_VOWELS) * len(_CODAS)  # upper bound
    return len(_SMALL_WORDS) + pseudo_space


def _filter_ambiguous(s: str) -> str:
    return "".join(c for c in s if c not in _AMBIG)


def _gen_segment(use_real_words: bool, allow_pseudowords: bool) -> str:
    # ~70% real word if available; otherwise pseudo
    if (
        use_real_words
        and _SMALL_WORDS
        and (not allow_pseudowords or secrets.randbelow(10) < 7)
    ):
        return _rand_choice(_SMALL_WORDS)
    return _make_pseudoword()


def generate_typable_password(
    min_entropy_bits: float = 64.0,
    *,
    lowercase_only: bool = True,  # per request
    min_segments: int = 4,  # bumped for lowercase-only
    max_segments: int = 6,
    digit_range: Tuple[int, int] = (3, 5),  # bumped for lowercase-only
    separators: str = "-_",
    enforce_classes: bool = True,
    allow_pseudowords: bool = True,
    use_real_words: bool = True,
) -> str:
    """
    Generate a human-typable password composed of short words (real/pseudo),
    separators, and digits, meeting or exceeding `min_entropy_bits`.

    - Uses `secrets` for all randomness.
    - Avoids ambiguous characters.
    - If `lowercase_only` is True (default), segments are forced to lowercase and
      entropy is compensated by default via more segments/digits.
    """
    # Prepare separators (filtered)
    sep_filtered: str = _filter_ambiguous(separators) or "-"
    segment_bits: float = log2(_entropy_words_pool_size())
    sep_bits: float = log2(len(sep_filtered))
    digit_bits: float = log2(8)  # using digits 2-9 only

    def estimate(seg_count: int, digit_count: int) -> float:
        return (
            seg_count * segment_bits
            + (seg_count - 1) * sep_bits
            + digit_count * digit_bits
        )

    # Determine baseline counts that satisfy the entropy constraint
    seg_baseline = max(min_segments, 1)
    digit_min, digit_max = digit_range
    digit_min = max(digit_min, 1)
    digit_baseline = digit_min

    while estimate(seg_baseline, digit_baseline) < min_entropy_bits:
        if seg_baseline < max_segments:
            seg_baseline += 1
            continue
        digit_baseline += 1

    seg_upper = max(seg_baseline, max_segments)
    digit_upper = max(digit_baseline, digit_max)

    # Build until entropy target is reached
    while True:
        if seg_baseline == seg_upper:
            seg_count = seg_baseline
        else:
            seg_count = seg_baseline + secrets.randbelow(seg_upper - seg_baseline + 1)

        segments: List[str] = [
            _gen_segment(
                use_real_words=use_real_words, allow_pseudowords=allow_pseudowords
            )
            for _ in range(seg_count)
        ]
        if lowercase_only:
            segments = [s.lower() for s in segments]

        separators_chosen: List[str] = [
            _rand_choice(tuple(sep_filtered)) for _ in range(max(0, seg_count - 1))
        ]

        if digit_baseline == digit_upper:
            nd = digit_baseline
        else:
            nd = digit_baseline + secrets.randbelow(digit_upper - digit_baseline + 1)
        digits: str = "".join(_rand_digit() for _ in range(nd))

        # Assemble (seg1 + sep + seg2 + sep + ... + segN) + digits
        parts: List[str] = []
        for i, seg in enumerate(segments):
            parts.append(_filter_ambiguous(seg))
            if i < len(separators_chosen):
                parts.append(separators_chosen[i])
        parts.append(digits)
        pwd: str = "".join(parts)

        if enforce_classes:
            if not any(ch.islower() for ch in pwd):
                continue
            if not any(ch.isdigit() for ch in pwd):
                continue

        est_bits: float = estimate(seg_count, nd)
        if est_bits >= min_entropy_bits:
            return pwd
