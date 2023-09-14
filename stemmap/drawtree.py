"""
The drawtree.py program derives directly from the C-equivalent drawtree.c

"""

import math
from newickio import readnewick, readnewick_string


# My own stuff
from utils import ErrHandle

VERSION="3.697"
fontname = ""

def plotrparms(ntips):
    xsizehold = xsize
    ysizehold = ysize
    penchange = no
    xcorner = 0.0
    ycorner = 0.0
    penchange = yes
    xunitspercm = 28.346456693
    yunitspercm = 28.346456693
    xsize = pagex
    ysize = pagey
    
    if xsizehold != 0.0 and ysizehold != 0.0:
        xmargin = xmargin * xsize / xsizehold;
        ymargin = ymargin * ysize / ysizehold;

def initialparms():
    # Main parameters
    paperx = 20.6375
    pagex  = 20.6375
    papery = 26.9875
    pagey  = 26.9875
    fontname = "Times-Roman"
    
    # Set plot parameters
    plotrparms(spp)
    
    # Remaining parameters
    grows = vertical
    treeangle = pi / 2.0
    ark = 2 * pi
    improve = true
    nbody = false
    regular = false
    rescaled = true
    bscale = 1.0
    labeldirec = middle
    xmargin = 0.08 * xsize
    ymargin = 0.08 * ysize
    labelrotation = 0.0
    charht = 0.3333
    plotter = DEFPLOTTER
    hpmargin = 0.02 * pagex
    vpmargin = 0.02 * pagey
    labelavoid = false
    uselengths = haslengths
        
def user_settings():
    xscale = xunitspercm
    yscale = yunitspercm
    plotrparms(spp)
    numlines = 1
    
    # Re calculat
    calculate()
    
    # Re scale
    rescale()
    
    # Indicate it can be plotted
    canbeplotted = True
    
def postscript_header(lst_out):
    count_x = pagex/paperx;
    count_y = pagey/papery;
    pages   = count_x * count_y;
    dm_x    = (int)( unit * pagex );
    dm_y    = (int)( unit * pagey );
    bb_ll_x = (int)( unit * xmargin );
    bb_ll_y = (int)( unit * ymargin );
    bb_ur_x = (int)( dm_x - bb_ll_x );  # re-cycle the margins for 
    bb_ur_y = (int)( dm_y - bb_ll_y );  # upper-right dimensions   
    
    lst_out.append("{}".format("%!PS-Adobe-3.0"))
    lst_out.append("{}".format("%Test postscript"))
    lst_out.append("{}".format("%%Title: Phylip Tree Output"))
    lst_out.append("{}".format("%%Creator: Phylip Drawgram"))
    lst_out.append("{} {} {}".format("%%Pages:", pages, 1))
    lst_out.append("{}".format("%%DocumentFonts: (atend)"))
    lst_out.append("{}".format("%%Orientation: Portrait"))
    
    # comment page name number width height
    lst_out.append("{} {} {} {} 0 ( ) ( )".format("%%DocumentMedia:", "Page", dm_x, dm_y))
    
    # comment lower left, upper right.
    lst_out.append("{} {} {} {} {}".format("%%BoundingBox:", bb_ll_x, bb_ll_y, bb_ur_x, bb_ur_y))
    
    lst_out.append("{}".format("%%EndComments"))
    lst_out.append("{}".format("/l {newpath moveto lineto stroke} def"))
    lst_out.append("{}".format("%%EndProlog"))
    lst_out.append("{}".format("%%Page: 1 1"))
    
    # set the media spec's.
    lst_out.append("<< /PageSize [ {} {} ] >> setpagedevice".format(dm_x, dm_y))
    lst_out.append("{}".format(" 1 setlinecap \n 1 setlinejoin"))
    lst_out.append("%8.2f {}".format(treeline, "setlinewidth newpath"))
        
def initplotter(ntips, fontname, lst_out):
    oErr = ErrHandle()
    try:
        treeline = 0.18 * labelheight * yscale * expand
        labelline = 0.06 * labelheight * yscale * expand
        linewidth = treeline
    
        # Postscript header
        postscript_header(lst_out)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("initplotter")
    # initplotter
    return None
    
def plottree(p, q):
    oErr = ErrHandle()
    try:
        x2 = xscale * (xoffset + p.xcoord)
        y2 = yscale * (yoffset + p.ycoord)
        if p != root:
            x1 = xscale * (xoffset + q.xcoord)
            y1 = yscale * (yoffset + q.ycoord)
            plot(penup, x1, y1)
            plot(pendown, x2, y2)

        if p.tip:
            return
        pp = p.next
    
        while True:
            plottree(pp.back, p)
            pp = pp.next
            bCondition = (((p == root) and (pp != p.next)) or ((p != root) and (pp != p)))
            if not bCondition:
                break

    except:
        msg = oErr.get_error_message()
        oErr.DoError("plottree")
    # Pro Memory
    return None
            
def changepen(pen, lst_out):
    lastpen = pen
    oErr = ErrHandle()
    try:    
        if pen == "treepen":
            linewidth = treeline
            lst_out.append("stroke {:8.2f} setlinewidth ;".format(treeline))
            lst_out.append(" 1 setlinecap 1 setlinejoin ")
        elif pen == "labelpen":
            linewidth = labelline
            lst_out.append("stroke {:8.2f} setlinewidth ;".format(labelline))
            lst_out.append(" 1 setlinecap 1 setlinejoin ")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("changepen")
    return None

def plotlabels(fontname, lst_out):
    oErr = ErrHandle()
    try:
        dx = 0
        dy = 0
    
        # Calculate the compression
        compr = xunitspercm / yunitspercm
    
        changepen('labelpen', lst_out)
    
        # Walk the nodes
        for i in range(0, (nextnode)):
            if nodep[i].tip:
                lp = nodep[i]
                labangle = labelrotation * pi / 180.0
                if labeldirec == radial:
                    labangle = nodep[i].theta
                elif (labeldirec == along):
                    labangle = nodep[i].oldtheta
                elif (labeldirec == middle):
                    labangle = 0.0
                if (cos(labangle) < 0.0):
                    labangle -= pi
                sino = sin(nodep[i].oldtheta)
                coso = cos(nodep[i].oldtheta)
                cosl = cos(labangle)
                sinl = sin(labangle)
                right = ((coso*cosl+sino*sinl) > 0.0) or (labeldirec == middle)
                vec = sqrt(1.0+firstlet[i]*firstlet[i])
                cosv = firstlet[i]/vec
                sinv = 1.0/vec
                if (labeldirec == middle):
                    if ((textlength[i]+1.0)*math.fabs(tan(nodep[i].oldtheta)) > 2.0):
                        dx = -0.5 * textlength[i] * labelheight * expand
                        if (sino > 0.0):
                            dy = 0.5 * labelheight * expand
                            if (math.fabs(nodep[i].oldtheta - pi/2.0) > 1000.0):
                                dx += labelheight * expand / (2.0*tan(nodep[i].oldtheta))
                        else:
                            dy = -1.5 * labelheight * expand
                            if (math.fabs(nodep[i].oldtheta - pi/2.0) > 1000.0):
                                dx += labelheight * expand / (2.0*tan(nodep[i].oldtheta))
                
                    else:
                        if (coso > 0.0):
                            dx = 0.5 * labelheight * expand
                            dy = (-0.5 + (0.5*textlength[i]+0.5)*tan(nodep[i].oldtheta)) * labelheight * expand
                        else:
                            dx = -(textlength[i]+0.5) * labelheight * expand
                            dy = (-0.5 - (0.5*textlength[i]+0.5)*tan(nodep[i].oldtheta)) * labelheight * expand

                else:
                    if (right):
                        dx = labelheight * expand * coso
                        dy = labelheight * expand * sino
                        dx += labelheight * expand * 0.5 * vec * (-cosl*cosv+sinl*sinv)
                        dy += labelheight * expand * 0.5 * vec * (-sinl*cosv-cosl*sinv)
                    else:
                        dx = labelheight * expand * coso
                        dy = labelheight * expand * sino
                        dx += labelheight * expand * 0.5 * vec * (cosl*cosv+sinl*sinv)
                        dy += labelheight * expand * 0.5 * vec * (sinl*cosv-cosl*sinv)
                        dx -= textlength[i] * labelheight * expand * cosl
                        dy -= textlength[i] * labelheight * expand * sinl

                plottext(lp.nayme, lp.naymlength,
                       labelheight * expand * xscale / compr, compr,
                       xscale * (lp.xcoord + dx + xoffset),
                       yscale * (lp.ycoord + dy + yoffset), -180 * labangle / pi,
                       font, fontname)
            # End if
        # End if
        if (penchange == yes):
            changepen(treepen)    
    except:
        msg = oErr.get_error_message()
        oErr.DoError("plotlabels")
    return None
    
def drawit(fontname, xoffset, yoffset, numlines, root, lst_out):
    oErr = ErrHandle()
    try:
        xpag = (int)((pagex-hpmargin-0.01)/(paperx - hpmargin))+1
        ypag = (int)((pagey-vpmargin-0.01)/(papery - vpmargin))+1

        pagecount = 1
        for j in range(0, ypag):
          for i in range(0, xpag):
            clipx0 = float( i *(paperx -  hpmargin))
            clipx1 = float(i*(paperx -  hpmargin))+(paperx - hpmargin)
            clipy0 = float(j*(papery -  vpmargin))
            clipy1 = float(j*(papery-hpmargin))+(papery+vpmargin)

            plottree(root,root, lst_out)
            plotlabels(fontname, lst_out)
            if not (i == xpag - 1 and j == ypag - 1) and plotter == lw:
                # page break
                plotpb()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("drawit")
    return None
      

def finishplotter(lst_out):
    padded_width = 0 # For bmp code
    byte_width = 0

    oErr = ErrHandle()
    try:
        if plotter == lw:
            lst_out.append( "stroke showpage \n\n")
            lst_out.append("%%%%PageTrailer\n")
            lst_out.append("%%%%PageFonts: {}\n".format("" if fontname == "Hershey" else fontname))
            lst_out.append("%%%%Trailer\n")
            lst_out.append("%%%%DocumentFonts: {}\n".format("" if fontname == "Hershey" else fontname))
    except:
        msg = oErr.get_error_message()
        oErr.DoError("finishplotter")
    return None

def get_text_from_file(filename):
    # Open the treefile
    with open(filename, "rb") as f:
        tree_text = f.read()
    
    # Convert it into proper text
    tree_text = tree_text.decode("utf-8")

    return tree_text

    
def setup_environment_alt(progname, treefile, plotfile):

    oErr = ErrHandle()
    try:
        # Show the version we are in
        print("DRAWTREE from PHYLIP version {}".format(VERSION))
    
        ## Open the treefile
        #with open(treefile, "rb") as f:
        #    tree_text = f.read()
    
        ## Convert it into proper text
        #tree_text = tree_text.decode("utf-8")

        ## Try to read the tree as a newick tree
        #trees = newick.loads(tree_text)

        # Alternative: read the newick using BioPhy stuff
        trees = readnewick(treefile)

        # Read the tree
        print("Reading tree ... \n", end = '')
        firsttree = True
    
        # Determine how large spp will be
        allocate_nodep(nodep, intree, spp)
    
        # Read the tree from the string
        treeread(intree, root, treenode, goteof, firsttree, nodep, nextnode, haslengths, grbg, initdrawtreenode, True, -1)
    
        q = root
        r = root
        while not(q.next == root):
            q = q.next
        q.next = root.next
        root = q
        chuck(grbg, r)
        nodep[spp] = q
        where = root
        rotate = True
        print("Tree has been read.")
        print("Loading the font ... ")
        loadfont(font, FONTFILE, progname.arg_value)
        print("Font loaded.")
        ansi = ANSICRT
        ibmpc = IBMCRT
        firstscreens = True
        initialparms()
        canbeplotted = False
        # 2nd. argument is not entered; use default. 
        maxNumOfIter = 50
    except:
        msg = oErr.get_error_message()
        oErr.DoError("setup_environment_alt")
    # setup_environment_alt
    return None 
    
def psdrawtree(oArgs):
    """
    Transform the tree file [treefname] into a PostScript plotfile [plotfname]
    - Avoid making use of a fontfile
    """
    
    oErr = ErrHandle()
    plot_output = ""
    try:
        # Get the arguments
        treefname = oArgs.get("input", "")
        plotfname = oArgs.get("output", "")

        if treefname == "" or plotfname == "":
            # Cannot handle this
            printf("drawtree: at least one argument is not specified")
            return plot_output

        # Set up the environment
        progname = "psdrawtree"

        # TEST
        trees = readnewick(treefname)

        #sTrees = get_text_from_file(treefname)
        #trees = readnewick_string(sTrees)

        # Older code
        setup_environment_alt(progname, treefname, plotfname)
    
        # Set default parameters for this specific purpose
        #  (don't elicit from the user)
        user_settings()
    
        # Open the plotfile to write data to
        plot_output = ""
        lst_out = []
        initplotter(spp, fontname, lst_out)
    
        numlines = 1
    
        drawit(fontname, xoffset, yoffset, numlines, root, lst_out)
    
        finishplotter(lst_out)
    
        wasplotted = True
    
        # Write the string to the plotfile
        plot_output = "\n".join(lst_out)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("psdrawtree")
    
    # Return the result
    return plot_output
    
