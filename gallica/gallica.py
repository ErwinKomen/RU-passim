"""
Decode the list of author names from LLTA

This version created by Erwin R. Komen
Date: 31/jan/2019
"""

import sys, getopt, os.path, importlib
import os, sys, math
import csv, json
import xml.etree.ElementTree as ET
import xmltodict

# My own stuff
import utils

# Make available error handling
errHandle = utils.ErrHandle()

try:
    from api.search_api import Search
except:
    sMsg = errHandle.get_error_message()
    errHandle.DoError("Cannot import search_api")
    
def check_int(s):
    s = str(s)
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()


# ----------------------------------------------------------------------------------
# Name :    main
# Goal :    Main body of the function
# History:
# 31/jan/2019    ERK Created
# Use Xpath to get to all the records
# mlns:ns7="http://gallica.bnf.fr/namespaces/gallica/" 
# xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" 
# xmlns:onix_dc="http://bibnum.bnf.fr/NS/onix_dc/" 
# xmlns:srw="http://www.loc.gov/zing/srw/" 
# xmlns:onix="http://www.editeur.org/onix/2.1/reference/" 
# xmlns:dc="http://purl.org/dc/elements/1.1/"
# Location:
# xmldoc['srw:searchRetrieveResponse']['srw:records']['srw:record'][9]['srw:recordData']['oai_dc:dc']
# ----------------------------------------------------------------------------------
def main(prgName, argv) :
    flInput = ''        # input file name: XML with author definitions
    flOutput = ''       # output file name
    lExtracted = []
    iChunkSize = 50
    keywords = ['sermon', 'sermons', 'homélie', 'homélies', 'homéliaire', 'homiliaire', 'liturgie', 'liturgique', 'sermonnaire', 'lectionnaire', 'bréviaire']
    ns = {'srw': "http://www.loc.gov/zing/srw/",
            'dc': "http://purl.org/dc/elements/1.1/",
            'oai_dc': "http://www.openarchives.org/OAI/2.0/oai_dc/"}

    try:
        # Set output name
        flOutput = "extracted.json"
        # Search for a collection of keywords -- Find out how many there are
        startRecord = "1"
        numRecords = "1"
        root = Search.search(startRecord, numRecords,  keywords)

        # Get the number of records
        iCount = int(root.find("srw:numberOfRecords", ns).text)

        # Iterate over the number of results in chunks of max 50
        iChunks = math.floor( iCount / iChunkSize)
        for iChunk in range(iChunks):
            iStart = iChunk * iChunkSize
            root = Search.search(str(iStart), str(iChunkSize), keywords)

            # Find out how many we found this time
            iCount = int(root.find("srw:numberOfRecords", ns).text)

            lRecord = root.findall('./srw:records/srw:record', ns)
            itemnum = len(lRecord)
            for record in lRecord:
                # Reset the data
                data = {'latin': False, 'dateStart': -1, 'dateEnd': -1}
                # Iterate over the DC data in this record
                lData = record.findall("./srw:recordData/oai_dc:dc/*", ns)
                for oData in lData:
                    tag = oData.tag
                    if "}" in tag: tag = tag.split("}", 1)[1]
                    sText = oData.text
                    if tag == "language" and sText == "lat":
                        data['latin'] = True
                    elif tag == "date":
                        # Is this an integer?
                        if check_int(sText):
                            # Yes, integer
                            iDate = int(sText)
                            data['dateStart'] = iDate
                            data['dateEnd'] = iDate
                        elif "-" in sText:
                            arDate = sText.split("-")
                            if check_int(arDate[0]) and check_int(arDate[1]):
                                data['dateStart'] = int(arDate[0])
                                data['dateEnd'] = int(arDate[1])
                            else:
                                data['dateString'] = sText
                        else:
                            data['dateString'] = sText

                    else:
                        # Check if there is already an item in there
                        if tag in data:
                            oldData = data[tag]
                            if isinstance(oldData, str):
                                # This used to be one string, now we get an addition
                                lText = [ oldData ]
                            else:
                                lText = oldData
                            lText.append(sText)
                            data[tag] = lText
                        else:
                            data[tag] = sText
                # Only actually append if the data is LATIN
                if data['latin']:
                    lExtracted.append(data)


        # Save output
        with open(flOutput, "w", encoding="utf-8-sig") as fp:
            json.dump(lExtracted, fp, indent=2)
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
