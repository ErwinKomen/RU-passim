"""
Find library names in cities in particular countries.
Combine the output into a grand list

This version created by Erwin R. Komen
Date: 14/jan/2019

Usage:
    python library.py -i "d:/data files/passim/data/LLTA_Names.xml" -o "d:/data files/passim/data/authors.json"

"""

import sys, getopt, os.path, importlib
import os, sys
import csv, json
# import yaml
# import ast
import requests
# import demjson

# My own stuff
import utils

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
  dirCity = ''        # Directory containing city definition files city_info_NUM.json
  flOutput = ''       # output file name

  try:
    sSyntax = prgName + ' -i <country input file> -c <city directory> -o <output file>'
    # get all the arguments
    try:
      # Get arguments and options
      opts, args = getopt.getopt(argv, "hi:c:o:", ["-ifile=", "-cdir", "-ofile"])
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
      elif opt in ("-c", "--cdir"):
        dirCity = arg
    # Check if all arguments are there
    if (flInput == '' or flOutput == '' or dirCity == ''):
      errHandle.DoError(sSyntax)

    # Continue with the program
    errHandle.Status('Input is "' + flInput + '"')
    errHandle.Status('Cities is "' + dirCity + '"')
    errHandle.Status('Output is "' + flOutput + '"')

    # Call the function that does the job
    oArgs = {'input': flInput,
             'cities': dirCity,
             'output': flOutput}
    if (not create_libraries(oArgs)) :
      errHandle.DoError("Could not complete")
      return False
    
      # All went fine  
    errHandle.Status("Ready")
  except:
    # act
    errHandle.DoError("main")
    return False

# ----------------------------------------------------------------------------------
# Name :    create_libraries
# Goal :    Fetch and create library definitions with their city and country
# History:
# 14/jan/2019    ERK Created
# ----------------------------------------------------------------------------------
def create_libraries(oArgs):
    """Create library definitions"""

    # Defaults
    flInput = ""
    flOutput = ""
    dirCity = ""
    CNRS_VILLE = "http://medium-avance.irht.cnrs.fr/External/villeforpays"
    CNRS_LIB = "http://medium-avance.irht.cnrs.fr/External/etablissementforville"

    count = 0

    try:
        # Recover the arguments
        if "input" in oArgs: flInput = oArgs["input"]
        if "cities" in oArgs: dirCity = oArgs["cities"]
        if "output" in oArgs: flOutput = oArgs["output"]

        # Check input file
        if not os.path.isfile(flInput):
            errHandle.Status("Please specify an input FILE")
            return False
        # Check city directory
        if not os.path.isdir(dirCity):
            errHandle.Status("Please specify a directory for the cities")
            return False

        # Prepare entries
        lEntry = []

        # Read the cities
        with open(flInput, "r", encoding="utf-8-sig") as fi:
            data = fi.read()
            lCountry = json.loads(data)

        # Walk all the cities
        for oCountry in lCountry:
            # Find the correct city information file
            country_id = oCountry['idPaysEtab']
            country_en = oCountry['CountryEN']
            fCity = os.path.abspath( os.path.join(dirCity, "city_info_{}.json".format(country_id)))
            # Check
            if not os.path.exists(fCity) or not os.path.isfile(fCity):
                errHandle.Status("Cannot find file: {} for country {}".format(fCity, country_en))
                return False

            # DEBUGGING
            if count > 10:
                break

            # Retrieve the city information
            lCity = []
            #with open(fCity, "r", encoding="utf-8") as fc:
            #    # Interpret the data with wingle quotes
            #    data = fc.read()
            #    lCity = demjson.decode(data)    
            with open(fCity, "r", encoding="utf-8") as fc:
                lCity = json.load(fc)

            # Walk all the cities of this country
            if 'items' in lCity:
                for oCity in lCity['items']:
                    # Get the name and the value of the city
                    city = oCity['name']
                    city_id = oCity['value']

                    # Show where we are
                    errHandle.Status("{}/{}".format(country_en, city))

                    # Get the libraries for this city
                    if city != "" and city_id != "":
                        # Prepare the data
                        # oData = 'idVilleEtab={}'.format(city_id)
                        # url = CNRS_LIB + "?" + json.dumps(oData)
                        url = "{}?idVilleEtab={}".format(CNRS_LIB, city_id)
                        try:
                            r = requests.get(url)
                        except:
                            sMsg = errHandle.get_error_message()
                            errHandle.DoError("Request problem")
                            return False
                        if r.status_code == 200:
                            # Return positively
                            # OLDEST: reply = json.loads(r.text.replace("\t", " "))
                            # OLD: reply = demjson.decode(r.text.replace("\t", " "))
                            sText = r.text.replace("\t", "")
                            reply = json.loads(sText)
                            if 'items' in reply:
                                libraries = reply['items']
                                for oLibrary in libraries:
                                    # Get the values of this library
                                    library = oLibrary['name']
                                    bBracketed = False
                                    if library.startswith("["):
                                        library = library.strip("[]")
                                        bBracketed = True
                                    library_id = oLibrary['value']
                                    if library != "" and library_id != "":
                                        # Store the information of library - city - country
                                        oEntry = {}
                                        oEntry['library'] = library
                                        oEntry['library_id'] = library_id
                                        oEntry['bracketed'] = bBracketed
                                        oEntry['city'] = city
                                        oEntry['city_id'] = city_id
                                        oEntry['country_fr'] = oCountry['CountryFR']
                                        oEntry['country_en'] = oCountry['CountryEN']
                                        oEntry['country_id'] = oCountry['idPaysEtab']
                                        # Add to entries
                                        lEntry.append(oEntry)
                                        count += 1


        # Write the list
        sJsonText = json.dumps(lEntry, indent=2)
        with open(flOutput, "w", encoding="utf-8") as fo:
            fo.write(sJsonText)

        # Return positively
        return True
    except:
        sMsg = errHandle.get_error_message()
        errHandle.DoError("create_libraries")
        return False



# ----------------------------------------------------------------------------------
# Goal :  If user calls this as main, then follow up on it
# ----------------------------------------------------------------------------------
if __name__ == "__main__":
  # Call the main function with two arguments: program name + remainder
  main(sys.argv[0], sys.argv[1:])
