"""
Stemmatology app main entry for calculating Leitfehler

"""

#!/usr/bin/env python
import sys
import re
import json
import difflib          # For perf

from passim.utils import ErrHandle
from passim.stemma.algdiffblock import diff


# Debug level CHANGE
# 0 : only matrix
# 1 : .. and a list of pot. leitfehler (lf) and their score
# 2 : ..... and a list of pot. lf and the ms. the occur in
# 3 : ....... and a list of matches of pot. lf
debug = 1

cut = 0  # threshold for globalLeit, currently not used
weight = 10  # weight. lf are counted .-times more for the best of them, the others proportionally down to 1

scoremax = 1
ur = {}
score = {}



# standardisation

def dodiff(a1, a2):
    # Copy the two arrays passed to this function into the variables wordArrMs1 and wordArrMs2
    wordArrMs1 = a1[:]
    wordArrMs2 = a2[:]

    oErr = ErrHandle()
    dist = 0
    response = None

    try:

        # diff computes the smallest set of additions and deletions necessary to turn the first sequence into the second
        # and returns a 2-dim array of differences (hunks with sequences);
        # each difference is a list of 3 elements (-/+, position of the change, string), e.g.:
        # [
        #    [
        #       ['-', 0, 'a']
        #    ],
        #    [
        #       ['-', 8, 'n'],
        #       ['+', 9, 'p']
        #    ]
        # ]        
        
        # Create the 2-dim array of differences between the two arrays
        # diffArray = list(difflib.ndiff(wordArrMs1, wordArrMs2))
        diffArray = diff(wordArrMs1, wordArrMs2)

        for hunk in diffArray:
            # sequenceArray = list(hunk)
            sequenceArray = hunk
            distInHunk = 0

            #sequence = []
            #sequence.append(sequenceArray[0])
            #sequence.append(sequenceArray[1])
            #sequence.append(sequenceArray[2:])

            # sequence = [sequenceArray[0], [sequenceArray[1], sequenceArray[2:] ]

            for sequence in sequenceArray:

                # assigning a score to the pot. leitfehler in wlist()

                # (1) OLD METHOD: combine into string and evaluate that
                #word = " ".join(str(x) for x in sequence)
                ## Remove +/- at the beginning and the digits (\d) of the position; leave only the char string
                #word = re.sub(r'^. \d+ (.+)', r'\1', word)

                # (2) NEW METHOD: just take the string part
                word = sequence[2]
            
                if '€' in word:
                    distInHunk = -2  # €-wildcard matches anything
            
                # Calibration to weight
                if score.get(word) and scoremax * weight != 0:
                    distInHunk += score[word] / scoremax * weight

                distInHunk += 1

            dist += distInHunk

        response = int(dist + 0.5)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("dodiff")

    return response

def outdiff():
    a = "Zz"
    b = "Br"

    arr1 = list(mssHash[a])
    arr2 = list(mssHash[b])

    diffArray = list(difflib.ndiff(arr1, arr2))

    for i in diffArray:
        len_i = len(i)
        print("({}): ".format(len_i), end="")
        for j in i:
            for k in j[2:]:
                print(k, end=",")
        print()

def rating(a1, a2, a3):
    r = min(a1, a2, a3)
    return r

def ratings(len_msLabelArray, a1, a2, a3, min_a):
    max_a = max(a1, a2, a3)
    s = len_msLabelArray - max_a - min_a
    return s

def rating_rs(len_msLabelArray, a1, a2, a3):
    r = min(a1, a2, a3)
    max_a = max(a1, a2, a3)
    s = len_msLabelArray - max_a - r
    return r, s

def vierer(word, otherWord, a1, a2, a3, t0, t1, t2, t3):
    if debug == 3:
        if t0 != 1 and t1 != 1 and t2 != 1 and t3 != 1:
            print(word + "/" + otherWord + " " + str(t0) + " " + str(t1) + " " + str(t2) + " " + str(t3) + " \n")

def wlist(numOfMss, mssHash, msLabelArray, oStatus = None):
    global cut, mssWordCountHash, globalWordCountHash, leit, globalLeit, ur, score, scoremax

    oErr = ErrHandle()
    bResult = False
    try:    
        cut = cut * numOfMss * numOfMss / 2500
        cut = int(cut)

        mssWordCountHash = {}
        globalWordCountHash = {}
        leit = []
        globalLeit = {}

        # Possibly set status
        if not oStatus is None:
            if oStatus.set_status("lf_new4", "wlist: preparations") == "interrupt": return False

        for msIndex in mssHash.keys():
            msContent = mssHash[msIndex]
            msContent = re.sub(r'[\s\|]+', ' ', msContent)
            while re.search(r'^\s*([^\s]+)', msContent):
                word = re.search(r'^\s*([^\s]+)', msContent).group(1)
                msContent = re.sub(r'^\s*[^\s]+', '', msContent)

                if msIndex not in mssWordCountHash:
                    mssWordCountHash[msIndex] = {}
                if word not in mssWordCountHash[msIndex]:
                    mssWordCountHash[msIndex][word] = 0
                mssWordCountHash[msIndex][word] += 1

                if word not in globalWordCountHash:
                    globalWordCountHash[word] = 0
                globalWordCountHash[word] += 1

        for msIndex in range(1, len(msLabelArray)):
            currMsLabel = msLabelArray[msIndex]

            for otherMsIndex in range(0, msIndex):
                otherMsLabel = msLabelArray[otherMsIndex]

                for word in globalWordCountHash.keys():
                    #if word == "christus": 
                    #    iStop = 1
                    xcurr = mssWordCountHash[currMsLabel].get(word, 0)
                    xother = mssWordCountHash[otherMsLabel].get(word, 0)
                    # WAS: if re.search(r'...', word) and abs(mssWordCountHash[currMsLabel].get(word, 0) - mssWordCountHash[otherMsLabel].get(word, 0)) > 0 and mssWordCountHash[currMsLabel].get(word, 0) + mssWordCountHash[otherMsLabel].get(word, 0) < 2:
                    if re.search(r'...', word) and abs(xcurr - xother) > 0 and (xcurr + xother) < 2:
                        if msIndex >= len(leit):
                            leit.append([])
                        if otherMsIndex >= len(leit[msIndex-1]):
                            leit[msIndex-1].append({})
                        leit[msIndex-1][otherMsIndex][word] = 1
                        if word not in globalLeit:
                            globalLeit[word] = 0
                        globalLeit[word] += 1

        if debug == 2:
            with open('log2', 'w') as LOG2:
                for word in globalLeit.keys():
                    if globalLeit[word] > cut:
                        LOG2.write(word + " (" + str(globalLeit[word]) + ") : ")
                        for msIndex in range(1, len(msLabelArray)):
                            currMsLabel = msLabelArray[msIndex]
                            if word in mssWordCountHash[currMsLabel]:
                                match = re.match(r'^[^ ]{1,4}', currMsLabel)
                                if match:
                                    LOG2.write(match.group(0) + ":" + str(mssWordCountHash[currMsLabel][word]) + " ")
                        LOG2.write("\n")

        # ========== DEBUG ==================
        #y = json.dumps(globalLeit, indent=2)
        #x = json.dumps(mssWordCountHash, indent=2)
        # ===================================


        numwords = len(globalLeit.keys())
        chunksize = numwords // 20
        len_msLabelArray = len(msLabelArray)

        # Preparation for speeding up
        lst_wcHash = []
        for msIndex in range(1, len_msLabelArray):
            currMsLabel = msLabelArray[msIndex]
            wcHash = mssWordCountHash[currMsLabel]
            lst_wcHash.append(wcHash)

        chunk = chunksize
        for idx1, word in enumerate(globalLeit.keys()):
            # ========= DEbug ================
            if debug > 0: 
                # oErr.Status("wlist #1: {}/{} word = {}".format(idx1,numwords, word))
                if idx1 >= chunk:
                    chunk += chunksize
                    oErr.Status("wlist #1: {:.2f}%".format(idx1 * 100 / numwords))
            # ================================
            # Possibly set status
            if not oStatus is None:
                if oStatus.set_status("lf_new4", "wlist: word {} of {}".format(idx1, numwords)) == "interrupt": return False


            # Consider only leitfehler, if its global leitfehler counter is heigher than cut
            if globalLeit[word] > cut:
                for idx2, otherWord in enumerate(globalLeit.keys()):

                    # Consider only leitfehler, if its global leitfehler counter is heigher than cut
                    if globalLeit[otherWord] > cut and word < otherWord:
                        # Use four separate variables 
                        t0, t1, t2, t3 = 0, 0, 0, 0

                        # - Iterate over all mss 
                        # - count the "relations" between the counter of word and otherWord in each ms
                        #for msIndex in range(1, len_msLabelArray):
                        #    currMsLabel = msLabelArray[msIndex]
                        #    wcHash = mssWordCountHash[currMsLabel]
                        #    x_curr = (wcHash.get(word,0) > 0)
                        #    x_other = (wcHash.get(otherWord,0) > 0)

                        #    if x_curr and x_other:
                        #        # Both, word and otherWord are in the current ms
                        #        t0 += 1
                        #    elif x_curr and not x_other:
                        #        # Only word is in the the current ms
                        #        t1 += 1
                        #    elif not x_curr and x_other:
                        #        # Only otherWord is in the the current ms
                        #        t2 += 1
                        #    else:
                        #        # Neither word nor otherWord are in the the current ms
                        #        t3 += 1
                        for wcHash in lst_wcHash:
                            x_curr = (wcHash.get(word,0) > 0)
                            x_other = (wcHash.get(otherWord,0) > 0)

                            if x_curr and x_other:
                                # Both, word and otherWord are in the current ms
                                t0 += 1
                            elif x_curr and not x_other:
                                # Only word is in the the current ms
                                t1 += 1
                            elif not x_curr and x_other:
                                # Only otherWord is in the the current ms
                                t2 += 1
                            else:
                                # Neither word nor otherWord are in the the current ms
                                t3 += 1


                        # Both words occur together in no ms
                        if t0 == 0 and t1 > 0 and t2 > 0 and t3 > 0:
                            if debug == 3:
                                vierer(word, otherWord, t1, t2, t3, *tab)
                            r, s = rating_rs(len_msLabelArray, t1, t2, t3)

                            if r > 1:
                                ur[word] = ur.get(word, 0) + (r - 1) ** 2 * s
                                ur[otherWord] = ur.get(otherWord, 0) + (r - 1) ** 2 * s
                        # Absence of word and presence of otherWord in no ms
                        elif t1 == 0 and t0 > 0 and t2 > 0 and t3 > 0:
                            if debug == 3:
                                vierer(word, otherWord, t0, t2, t3, *tab)
                            r, s = rating_rs(len_msLabelArray, t0, t2, t3)

                            if r > 1:
                                ur[word] = ur.get(word, 0) + (r - 1) ** 2 * s
                                ur[otherWord] = ur.get(otherWord, 0) + (r - 1) ** 2 * s
                        # Presence of word and absence of otherWord in no ms
                        elif t2 == 0 and t0 > 0 and t1 > 0 and t3 > 0:
                            if debug == 3:
                                vierer(word, otherWord, t0, t1, t3, *tab)
                            r, s = rating_rs(len_msLabelArray, t0, t1, t3)

                            if r > 1:
                                ur[word] = ur.get(word, 0) + (r - 1) ** 2 * s
                                ur[otherWord] = ur.get(otherWord, 0) + (r - 1) ** 2 * s
                        # Absence of word and otherWord in no ms
                        elif t3 == 0 and t0 > 0 and t1 > 0 and t2 > 0:
                            if debug == 3:
                                vierer(word, otherWord, t0, t1, t2, *tab)
                            r, s = rating_rs(len_msLabelArray, t0, t1, t2)

                            if r > 1:
                                ur[word] = ur.get(word, 0) + (r - 1) ** 2 * s
                                ur[otherWord] = ur.get(otherWord, 0) + (r - 1) ** 2 * s
                    # if ($globalLeit{$otherWord} > $cut && $word lt $otherWord)
                # foreach my $otherWord (keys %globalLeit)
            # if ($globalLeit{$word} > $cut)
        # foreach my $word (keys %globalLeit)

        # %ur counts and weights cases with only 3 combinations; %scoremax is its maximum

        # Possibly set status
        if not oStatus is None:
            if oStatus.set_status("lf_new4", "wlist: wrapping up") == "interrupt": return False

        # ADDED calculate counter: number of occurences of word 
        for word in globalLeit.keys():
            counter = 0

            # Iterate over all mss and 
            # count the number of mss that contain word
            for msIndex in range(1, len(msLabelArray)):
                currMsLabel = msLabelArray[msIndex]

                if mssWordCountHash[currMsLabel].get(word):
                    counter += 1

            if counter > numOfMss / 2:
                counter = numOfMss - counter

            # if (globalLeit counter for this word * counter) not 0
            if globalLeit[word] * counter:
                score[word] = ur.get(word,0) / counter
            else:
                score[word] = ur.get(word,0)

        # calculate scoremax   
        for word in ur.keys():
            scoremax = score[word] if scoremax < score[word] else scoremax
        
        # Print score if debug=1
        if debug > 0:
            with open("log", "w") as logfile:
                sorted_keys = sorted(score, key=lambda k: score[k], reverse=True)
                for k in sorted_keys:
                    ur_val = ur.get(word,0)
                    if ur_val > 0 and score[k] > scoremax / 100:
                        logfile.write("{}  --  {} - {} {}% \n")
                        logfile.write("".format(
                            k, int(score[k]), ur_val, int(score[k] / scoremax * 100) ))

        # we are okay
        bResult = True
    except:
        msg = oErr.get_error_message()
        oErr.DoError("lf_new4")
        bResult = False
        # Communicate this to the status
        if not oStatus is None:
            oStatus.set_status("error", msg)
    return bResult

def lf_new4(sTexts, oStatus=None):
    """Perform the LeitFehler algorithm on a list of lines"""

    oErr = ErrHandle()
    numOfMss = 0
    mssHash = {}
    msLabelArray = []
    lst_result = []
    try:    

        # ========== DEBUGGING =========
        #with open("arrayms1", "r") as fp:  wordArrayMs1 = json.load(fp)
        #with open("arrayms2", "r") as fp:  wordArrayMs2 = json.load(fp)

        #el = dodiff(wordArrayMs1, wordArrayMs2)
        #wordArrayMs1[100]
        # ==============================


        # Possibly set status
        if not oStatus is None:
            if oStatus.set_status("lf_new4", "Preparing lines") == "interrupt": return lst_result

        lst_line = sTexts.split("\n")

        ## ========== DEBUGGING =========
        #lst_line = lst_line[:3]
        #lst_line[0] = "{}".format(2)
        ## ==============================

        for line in lst_line:
            line = line.rstrip("\n")
            line = re.sub(r"[\,!\?\"]", "", line)  # remove punctuation
            # line = re.sub(r"\.", "", line)  # remove . ?
            line = re.sub(r"\s[^\s]*\*[^\s]*", " €", line)  # convert word with a *-wildcard to €
            line = line.rstrip()

            # label manuscripts (3 chars), or n chars make (n-1) dots in next line
            match = re.match(r"^(\w..)[\w\s]{7}(.+)$", line)
            if match:
                mssHash[match.group(1)] = match.group(2)  # hash of all mss.
                msLabelArray.append(match.group(1))  # all mss. label, n: index

                mssHash[msLabelArray[numOfMss]] = re.sub(r"\([^\)]+\)", "", mssHash[msLabelArray[numOfMss]])  # remove ()
                mssHash[msLabelArray[numOfMss]] = re.sub(r"\[[^\]]+\]", "", mssHash[msLabelArray[numOfMss]])  # remove []

                numOfMss += 1

        # Possibly set status
        if not oStatus is None:
            if oStatus.set_status("lf_new4", "Starting wlist") == "interrupt": return lst_result

        bResult = wlist(numOfMss, mssHash, msLabelArray, oStatus)

        # remove to get a fast result without calculating the lff

        ##########

        # Possibly set status
        if not oStatus is None:
            if oStatus.set_status("lf_new4", "Starting dodiff") == "interrupt": return lst_result

        print(len(msLabelArray))  # print length of array
        print("\n" + msLabelArray[0])

        for msIndex in range(1, len(msLabelArray)):
            # Start a new line
            lst_row = []
            # Add the row label to this
            lst_row.append(msLabelArray[msIndex])
            # print(msLabelArray[msIndex], end=" ")

            for otherMsIndex in range(msIndex):
                # split content of these manuscripts into words
                wordArrayMs1 = re.split(r'\s+', mssHash[msLabelArray[msIndex]])  
                wordArrayMs2 = re.split(r'\s+', mssHash[msLabelArray[otherMsIndex]])
                
                # Possibly set status
                if not oStatus is None:
                    if oStatus.set_status("lf_new4", "dodiff: {}, {} (len={})".format(
                        msIndex, otherMsIndex, len(msLabelArray))) == "interrupt": return lst_result

                # diff
                el = dodiff(wordArrayMs1, wordArrayMs2)
                # Add to this row
                lst_row.append("{}".format(el))
                # print(" {} ".format(el), end=" ")

            # print()
            # Add the row to the overall result
            lst_result.append(lst_row)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("lf_new4")

    # Return the result
    return lst_result

# End of code