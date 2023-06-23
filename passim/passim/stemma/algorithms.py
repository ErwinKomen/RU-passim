

#!/usr/bin/env python
import sys
import re
import difflib          # For perf

from passim.utils import ErrHandle


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
    wordArrMs1 = a1[:]
    wordArrMs2 = a2[:]

    # Create the 2-dim array of differences between the two arrays
    diffArray = list(difflib.ndiff(wordArrMs1, wordArrMs2))

    dist = 0

    for hunk in diffArray:
        sequenceArray = list(hunk)
        distInHunk = 0

        for sequence in sequenceArray:
            # Assigning a score to the pot. leitfehler in wlist()
            word = sequence[2:]  # Extract the third element of the list
            # Remove +/- at the beginning and the digits (\d) of the position; leave only the char string
            word = word[2:] if word.startswith(' ') else word[1:]
            
            if '€' in word:
                distInHunk = -2  # €-wildcard matches anything
            
            # Calibration to weight
            if score.get(word) and scoremax * weight != 0:
                distInHunk += score[word] / scoremax * weight

            distInHunk += 1

        dist += distInHunk

    return int(dist + 0.5)

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

def rating(a1, a2, a3, word, otherWord):
    a = [a1, a2, a3]
    r = min(a)
    return r

def ratings(a1, a2, a3, word, otherWord):
    a = [a1, a2, a3]
    s = len(msLabelArray) - max(a) - min(a)
    return s

def vierer(word, otherWord, a1, a2, a3, t0, t1, t2, t3):
    if debug == 3:
        if t0 != 1 and t1 != 1 and t2 != 1 and t3 != 1:
            print(word + "/" + otherWord + " " + str(t0) + " " + str(t1) + " " + str(t2) + " " + str(t3) + " \n")

def wlist(numOfMss, mssHash, msLabelArray):
    global cut, mssWordCountHash, globalWordCountHash, leit, globalLeit, ur, score, scoremax

    oErr = ErrHandle()
    bResult = False
    try:    
        cut = cut * numOfMss * numOfMss / 2500

        mssWordCountHash = {}
        globalWordCountHash = {}
        leit = []
        globalLeit = {}

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
                    if re.search(r'...', word) and abs(mssWordCountHash[currMsLabel].get(word, 0) - mssWordCountHash[otherMsLabel].get(word, 0)) > 0 and mssWordCountHash[currMsLabel].get(word, 0) + mssWordCountHash[otherMsLabel].get(word, 0) < 2:
                        if msIndex >= len(leit):
                            leit.append([])
                        if otherMsIndex >= len(leit[msIndex]):
                            leit[msIndex].append({})
                        leit[msIndex][otherMsIndex][word] = 1
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

        for word in globalLeit.keys():
            if globalLeit[word] > cut:
                for otherWord in globalLeit.keys():
                    if globalLeit[otherWord] > cut and word < otherWord:
                        tab = [0, 0, 0, 0]

                        # Both words occur together in no ms
                        for msIndex in range(1, len(msLabelArray)):
                            currMsLabel = msLabelArray[msIndex]

                            if mssWordCountHash[currMsLabel].get(word) and mssWordCountHash[currMsLabel].get(otherWord):
                                tab[0] += 1
                            elif mssWordCountHash[currMsLabel].get(word) and not mssWordCountHash[currMsLabel].get(otherWord):
                                tab[1] += 1
                            elif not mssWordCountHash[currMsLabel].get(word) and mssWordCountHash[currMsLabel].get(otherWord):
                                tab[2] += 1
                            else:
                                tab[3] += 1

                        if tab[0] == 0 and tab[1] > 0 and tab[2] > 0 and tab[3] > 0:
                            if debug:
                                vierer(word, otherWord, tab[1], tab[2], tab[3], *tab)
                            r = rating(tab[1], tab[2], tab[3], word, otherWord)
                            s = ratings(tab[1], tab[2], tab[3], word, otherWord)
                            if r > 1:
                                ur[word] = ur.get(word, 0) + (r - 1) ** 2 * s
                                ur[otherWord] = ur.get(otherWord, 0) + (r - 1) ** 2 * s
                        # Absence of word and presence of otherWord in no ms
                        elif tab[1] == 0 and tab[0] > 0 and tab[2] > 0 and tab[3] > 0:
                            if debug:
                                vierer(word, otherWord, tab[0], tab[2], tab[3], *tab)
                            r = rating(tab[0], tab[2], tab[3], word, otherWord)
                            s = ratings(tab[0], tab[2], tab[3], word, otherWord)
                            if r > 1:
                                ur[word] = ur.get(word, 0) + (r - 1) ** 2 * s
                                ur[otherWord] = ur.get(otherWord, 0) + (r - 1) ** 2 * s
                        # Presence of word and absence of otherWord in no ms
                        elif tab[2] == 0 and tab[0] > 0 and tab[1] > 0 and tab[3] > 0:
                            if debug:
                                vierer(word, otherWord, tab[0], tab[1], tab[3], *tab)
                            r = rating(tab[0], tab[1], tab[3], word, otherWord)
                            s = ratings(tab[0], tab[1], tab[3], word, otherWord)
                            if r > 1:
                                ur[word] = ur.get(word, 0) + (r - 1) ** 2 * s
                                ur[otherWord] = ur.get(otherWord, 0) + (r - 1) ** 2 * s
                        # Absence of word and otherWord in no ms
                        elif tab[3] == 0 and tab[0] > 0 and tab[1] > 0 and tab[2] > 0:
                            if debug:
                                vierer(word, otherWord, tab[0], tab[1], tab[2], *tab)
                            r = rating(tab[0], tab[1], tab[2], word, otherWord)
                            s = ratings(tab[0], tab[1], tab[2], word, otherWord)
                            if r > 1:
                                ur[word] = ur.get(word, 0) + (r - 1) ** 2 * s
                                ur[otherWord] = ur.get(otherWord, 0) + (r - 1) ** 2 * s
                    # if ($globalLeit{$otherWord} > $cut && $word lt $otherWord)
                # foreach my $otherWord (keys %globalLeit)
            # if ($globalLeit{$word} > $cut)
        # foreach my $word (keys %globalLeit)

        # %ur counts and weights cases with only 3 combinations; %scoremax is its maximum

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
                score[word] = ur[word] / counter
            else:
                score[word] = ur[word]

        # calculate scoremax   
        for word in ur.keys():
            scoremax = score[word] if scoremax < score[word] else scoremax
        
        # Print score if debug=1
        if debug > 0:
            with open("log", "w") as logfile:
                sorted_keys = sorted(score, key=lambda k: score[k], reverse=True)
                for k in sorted_keys:
                    if ur[k] > 0 and score[k] > scoremax / 100:
                        logfile.write("{}  --  {} - {} {}% \n")
                        logfile.write("".format(
                            k, int(score[k]), ur[k], int(score[k] / scoremax * 100) ))

        # we are okay
        bResult = True
    except:
        msg = oErr.get_error_message()
        oErr.DoError("lf_new4")
    return bResult

def lf_new4(sTexts):
    """Perform the LeitFehler algorithm on a list of lines"""

    oErr = ErrHandle()
    numOfMss = 0
    mssHash = {}
    msLabelArray = []
    try:    
        lst_line = sTexts.split("\n")

        for line in lst_line:
            line = line.rstrip("\n")
            line = re.sub(r"[\,!\?\"]", "", line)  # remove punctuation
            # line = re.sub(r"\.", "", line)  # remove . ?
            line = re.sub(r"\s[^\s]*\*[^\s]*", "€", line)  # convert word with a *-wildcard to €
            line = line.rstrip()

            # label manuscripts (3 chars), or n chars make (n-1) dots in next line
            match = re.match(r"^(\w..)[\w\s]{7}(.+)$", line)
            if match:
                mssHash[match.group(1)] = match.group(2)  # hash of all mss.
                msLabelArray.append(match.group(1))  # all mss. label, n: index

                mssHash[msLabelArray[numOfMss]] = re.sub(r"\([^\)]+\)", "", mssHash[msLabelArray[numOfMss]])  # remove ()
                mssHash[msLabelArray[numOfMss]] = re.sub(r"\[[^\]]+\]", "", mssHash[msLabelArray[numOfMss]])  # remove []

                numOfMss += 1

        bResult = wlist(numOfMss, mssHash, msLabelArray)

        # remove to get a fast result without calculating the lff

        ##########

        print(len(msLabelArray))  # print length of array
        print("\n" + msLabelArray[0])

        for msIndex in range(1, len(msLabelArray)):
            print(msLabelArray[msIndex], end=" ")
            for otherMsIndex in range(msIndex):
                wordArrayMs1 = mssHash[msLabelArray[msIndex]].split(' ')  # split content of this ms into words
                wordArrayMs2 = mssHash[msLabelArray[otherMsIndex]].split(' ')  # split content of the other ms into words

                # diff
                el = difflib.SequenceMatcher(None, wordArrayMs1, wordArrayMs2).ratio()
                print(el, end=" ")
                # matrix[msIndex+1][otherMsIndex+1] = el
                # matrix[otherMsIndex+1][msIndex+1] = el

            print()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("lf_new4")

# End of code