import numpy as np
import pandas as pd

import warnings

from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from cfpbsignals.text import STOP_WORDS, clean, template_key, topic_weights


def test_clean_removes_redactions_amounts_and_brands():
    raw = "On XX/XX/2023 Wells Fargo charged me {$1,250.00} via Cash App. XXXX XXXX said NO!"
    assert clean(raw) == "on charged me via said no"


def test_clean_handles_missing():
    assert clean(None) == ""
    assert clean(float("nan")) == ""


def test_template_key_matches_copy_paste_openings():
    a = clean("15 USC 1681 SECTION 602 STATES I HAVE THE RIGHT TO PRIVACY. My account XXXX")
    b = clean("15 USC 1681 section 602 states I have the right to privacy. Other text")
    assert template_key(a, 40) == template_key(b, 40)


def test_topics_separate_obvious_themes():
    fraud = ["identity theft fraudulent account opened without my knowledge police report"] * 40
    fees = ["late fee charged on my payment even though payment was on time statement balance"] * 40
    docs = pd.Series(fraud + fees)
    vec = TfidfVectorizer(stop_words=STOP_WORDS)  # default thresholds for the tiny synthetic corpus
    X = vec.fit_transform(docs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # perfect fit on duplicated docs triggers a harmless sqrt warning
        nmf = NMF(n_components=2, init="nndsvda", random_state=0, max_iter=400).fit(X)
    W = topic_weights(vec, nmf, docs)
    assert np.allclose(W.sum(axis=1), 1.0)
    assert W[:40].argmax(axis=1).tolist().count(W[0].argmax()) == 40
    assert W[0].argmax() != W[-1].argmax()
