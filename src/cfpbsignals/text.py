"""Narrative cleaning, TF-IDF features, and NMF topic modeling."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

# CFPB scrubs personal data: names/dates/account numbers become "XXXX", amounts become "{$1,234.00}".
_REDACT = re.compile(r"\bx{2,}\b|\bx+/x+/\S*", re.I)
_AMOUNT = re.compile(r"\{\$[\d,\.]+\}")
_URL = re.compile(r"https?://\S+|www\.\S+")
_NONALPHA = re.compile(r"[^a-z\s]")
_WS = re.compile(r"\s+")
# Brand / product names are removed so topics describe the PROBLEM, not the company
# (otherwise NMF learns one "topic" per issuer and topic-by-company comparisons become circular).
_BRANDS = re.compile(
    r"\b(cash\s?app|cashapp|paypal|venmo|jp\s?morgan|chase|wells\s?fargo|wells|fargo|bank\s+of\s+america|"
    r"boa|bofa|citi\w*|capital\s?one|synchrony|syncb|amex|american\s+express|ally(\s+bank|\s+financial)?|"
    r"block\s+inc|square\s+inc)\b", re.I)

# Words that appear in nearly every complaint and carry no topic information.
DOMAIN_STOP = {
    "told", "said", "called", "call", "calls", "asked", "time", "times", "day", "days", "did", "just",
    "like", "know", "want", "going", "got", "get", "make", "made", "need", "dont", "didnt", "im", "ive",
    "wa", "isnt", "wasnt", "cant", "able", "also", "would", "could", "still", "please", "help", "back",
    "contacted", "contact", "stated", "advised", "received", "informed", "regarding", "since", "even",
    "company", "phone", "number", "date", "dollar", "dollars", "amount", "one", "two", "ago",
}
STOP_WORDS = sorted(ENGLISH_STOP_WORDS | DOMAIN_STOP)


def clean(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = _URL.sub(" ", t)
    t = _BRANDS.sub(" ", t)
    t = _AMOUNT.sub(" ", t)
    t = _REDACT.sub(" ", t)
    t = _NONALPHA.sub(" ", t)
    return _WS.sub(" ", t).strip()


def fit_topics(docs: pd.Series, n_topics: int, seed: int, n_top: int = 12):
    vec = TfidfVectorizer(stop_words=STOP_WORDS, min_df=25, max_df=0.4, ngram_range=(1, 2),
                          max_features=30_000, sublinear_tf=True, dtype=np.float32)
    X = vec.fit_transform(docs)
    nmf = NMF(n_components=n_topics, init="nndsvda", random_state=seed, max_iter=400)
    nmf.fit(X)
    terms = np.array(vec.get_feature_names_out())
    top = [list(terms[np.argsort(row)[::-1][:n_top]]) for row in nmf.components_]
    return vec, nmf, top


def topic_weights(vec, nmf, docs: pd.Series, batch: int = 50_000) -> np.ndarray:
    """Row-normalised topic mixture for every document (rows with no signal stay all-zero)."""
    out = []
    for i in range(0, len(docs), batch):
        W = nmf.transform(vec.transform(docs.iloc[i:i + batch]))
        s = W.sum(axis=1, keepdims=True)
        out.append(np.divide(W, s, out=np.zeros_like(W), where=s > 0))
    return np.vstack(out)


def template_key(cleaned: str, n_chars: int = 120) -> str:
    """Opening characters of a cleaned narrative; identical openings flag copy-paste campaigns."""
    return cleaned[:n_chars]
