"""
Test function to call psdrawtree

This version created by Erwin R. Komen
Date: 17/jul/2023

Usage:
    python stemmap.py -i "d:/etc/tree_erwin.txt" -o "d:/etc/tree_erwin_out.ps"

"""

import sys, getopt, os.path, importlib
import os, sys
import csv, json

# My own stuff
import utils
from drawtree import psdrawtree

# Make available error handling
errHandle = utils.ErrHandle()

# ----------------------------------------------------------------------------------
# Name :    main
# Goal :    Main body of the function
# History:
# 14/jan/2019    ERK Created
# ----------------------------------------------------------------------------------
def main(prgName, argv) :
    flInput = ''        # input file name: JSON with country definitions
    flOutput = ''       # output file name

    try:
        sSyntax = prgName + '  -i <tree file> -o <Postscript file>'
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
            errHandle.DoError(sSyntax)

        # Continue with the program
        errHandle.Status('Input is "' + flInput + '"')
        errHandle.Status('Output is "' + flOutput + '"')

        # Call the function that does the job
        oArgs = {'input': flInput, 'output': flOutput}
        if (not psdrawtree(oArgs)) :
            errHandle.DoError("Could not complete")
            return False
    
            # All went fine  
        errHandle.Status("Ready")
    except:
        # act
        errHandle.DoError("main")
    return False


# ----------------------------------------------------------------------------------
# Goal :  If user calls this as main, then follow up on it
# ----------------------------------------------------------------------------------
if __name__ == "__main__":
  # Call the main function with two arguments: program name + remainder
  main(sys.argv[0], sys.argv[1:])
