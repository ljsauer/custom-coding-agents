"""
KeywordExtractor — Domain Service

Extracts and ranks the most significant keywords from a body of plain text.
This is a stateless service: it holds configuration, accepts text, and
returns a ranked list of Keyword value objects.

Classification: Domain Service
  - Encapsulates domain logic (what makes a word "significant") that spans
    no persistent entities and requires no I/O.
  - Depends only on the domain model (Keyword) and the standard library /
    NLTK. NLTK is a pure computation library with no I/O side effects here.
  - Has no knowledge of Flask, databases, filesystems, or HTTP.

Replaces: app/NLP/important_words.py  (ImportantWords)
Renamed because "ImportantWords" is vague. "KeywordExtractor" names the
intent — extracting keywords — not the data it happens to hold.
"""

from __future__ import annotations

from string import punctuation

from nltk import FreqDist
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from collage_maker.domain.model.keyword import Keyword

# Characters stripped from token edges before a word is considered clean.
_STRIP_CHARS = "-/',.1234567890~"


class KeywordExtractor:
    """
    Extracts the top *n_keywords* most frequent meaningful words from text,
    filtering out English stopwords, punctuation, and a caller-supplied list
    of domain-specific noise words.
    """

    def __init__(
        self,
        n_keywords: int = 25,
        extra_stopwords: list[str] | None = None,
    ) -> None:
        self._n_keywords = n_keywords
        self._extra_stopwords: list[str] = extra_stopwords or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, text: str) -> list[Keyword]:
        """
        Return the top *n_keywords* Keywords ranked by frequency, most
        frequent first.
        """
        tokens = self._clean(text)
        freq_dist = FreqDist(tokens)
        ranked = sorted(freq_dist.items(), key=lambda pair: pair[1], reverse=True)

        keywords: list[Keyword] = []
        for word, _ in ranked:
            keywords.append(Keyword(word))
            if len(keywords) >= self._n_keywords:
                break

        return keywords

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clean(self, text: str) -> list[str]:
        tokens = word_tokenize(text.lower())
        noise = (
            set(stopwords.words("english"))
            | set(punctuation)
            | set(self._extra_stopwords)
        )
        return [
            token.strip(_STRIP_CHARS)
            for token in tokens
            if token not in noise and len(token) > 3
        ]
