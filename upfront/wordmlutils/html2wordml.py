#!/usr/bin/env python

import os
import sys
import urllib
import zipfile
import argparse
from cStringIO import StringIO
from lxml import etree, html
from lxml.html import soupparser
from PIL import Image

dirname = os.path.dirname(__file__)

def get_images(basepath, doc):
    images = {}
    for img in doc.xpath('//img'):
        url = img.get('src')
        image = urllib.urlopen('%s/%s' % (basepath, url))
        filename = url.split('/')[-1]
        images[filename] = (url, StringIO(image.read()))
    return images
    
def convertPixelsToEMU(px):
    points = px * 72.0 / 96.0
    inches = points / 72.0
    emu = inches * 914400
    return int(emu)

def transform(basepath, htmlfile, image_resolver=None,
        create_package=True, outfile=sys.stdout):

    """ transform html to wordml
        
        image_resolver needs to be an instance of a class with a
        get_images method accepting `basepath` and `doc` as args. it should
        return images in the same format as the get_images method above.
    """

    xslfile = open(os.path.join(dirname, 'xsl/html2wordml.xsl'))

    xslt_root = etree.XML(xslfile.read())
    transform = etree.XSLT(xslt_root)

    doc = soupparser.fromstring(htmlfile)
    if image_resolver:
        image_resolver.get_images(basepath, doc)
    else:
        images = get_images(basepath, doc)
    result_tree = transform(doc)
    wordml = etree.tostring(result_tree)
    wordml = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>' + \
        wordml

    template = zipfile.ZipFile(os.path.join(dirname, 'template.docx'))

    # read and parse relations from template so that we can update it
    # with links to images
    rels = template.read('word/_rels/document.xml.rels')
    rels = etree.parse(StringIO(rels)).getroot()

    output = StringIO()
    zf = zipfile.ZipFile(output, 'w')
    namelist = template.namelist()
    docindex = namelist.index('word/document.xml')
    for filename, img in images.items():
        url, data = img
        # insert image before document
        namelist.insert(docindex, 'word/media/%s' % filename)

        # insert image sizes in the wordml
        img = Image.open(data)
        width, height = img.size

        # convert to EMU (English Metric Unit) 
        width = convertPixelsToEMU(width)
        height = convertPixelsToEMU(height)

        widthattr = '%s-$width' % url
        heightattr = '%s-$height' % url
        ridattr = '%s-$rid' % url
        wordml = wordml.replace(widthattr, str(width))
        wordml = wordml.replace(heightattr, str(height))
        wordml = wordml.replace(ridattr, filename)
        relxml = """<Relationship Id="%s" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/%s"/>""" % (
            filename, filename)
        rels.append(etree.fromstring(relxml))

    relsxml = etree.tostring(rels)

    for filepath in namelist:
        if filepath == 'word/document.xml':
            zf.writestr(filepath, wordml)
        elif filepath.startswith('word/media'):
            filename = filepath.split('/')[-1]
            filecontent = images[filename][-1]
            filecontent.seek(0)
            zf.writestr(filepath, filecontent.read())
        elif filepath.startswith('word/_rels/document.xml.rels'):
            zf.writestr(filepath, relsxml)
        else:
            content = template.read(filepath)
            zf.writestr(filepath, content)
        
    template.close()
    zf.close()
    zipcontent = output.getvalue()
    if create_package:
        outfile.write(zipcontent)
    else:
        outfile.write(wordml)

def main():
    parser = argparse.ArgumentParser(description='Convert HTML to WordML')
    parser.add_argument('-c', '--create-package', action='store_true',
        help='Create WordML package') 
    parser.add_argument('-p', '--basepath', help='Base path for relative urls',
        required=True)
    parser.add_argument('htmlfile', help='/path/to/htmlfile') 
    args = parser.parse_args()

    htmlfile = urllib.urlopen(args.htmlfile)
    basepath = args.basepath

    transform(basepath, htmlfile, create_package=args.create_package)

if __name__ == '__main__':

    main()
