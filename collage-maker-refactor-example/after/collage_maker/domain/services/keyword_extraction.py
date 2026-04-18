"""
KeywordExtractor — Enhanced Domain Service with modern NLP

Extracts and ranks the most significant keywords from a body of plain text
using modern techniques and configurable quality filters.

This enhanced version includes better preprocessing, quality scoring,
and semantic filtering for improved keyword selection.
"""

from __future__ import annotations

import re
from string import punctuation
from logging import getLogger

from nltk import FreqDist
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

from collage_maker.domain.model.keyword import Keyword


# Characters stripped from token edges before a word is considered clean.
_STRIP_CHARS = "-/',.1234567890~@#$%^&*()+=[]{}|\\:;\"<>?"

# Common web artifacts that often appear in scraped text
_WEB_ARTIFACTS = {
    "http",
    "https",
    "www",
    "com",
    "org",
    "net",
    "html",
    "htm",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "pdf",
    "doc",
    "docx",
    "click",
    "here",
    "more",
    "link",
    "url",
    "email",
    "mailto",
    "javascript",
    "css",
    "style",
    "script",
    "div",
    "span",
}

# Domain-specific patterns that often indicate low-quality keywords
_NOISE_PATTERNS = [
    r"^\d+$",  # Pure numbers
    r"^[a-z]$",  # Single letters
    r".*\d{4,}.*",  # Contains 4+ consecutive digits (years, IDs, etc.)
    r"^(chapter|section|page|line|paragraph|figure|table)\d*$",
    r"^[a-z]{1,2}\d+$",  # Short letter+number combinations
]

logger = getLogger(__name__)


class KeywordExtractor:
    """
    Enhanced keyword extractor with quality scoring and semantic filtering.
    """

    def __init__(
        self,
        n_keywords: int = 25,
        extra_stopwords: list[str] | None = None,
        min_word_length: int = 3,
        max_word_length: int = 25,
        min_frequency: int = 2,
        quality_threshold: float = 0.4,
        enable_lemmatization: bool = True,
    ) -> None:
        self._n_keywords = n_keywords
        self._extra_stopwords: list[str] = extra_stopwords or []
        self._min_word_length = min_word_length
        self._max_word_length = max_word_length
        self._min_frequency = min_frequency
        self._quality_threshold = quality_threshold
        self._enable_lemmatization = enable_lemmatization

        # Initialize NLTK components with error handling
        if self._enable_lemmatization:
            try:
                self._lemmatizer = WordNetLemmatizer()
            except Exception as e:
                logger.warning(f"Failed to initialize lemmatizer, disabling: {e}")
                self._enable_lemmatization = False

        # Compile noise patterns for efficiency
        try:
            self._noise_patterns = [
                re.compile(pattern, re.IGNORECASE) for pattern in _NOISE_PATTERNS
            ]
        except Exception as e:
            logger.error(f"Failed to compile noise patterns: {e}")
            self._noise_patterns = []

        logger.info("Keyword extractor initialized successfully")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, text: str) -> list[Keyword]:
        """
        Extract and rank keywords with enhanced quality filtering.

        Returns the top *n_keywords* Keywords ranked by a composite score
        that considers frequency, length, and semantic quality.
        """
        logger.info("Beginning keyword extraction...")

        if not text or len(text.strip()) < 50:
            logger.warning(
                "Source file is empty or does not have substantial enough text for processing"
            )
            return []

        try:
            # Enhanced preprocessing pipeline
            tokens = self._preprocess_text(text)
            logger.info(f"Extracted {len(tokens)} valid tokens from text")

            if not tokens:
                logger.warning("No valid tokens found after preprocessing")
                return []

            # Frequency analysis with quality scoring
            freq_dist = FreqDist(tokens)
            keyword_candidates = self._score_candidates(freq_dist)

            # Filter and rank by composite score
            high_quality_keywords = [
                kw
                for kw in keyword_candidates
                if kw.is_high_quality() and kw.confidence >= self._quality_threshold
            ]

            # Sort by composite score (frequency * confidence)
            ranked_keywords = sorted(
                high_quality_keywords,
                key=lambda kw: (kw.frequency * kw.confidence, len(kw.text)),
                reverse=True,
            )

            logger.info(f"Found {len(ranked_keywords)} high-quality keywords")

            if ranked_keywords:
                top_5 = [f"{kw.text}({kw.frequency})" for kw in ranked_keywords[:5]]
                logger.info(f"Top 5 keywords: {top_5}")

            return ranked_keywords[: self._n_keywords]

        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            return []

    def extract_with_categories(self, text: str) -> dict[str, list[Keyword]]:
        """
        Extract keywords organized by semantic categories.

        Returns:
            Dict mapping category names to keyword lists
        """
        keywords = self.extract(text)
        categories = {
            "entities": [],  # Proper nouns, names, places
            "concepts": [],  # Abstract concepts, ideas
            "objects": [],  # Concrete objects, things
            "actions": [],  # Verbs, processes
            "qualities": [],  # Adjectives, properties
        }

        for keyword in keywords:
            category = self._classify_keyword(keyword.text)
            categories[category].append(keyword)

        return categories

    # ------------------------------------------------------------------
    # Enhanced preprocessing pipeline
    # ------------------------------------------------------------------

    def _preprocess_text(self, text: str) -> list[str]:
        """Enhanced text preprocessing with multiple cleaning stages."""
        try:
            # Stage 1: Basic cleaning
            logger.debug(f"Incoming text length: {len(text)}")
            text = self._clean_text(text)

            # Stage 2: Tokenization
            tokens = word_tokenize(text.lower())
            logger.debug(f"Initial tokens: {len(tokens)}")

            # Stage 3: Advanced filtering
            filtered_tokens = []
            stopword_set = self._get_stopwords()

            for token in tokens:
                try:
                    cleaned_token = self._clean_token(token)
                    if self._is_valid_token(cleaned_token, stopword_set):
                        if self._enable_lemmatization and self._lemmatizer:
                            cleaned_token = self._lemmatizer.lemmatize(cleaned_token)
                        filtered_tokens.append(cleaned_token)
                except Exception as e:
                    logger.debug(f"Error processing token '{token}': {e}")
                    continue

            logger.debug(f"Filtered tokens: {len(filtered_tokens)}")
            return filtered_tokens

        except Exception as e:
            logger.error(f"Text preprocessing failed: {e}")
            return []

    def _clean_text(self, text: str) -> str:
        """Clean text of common artifacts and formatting issues."""
        try:
            # Remove URLs and email addresses
            text = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", " ", text)

            # Remove HTML-like tags
            text = re.sub(r"<[^>]+>", " ", text)

            # Normalize whitespace
            text = re.sub(r"\s+", " ", text)

            # Remove very long "words" (likely corrupted data)
            words = text.split()
            filtered_words = [w for w in words if len(w) <= 50]

            return " ".join(filtered_words)

        except Exception as e:
            logger.warning(f"Text cleaning failed, using original: {e}")
            return text

    def _clean_token(self, token: str) -> str:
        """Clean individual tokens."""
        try:
            # Strip problematic characters from edges
            cleaned = token.strip(_STRIP_CHARS)

            # Handle contractions and hyphenated words
            if "'" in cleaned and len(cleaned) > 3:
                # Keep meaningful contractions like "don't" -> "dont"
                cleaned = cleaned.replace("'", "")

            return cleaned
        except Exception:
            return token

    def _is_valid_token(self, token: str, stopwords_set: set[str]) -> bool:
        """Enhanced token validation with multiple criteria."""
        try:
            if not token or len(token) < self._min_word_length:
                return False

            if len(token) > self._max_word_length:
                return False

            if token in stopwords_set:
                return False

            if token in _WEB_ARTIFACTS:
                return False

            # Check against noise patterns
            if any(pattern.match(token) for pattern in self._noise_patterns):
                return False

            # Must contain at least some letters
            if not any(c.isalpha() for c in token):
                return False

            # Reject if mostly punctuation
            alpha_ratio = sum(c.isalpha() for c in token) / len(token)
            if alpha_ratio < 0.5:
                return False

            return True

        except Exception:
            return False

    def _get_stopwords(self) -> set[str]:
        """Get comprehensive stopword set with error handling."""
        try:
            base_stopwords = set(stopwords.words("english"))
        except Exception as e:
            logger.warning(f"Failed to load NLTK stopwords, using minimal set: {e}")
            base_stopwords = {
                "a",
                "an",
                "and",
                "are",
                "as",
                "at",
                "be",
                "by",
                "for",
                "from",
                "has",
                "he",
                "in",
                "is",
                "it",
                "its",
                "of",
                "on",
                "that",
                "the",
                "to",
                "was",
                "will",
                "with",
            }

        punctuation_set = set(punctuation)
        extra_stopwords = set(self._extra_stopwords)

        return base_stopwords | punctuation_set | extra_stopwords

    # ------------------------------------------------------------------
    # Quality scoring and classification
    # ------------------------------------------------------------------

    def _score_candidates(self, freq_dist: FreqDist) -> list[Keyword]:
        """Score keyword candidates based on multiple factors."""
        candidates = []

        for word, frequency in freq_dist.items():
            if frequency >= self._min_frequency:
                try:
                    confidence = self._calculate_confidence_score(
                        word, frequency, freq_dist
                    )
                    keyword = Keyword(
                        text=word, frequency=frequency, confidence=confidence
                    )
                    candidates.append(keyword)
                except Exception as e:
                    logger.debug(f"Failed to score candidate '{word}': {e}")
                    continue

        return candidates

    def _calculate_confidence_score(
        self, word: str, frequency: int, freq_dist: FreqDist
    ) -> float:
        """
        Calculate confidence score for a keyword candidate.

        Factors considered:
        - Frequency (higher is better, but with diminishing returns)
        - Word length (moderate length preferred)
        - Letter/digit ratio (more letters is better)
        - Relative frequency compared to most common words
        """
        try:
            # Base frequency score with diminishing returns
            max_freq = max(freq_dist.values()) if freq_dist.values() else 1
            freq_score = min(frequency / max_freq, 1.0)

            # Length score - prefer moderate length words
            length_score = self._calculate_length_score(word)

            # Character composition score
            char_score = self._calculate_character_score(word)

            # Relative frequency score
            total_words = sum(freq_dist.values())
            relative_score = frequency / total_words if total_words > 0 else 0

            # Weighted combination
            confidence = (
                freq_score * 0.4
                + length_score * 0.2
                + char_score * 0.2
                + relative_score * 0.2
            )

            return min(1.0, max(0.0, confidence))

        except Exception as e:
            logger.debug(f"Confidence scoring failed for '{word}': {e}")
            return 0.5  # Default moderate confidence

    def _calculate_length_score(self, word: str) -> float:
        """Score based on word length - prefer moderate lengths."""
        length = len(word)
        if 4 <= length <= 8:
            return 1.0
        elif 3 <= length <= 12:
            return 0.8
        elif length >= 2:
            return 0.6
        else:
            return 0.2

    def _calculate_character_score(self, word: str) -> float:
        """Score based on character composition."""
        if not word:
            return 0.0

        alpha_count = sum(c.isalpha() for c in word)
        alpha_ratio = alpha_count / len(word)

        # Prefer words that are mostly alphabetic
        if alpha_ratio >= 0.9:
            return 1.0
        elif alpha_ratio >= 0.7:
            return 0.8
        elif alpha_ratio >= 0.5:
            return 0.6
        else:
            return 0.3

    def _classify_keyword(self, word: str) -> str:
        """
        Classify keywords into semantic categories using simple heuristics.
        In a production system, this could use more sophisticated NLP models.
        """
        # Simple classification based on word patterns and endings
        word_lower = word.lower()

        # Proper nouns (entities) - would be better with NER
        if word.istitle():
            return "entities"

        # Action words (simplified - would benefit from POS tagging)
        action_endings = ("ing", "tion", "sion", "ment", "ance", "ence")
        if any(word_lower.endswith(suffix) for suffix in action_endings):
            return "actions"

        # Quality/property words
        quality_endings = ("ful", "less", "ous", "ive", "able", "ible")
        if any(word_lower.endswith(suffix) for suffix in quality_endings):
            return "qualities"

        # Abstract concepts
        concept_endings = ("ism", "ity", "ness", "ship", "hood")
        if any(word_lower.endswith(suffix) for suffix in concept_endings):
            return "concepts"

        # Default to objects/things
        return "objects"
