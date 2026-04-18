# tests/unit/domain/test_keyword_extraction.py
#
# Unit tests for KeywordExtractor — the domain service that replaces
# the before/ ImportantWords class.
# Zero I/O. Pure domain logic + NLTK (computation only, no network).


from collage_maker.domain.services.keyword_extraction import KeywordExtractor


class TestKeywordExtractor:
    def test_most_frequent_word_is_first(self):
        text = "peach banana apple pear peach pear peach apple peach banana pear apple"
        extractor = KeywordExtractor(n_keywords=10)
        keywords = extractor.extract(text)
        assert keywords[0].text == "peach"

    def test_returns_at_most_n_keywords(self):
        text = " ".join(["word"] * 5 + ["another"] * 3 + ["third"] * 2)
        extractor = KeywordExtractor(n_keywords=2)
        keywords = extractor.extract(text)
        assert len(keywords) <= 2

    def test_keywords_are_lowercase(self):
        text = "Apple APPLE apple Banana BANANA"
        extractor = KeywordExtractor(n_keywords=5)
        keywords = extractor.extract(text)
        for kw in keywords:
            assert kw.text == kw.text.lower()

    def test_stopwords_are_excluded(self):
        # "the", "and", "with" are English stopwords
        text = "the apple and the banana with the cherry apple apple"
        extractor = KeywordExtractor(n_keywords=10)
        keywords = extractor.extract(text)
        texts = [kw.text for kw in keywords]
        assert "the" not in texts
        assert "and" not in texts
        assert "with" not in texts

    def test_extra_stopwords_are_excluded(self):
        text = "gutenberg project apple apple apple banana"
        extractor = KeywordExtractor(
            n_keywords=10,
            extra_stopwords=["gutenberg", "project"],
        )
        keywords = extractor.extract(text)
        texts = [kw.text for kw in keywords]
        assert "gutenberg" not in texts
        assert "project" not in texts

    def test_short_tokens_are_excluded(self):
        # Tokens of 3 characters or fewer are dropped
        text = "the cat sat on the mat apple banana cherry"
        extractor = KeywordExtractor(n_keywords=10)
        keywords = extractor.extract(text)
        for kw in keywords:
            assert len(kw.text) > 3

    def test_empty_text_returns_empty_list(self):
        extractor = KeywordExtractor()
        assert extractor.extract("") == []

    def test_punctuation_is_stripped(self):
        text = "apple! banana, cherry. apple apple"
        extractor = KeywordExtractor(n_keywords=5)
        keywords = extractor.extract(text)
        for kw in keywords:
            assert "!" not in kw.text
            assert "," not in kw.text
            assert "." not in kw.text
