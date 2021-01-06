from typing import Iterator, List, Optional, Sequence, Tuple, TypeVar

_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")


def rzip_longest(
    seq1: Sequence[_T1], seq2: Sequence[_T2]
) -> Iterator[Tuple[_T1, Optional[_T2]]]:
    """Make an iterator over tuples, with elements from the input sequences.

    If the second sequence is shorter than the first by N elements,
    the second element of the first N tuples is set to None.

    >>> list(rzip_longest([1,2,3], ["a", "b"]))
    [(1, None), (2, "a"), (3, "b")]
    """

    len_diff = len(seq1) - len(seq2)
    if len_diff < 0:
        raise ValueError("seq2 can't be longer than seq1")
    padded_seq2: List[Optional[_T2]] = [None] * len_diff
    padded_seq2.extend(seq2)
    return zip(seq1, padded_seq2)
