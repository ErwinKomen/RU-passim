import random
import math
import itertools

# ==========================================================================================
#
# These routines come from: https://stackoverflow.com/questions/49606404
#
# ==========================================================================================

# this only works for Iterable[Iterable]
def is_latin_rectangle(rows):
    valid = True
    for row in rows:
        if len(set(row)) < len(row):
            valid = False
    if valid and rows:
        for i, val in enumerate(rows[0]):
            col = [row[i] for row in rows]
            if len(set(col)) < len(col):
                valid = False
                break
    return valid


def is_latin_square(rows):
    return is_latin_rectangle(rows) and len(rows) == len(rows[0])


def latin_square1(items, shuffle=True):
    result = []
    for elems in itertools.permutations(items):
        valid = True
        for i, elem in enumerate(elems):
            orthogonals = [x[i] for x in result] + [elem]
            if len(set(orthogonals)) < len(orthogonals):
                valid = False
                break
        if valid:
            result.append(elems)
    if shuffle:
        random.shuffle(result)
    return result


def latin_square2(items, shuffle=True, forward=False):
    sign = -1 if forward else 1
    result = [items[sign * i:] + items[:sign * i] for i in range(len(items))]
    if shuffle:
        random.shuffle(result)
    return result


def latin_square3(items):
    result = [list(items)]
    while len(result) < len(items):
        new_row = list(items)
        random.shuffle(new_row)
        result.append(new_row)
        if not is_latin_rectangle(result):
            result = result[:-1]
    return result
