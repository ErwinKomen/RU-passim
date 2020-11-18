"""
Convert latin batsbi into Georgian script

This version created by Erwin R. Komen
Date: 16/nov/2020

Example:
    python latinbats.py -m "test1" 
                        -i "d:/data files/sil-neg/consultant/projects/batsbi/test_latin.txt" 
                        -o "d:/data files/sil-neg/consultant/projects/batsbi/test_batsbi1.txt"
"""

import sys, getopt, os.path, importlib
import re

trans_batsbi1 = [
    {"latin": "a", "bats": "ა"},
    {"latin": "b", "bats":  "ბ"},
    {"latin": "ch'", "bats":  "ჭ"},
    {"latin": "chw", "bats":  "ჩჺ"},   # {"latin": "chw", "bats":  "ჩჰჺ"},
    {"latin": "ch", "bats":  "ჩ"},
    {"latin": "c'", "bats":  "წ"},
    {"latin": "cw", "bats":  "ცჺ"},    # {"latin": "cw", "bats":  "ცჰჺ"},
    {"latin": "c", "bats":  "ც"},
    {"latin": "d", "bats":  "დ"},
    {"latin": "e", "bats":  "ე"},
    {"latin": "gh", "bats":  "ღ"},
    {"latin": "g", "bats":  "გ"},
    {"latin": "hw", "bats":  "ჰჺ"}, #
    {"latin": "h", "bats":  "ჰ"},
    {"latin": "i", "bats":  "ი"},
    {"latin": "j", "bats":  "ჲ"},
    {"latin": "k'", "bats":  "კ"},
    {"latin": "kw", "bats":  "ქჺ"},    # {"latin": "kw", "bats":  "ქჰჺ"},
    {"latin": "k", "bats":  "ქ"},
    {"latin": "lh", "bats":  "ლჰ"},
    {"latin": "l", "bats":  "ლ"},
    {"latin": "m", "bats":  "მ"},
    {"latin": "n", "bats":  "ნ"},
    {"latin": "o", "bats":  "ო"},
    {"latin": "p'", "bats":  "პ"},
    {"latin": "pw", "bats":  "ფჺ"},    # {"latin": "pw", "bats":  "ფჰჺ"},
    {"latin": "p", "bats":  "ფ"},
    {"latin": "q'", "bats":  "ყ"},
    {"latin": "q", "bats":  "ჴ"},
    {"latin": "r", "bats":  "რ"},
    {"latin": "shw", "bats":  "შჺ"},   # {"latin": "shw", "bats":  "შჰჺ"},
    {"latin": "sh", "bats":  "შ"},
    {"latin": "sw", "bats":  "სჺ"},    # {"latin": "sw", "bats":  "სჰჺ"},
    {"latin": "s", "bats":  "ს"},
    {"latin": "t'", "bats":  "ტ"},
    {"latin": "tw", "bats":  "თჺ"},    # {"latin": "tw", "bats":  "თჰჺ"},
    {"latin": "t", "bats":  "თ"},
    {"latin": "u", "bats":  "უ"},
    {"latin": "v", "bats":  "ვ"},
    {"latin": "w", "bats":  "ჺ"},
    {"latin": "x", "bats":  "ხ"},
    {"latin": "zh", "bats":  "ჟ"},
    {"latin": "z", "bats":  "ზ"},
    {"latin": "'", "bats":  "ჸ"}
    ]

trans_batsbi2 = [
    {"latin": "aa", "bats": "ა’"},
    {"latin": "a", "bats": "ა"},
    {"latin": "b", "bats":  "ბ"},
    {"latin": "ch'", "bats":  "ჭ"},
    {"latin": "chw", "bats":  "ჩჰ’"},
    {"latin": "ch", "bats":  "ჩ"},
    {"latin": "c'", "bats":  "წ"},
    {"latin": "cw", "bats":  "ცჰ’"},
    {"latin": "c", "bats":  "ც"},
    {"latin": "d", "bats":  "დ"},
    {"latin": "ee", "bats":  "ე’"},
    {"latin": "e", "bats":  "ე"},
    {"latin": "gh", "bats":  "ღ"},
    {"latin": "g", "bats":  "გ"},
    {"latin": "hw", "bats":  "ჰ’"},
    {"latin": "h", "bats":  "ჰ"},
    {"latin": "ii", "bats":  "ი’"},
    {"latin": "i", "bats":  "ი"},
    {"latin": "j", "bats":  "ჲ"},
    {"latin": "k'", "bats":  "კ"},
    {"latin": "kw", "bats":  "ქჰ’"},
    {"latin": "k", "bats":  "ქ"},
    {"latin": "lh", "bats":  "ლ’"},
    {"latin": "l", "bats":  "ლ"},
    {"latin": "m", "bats":  "მ"},
    {"latin": "n", "bats":  "ნ"},
    {"latin": "oo", "bats":  "ო’"},
    {"latin": "o", "bats":  "ო"},
    {"latin": "p'", "bats":  "პ"},
    {"latin": "pw", "bats":  "ფჰ’"},
    {"latin": "p", "bats":  "ფ"},
    {"latin": "q'", "bats":  "ყ"},
    {"latin": "q", "bats":  "ჴ"},
    {"latin": "r", "bats":  "რ"},
    {"latin": "shw", "bats":  "შჰ’"},
    {"latin": "sh", "bats":  "შ"},
    {"latin": "sw", "bats":  "სჰ’"},
    {"latin": "s", "bats":  "ს"},
    {"latin": "t'", "bats":  "ტ"},
    {"latin": "tw", "bats":  "თჰ’"},
    {"latin": "t", "bats":  "თ"},
    {"latin": "uu", "bats":  "უ’"},
    {"latin": "u", "bats":  "უ"},
    {"latin": "v", "bats":  "ვ"},
    {"latin": "w", "bats":  "ჵ"},
    {"latin": "x", "bats":  "ხ"},
    {"latin": "zh", "bats":  "ჟ"},
    {"latin": "z", "bats":  "ზ"},
    {"latin": "'", "bats":  "ჸ"}
    ]


# ================== General helper functions =============================
def get_error_message():
    arInfo = sys.exc_info()
    if len(arInfo) == 3:
        sMsg = str(arInfo[1])
        if arInfo[2] != None:
            sMsg += " at line " + str(arInfo[2].tb_lineno)
        return sMsg
    else:
        return ""

def Status( msg):
    # Just print the message
    print(msg, file=sys.stderr)

def DoError(msg, bExit = False):
    # get the message
    sErr = get_error_message()
    # Print the error message for the user
    print("Error: {}\nSystem:{}".format(msg, sErr), file=sys.stderr)
    # Is this a fatal error that requires exiting?
    if (bExit):
        sys.exit(2)
    # Otherwise: return the string that has been made
    return msg


# ----------------------------------------------------------------------------------
# Name :    main
# Goal :    Main body of the function
# History:
# 31/jan/2019    ERK Created
# ----------------------------------------------------------------------------------
def main(prgName, argv) :
    flInput = ''        # input file name: XML with author definitions
    flOutput = ''       # output file name
    method = 'test1'    # Method used

    try:
        sSyntax = prgName + ' -i <Latin text> -o <Batsbi text>'
        # get all the arguments
        try:
            # Get arguments and options
            opts, args = getopt.getopt(argv, "hi:o:m:", ["-ifile=", "-ofile", "method"])
        except getopt.GetoptError:
            print(sSyntax)
            sys.exit(2)
        # Walk all the arguments
        for opt, arg in opts:
            if opt in ("-h", "--help"):
                print(sSyntax)
                sys.exit(0)
            elif opt in ("-i", "--ifile"):
                flInput = arg
            elif opt in ("-o", "--ofile"):
                flOutput = arg
            elif opt in ("-m", "--method"):
                method = arg
        # Check if all arguments are there
        if (flInput == '' or flOutput == ''):
            DoError(sSyntax)

        # Continue with the program
        Status('Input is "' + flInput + '"')
        Status('Output is "' + flOutput + '"')
        Status('Method: "' + method + '"')

        oArgs = dict(input=flInput, output=flOutput, method=method)

        # Call the function that actually does the work
        if not latin2batsbi(oArgs):
            DoError("Could not complete conversion", True)

        Status("Ready")
    except:
        DoError("main")


# ----------------------------------------------------------------------------------
# Name :    latin2batsbi
# Goal :    Read the authors from the XML intput file
# History:
# 16/nov/2020    ERK Created
# ----------------------------------------------------------------------------------
def latin2batsbi(oArgs):
    """Read the CorpusSearch results and convert into Excel"""

    # Defaults
    flInput = ""
    flOutput = ""
    method = "test1"
    
    try:
        # Recover the arguments
        if "input" in oArgs: flInput = oArgs["input"]
        if "output" in oArgs: flOutput = oArgs["output"]
        if "method" in oArgs: method = oArgs['method']

        trans_batsbi = trans_batsbi1 if method == "test1" else trans_batsbi2

        # Check input file
        if not os.path.isfile(flInput):
            Status("Please specify an input FILE")
            return False
        
        # Read the text file into an array
        with open(flInput, "r", encoding="utf-8") as fd:
            lst_input = fd.readlines()

        # Go through all the lines and emend them
        lst_output = []
        for line in lst_input:
            # Break the line into words
            words = line.split(" ")
            words_out = []
            for word in words:
                # Convert to lower-case
                word = word.lower()
                # Visit all characters of the word
                letter = []
                idx = 0
                while idx < len(word):
                    bFound = False
                    # Action depends on the character
                    for oTrans in trans_batsbi:
                        k = oTrans['latin']
                        trans = oTrans['bats']
                        ln = len(k)
                        if word[idx:idx+ln] == k:
                            letter.append(trans)
                            idx += ln
                            bFound = True
                            break
                    if not bFound:
                        letter.append(word[idx:idx+1])
                        idx += 1
                # Add to output
                words_out.append("".join(letter))

            # COmbine the words again
            line_out = " ".join(words_out)
            lst_output.append(line_out)

        # Save the output
        with open(flOutput, "w", encoding="utf-8") as fd:
            fd.writelines(lst_output)


        # Return positively
        return True
    except:
        sMsg = get_error_message()
        DoError("latin2batsbi")
        return False


# ----------------------------------------------------------------------------------
# Goal :  If user calls this as main, then follow up on it
# ----------------------------------------------------------------------------------
if __name__ == "__main__":
    # Call the main function with two arguments: program name + remainder
    main(sys.argv[0], sys.argv[1:])
