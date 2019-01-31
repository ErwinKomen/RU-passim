"""
Decode the list of author names from LLTA

This version created by Erwin R. Komen
Date: 31/jan/2019
"""

import sys, getopt, os.path, importlib
import os, sys
import csv, json
import xml.etree.ElementTree as ET

# My own stuff
import utils

# Make available error handling
errHandle = utils.ErrHandle()

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
    sSyntax = prgName + ' -i <author XML input file> -o <output file>'
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
    oArgs = {'input': flInput,
             'output': flOutput}
    if (not read_authors(oArgs)) :
      errHandle.DoError("Could not complete")
      return False
    
      # All went fine  
    errHandle.Status("Ready")
  except:
    # act
    errHandle.DoError("main")
    return False

# ----------------------------------------------------------------------------------
# Name :    read_authors
# Goal :    Read the authors from the XML intput file
# History:
# 31/jan/2019    ERK Created
# ----------------------------------------------------------------------------------
def read_authors(oArgs):
    """Read author names"""

    # Defaults
    flInput = ""
    flOutput = ""
    lAuthor = []

    count = 0

    try:
        # Recover the arguments
        if "input" in oArgs: flInput = oArgs["input"]
        if "output" in oArgs: flOutput = oArgs["output"]

        # Check input file
        if not os.path.isfile(flInput):
            errHandle.Status("Please specify an input FILE")
            return False

        # Read the input file as XML
        tree = ET.parse(flInput)
        # Get to the root: <table>
        root = tree.getroot()
        # Get to <tbody>
        for tbody in root.iter('tbody'):
            # Iterate over the <tr> elements
            for tr in tbody.iter('tr'):
                # Iterate over all the <td> elements
                for td in tr.iter('td'):
                    # Check for attribute class=auth
                    sClass = td.get('class')
                    if sClass != None and sClass == "auth":
                        # This is an author cell
                        sText = td.text
                        if sText == None:
                            # get to the <b> part
                            for b in td.iter('b'):
                                sText = b.text
                                if sText == None:
                                    for i in b.iter('i'):
                                        sText = i.text
                        # This is an author...
                        lAuthor.append(sText)

        # Write the list of author names
        sJsonText = json.dumps(lAuthor, indent=2)
        with open(flOutput, "w", encoding="utf-8") as fo:
            fo.write(sJsonText)

        # Return positively
        return True
    except:
        sMsg = errHandle.get_error_message()
        errHandle.DoError("read_authors")
        return False



# ----------------------------------------------------------------------------------
# Goal :  If user calls this as main, then follow up on it
# ----------------------------------------------------------------------------------
if __name__ == "__main__":
  # Call the main function with two arguments: program name + remainder
  main(sys.argv[0], sys.argv[1:])
