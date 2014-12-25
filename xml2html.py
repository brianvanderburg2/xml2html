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


# Some utility functions/etc
################################################################################

class Error(Exception):
    """ A basic error class for our errors. """
    pass

def write_output(s):
    """ Output something to stderr. """
    sys.stderr.write(s)
    sys.stderr.flush()

def handle_error(e, abort=True):
    """ Handle an error. """
    if isinstance(e, etree.Error):
        result = ''
        for entry in e.error_log:
            result += '[' + str(entry.filename) + ', ' + str(entry.line) + ', ' + str(entry.column) + '] ' + entry.message + '\n'
        write_output(result)
    else:
        write_output(str(e) + '\n')

    if abort:
        sys.exit(-1)

def getbool(b):
    """ Test if a value it true or not """
    return b.lower() in ('yes', 'true', 'on', 1)

# Setup lxml
################################################################################

# Set up some custom xsl/xpath functions
def lxml_base_uri(context, node=None):
    base = node[0].base if node else context.context_node.base
    return base.replace(os.sep, '/')

def lxml_rbase_uri(context, node=None):
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
    pos = base.rfind('/')
    return base[:pos + 1] if pos >= 0 else ""

def lxml_basename(context, base):
    pos = base.rfind('/')
    return base[pos + 1:] if pos >= 0 else base

# Syntax highlighting
def lxml_highlight_code(context, code, syntax):
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
    return lxml_highlight_code(context, file(filename, "rU").read(), syntax)


# Add custom functions
def lxml_setup():
    ns = etree.FunctionNamespace('urn:mrbavii:xmlsite')

    ns['base-uri'] = lxml_base_uri
    ns['rbase-uri'] = lxml_rbase_uri
    ns['dirname'] = lxml_dirname
    ns['basename'] = lxml_basename

    ns['highlight_code'] = lxml_highlight_code
    ns['highlight_file'] = lxml_highlight_file


# build
################################################################################

def build():

    # Load the inputs
    inxml = etree.parse(cmdline.input)
    inxml.xinclude()

    xsl = etree.parse(cmdline.transform)
    xsl.xinclude()
    
    transform = etree.XSLT(xsl)

    # build the output
    result = transform(inxml, **cmdline.params)
    if result is None:
        raise Error('No output')

    result = cleanup(etree.tostring(result, pretty_print=True))

    # save the output
    file(cmdline.output, 'wb').write(result.encode(cmdline.encoding))

def cleanup(output):
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

    # Find and replace
    #for pair in self.replacements:
    #    output = output.replace(pair[0], pair[1])

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
    def helper(mo):
        key = mo.group(1)
        if key == '':
            return '@';
        return cmdline.params[key]

    if cmdline.header:
        header = codecs.open(cmdline.header, 'rU', encoding=cmdline.encoding).read()
        output = re.sub('@([a-zA-Z0-9]*?)@', helper, header) + "\n" + output

    if cmdline.footer:
        footer = codecs.open(cmdline.footer, 'rU', encoding=cmdline.encoding).read()
        output = output + "\n" + re.sub('@([a-zA-Z0-9]*?)@', helper, footer)

    return output

# Entry point
################################################################################


# Parse the command line


class _CmdOptions(object):
    pass

def parse_cmdline():
    """ Parse command line arguments """

    # Setup and parse command line
    parser = argparse.ArgumentParser(description='XML to HTML.', add_help=False)
    parser.add_argument('--help', action='help')
    parser.add_argument('-r', '--root', dest='root', action='store', required=True, help='root path used for relative names')
    parser.add_argument('-i', '--input', dest='input', action='store', required=True, help='input file name')
    parser.add_argument('-o', '--output', dest='output', action='store', required=True, help='output file name')
    parser.add_argument('-t', '--transform', dest='transform', action='store', required=True, help='XSLT tranform file name')
    parser.add_argument('-h', '--header', dest='header', action='store', help='header file name')
    parser.add_argument('-f', '--footer', dest='footer', action='store', help='footer file name')
    parser.add_argument('-p', '--property', dest='properties', action='append', help='property in the form of name=value')
    parser.add_argument('-e', '--encoding', dest='encoding', action='store', default='utf-8', help='output character encoding')
    parser.add_argument('-s', '--strip', dest='strip', action='store_true', default=False, help='strip spaces from output')
    parser.add_argument('--selfclose', dest='selfclose_tags', action='append', help='tags that are allowed to be self closing')
    parser.add_argument('--preserve', dest='preserve_tags', action='append', help='tags that should not be stripped')
    parser.add_argument('params', action='store', nargs='*', help='a list of name=value parameters for XSL processing')

    result = parser.parse_args()

    # Set global variables in this module
    o = _CmdOptions()

    o.root = os.path.abspath(result.root)
    o.input = os.path.abspath(result.input)
    o.output = os.path.abspath(result.output)
    o.transform = result.transform
    o.header = result.header
    o.footer = result.footer

    o.properties = {}
    if result.properties:
        for i in result.properties:
            pair = i.split('=', 1)
            if len(pair) == 2:
                o.properties[pair[0]] = pair[1]

    o.encoding = result.encoding
    o.strip = result.strip

    o.selfclose_tags = []
    if result.selfclose_tags:
        for i in result.selfclose_tags:
            o.selfclose_tags.extend(i.split(','))

    o.preserve_tags = []
    if result.preserve_tags:
        for i in result.preserve_tags:
            o.preserve_tags.extend(i.split(','))

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

    for i in o.params:
        o.params[i] = etree.XSLT.strparam(o.params[i])

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


