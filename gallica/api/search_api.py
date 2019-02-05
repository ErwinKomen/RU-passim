import urllib
import xml
import xmltodict
import xml.etree.ElementTree as ET
import requests
from utils import ErrHandle

# Full documentation for this API can be found on Gallica's site: http://api.bnf.fr/api-gallica-de-recherche


class Search(object):
    
    @staticmethod
    def search(startRecord, maxRecords, *args):
        """This function passes your queries, separated by commas, in addition to the record you'd like to start with. """

        oErr = ErrHandle()
        RECHERCHE_BASEURL = "https://gallica.bnf.fr/SRU"

        try:
            for arg in args:
                search_string = (', '.join('"' + item + '"' for item in arg))
      
            oData = {}
            oData['operation'] = 'searchRetrieve'
            oData['version'] = "1.2"
            # oData['query'] = "((dc.language any lat) and (gallica all {}))".format(search_string)
            oData['query'] = urllib.parse.quote("((dc.language any \"lat\" \"latin\") and (dc.type any \"manuscript\" \"manuscrit\") and (dc.title any {}))".format(search_string))
            oData['query'] = "((dc.language all \"lat\") and (dc.type all \"manuscrit\") and (notice any {}))".format(search_string)
            oData['query'] = "( (dc.language all \"lat\") and (dc.title adj \"latin\"))"
            oData['query'] = "( (dc.language all \"lat\") and (dc.source adj \"département des manuscrits\"))"
            oData['maximumRecords'] = maxRecords
            oData['startRecord'] = startRecord

            # Combine the data into an URL
            sData = ""
            for k,v in oData.items():
                if sData == "":
                    sData = "?"
                else:
                    sData = sData + "&"
                sData = sData + k + "=" + v
            url = RECHERCHE_BASEURL + sData

            print(url)

            attempts = 10
            bSuccess = False
            root = None
        except:
            oErr.DoError("Search/search error 1")
            return ""

        # set up a filename
        filename = "gallica_{}.xml".format(startRecord)

        while not bSuccess and attempts > 0:

            # Show progess if attempts are lower than 10
            if attempts < 10:
                print("Attempts left: {}".format(attempts))

            bHaveRequest = True
            try:
                r = requests.get(url)
            except:
                oErr.DoError("Search/search error 2")
                bHaveRequest = False

            # Action depends on what we receive
            if bHaveRequest and r.status_code == 200:
                # Read the content
                contents = r.text
                # contents = s.read()

                try:
                    # Write the contents to a local directory Gallica.xml
                    file = open(filename, 'w', encoding="utf-8-sig")
                    file.write(contents)
                    file.close()
            
                    # Open this file and parse it as xml
                    with open(filename, encoding="utf-8-sig") as xml:
                        # Read the text
                        sText = xml.read()

                    # Convert text to XML object
                    root = ET.fromstring(sText)
                    # Indicate we have it
                    bSuccess = True
                except:
                    oErr.DoError("Could not read the XML")
                    return ""
            else:
                oErr.Status("Site returns status: {}".format(r.status_code))
                # Keep track of attempts
                attempts -= 1

        if bSuccess:
            # return this document
            return root
        else:
            # Were not able to process the request
            oErr.DoError("Could not process the request")
            return ""
