# coding: utf-8
# copied-and-pasted from
# https://www.geeksforgeeks.org/longest-common-substring-dp-29/

from functools import lru_cache
from operator import itemgetter


def longest_common_substring(x: str, y: str) -> (int, int, int):
    """ Note: NOT subsequence! """

    @lru_cache(100)
    def longest_common_prefix(i: int, j: int) -> int:

        if 0 <= i < len(x) and 0 <= j < len(y) and x[i] == y[j]:
            return 1 + longest_common_prefix(i + 1, j + 1)
        else:
            return 0

    def digonal_computation():
        """ Diagonally computing the subproblems to decrease memory dependency """

        # upper right triangle of the 2D array
        for k in range(len(x)):
            yield from ((longest_common_prefix(i, j), i, j) for i, j in zip(range(k, -1, -1), range(len(y) - 1, -1, -1)))

        # lower left triangle of the 2D array
        for k in range(len(y)):
            yield from ((longest_common_prefix(i, j), i, j) for i, j in zip(range(k, -1, -1), range(len(x) - 1, -1, -1)))

    # returning the maximum of all the subproblems
    return max(digonal_computation(), key=itemgetter(0), default=(0, 0, 0))




if __name__ == '__main__':
    x: str = 'aubergine'
    y: str = 'ingmarbergman'

    length, i, j = longest_common_substring(x, y)
    print(f'length: {length}, i: {i}, j: {j}')
    print(f'x substring: {x[i: i + length]}', i)
    print(f'y substring: {y[j: j + length]}', j)
