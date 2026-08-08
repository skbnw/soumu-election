#!/usr/bin/env python3
from soumu_election.municipality import normalize_municipality_name

cases = [
    "札幌市西区（１区）",
    "札幌市西区(1区)",
    "札幌市西区（1区）",
    "札幌市西区第（４区）",
    "南九州市(２区）",
    "越谷市（13区)",
    "さいたま市見沼区(5区)",
    "さいたま市見沼区（５区）",
    "札幌市中央区",
    None,
    "  ",
]
for c in cases:
    print(repr(c), "->", repr(normalize_municipality_name(c)))
