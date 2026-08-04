"""
Text normalization and fuzzy-similarity helpers for entity resolution.

These mirror the helper functions from the course ER demo (normalize_text,
token_set, overlap_count, text_similarity) so our product crosswalk uses the
same techniques taught in class, plus attribute signals layered on top in
src/crosswalk.py.
"""

import re

import pandas as pd
from fuzzywuzzy import fuzz


def normalize_text(value):
    """Lowercase, strip, replace non-alphanumerics with spaces, collapse spaces.
    'SummitRunner Jacket 200' -> 'summitrunner jacket 200'. NaN -> ''."""
    if pd.isna(value):
        return ""
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def token_set(value):
    """Split a normalized string into a set of word tokens."""
    return set(value.split())


def overlap_count(left, right):
    """Number of shared tokens between two strings."""
    return len(token_set(left) & token_set(right))


def text_similarity(left, right, method="token_set_ratio"):
    """Similarity in [0, 1] between two strings via fuzzy matching.

    method: 'token_set_ratio' (default, order/duplicate-insensitive),
            'partial_ratio', 'edit_distance' (fuzz.ratio),
            'exact_token_overlap'.
    """
    if method == "edit_distance":
        return fuzz.ratio(left, right) / 100
    if method == "partial_ratio":
        return fuzz.partial_ratio(left, right) / 100
    if method == "exact_token_overlap":
        denom = max(len(token_set(left)), len(token_set(right))) or 1
        return overlap_count(left, right) / denom
    return fuzz.token_set_ratio(left, right) / 100
