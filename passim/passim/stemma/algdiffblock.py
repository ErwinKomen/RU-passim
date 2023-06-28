import copy
from passim.utils import ErrHandle

def default_keyGen(value):
    return value


def _withPositionsOfInInterval(aCollection, start, end, keyGen, *args):
    """
    # Create a hash that maps each element of $aCollection to the set of positions
    # it occupies in $aCollection, restricted to the elements within the range of
    # indexes specified by $start and $end.
    # The fourth parameter is a subroutine reference that will be called to
    # generate a string to use as a key.
    # Additional parameters, if any, will be passed to this subroutine.
    #
    # my $hashRef = _withPositionsOfInInterval( \@array, $start, $end, $keyGen );    
    """

    d = {}
    oErr = ErrHandle()
    response = None
    try:
        for index in range(start, end+1):
            element = aCollection[index]
            key = keyGen(element, *args)
            if key in d:
                d[key].insert(0, index)  # unshift
            else:
                d[key] = [index]
    
        if args and args[0] == 'wantarray':
            response = d
        else:
            response = d.copy()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("_withPositionsOfInInterval")
    return response

def _replaceNextLargerWith(array, aValue, high=None):
    """
    # Find the place at which aValue would normally be inserted into the array. If
    # that place is already occupied by aValue, do nothing, and return undef. If
    # the place does not exist (i.e., it is off the end of the array), add it to
    # the end, otherwise replace the element at that point with aValue.
    # It is assumed that the array's values are numeric.
    # This is where the bulk (75%) of the time is spent in this module, so try to
    # make it fast!
    """

    oErr = ErrHandle()
    low = 0
    try:
        high = high if high is not None else len(array) - 1

        # off the end?
        array_last = 0 if len(array) == 0 else array[-1]
        if high == -1 or aValue > array_last:
            array.append(aValue)
            return high + 1

        if not isinstance(low, int) or not isinstance(high, int):
            iStop = 1

        # binary search for insertion point...
        low = 0
        index = 0
        found = None
        while low <= high:
            index = (high + low) // 2

            found = array[index]

            if aValue == found:
                return None
            elif aValue > found:
                low = index + 1
            else:
                high = index - 1

        # now insertion point is in low.
        array[low] = aValue  # overwrite next larger
    except:
        msg = oErr.get_error_message()
        oErr.DoError("_replaceNextLargerWith")
    return low

def _longestCommonSubsequence(a, b, keyGen=None, *args):
    """
    # This method computes the longest common subsequence in $a and $b.

    # Result is array or ref, whose contents is such that
    # 	$a->[ $i ] == $b->[ $result[ $i ] ]
    # foreach $i in ( 0 .. $#result ) if $result[ $i ] is defined.

    # An additional argument may be passed; this is a hash or key generating
    # function that should return a string that uniquely identifies the given
    # element.  It should be the case that if the key is the same, the elements
    # will compare the same. If this parameter is undef or missing, the key
    # will be the element as a string.

    # By default, comparisons will use "eq" and elements will be turned into keys
    # using the default stringizing operator '""'.

    # Additional parameters, if any, will be passed to the key generation routine.
    """

    def get_list_el(lst_this, idx):
        """Get a list element if existing, else return None"""

        ln = len(lst_this)
        if idx >= ln - 1 or idx < 0:
            response = None
        else:
            response = lst_this[idx]
        return response

    def add_list_el(lst_this, idx, value):
        """Add a list element at [idx]"""

        ln = len(lst_this)
        while idx >= ln:
            lst_this.append(None)
            # Calculate new length
            ln = len(lst_this)

        lst_this[idx] = value

    oErr = ErrHandle()
    response = None
    try:
        # set up code refs
        # Note that these are optimized.
        if keyGen is None:    # optimize for strings
            keyGen = lambda x: x
            compare = lambda a, b: a == b
        else:
            compare = lambda a, b: keyGen(a, *args) == keyGen(b, *args)

        aStart, aFinish, bStart, bFinish = 0, len(a) - 1, 0, len(b) - 1
        matchVector = [None] * len(a)

        # First we prune off any common elements at the beginning
        while aStart <= aFinish and bStart <= bFinish and compare(a[aStart], b[bStart], *args):
            matchVector[aStart] = bStart
            aStart += 1
            bStart += 1

        # now the end
        while aStart <= aFinish and bStart <= bFinish and compare(a[aFinish], b[bFinish], *args):
            matchVector[aFinish] = bFinish
            aFinish -= 1
            bFinish -= 1

        # Now compute the equivalence classes of positions of elements
        bMatches = _withPositionsOfInInterval(b, bStart, bFinish, keyGen, *args)
        thresh = []
        links = []

        for i in range(aStart, aFinish+1):
            ai = keyGen(a[i], *args)
            if ai in bMatches:
                k = 0
                for j in bMatches[ai]:
                    # optimization: most of the time this will be true
                    if k and thresh[k] > j and thresh[k - 1] < j:
                        thresh[k] = j
                    else:
                        k = _replaceNextLargerWith(thresh, j, k)

                    # oddly, it's faster to always test this (CPU cache?).
                    if k is not None:
                        if k == 0:
                            links[k] = [None, i, j]
                        else:
                            # Mimicking: links[k] = [ links[k-1], i, j]
                            value = [ get_list_el(links, k-1), i, j ]
                            add_list_el(links, k, value)
    
        if thresh:
            link = links[-1]
            while link:
                matchVector[link[1]] = link[2]
                link = link[0]

        if args and args[0] == 'wantarray':
            response = matchVector
        else:
            response = matchVector[:]
    except:
        msg = oErr.get_error_message()
        oErr.DoError("_longestCommonSubsequence")
    return response

def traverse_sequences(a, b,  match=None, discard_a=None, discard_b=None,
                        finished_a=None, finished_b=None, keyGen=None, *args):
    """

    """

    oErr = ErrHandle()
    try:
        #callbacks = callbacks or {}
        #matchCallback = callbacks.get('MATCH', lambda *args: None)
        #discardACallback = callbacks.get('DISCARD_A', lambda *args: None)
        #finishedACallback = callbacks.get('A_FINISHED')
        #discardBCallback = callbacks.get('DISCARD_B', lambda *args: None)
        #finishedBCallback = callbacks.get('B_FINISHED')
        matchVector = _longestCommonSubsequence(a, b, keyGen, *args)

        # Process all the lines in matchVector
        lastA = len(a) - 1
        lastB = len(b) - 1
        bi = 0
        ai = 0

        while ai <= len(matchVector) - 1:
            bLine = matchVector[ai]
            if bLine is not None:    # matched
                while bi < bLine:
                    discard_b(ai, bi, *args)
                    bi += 1
                match(ai, bi, *args)
                bi += 1
            else:
                discard_a(ai, bi, *args)
            ai += 1

        # The last entry (if any) processed was a match.
        # ai and bi point just past the last matching lines in their sequences.

        while ai <= lastA or bi <= lastB:
            # last A?
            if ai == lastA + 1 and bi <= lastB:
                if finished_a:
                    finished_a(lastA, *args)
                    finished_a = None
                else:
                    while bi <= lastB:
                        discard_b(ai, bi, *args)
                        bi += 1

            # last B?
            if bi == lastB + 1 and ai <= lastA:
                if finished_b:
                    finished_b(lastB, *args)
                    finished_b = None
                else:
                    while ai <= lastA:
                        discard_a(ai, bi, *args)
                        ai += 1

            if ai <= lastA:
                discard_a(ai, bi, *args)
                ai += 1
            if bi <= lastB:
                discard_b(ai, bi, *args)
                bi += 1
    except:
        msg = oErr.get_error_message()
        oErr.DoError("traverse_sequences")

    return 1

#def traverse_balanced(a, b, callbacks=None, keyGen=None, *args):
#    oErr = ErrHandle()
#    try:
#        callbacks = callbacks or {}
#        matchCallback = callbacks.get('MATCH', lambda *args: None)
#        discardACallback = callbacks.get('DISCARD_A', lambda *args: None)
#        discardBCallback = callbacks.get('DISCARD_B', lambda *args: None)
#        changeCallback = callbacks.get('CHANGE')
#        matchVector = _longestCommonSubsequence(a, b, keyGen, *args)

#        lastA = len(a) - 1
#        lastB = len(b) - 1
#        bi = 0
#        ai = 0
#        ma = -1
#        mb = None

#        while True:
#            while ma <= len(matchVector) - 1 and matchVector[ma] is None:
#                ma += 1

#            if ma > len(matchVector) - 1:
#                break

#            mb = matchVector[ma]

#            while ai < ma or bi < mb:
#                if ai < ma and bi < mb:
#                    if changeCallback:
#                        changeCallback(ai, bi, *args)
#                    else:
#                        discardACallback(ai, bi, *args)
#                        discardBCallback(ai, bi, *args)
#                    ai += 1
#                    bi += 1
#                elif ai < ma:
#                    discardACallback(ai, bi, *args)
#                    ai += 1
#                else:
#                    discardBCallback(ai, bi, *args)
#                    bi += 1

#            matchCallback(ai, bi, *args)
#            ai += 1
#            bi += 1

#        while ai <= lastA or bi <= lastB:
#            if ai <= lastA and bi <= lastB:
#                if changeCallback:
#                    changeCallback(ai, bi, *args)
#                else:
#                    discardACallback(ai, bi, *args)
#                    discardBCallback(ai, bi, *args)
#                ai += 1
#                bi += 1
#            elif ai <= lastA:
#                discardACallback(ai, bi, *args)
#                ai += 1
#            else:
#                discardBCallback(ai, bi, *args)
#                bi += 1
#    except:
#        msg = oErr.get_error_message()
#        oErr.DoError("traverse_balanced")

#    return 1

def diff(a, b, *args):
    retval = []
    hunk = []
    
    #def discard(idx):
    #    hunk.append(['-', idx, a[idx]])
    
    #def add(idx):
    #    hunk.append(['+', idx, b[idx]])
    
    #def match():
    #    nonlocal hunk
    #    if hunk:
    #        retval.append(hunk)
    #    hunk = []

    def match(x, y, *args):
        nonlocal retval, hunk
        retval.append(hunk)
        hunk = []

    def discard_a(x, y, *args):
        nonlocal hunk
        hunk.append(['-', x, a[x]])

    def discard_b(x, y, *args):
        nonlocal hunk
        hunk.append(['+', y, b[y]])

    oErr = ErrHandle()
    response = None
    try:
        # Use my own match(), discard() and add() functions
        # traverse_sequences(a, b, {'MATCH': match, 'DISCARD_A': discard_a, 'DISCARD_B': discard_b}, *args)
        traverse_sequences(a, b, match=match, discard_a=discard_a, discard_b=discard_b, *args)

        # Call my own match function
        match(1, 2)

        response = retval if isinstance(retval, list) else [retval]
    except:
        msg = oErr.get_error_message()
        oErr.DoError("diff")

    return response

