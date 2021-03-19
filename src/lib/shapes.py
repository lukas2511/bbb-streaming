#!/usr/bin/env python3

import re
import logging
log = logging.getLogger('bbb-streamer')

def yield_datapoints(annotation):
    for i in range(0, len(annotation['points']), 2):
        yield [annotation['points'][i]/100, annotation['points'][i+1]/100]

def get_datapoints(annotation):
    if 'points' in annotation:
        return list(yield_datapoints(annotation))
    else:
        return list([(float(x)/100, float(y)/100) for x, y in re.findall(r'([^,]+),([^,]+)', annotation['dataPoints'])])

def annot_pencil(annotation, res):
    if 'commands' not in annotation:
        return ''

    width,height = res
    svg = '<path stroke="#%06x" fill="none" stroke-linejoin="round" stroke-linecap="round" stroke-width="%.2f" d="' % (int(annotation['color']), (float(annotation['thickness'])/100*width))
    datapoints = get_datapoints(annotation)
    for c in annotation['commands']:
        if c == 1:
            x, y = datapoints.pop(0)
            svg += 'M%s, %s ' % (x*width, y*height)
        elif c == 2:
            x, y = datapoints.pop(0)
            svg += 'L%s, %s ' % (x*width, y*height)
        elif c == 3:
            x1, y1 = datapoints.pop(0)
            x2, y2 = datapoints.pop(0)
            svg += 'Q%s, %s, %s, %s ' % (x1*width, y1*height, x2*width, y2*height)
        elif c == 4:
            x1, y1 = datapoints.pop(0)
            x2, y2 = datapoints.pop(0)
            x3, y3 = datapoints.pop(0)
            svg += 'C%s, %s, %s, %s, %s, %s ' % (x1*width, y1*height, x2*width, y2*height, x3*width, y3*height)
    svg += '"/>'
    return svg

def annot_line(annotation, res):
    width,height = res
    annotation["commands"] = [1, 2]
    return annot_pencil(annotation, res)

def annot_ellipse(annotation, res):
    width,height = res
    datapoints = get_datapoints(annotation)
    x1, y1 = datapoints[0]
    x2, y2 = datapoints[1]
    rx = (x2 - x1) / 2
    ry = (y2 - y1) / 2
    cx = ((rx + x1) * width)
    cy = ((ry + y1) * height)
    rx = abs(rx * width)
    ry = abs(ry * height)
    svg = '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="none" stroke="#%06x" stroke-width="%s" />' % (cx, cy, rx, ry, int(annotation['color']), float(annotation['thickness'])/100*width)
    return svg

def annot_rectangle(annotation, res):
    width,height = res
    datapoints = get_datapoints(annotation)
    x1, y1 = datapoints[0]
    x2, y2 = datapoints[1]

    if x2 < x1:
        x1 = datapoints[1][0]
        x2 = datapoints[0][0]

    if y2 < y1:
        y1 = datapoints[1][1]
        y2 = datapoints[0][1]

    svg = '<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="#%06x" stroke-width="%s" />' % (x1 * width, y1 * height, (x2-x1)*width, (y2-y1)*height, int(annotation['color']), float(annotation['thickness'])/100*width)
    return svg

def annot_triangle(annotation, res):
    width,height = res
    datapoints = get_datapoints(annotation)
    xBottomLeft, yTop = datapoints[0]
    xBottomRight, yBottomLeft = datapoints[1]
    yBottomRight = yBottomLeft
    xTop = (xBottomRight - xBottomLeft)/2 + xBottomLeft

    d = "M%s, %s, %s, %s, %s, %s Z" % (xTop*width, yTop*height, xBottomLeft*width, yBottomLeft*height, xBottomRight*width, yBottomRight*height)

    svg = '<path d="%s" fill="none" stroke="#%06x" stroke-width="%s" />' % (d, int(annotation['color']), float(annotation['thickness'])/100*width)
    return svg

def annot_text(annotation, res):
    width,height = res
    if annotation["textBoxWidth"] == 0:
        return ""

    if annotation["text"] is None:
        return ""

    datapoints = get_datapoints(annotation)
    x, y = datapoints[0]

    textboxwidth = float(annotation["textBoxWidth"])/100 * width
    textboxheight = float(annotation["textBoxHeight"])/100 * height

    svg = '<text x="%s" y="%s" width="%s" height="%s" font-family="Arial" font-size="%s" fill="#%06x">' % (float(annotation['x'])/100*width, float(annotation['y'])/100*height, textboxwidth, textboxheight, float(annotation['calcedFontSize'])/100*height, int(annotation['fontColor']))
    svg += annotation['text']
    svg += '</text>'
    return svg

def generate_svg(annotation, slide):
    width, height = slide['width'], slide['height']

    if annotation["type"] == "pencil":
        return annot_pencil(annotation, res=(width,height))
    elif annotation["type"] == "line":
        return annot_line(annotation, res=(width,height))
    elif annotation["type"] == "ellipse":
        return annot_ellipse(annotation, res=(width,height))
    elif annotation["type"] == "rectangle":
        return annot_rectangle(annotation, res=(width,height))
    elif annotation["type"] == "triangle":
        return annot_triangle(annotation, res=(width,height))
    elif annotation["type"] == "text":
        return annot_text(annotation, res=(width,height))
    else:
        log.error("Unknown annotation type: %s" % annotation["type"])
        return ""
