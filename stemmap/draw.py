import math

class pensttstype(Enum):
    PENUP = 0
    PENDOWN = 1

class LOC_plottext:

    def __init__(self):
        #instance fields found by C++ to Python Converter:
        self.height = 0
        self.compress = 0
        self.font = None
        self.coord = 0
        self.heightfont = 0
        self.xfactor = 0
        self.yfactor = 0
        self.xfont = 0
        self.yfont = 0
        self.xplot = 0
        self.yplot = 0
        self.sinslope = 0
        self.cosslope = 0
        self.xx = 0
        self.yy = 0
        self.penstatus = 0
       
         
def metricforfont(fontname, fontmetric):
    i = 0
    loopcount = 0

    if fontname in ["Helvetica", "Helvetica-Oblique"]:
        for i in range(31, 256):
            fontmetric[i-31] = helvetica_metric[i-31]
    elif fontname in ["Helvetica-Bold", "Helvetica-BoldOblique"]:
        for i in range(31, 256):
            fontmetric[i-31] = helveticabold_metric[i-31]
    elif fontname == "Times-Roman":
        for i in range(31, 256):
            fontmetric[i-31] = timesroman_metric[i-31]
    elif fontname == "Times":
        for i in range(31, 256):
            fontmetric[i-31] = timesroman_metric[i-31]
    elif fontname == "Times-Italic":
        for i in range(31, 256):
            fontmetric[i-31] = timesitalic_metric[i-31]
    elif fontname == "Times-Bold":
        for i in range(31, 256):
            fontmetric[i-31] = timesbold_metric[i-31]
    elif fontname == "Times-BoldItalic":
        for i in range(31, 256):
            fontmetric[i-31] = timesbolditalic_metric[i-31]

    elif "Courier" in fontname:
        fontmetric[0] = 562
        for i in range(32, 256):
            fontmetric[i-31] = short(int(600))
    else:
        pass
        
def heighttext(font, fontname):
    afmetric = [0 for _ in range(256)]
    #C++ TO PYTHON CONVERTER TASK: There is no preprocessor in Python:
    if fontname == "Hershey":
        response = float(font[2])
    else:
        metricforfont(fontname,afmetric)
        response = float(afmetric[0]) # heighttext
    # REturn the result
    return response
    
def pointinrect(x, y, x0, y0, x1, y1):
    tmp = 0
    if x0 > x1:
        tmp = x0, x0 = x1, x1 = tmp
    if y0 > y1:
        tmp = y0, y0 = y1, y1 = tmp

    return 1 if ((x >= x0 and x <= x1) and (y >= y0 and y <= y1)) else 0 # pointinrect

def rectintersects(xmin1, ymin1, xmax1, ymax1, xmin2, ymin2, xmax2, ymax2):
    temp = 0

    #   check if any of the corners of either square are contained within the  *
    #   * other one. This catches MOST cases, the last one (two) is two thin     *
    #   * bands crossing each other (like a '+' )                                

    if xmin1 > xmax1:
        temp = xmin1
        xmin1 = xmax1
        xmax1 = temp
    if xmin2 > xmax2:
        temp = xmin2
        xmin2 = xmax2
        xmax2 = temp
    if ymin1 > ymax1:
        temp = ymin1
        ymin1 = ymax1
        ymax1 = temp
    if ymin2 > ymax2:
        temp = ymin2
        ymin2 = ymax2
        ymax2 = temp

    response = 0
    if (pointinrect(xmin1, ymin1, xmin2, ymin2, xmax2, ymax2) != 0 \
        or pointinrect(xmax1, ymin1, xmin2, ymin2, xmax2, ymax2) != 0 \
        or pointinrect(xmin1, ymax1, xmin2, ymin2, xmax2, ymax2) != 0 \
        or pointinrect(xmax1, ymax1, xmin2, ymin2, xmax2, ymax2) != 0 \
        or pointinrect(xmin2, ymin2, xmin1, ymin1, xmax1, ymax1) != 0 \
        or pointinrect(xmax2, ymin2, xmin1, ymin1, xmax1, ymax1) != 0 \
        or pointinrect(xmin2, ymax2, xmin1, ymin1, xmax1, ymax1) != 0 \
        or pointinrect(xmax2, ymax2, xmin1, ymin1, xmax1, ymax1) != 0 \
        or (xmin1 >= xmin2 and xmax1 <= xmax2 and ymin2 >= ymin1 and ymax2 <= ymax1) \
        or (xmin2 >= xmin1 and xmax2 <= xmax1 and ymin1 >= ymin2 and ymax1 <= ymax2)):
        response = 1
    
    # rectintersects
    return response
        
def plotchar(place, oText):
    oText.heightfont = oText.font[place + 1]
    #C++ TO PYTHON CONVERTER TASK: C++ to Python Converter cannot determine whether both operands of this division are integer types - 
    #   if they are then you should change 'lhs / rhs' to 'math.trunc(lhs / float(rhs))':
    oText.yfactor = oText.height / oText.heightfont
    oText.xfactor = oText.yfactor
    place += 3
    loop_condition = True
    while loop_condition:
        place += 1
        oText.coord = oText.font[place - 1]
        if oText.coord > 0:
            oText.penstatus = pendown
        else:
            oText.penstatus = penup
        oText.coord = abs(oText.coord)
        oText.coord = math.fmod(oText.coord, 10000)
        #C++ TO PYTHON CONVERTER TASK: C++ to Python Converter cannot determine whether both operands of this division are integer types - 
        #   if they are then you should change 'lhs / rhs' to 'math.trunc(lhs / float(rhs))':
        oText.xfont = (oText.coord / 100 - xstart) * oText.xfactor
        oText.yfont = (math.fmod(oText.coord, 100) - ystart) * oText.yfactor
        oText.xplot = oText.xx + (oText.xfont * oText.cosslope + oText.yfont * oText.sinslope) * oText.compress
        oText.yplot = oText.yy - oText.xfont * oText.sinslope + oText.yfont * oText.cosslope
        plot(oText.penstatus, oText.xplot, oText.yplot)
        loop_condition = abs(oText.font[place - 1]) < 10000
    oText.xx = oText.xplot
    oText.yy = oText.yplot # plotchar
    
    # Return the newly calculated place
    return place

def plottext(pstring, nchars, height_, cmpress2, x, y, slope, font_, fontname, lst_out):
    text = LOC_plottext()
    i = 0
    j = 0
    code = 0
    pointsize = 0
    epointsize = 0 # effective pointsize before scale in idraw matrix
    iscale = 0
    textlen = 0
    px0 = 0 # square bounding box of text
    py0 = 0
    px1 = 0
    py1 = 0

    text.heightfont = font_[2]
    pointsize = (((height_ / xunitspercm) / 2.54) * 72.0)

    if strcmp(fontname.arg_value,"Hershey") !=0:
        pointsize *= (float(1000.0) / heighttext(font_,fontname.arg_value))

    text.height = height_
    text.compress = cmpress2
    text.font = font_
    text.xx = x
    text.yy = y
    text.sinslope = math.sin(pi * slope / 180.0)
    text.cosslope = math.cos(pi * slope / 180.0)

    if fontname == "Hershey":
        for i in range(0, nchars):
            code = pstring.arg_value[i]
            j = 1
            while text.font[j] != code and text.font[j - 1] != 0:
                j = text.font[j - 1]
            j = plotchar(j, text)
    # print native font.  idraw, PS, pict, and fig. 

    elif plotter == lw:
        #     If there's NO possibility that the line intersects the square bounding
        #     * box of the font, leave it out. Otherwise, let postscript clip to region.
        #     * Compute text boundary, be REAL generous. 
        #C++ TO PYTHON CONVERTER TASK: C++ to Python Converter cannot determine whether both operands of this division are integer types - 
        #    if they are then you should change 'lhs / rhs' to 'math.trunc(lhs / float(rhs))':
        textlen = (lengthtext(pstring.arg_value,nchars,fontname.arg_value,font_)/1000)*pointsize
        px0 = min(x + (text.cosslope * pointsize),
               x - (text.cosslope * pointsize),
               x + (text.cosslope * pointsize) + (text.sinslope * textlen),
               x - (text.cosslope * pointsize) + (text.sinslope * textlen)) / 28.346
        px1 = max(x + (text.cosslope * pointsize),
                   x - (text.cosslope * pointsize),
                   x + (text.cosslope * pointsize) + (text.sinslope * textlen),
                   x - (text.cosslope * pointsize) + (text.sinslope * textlen)) / 28.346
        py0 = min(y + (text.sinslope * pointsize),
                   y - (text.sinslope * pointsize),
                   y + (text.sinslope * pointsize) + (text.cosslope * textlen),
                   y - (text.sinslope * pointsize) + (text.cosslope * textlen)) / 28.346
        py1 = max(y + (text.sinslope * pointsize),
                   y - (text.sinslope * pointsize),
                   y + (text.sinslope * pointsize) + (text.cosslope * textlen),
                   y - (text.sinslope * pointsize) + (text.cosslope * textlen)) / 28.346
               
        
        # if rectangles intersect, print it. 
        if rectintersects(px0,py0,px1,py1,clipx0,clipy0,clipx1,clipy1):
            lst_out.append("gsave\n")
            lst_out.append("/{} findfont {:f} scalefont setfont\n",fontname.arg_value, pointsize)
            lst_out.append("{:f} {:f} translate {:f} rotate\n", 
                x-(clipx0 *xunitspercm),
                y-(clipy0 *xunitspercm),
                -slope)
            lst_out.append("0 0 moveto\n")
            lst_out.append("({}) show\n",pstring.arg_value)
            lst_out.append("grestore\n")

def drawit(fontname, xoffset, yoffset, numlines, root):
    i = 0
    j = 0
    line = 0
    xpag = 0
    ypag = 0

    test_long = 0 # To get a division out of a loop

    xpag = int(((pagex-hpmargin-0.01)/(paperx - hpmargin)))+1
    ypag = int(((pagey-vpmargin-0.01)/(papery - vpmargin)))+1

    pagecount = 1
    for j in range(0, ypag):
        for i in range(0, xpag):
            clipx0 = float(i)*(paperx - hpmargin)
            clipx1 = float((i*(paperx - hpmargin)))+(paperx - hpmargin)
            clipy0 = float((j*(papery - vpmargin)))
            clipy1 = float((j*(papery-hpmargin)))+(papery+vpmargin)

            plottree(root,root)
            plotlabels(fontname.arg_value)
            if not(i == xpag - 1 and j == ypag - 1) and plotter == lw:
                plotpb() # page break

