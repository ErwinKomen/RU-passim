import re
# My own stuff
from passim.utils import ErrHandle


def ps2svg(sFile, method="default"):
    """Convert postscript file into SVG"""

    sBack = ""
    oErr = ErrHandle()
    try:
        # Read the file
        sText = ""
        with open(sFile, "r") as f:
            sText = f.read()
        if method == "default":
            sBack = ps2svg_string(sText)
        elif method == "simple":
            sBack = ps2svg_simple(sText)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("ps2svg")

    # Return what we have gathered
    return sBack

sSvgNamespaces = 'xmlns:dc="http://purl.org/dc/elements/1.1/" \
     xmlns:cc="http://creativecommons.org/ns#" \
     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" \
     xmlns:svg="http://www.w3.org/2000/svg"'

sIntro = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\
<!-- Passim research project (https://www.ru.nl) -->\
<svg xmlns="http://www.w3.org/2000/svg" \
     viewBox="0 0 780 1020" height="1020" width="780" \
     xml:space="preserve" id="svg2" version="1.1">\
  <g transform="matrix(1.3333333,0,0,-1.3333333,0,1020)" id="g10">\
    <g transform="scale(0.1)" id="g12">'

height_simple = 765
width_simple = 585
sIntroSimple = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\
<!-- Passim research project (https://www.ru.nl) -->\
<svg xmlns="http://www.w3.org/2000/svg" \
     @viewbox xml:space="preserve" id="svg2" version="1.1">'


def ps2svg_string(sPostscript):
    """Convert postscript into SVG"""

    def group_numbers(result, times = 1):
        nums = []
        for sNum in result.groups():
            if re.match(r'[a-zA-Z]+', sNum):
                # This is just a string
                nums.append(sNum)
            else:
                # This must be a floating point number
                nums.append("{:.6f}".format(times * float(sNum) ))
        return nums

    sBack = ""
    lst_out = []
    oErr = ErrHandle()
    path_style = "fill:none;stroke:#000000;stroke-width:16;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:10;stroke-dasharray:none;stroke-opacity:1"
    point_style = "font-variant:normal;font-weight:normal;font-size:13.39669991px;font-family:Times;-inkscape-font-specification:Times-Roman;writing-mode:lr-tb;fill:#0000FF;fill-opacity:1;fill-rule:nonzero;stroke:none"
    try:
        # Recognize the initial lines we are looking for
        re_Line = re.compile( r'^\s+([0-9]+\.?[0-9]*)\s+([0-9]+\.?[0-9]*)\s+([0-9]+\.?[0-9]*)\s+([0-9]+\.?[0-9]*)\s+l$')
        re_point = re.compile(r'^([0-9]+\.?[0-9]*)\s+([0-9]+\.?[0-9]*)\s+translate\s+([0-9]+\.?[0-9]*)\s+rotate$')
        re_label = re.compile(r'^\(([a-zA-Z]+)\)\s+show$')

        lst_out.append(sIntro)

        # Split into lines
        lines = sPostscript.split("\n")
        section = "pre"
        idx = 14
        point_info = []
        bFirstPoint = True
        oorsprong = dict(x=0.0, y=0.0)
        for line in lines:
            # Check if we have a line 
            if section == "pre":
                result = re_Line.search(line)
                if result:
                    section = "lines"
            else:
                # We are not in a lines section
                pass
            if section == "lines":
                result = re_Line.search(line)
                if result:
                    nums = group_numbers(result, 10)
                    # Convert into path line
                    sPathLine = '<path id="path{}" style="{}" d="M {},{} {},{}" />'.format(
                        idx, path_style, nums[0], nums[1], nums[2], nums[3])
                    idx += 2
                    lst_out.append(sPathLine)
                else:
                    # We have exited the lines section
                    section = "point"
                    lst_out.append('<g transform="scale(10)" id="g{}">'.format(idx))
                    idx += 2
            elif section == "point":
                # Look for a point
                result = re_point.search(line)
                if result:
                    # We have found a point: get it in
                    nums = group_numbers(result, 1)

                    # Is this the first point?
                    if bFirstPoint:
                        lst_out.append('<text id="text{}" style="{}" transform="matrix(1,0,0,-1,{},{})">'.format(
                            idx, point_style, nums[0], nums[1]))
                        idx += 2
                        oorsprong['x'] = float(nums[0])
                        oorsprong['y'] = float(nums[1])
                        bFirstPoint = False

                    # In all situations: position w.r.t. oorsprong
                    pos_x = "{:.6f}".format(float(nums[0]) - oorsprong['x']) 
                    pos_y = "{:.6f}".format(oorsprong['y'] - float(nums[1]) )
                    point_info.append(pos_y)
                    point_info.append(pos_x)

                    section = "label"
            elif section == "label":
                # Look for a label
                result = re_label.search(line)
                if result:
                    # we have found a label: get it
                    sLabel = result.groups()[0]
                    point_info.append(sLabel)

                    # Output this label
                    sLabel = '<tspan id="tspan{}" y="{}" x="{}">{}</tspan>'.format(
                        idx, pos_y, pos_x, sLabel)
                    idx += 2
                    lst_out.append(sLabel)

                    section = "point"
                    point_info = []

        # Finish up the svg nicely
        lst_out.append("        </text>")
        lst_out.append("      </g>")
        lst_out.append("    </g>")
        lst_out.append("  </g>")
        lst_out.append("</svg>")
        # Convert the list into a string
        sBack = "\n".join(lst_out)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("ps2svg")

    # Return what we have gathered
    return sBack

def ps2svg_simple(sPostscript):
    """Convert postscript into SVG
    
    This uses a simple straight-forward conversion principle
    """

    def group_numbers(result, times = 1):
        nums = []
        for sNum in result.groups():
            if re.match(r'[a-zA-Z]+', sNum):
                # This is just a string
                nums.append(sNum)
            else:
                # This must be a floating point number
                nums.append("{:.6f}".format(times * float(sNum) ))
        return nums

    sBack = ""
    lst_out = []
    oErr = ErrHandle()
    line_style = 'stroke:black;stroke-width:1'
    point_style = "fill:blue;font-family:Times"
    offset_y = 18       # Adding 18px to compensate for double mirroring
    min_y = width_simple
    min_x = height_simple
    max_y = 0
    max_x = 0
    try:
        # Recognize the initial lines we are looking for
        re_Line = re.compile( r'^\s+([0-9]+\.?[0-9]*)\s+([0-9]+\.?[0-9]*)\s+([0-9]+\.?[0-9]*)\s+([0-9]+\.?[0-9]*)\s+l$')
        re_point = re.compile(r'^([0-9]+\.?[0-9]*)\s+([0-9]+\.?[0-9]*)\s+translate\s+([0-9]+\.?[0-9]*)\s+rotate$')
        re_label = re.compile(r'^\(([a-zA-Z]+)\)\s+show$')

        lst_out.append(sIntroSimple)

        # Split into lines
        lines = sPostscript.split("\n")
        section = "pre"
        idx = 14
        bFirstPoint = True
        oorsprong = dict(x=0.0, y=0.0)
        for line in lines:
            # Check if we have a line 
            if section == "pre":
                result = re_Line.search(line)
                if result:
                    section = "lines"
            else:
                # We are not in a lines section
                pass
            if section == "lines":
                result = re_Line.search(line)
                if result:
                    nums = group_numbers(result, 1)
                    # Convert into <line> element
                    sLine = '<g id=line{}><line x1="{}" y1="{}" x2="{}" y2="{}" style="{}" stroke-linecap="round" /></g>'.format(
                        idx, nums[0], nums[1], nums[2], nums[3], line_style)
                    idx += 2
                    lst_out.append(sLine)

                    # Keep track of min_y and min_x
                    min_x = min(min_x, float(nums[0]), float(nums[2]))
                    min_y = min(min_y, float(nums[1]), float(nums[3]))
                    max_x = max(max_x, float(nums[0]), float(nums[2]))
                    max_y = max(max_y, float(nums[1]), float(nums[3]))
                else:
                    # We have exited the lines section
                    section = "point"

            elif section == "point":
                # Look for a point
                result = re_point.search(line)
                if result:
                    # We have found a point: get it in
                    nums = group_numbers(result, 1)
                    pos_x = "{:.6f}".format(float(nums[0])) 
                    pos_y = "{:.6f}".format(float(nums[1]) + offset_y )

                    # Keep track of min_y and min_x
                    min_x = min(min_x, float(nums[0]))
                    min_y = min(min_y, float(nums[1]))
                    max_x = max(max_x, float(nums[0]))
                    max_y = max(max_y, float(nums[1]))

                    section = "label"
            elif section == "label":
                # Look for a label
                result = re_label.search(line)
                if result:
                    # we have found a label: get it
                    sLabel = result.groups()[0]

                    # Output this label
                    sLabel = '<g id="text{}"><text y="{}" x="{}" style="{}">{}</text></g>'.format(
                        idx, pos_y, pos_x, point_style, sLabel)
                    idx += 2
                    lst_out.append(sLabel)

                    section = "point"

        # Finish up the svg nicely
        lst_out.append("</svg>")
        # Convert the list into a string
        sBack = "\n".join(lst_out)

        # Adapt w.r.t. min_x and min_y, max_x, max_y
        fHeight = height_simple - 2 * min_y + offset_y
        sViewbox = 'viewBox="{} {} {} {}" width="{}" height="{}"'.format(
            0, min_y, width_simple, fHeight, width_simple, fHeight
            )
        sBack = sBack.replace('@viewbox', sViewbox)

    except:
        msg = oErr.get_error_message()
        oErr.DoError("ps2svg")

    # Return what we have gathered
    return sBack



