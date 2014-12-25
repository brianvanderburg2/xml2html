#!/usr/bin/env python
#
# File:     xml2html.py
# Author:   Brian Allen Vanderburg II
# Purpose:  A simple xml2html converter uxing XSLT and providing
#           some utility functions such as syntax highlighting.

# Imports
################################################################################

import sys
import os
import re
import codecs
import argparse

from lxml import etree


# Globals
################################################################################

cmdline = None

DEFAULT_SELFCLOSE_TAGS = [
    'area', 'base', 'br', 'col', 'command', 'embed',
    'hr', 'img', 'input', 'keygen', 'link', 'meta',
    'param', 'source', 'track', 'wbr'
]

DEFAULT_PRESERVE_TAGS = [
    'pre', 'textarea', 'script', 'style'
]


# Some utility functions/etc
################################################################################

class Error(Exception):
    """ A basic error class for our errors. """
    pass


def write_output(s):
    """ Output something to stderr. """
    sys.stderr.write(s)
    sys.stderr.flush()


def handle_error(error, abort=True):
    """ Handle an error. """
    if isinstance(error, etree.Error):
        result = ''
        for i in error.error_log:
            data = (str(i.filename), str(i.line), str(i.column), str(i.message))
            result += '[{0}, {1}, {2}] {3}\n'.format(*data)
            #result += '[' + str(entry.filename) + ', ' + str(entry.line) + ', ' + str(entry.column) + '] ' + entry.message + '\n'
        write_output(result)
    else:
        write_output(str(error) + '\n')

    if abort:
        sys.exit(-1)


def getbool(b):
    """ Test if a value it true or not """
    return b.lower() in ('yes', 'true', 'on', 1)

# Setup lxml
################################################################################

def lxml_base_uri(context, node=None):
    """ Return the base uri of a node. """
    base = node[0].base if node else context.context_node.base
    return base.replace(os.sep, '/')


def lxml_rbase_uri(context, node=None):
    """ Return the base uri fo a node relative to the base uri of the root node. """
    node = node[0] if node else context.context_node
    base = node.base
    pbase = base

    parent = node.getparent()
    while parent is not None:
        pbase = parent.base
        parent = parent.getparent()

    base = base.replace('/', os.sep)
    pbase = pbase.replace('/', os.sep)


    rbase = os.path.relpath(base, os.path.dirname(pbase))
    rbase = rbase.replace(os.sep, '/')

    # If base is /path/to/something/, relpath will strip out the trailing '/'
    # But we need to keep it as it is a directory and not a file
    if base.endswith(os.sep) and not rbase.endwith('/'):
        rbase = rbase + '/'

    return rbase


def lxml_dirname(context, base):
    """ Return the directory portion of a path containing '/' """
    pos = base.rfind('/')
    return base[:pos + 1] if pos >= 0 else ""


def lxml_basename(context, base):
    """ Return the filename portion of a path containing '/' """
    pos = base.rfind('/')
    return base[pos + 1:] if pos >= 0 else base


def lxml_highlight_code(context, code, syntax):
    """ Perform highlighting using Pygments. """
    import pygments
    import pygments.formatters
    import pygments.lexers

    global cmdline

    # Options
    nowrap = not getbool(cmdline.properties.get('highlight.wrap', 'no'))
    noclasses = not getbool(cmdline.properties.get('highlight.classes', 'yes'))
    nobackground = not getbool(cmdline.properties.get('highlight.background', 'no'))
    cssclass = cmdline.properties.get('highlight.cssclass', 'highlight')

    lexer = pygments.lexers.get_lexer_by_name(syntax, stripall=True)
    formatter = pygments.formatters.HtmlFormatter(nowrap=nowrap,
                                                  cssclass=cssclass,
                                                  noclasses=noclasses,
                                                  nobackground=nobackground)
    result = pygments.highlight(code, lexer, formatter)

    return result


def lxml_highlight_file(context, filename, syntax):
    """ Highlight the contents of a file. """
    return lxml_highlight_code(context, file(filename, "rU").read(), syntax)


def lxml_setup():
    """ Add the functions to LXML. """
    ns = etree.FunctionNamespace('urn:mrbavii:xml2html')

    ns['base-uri'] = lxml_base_uri
    ns['rbase-uri'] = lxml_rbase_uri
    ns['dirname'] = lxml_dirname
    ns['basename'] = lxml_basename

    ns['highlight_code'] = lxml_highlight_code
    ns['highlight_file'] = lxml_highlight_file


# build
################################################################################

def build():
    """ Build the HTML from the XML. """
    # Load the inputs
    inxml = etree.parse(cmdline.input)
    inxml.xinclude()

    xsl = etree.parse(cmdline.transform)
    xsl.xinclude()
    
    transform = etree.XSLT(xsl)

    # prepare parameters
    params = dict(cmdline.params)
    for i in params:
        params[i] = etree.XSLT.strparam(params[i])

    #build the output
    result = transform(inxml, **params)
    if result is None:
        raise Error('No output')

    result = cleanup(etree.tostring(result, pretty_print=True))

    # save the output
    file(cmdline.output, 'wb').write(result.encode(cmdline.encoding))


def cleanup_helper(mo):
    """ Callback for the header/footer. """
    key = mo.group(1)
    if key == '':
        return '@';
    return cmdline.params[key]


def cleanup(output):
    """ Clean up and fix the output. """
    # Remove leading/tailing whitespace
    output = output.strip()

    # Remove <?xml .. ?>
    if output[:2] == '<?':
        pos = output.find('?>')
        if pos >= 0:
            output = output[pos + 2:]
            output = output.lstrip()

    # Remove <!DOCTYPE ... >
    if output[:2] == '<!':
        pos = output.find('>')
        if pos > 0:
            output = output[pos + 1:]
            output = output.lstrip()

    # Fix self closing tags: <tag /> -> <tag></tag> by changing all tags except those allowed to self close
    selfclose_re = ''
    if len(cmdline.selfclose_tags) > 0:
        selfclose_re = r'(?!' + r'|'.join(cmdline.selfclose_tags) + r')'
    output = re.sub(r'(?si)<' + selfclose_re + r'([a-zA-Z0-9:]*?)(((\s[^>]*?)?)/>)', r'<\1\3></\1>', output)

    # Strip whitespace from empty lines and start of lines
    if cmdline.strip:
        pos = 0
        result = ''

        # Make sure to preserve certain tags
        if len(cmdline.preserve_tags) > 0:
            pattern = r'(?si)<(' + r'|'.join(cmdline.preserve_tags) + r')(>|\s[^>]*?>).*?</\1>'
            matches = re.finditer(pattern, output)

            for match in matches:
                offset = match.start()
                if offset > pos:
                    result += re.sub(r'(?m)^\s+', r'', output[pos:offset])
            
                result += match.group()
                pos = match.end()

        # Any leftover is also stripped
        if pos < len(output):
            result += re.sub(r'(?m)^\s+', r'', output[pos:])

        output = result

    # Add header and footer to output
    if cmdline.header:
        header = codecs.open(cmdline.header, 'rU', encoding=cmdline.encoding).read().strip()
        output = re.sub('@([a-zA-Z0-9]*?)@', cleanup_helper, header) + "\n" + output

    if cmdline.footer:
        footer = codecs.open(cmdline.footer, 'rU', encoding=cmdline.encoding).read().strip()
        output = output + "\n" + re.sub('@([a-zA-Z0-9]*?)@', cleanup_helper, footer)

    return output

# Entry point
################################################################################

class Options(object):
    """ Container to hold the options. """
    pass


def update_set(output, input):
    """ Update a set with values from a string. """
    if input[0:1] == '+':
        fn = output.add
        input = input[1:]
    elif input[0:1] == '!':
        fn = output.discard
        input = input[1:]
    else:
        fn = output.add
        output.clear()

    for i in input.split(','):
        if i:
            fn(i)

def parse_cmdline():
    """ Parse command line arguments """

    # Setup and parse command line
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--help', action='help')
    parser.add_argument('-r', '--root', dest='root', action='store', required=True, help='root directory')
    parser.add_argument('-i', '--input', dest='input', action='store', required=True, help='input file name')
    parser.add_argument('-o', '--output', dest='output', action='store', required=True, help='output file name')
    parser.add_argument('-t', '--transform', dest='transform', action='store', required=True, help='XSL file name')
    parser.add_argument('-h', '--header', dest='header', action='store', help='header file name')
    parser.add_argument('-f', '--footer', dest='footer', action='store', help='footer file name')
    parser.add_argument('-p', '--property', dest='property', action='append', help='a property name=value pair')
    parser.add_argument('-e', '--encoding', dest='encoding', action='store', default='utf-8', help='output character encoding')
    parser.add_argument('-s', '--strip', dest='strip', action='store_true', default=False, help='strip leading spaces from output')
    parser.add_argument('--selfclose', dest='selfclose_tags', action='append', help='allowed self closing tags')
    parser.add_argument('--preserve', dest='preserve_tags', action='append', help='preserved tags')
    parser.add_argument('params', action='store', nargs='*', help='XSL name=value parameters')

    result = parser.parse_args()

    # Set the variables in the options object
    o = Options()

    o.root = os.path.abspath(result.root)
    o.input = os.path.abspath(result.input)
    o.output = os.path.abspath(result.output)
    o.transform = os.path.abspath(result.transform)
    o.header = os.path.abspath(result.header) if result.header else None
    o.footer = os.path.abspath(result.footer) if result.footer else None

    o.properties = {}
    if result.property:
        for i in result.property:
            pair = i.split('=', 1)
            if len(pair) == 2:
                o.properties[pair[0]] = pair[1]

    o.encoding = result.encoding
    o.strip = result.strip

    o.selfclose_tags = set(DEFAULT_SELFCLOSE_TAGS)
    if result.selfclose_tags:
        for i in result.selfclose_tags:
            update_set(o.selfclose_tags, i)

    o.preserve_tags = set(DEFAULT_PRESERVE_TAGS)
    if result.preserve_tags:
        for i in result.preserve_tags:
            update_set(o.preserve_tags, i)

    relinput = os.path.relpath(o.input, o.root)
    reloutput = os.path.relpath(o.output, o.root)
    o.params = {
        'root': o.root.replace(os.sep, '/'),
        'input': o.input.replace(os.sep, '/'),
        'output': o.output.replace(os.sep, '/'),
        'inputrelroot': '../' * relinput.count(os.sep),
        'outputrelroot': '../' * reloutput.count(os.sep),
        'relinput': relinput.replace(os.sep, '/'),
        'reloutput': reloutput.replace(os.sep, '/')
    }
    if result.params:
        for i in result.params:
            pair = i.split('=', 1)
            if len(pair) == 2:
                o.params[pair[0]] = pair[1]
    return o


def main():
    """ The real program entry point. """
    global cmdline

    try:
        lxml_setup()
        cmdline = parse_cmdline()
        build()
    except (Error, etree.Error, OSError, IOError, ValueError) as e:
        handle_error(e)

if __name__ == "__main__":
    main()


