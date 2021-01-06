from stub_extractor.util import rzip_longest


class TestRZipLongest:
    def test_both_empty(self) -> None:
        assert list(rzip_longest([], [])) == []

    def test_same_length(self) -> None:
        assert list(rzip_longest([1, 2, 3], ["a", "b", "c"])) == [
            (1, "a"),
            (2, "b"),
            (3, "c"),
        ]

    def test_second_shorter(self) -> None:
        assert list(rzip_longest([1, 2, 3], ["a", "b"])) == [
            (1, None),
            (2, "a"),
            (3, "b"),
        ]
