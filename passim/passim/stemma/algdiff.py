from passim.utils import ErrHandle

#class AlgorithmDiff:
# Default key generator to use in the most common case:
# comparison of two strings
#def default_keyGen(self, value):
#    return value
def default_keyGen(value):
    return value

def _withPositionsOfInInterval(aCollection, start, end, keyGen):
    d = {}
    oErr = ErrHandle()
    try:
        for index in range(start, end+1):
            element = aCollection[index]
            key = keyGen(element)
            if key in d:
                d[key].insert(0, index)
            else:
                d[key] = [index]
    except:
        msg = oErr.get_error_message()
        oErr.DoError("_withPositionsOfInInterval")
    return d

def _replaceNextLargerWith(array, aValue, high=None):
    """
    Find the place at which aValue would normally be inserted into the array. If
    that place is already occupied by aValue, do nothing, and return undef. If
    the place does not exist (i.e., it is off the end of the array), add it to
    the end, otherwise replace the element at that point with aValue.
    It is assumed that the array's values are numeric.
    This is where the bulk (75%) of the time is spent in this module, so try to
    make it fast!
    """

    oErr = ErrHandle()
    low = 0
    try:
        high = high if high is not None else len(array) - 1

        array_last = 0 if len(array) == 0 else array[-1]
        if high == -1 or aValue > array_last:
            array.append(aValue)
            return high + 1

        index = None
        found = None

        if not isinstance(low, int) or not isinstance(high, int):
            iStop = 1

        while low <= high:
            index = int((high + low) / 2)
            found = array[index]

            if aValue == found:
                return index
            elif aValue > found:
                low = index + 1
            else:
                high = index - 1

        array[low] = aValue
    except:
        msg = oErr.get_error_message()
        oErr.DoError("_replaceNextLargerWith")
    return low

def _longestCommonSubsequence(a, b, counting=0, keyGen=None):
    """
    This method computes the longest common subsequence in $a and $b.

    Result is array or ref, whose contents is such that
    $a->[ $i ] == $b->[ $result[ $i ] ]
    foreach $i in ( 0 .. $#result ) if $result[ $i ] is defined.

    An additional argument may be passed; this is a hash or key generating
    function that should return a string that uniquely identifies the given
    element.  It should be the case that if the key is the same, the elements
    will compare the same. If this parameter is undef or missing, the key
    will be the element as a string.

    By default, comparisons will use "eq" and elements will be turned into keys
    using the default stringizing operator '""'.

    Additional parameters, if any, will be passed to the key generation routine.
    """

    keyGen = keyGen if keyGen is not None else default_keyGen

    def compare(a, b):
        return keyGen(a) == keyGen(b)

    oErr = ErrHandle()
    try:
        aStart, aFinish = 0, len(a) - 1
        bStart, bFinish = 0, len(b) - 1
        matchVector = [None] * len(a)
        prunedCount = 0
        bMatches = {}

        while aStart <= aFinish and bStart <= bFinish and compare(a[aStart], b[bStart]):
            matchVector[aStart] = bStart
            aStart += 1
            bStart += 1
            prunedCount += 1

        while aStart <= aFinish and bStart <= bFinish and compare(a[aFinish], b[bFinish]):
            matchVector[aFinish] = bFinish
            aFinish -= 1
            bFinish -= 1
            prunedCount += 1

        bMatches = _withPositionsOfInInterval(b, bStart, bFinish, keyGen)

        response = _longestCommonSubsequence_helper(a, bMatches, counting, keyGen, prunedCount, aStart, aFinish, matchVector)

    except:
        msg = oErr.get_error_message()
        oErr.DoError("_longestCommonSubsequence")
    return response

def _longestCommonSubsequence_helper(a, bMatches, counting, keyGen, prunedCount, aStart, aFinish, matchVector):

    thresh = []
    links = []
    oErr = ErrHandle()
    try:
        if aFinish is None:
            aFinish = len(a) - 1    

        for i in range(aStart, aFinish+1):
            ai = keyGen(a[i]) 

            if ai in bMatches:
                for j in bMatches[ai]:

                    if i==24 and j==9:
                        iStop = 1

                    k = None
                    if k and thresh[k] > j and thresh[k - 1] < j:
                        thresh[k] = j
                    else:
                        k = _replaceNextLargerWith(thresh, j, k)

                    if k is not None:
                        if k:
                            if k >= len(links):
                                # links.append(links[k - 1] + [i, j])
                                links.extend(links[k-1], [i,j])
                            else:
                                links[k] = links[k - 1] + [i, j]
                        else:
                            # This means k=0
                            links.extend([i, j])
                            # OLD links.append([None, i, j])
                            # OLD links[k] = [None, i, j]

        if thresh:
            if counting:
                return prunedCount + len(thresh)

            link = links[len(thresh) - 1]
            while link:
                matchVector[link[1]] = link[2]
                link = links[link[0]]

        elif counting:
            return prunedCount

    except:
        msg = oErr.get_error_message()
        oErr.DoError("_longestCommenSubsequence_helper")
    return matchVector

def traverse_sequences(a, b, keyGen=default_keyGen, match=None, discard_a=None, discard_b=None,
                        finished_a=None, finished_b=None):
    oErr = ErrHandle()
    try:
        matchVector = _longestCommonSubsequence(a, b, 0, keyGen)

        lastA = len(a) - 1
        lastB = len(b) - 1
        bi = 0
        ai = 0

        while ai < len(matchVector):
            bLine = matchVector[ai]
            if bLine is not None:  # matched
                while bi < bLine:
                    discard_b(ai, bi)
                    bi += 1
                match(ai, bi)
                bi += 1
            else:
                discard_a(ai, bi)
            ai += 1

        while ai <= lastA or bi <= lastB:
            if ai == lastA + 1 and bi <= lastB:  # last A
                if finished_a is not None:
                    finished_a(lastA)
                    finished_a = None
                else:
                    while bi <= lastB:
                        discard_b(ai, bi)
                        bi += 1

            if bi == lastB + 1 and ai <= lastA:  # last B
                if finished_b is not None:
                    finished_b(lastB)
                    finished_b = None
                else:
                    while ai <= lastA:
                        discard_a(ai, bi)
                        ai += 1

            if ai <= lastA:
                discard_a(ai, bi)
                ai += 1

            if bi <= lastB:
                discard_b(ai, bi)
                bi += 1

    except:
        msg = oErr.get_error_message()
        oErr.DoError("traverse_sequences")
    return 1

def diff(a, b):
    retval = []
    hunk = []

    def match(x, y):
        nonlocal retval, hunk
        retval.append(hunk)
        hunk = []

    def discard_a(x, y):
        nonlocal hunk
        hunk.append(['-', x, a[x]])

    def discard_b(x, y):
        nonlocal hunk
        hunk.append(['+', y, b[y]])

    oErr = ErrHandle()
    try:

        traverse_sequences(a, b, match=match, discard_a=discard_a, discard_b=discard_b)

    except:
        msg = oErr.get_error_message()
        oErr.DoError("diff")

    return retval + hunk


