"""
Convert HUWA signatures JSON

This version created by Erwin R. Komen
Date: 1/jun/2022
"""

import sys, getopt, os.path, importlib
import json
import copy

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

    try:
        sSyntax = prgName + ' -i <huwasig input file> -o <huwasig output file>'
        # get all the arguments
        try:
            # Get arguments and options
            opts, args = getopt.getopt(argv, "hi:o:", ["-ifile=", "-ofile"])
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
        # Check if all arguments are there
        if (flInput == '' or flOutput == ''):
            DoError(sSyntax)

        # Continue with the program
        Status('Input is "' + flInput + '"')
        Status('Output is "' + flOutput + '"')

        oArgs = dict(input=flInput, output=flOutput)

        # Call the function that actually reads the CorpusSearch file
        if not convert_huwa_signatures(oArgs):
            DoError("Could not complete reading results", True)

        Status("Ready")
    except:
        DoError("main")

def convert_huwa_signatures(oArgs):
    """Convert HUWA signature conversion definition"""

    # Defaults
    flInput = ""
    flOutput = ""
    data_in = []
    data_out = []
    bResult = True

    try:
        # Recover the arguments
        if "input" in oArgs: flInput = oArgs["input"]
        if "output" in oArgs: flOutput = oArgs["output"]

        # Check input file
        if not os.path.isfile(flInput):
            errHandle.Status("Please specify an input FILE")
            return False
        
        # Read the text file into an array
        with open(flInput, "r", encoding="utf-8") as fd:
            data_in = json.load(fd)

        for oEntry in data_in:
            huwa = oEntry.get("HUWA")
            gryson = oEntry.get("GRYSON")
            clavis = oEntry.get("CLAVIS")
            other = oEntry.get("Other code (PASSIM)")
            alt_huwa = oEntry.get("Alternate HUWA code")
            excl = oEntry.get("Exclusion")
            has_code = not ( gryson is None and clavis is None and other is None)
            if excl is None and has_code:
                oOut = dict(huwa=huwa, gryson=gryson, clavis=clavis, other=other)
                data_out.append(oOut)
                if not alt_huwa is None:
                    lst_alt = alt_huwa.split(";")
                    for sHuwa in lst_alt:
                        sHuwa = sHuwa.strip()
                        oAlt = copy.copy(oOut)
                        oAlt['huwa'] = sHuwa
                        data_out.append(oAlt)
        # Save the output
        with open(flOutput, "w", encoding="utf-8") as fd:
            json.dump(data_out, fd, indent=2)

        Status("Ready")

    except:
        DoError("main")
        bResult = False

    return bResult


# ----------------------------------------------------------------------------------
# Goal :  If user calls this as main, then follow up on it
# ----------------------------------------------------------------------------------
if __name__ == "__main__":
    # Call the main function with two arguments: program name + remainder
    main(sys.argv[0], sys.argv[1:])
