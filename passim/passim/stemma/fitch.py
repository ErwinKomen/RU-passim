"""
This is the Python equivalent of FITCH

"""
from passim.utils import ErrHandle

class MyFitch(Object):
    lower = True

    def __init__(self, *args, **kwargs):

        self.minev = False
        self.global_ = False
        self.jumble = False
        self.njumble = 1
        self.lengths = False
        self.lower = False
        self.negallowed = False
        self.outgrno = 1
        self.outgropt = False
        self.power = 2.0
        self.replicates = False
        self.trout = True
        self.upper = False
        self.usertree = False
        self.printdata = False
        self.progress = True
        self.treeprint = True
        self.loopcount = 0

        # Specific information
        self.mulsets = False
        self.datasets = 1
        self.firstset = True

        return None
 

def main(argc, args):
    i = 0

    init(argc,args)
    progname = args[0]
    openfile(infile, INFILE, "input file", "r", args[0], infilename)
    openfile(outfile, OUTFILE, "output file", "w", args[0], outfilename)

    #ibmpc = IBMCRT
    #ansi = ANSICRT
    #mulsets = False
    #datasets = 1
    #firstset = True
    doinit()
    if trout:
        openfile(outtree, OUTTREE, "output tree file", "w", args[0], outtreename)
    i = 0
    while i<spp:
        enterorder[i]=0
        i += 1
    ith = 1
    while ith <= datasets:
        if datasets > 1:
            fprintf(outfile, "Data set # %ld:\n\n",ith)
            if progress:
                print("\nData set # {0:d}:\n\n".format(ith), end = '')
        fitch_getinput()
        jumb = 1
        while jumb <= njumble:
            maketree()
            jumb += 1
        firstset = False
        if eoln(infile) and (ith < datasets):
            scan_eoln(infile)
        ith += 1
    if trout:
        FClose(outtree)
    FClose(outfile)
    FClose(infile)
    print("\nDone.\n\n", end = '')

def do_fitch(sInput):
    """Perform the FITCH algorithm on the string input"""

    oErr = ErrHandle()
    response = ""
    try:
        mulsets = False
        datasets = 1
        firstset = True

        # Perform initialization
        pass
    except:
        msg = oErr.get_error_message()
        oErr.DoError("")
    return response

