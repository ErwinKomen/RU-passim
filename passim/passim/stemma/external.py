"""
External C-code to be called from python
"""

import platform
import tempfile
import os
from ctypes import *

from passim.settings import MEDIA_ROOT
from passim.utils import ErrHandle
from passim.stemma.convert import ps2svg_string



def myfitch(distNames, distMatrix):
    """
    Given an array of names and a matrix, execute the FITCH algorithm.
    This returns a tree (newick style).
    """

    def get_dist_string(lNames, lMatrix):
        """Combine names and matrix into string
        
        Example of what we get:
        - lNames = ['aaa', 'aab', 'aac', 'aad']
        - lMatrix = [ [0],
                      [1.3, 0],
                      [5.1, 6.4, 0],
                      [7.8, 1.4, 3.9, 0],
                    ]
        """

        lHtml = []
        oErr = ErrHandle()
        sBack = ""
        try:
            # First the size
            iSize = len(lNames)
            lHtml.append("{}".format(iSize))
            # Iterate
            for idx in range(0, iSize):
                lRow = []
                # Start out with the name
                lRow.append("{}".format(lNames[idx]))
                # Add as many spaces as needed
                lRow.append(' ' * (10 - len(lRow[0])))
                # Add the information from this row
                for idy in range(0, idx):
                    lRow.append("{:5.1f} ".format(lMatrix[idx][idy]))
                lHtml.append("".join(lRow))
            # Combine into back
            sBack = "\n".join(lHtml)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_dist_string")
        return sBack

    sBack = ""
    oErr = ErrHandle()
    try:
        # Convert the names + matrix into a string for C-fitch
        sInput = get_dist_string(distNames, distMatrix)
        # Think of a name where to save this
        with open("{}_inp.txt".format(tempfile.NamedTemporaryFile(dir=MEDIA_ROOT, mode="w").name), "w") as f:
            inputfile = os.path.abspath(f.name)
            f.write(sInput)
        outputfile = inputfile.replace("_inp.txt", "_out.txt")
        outtreefile = inputfile.replace("_inp.txt", "_tre.txt")

        # Identify the library, depending on the platform
        if platform.system() == "Windows":
            sLibrary = "d:/data files/vs2010/projects/RU-passim/stemmac/fitch.dll"
        else:
            sLibrary = "/var/www/passim/live/repo/stemmac/bin/fitch.so"
        do_fitch = cdll.LoadLibrary(sLibrary).do_fitch
        do_fitch.restype = c_bool  # C-type boolean
        do_fitch.argtypes = [POINTER(c_char),POINTER(c_char),POINTER(c_char)]

        response = do_fitch(inputfile.encode(), outputfile.encode(), outtreefile.encode())

        # Is the response okay?
        if response:
            # Response is okay: read the result
            with open(outtreefile, "r") as f:
                # Not sure if any string conversion needs to take place...
                sBack = f.read()
        
    except:
        msg = oErr.get_error_message()
        oErr.DoError("myfitch")

    # Return what we have gathered
    return sBack


def mydrawtree(sTree):
    """
    Given a newick type tree in a string, use the DRAWTREE algorithm 
      to convert this into a SVG
    """

    sBack = ""
    oErr = ErrHandle()
    try:
        treefile = None

        # Think of a name where to save this
        with open("{}_tree.txt".format(tempfile.NamedTemporaryFile(dir=MEDIA_ROOT, mode="w").name), "w") as f:
            treefile = os.path.abspath(f.name)
            f.write(sTree)
        # Determine the POSTSCRIPT file name
        outputfile = treefile.replace("_tree.txt", "_tree.ps")

        # The fontfile should be taken from media stemma
        fontfile = os.path.abspath(os.path.join(MEDIA_ROOT, "stemma", "fontfile"))


        # Identify the library, depending on the platform
        if platform.system() == "Windows":
            sLibrary = "d:/data files/vs2010/projects/RU-passim/stemmac/drawtree.dll"
        else:
            sLibrary = "/var/www/passim/live/repo/stemmac/bin/drawtree.so"
        psdrawtree = cdll.LoadLibrary(sLibrary).psdrawtree
        psdrawtree.restype = c_bool  # C-type boolean
        psdrawtree.argtypes = [POINTER(c_char),POINTER(c_char),POINTER(c_char)]

        response = psdrawtree(treefile.encode(), fontfile.encode(), outputfile.encode())

        # Is the response okay?
        if response:
            sPostscript = ""
            # Response is okay: read the result
            with open(outputfile, "r") as f:
                # Not sure if any string conversion needs to take place...
                sPostscript = f.read()

            # Now the postscript needs to be converted into SVG
            sSvg = ps2svg_string(sPostscript)
            # This will be returned
            sBack = sSvg
    except:
        msg = oErr.get_error_message()
        oErr.DoError("mydrawtree")

    # Return what we have gathered
    return sBack

