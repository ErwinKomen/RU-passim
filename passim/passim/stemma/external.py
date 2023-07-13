"""
External C-code to be called from python
"""

import platform
import tempfile
import os
from ctypes import *

from passim.settings import MEDIA_ROOT
from passim.utils import ErrHandle


def myfitch(distNames, distMatrix):
    """
    Given an array of names and a matrix, execute the FITCH algorithm.
    This returns a tree.
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

