"""
Convert the latin chechen interlinear line (FLEX) into phonemic script

Input:  "FlexInterlinear" xml
Output: MS Word XML (to be opened by MS word)

This version created by Erwin R. Komen
Date: 8/jun/2023

Example:
    python interche_epub.py  -m "test1" 
                        -i "d:/data files/elpash/stories.xml" 
                        -o "d:/data files/elpash/stories_phon.xml"
"""

import sys, getopt, os.path, importlib
import re, json
from lxml import etree
from django.template.loader import render_to_string
import jinja2
from jinja2 import Environment, FileSystemLoader

# import settings

trans_phonemic = [
    {"latin": "ae", "phoneme": "æ"},
    {"latin": "a", "phoneme": "a"},
    {"latin": "b", "phoneme":  "b"},
    {"latin": "ch'", "phoneme":  "ʧ’"},
    {"latin": "chw", "phoneme":  "ʧħ"}, 
    {"latin": "ch", "phoneme":  "ʧ"},
    {"latin": "c'", "phoneme":  "ʦ’"},
    {"latin": "cw", "phoneme":  "ʦħ"},
    {"latin": "c", "phoneme":  "ʦ"},
    {"latin": "d", "phoneme":  "d"},
    {"latin": "ev", "phoneme":  "ey"},
    {"latin": "e", "phoneme":  "e"},
    {"latin": "gh", "phoneme":  "ʁ"},
    {"latin": "g", "phoneme":  "g"},
    {"latin": "hhw", "phoneme":  "ħħ"}, #
    {"latin": "hw", "phoneme":  "ħ"}, #
    {"latin": "h", "phoneme":  "h"},
    {"latin": "i", "phoneme":  "i"},
    {"latin": "j", "phoneme":  "j"},
    {"latin": "k'", "phoneme":  "k’"},
    {"latin": "k", "phoneme":  "k"},
    {"latin": "l", "phoneme":  "l"},
    {"latin": "m", "phoneme":  "m"},
    {"latin": "n", "phoneme":  "n"},
    {"latin": "ov", "phoneme":  "ou"},
    {"latin": "o", "phoneme":  "o"},
    {"latin": "p'", "phoneme":  "p’"},
    {"latin": "pw", "phoneme":  "pħ"},
    {"latin": "p", "phoneme":  "p"},
    {"latin": "q'", "phoneme":  "q’"},
    {"latin": "q", "phoneme":  "q"},
    {"latin": "rh", "phoneme":  "r̥"},
    {"latin": "r", "phoneme":  "r"},
    {"latin": "shw", "phoneme":  "ʃħ"}, 
    {"latin": "ssh", "phoneme":  "ʃʃ"},
    {"latin": "sh", "phoneme":  "ʃ"},
    {"latin": "sw", "phoneme":  "sħ"},  
    {"latin": "s", "phoneme":  "s"},
    {"latin": "t'", "phoneme":  "t’"},
    {"latin": "tw", "phoneme":  "tħ"},  
    {"latin": "t", "phoneme":  "t"},
    {"latin": "u", "phoneme":  "u"},
    {"latin": "v", "phoneme":  "v"},
    {"latin": "w", "phoneme":  "ʕ"},
    {"latin": "x", "phoneme":  "χ"},
    {"latin": "zh", "phoneme":  "ʒ"},
    {"latin": "z", "phoneme":  "z"},
    {"latin": "'", "phoneme":  "ʔ"}
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
        sSyntax = prgName + ' -i <FLEX interlinear> -o <FLEX interlinear>'
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

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

        # Call the function that actually does the work
        if not interlinear2phonemic(oArgs):
            DoError("Could not complete conversion", True)

        Status("Ready")
    except:
        DoError("main")


# ----------------------------------------------------------------------------------
# Name :    interlinear2phonemic
# Goal :    Convert the FLEX interlinear XML into phonemic
# History:
# 16/nov/2020    ERK Created
# ----------------------------------------------------------------------------------
def interlinear2phonemic(oArgs):
    """Read the FLEX MS-word and convert the ce-Latn parts into IPA"""

    # Defaults
    flInput = ""
    flOutput = ""
    method = "test1"
    rBreak =re.compile( r'[\-\:\.]')
    template_name = "templates/flexword.xml"
    namespaces = {'m': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
                  'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    try:
        # Recover the arguments
        if "input" in oArgs: flInput = oArgs["input"]
        if "output" in oArgs: flOutput = oArgs["output"]
        if "method" in oArgs: method = oArgs['method']



        trans_phon = trans_phonemic

        # Check input file
        if not os.path.isfile(flInput):
            Status("Please specify an input FILE")
            return False

        namespacestyle = 'xmlns:m="{}" xmlns:w="{}"'.format(namespaces['m'], namespaces['w'])
        
        # Read the text file into an array
        xmldoc = etree.parse(flInput)

        # Highest level: <interlinear-text>
        interlinear_texts = []
        docpr_id = 1
        intl_texts = xmldoc.xpath("//interlinear-text")
        for intl_text in intl_texts:
            oText = {}
            # Get the title, comment
            title = intl_text.xpath("./item[@type='title']")[0].text
            comment = intl_text.xpath("./item[@type='comment']")[0].text

            oText['title'] = title
            oText['comment'] = comment
            oText['paragraphs'] = []

            paragraphs = intl_text.xpath("./descendant::paragraph")
            for paragraph in paragraphs:
                oParagraph = dict(phrases=[])
                # One 'paragraph' is a set of sentences
                sentences = paragraph.xpath("./child::phrases/child::word")
                for sentence in sentences:
                    segnum = sentence.xpath("./item[@type='segnum']")[0].text
                    oItem = dict(part_orig=segnum, part_trans="", part_morph="", docpr_id=docpr_id)
                    docpr_id += 1
                    freeform = sentence.xpath("./item[@type='gls']")[0].text
                    oPhrase = dict(segnum=oItem, freeform=freeform, items=[])
                    words = sentence.xpath("./descendant::word")
                    for word in words:
                        word_type = word.xpath("./item")[0].attrib['type']
                        if word_type == "txt":
                            part_orig = word.xpath("./item[@lang='ce']")[0].text
                            part_trans = word.xpath("./item[@lang='ce-Latn']")[0].text
                            part_morph = word.xpath("./item[@lang='en']")[0].text

                            # Convert the latin che word
                            part_trans = convert_word(part_trans)
                        elif word_type == "punct":
                            part_orig = word.xpath("./item[@lang='ce']")[0].text
                            part_trans = ""
                            part_morph = ""

                        # Create the 'item'
                        oItem = dict(part_orig=part_orig, part_trans=part_trans, 
                                     part_morph=part_morph, docpr_id=docpr_id)
                        docpr_id += 1
                        oPhrase['items'].append(oItem)
                    oParagraph['phrases'].append(oPhrase)
                # Only append [oParagraph], if it has contents
                if len(oParagraph['phrases']) > 0:
                    oText['paragraphs'].append(oParagraph)

            interlinear_texts.append(oText)
        
        sResult = json.dumps(interlinear_texts, indent=2)
        iStop = 1

        # Now use this as input to the [flexword.xml]
        context = dict(interlinear_texts=interlinear_texts)

        # Method #1
        # sResult = render_to_string(template_name, context, None)

        # Method #2: jinja-style
        environment = Environment(loader=FileSystemLoader("templates/"))
        template = environment.get_template("flexword.xml")
        sResult = template.render(context)
        
        # Find all the Interlinear lines in [ce-Latn]
        phoneme_lines = xmldoc.xpath("//m:t[parent::m:r[child::w:rPr/child::w:rStyle[contains(@w:val, 'ce-Latn')]]]", namespaces=namespaces)
        for el in phoneme_lines:
            # Get the text of this line
            line = el.text
            # Convert
            el.text = convert_word(line)

        # Find all [Interlin Word Gloss en] lines
        gloss_lines = xmldoc.xpath("//m:e[descendant::w:rStyle[contains(@w:val, 'Word Gloss')]]", namespaces=namespaces)
        for gloss in gloss_lines:
            # Get the text  of this gloss
            text_lst = gloss.xpath("./descendant::m:t", namespaces=namespaces)
            gloss_txt = text_lst[0].text
            Status("Gloss = [{}]".format(gloss_txt))

            # Split on period
            # OLD gloss_parts = gloss_txt.split(".")

            # Find a list of all splittable elements:'-','.'
            gloss_break = rBreak.findall(gloss_txt)
            gloss_parts = rBreak.split(gloss_txt)

            # Remove the current <m:r> child
            for mr in gloss.getchildren():
                gloss.remove(mr)

            # Walk the parts and add children respecively
            for idx, gloss_part in enumerate(gloss_parts):
                style = "Interlin Word Gloss en"
                if gloss_part[-1] != gloss_part[-1].lower():
                    gloss_part = gloss_part.lower()
                    style = "Interlin Morpheme Gloss en"
                # Add the period for anything but the first element
                if idx > 0: 
                    # gloss_part = "." + gloss_part
                    gloss_part = gloss_break[idx-1] + gloss_part
                # Create a child
                child_mr = etree.fromstring('<m:r {}><m:rPr><m:nor /></m:rPr><w:rPr><w:rStyle w:val="{}" /></w:rPr><m:t>{}</m:t></m:r>'.format(
                    namespacestyle, style, gloss_part))
                # Add the child to the <m:e> gloss
                gloss.append(child_mr)

        # Find all the <m:rSp m:val="3" /> instances and change the value into 2 (vertical spacing within formula's)
        vert_spacing = xmldoc.xpath("//m:rSp[@m:val]", namespaces=namespaces)
        for vert in vert_spacing:
            # Change the value of the m:val attribute
            vert.attrib['{' + namespaces['m'] + '}val'] = '2'

        # Write the result to the new XML file
        str_output = etree.tostring(xmldoc, xml_declaration=True, encoding="utf-8", pretty_print=True).decode("utf-8")
        with open(flOutput, "w", encoding="utf-8") as fp:
            fp.write(str_output)

        # Return positively
        return True
    except:
        sMsg = get_error_message()
        DoError("interlinear2phonemic")
        return False

def convert_word(word):

    sBack = ""
    try:
        # Convert to lower-case
        word = word.lower()
        # Visit all characters of the word
        letter = []
        idx = 0
        while idx < len(word):
            bFound = False
            # Action depends on the character
            for oTrans in trans_phonemic:
                k = oTrans['latin']
                trans = oTrans['phoneme']
                ln = len(k)
                if word[idx:idx+ln] == k:
                    letter.append(trans)
                    idx += ln
                    bFound = True
                    break
            if not bFound:
                letter.append(word[idx:idx+1])
                idx += 1
        sBack = "".join(letter)
    except:
        sMsg = get_error_message()
        DoError("convert_word")
    return sBack



# ----------------------------------------------------------------------------------
# Goal :  If user calls this as main, then follow up on it
# ----------------------------------------------------------------------------------
if __name__ == "__main__":
    # Call the main function with two arguments: program name + remainder
    main(sys.argv[0], sys.argv[1:])
