#!/usr/bin/env python

__author__ = "Brian Allen Vanderburg II"


import sys
import os
import re
import argparse
import fnmatch

try:
    from codecs import open
except ImportError:
    pass # Python3 open can directly handle encoding

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

import mrbavii_lib_template


class XmlWrapper(mrbavii_lib_template.Library):
    """ Class to wrap an XML node for the template engine. """

    def __init__(self, node):
        """ Init the wrapper. """
        self._node = node

        tag = node.tag

        if tag[0] == "{":
            end = tag.find("}")
            if end < 0:
                pass # TODO: error

            ns = tag[1:end]
            tag = tag[end + 1:]
        else:
            ns = ""

        self._ns = ns
        self._tagname = tag

    def call_tag(self):
        return self._node.tag

    def call_ns(self):
        return self._ns

    def call_tagname(self):
        return self._tagname

    def call_text(self):
        return self._node.text if self._node.text else ""

    def call_tail(self):
        return self._node.tail if self._node.tail else ""

    def call_alltext(self):
        return "".join(self._node.itertext())

    def lib_attr(self, name, defval=None):
        return self._node.attrib.get(name, defval)

    def __iter__(self):
        for child in self._node:
            yield XmlWrapper(child)

    def lib_findall(self, path):
        for child in self._node.findall(path):
            yield XmlWrapper(child)

    def lib_find(self, path):
        child = self._node.find(path)
        if not child is None:
            child = XmlWrapper(child)

        return child


class Lib(mrbavii_lib_template.Library):
    """ A custom library for xml2html. """

    def __init__(self):
        mrbavii_lib_template.Library.__init__(self)

    def set_fn(self, fn):
        self._fn = fn

    def lib_esc(self, what, quote=False):
        import cgi
        return cgi.escape(what, quote)

    def lib_highlight(self, what, syntax, classprefix=""):
        import pygments
        import pygments.formatters
        import pygments.lexers

        lexer = pygments.lexers.get_lexer_by_name(syntax, stripall=True)
        formatter = pygments.formatters.HtmlFormatter(
            nowrap=True,
            noclasses=False,
            nobackground=True,
            classprefix=classprefix)

        result = pygments.highlight(what.strip(), lexer, formatter)
        return result

    def lib_highlight_file(self, where, syntax, classprefix=""):
        fn = os.path.join(os.path.dirname(self._fn), where)

        with open(fn, "rU") as handle:
            what = handle.read()

        return self.lib_highlight(what, syntax, classprefix)

class Builder(object):
    """ A builder is responsible for building the output. """

    def __init__(self, template, search):
        """ Initialize a builder. """

        # Store parameters
        self._template = template

        # Prepare default context and template
        self._lib = Lib()

        self._context = {
            "lib": mrbavii_lib_template.StdLib(),
            "xml2html": self._lib
        }
        
        loader = mrbavii_lib_template.FileSystemLoader(search)
        self._env = mrbavii_lib_template.Environment(
            loader = loader
        )

    def log(self, input, output):
        """ Write a log message. """

        print("{0} -> {1}".format(input, output))


    def build(self, input, output, params):
        """ Build the output and return the result. """
        
        xml = ET.parse(input)
        self._lib.set_fn(input)

        our_params = dict(self._context)
        our_params.update({
            "xml": XmlWrapper(xml.getroot())
        })
        our_params.update(params)


        renderer = mrbavii_lib_template.StringRenderer()
        self._env.clear()
        template = self._env.load_file(self._template)
        template.render(renderer, our_params)

        outdir = os.path.dirname(output)
        if not os.path.isdir(outdir):
            os.makedirs(outdir)

        self.log(input, output)
        with open(output, "wt") as handle:
            handle.write(renderer.get())

def checktimes(source, target):
    """ Check timestamps and return true to continue, false if up to date. """
    if not os.path.isfile(target):
        return True

    stime = os.path.getmtime(source)
    ttime = os.path.getmtime(target)

    return stime > ttime

def main():
    """ Run the program. """

    # Parse arguments
    parser = argparse.ArgumentParser(description="Convert XML to HTML or other text output.")
    parser.add_argument("-o", dest="output", required=True,
        help="Output directory.")
    parser.add_argument("-r", dest="root", required=True,
        help="Input root.")
    parser.add_argument("-t", dest="template", required=True,
        help="Template file.")
    parser.add_argument("-s", dest="search", action="append", default=None, required=False,
        help="Template search path. May be specified multiple times.")
    parser.add_argument("-D", dest="params", action="append",
        help="name=value parameters to pass")
    parser.add_argument("-w", dest="walk", default=None,
        help="Walk the root directory.  Value is a glob pattern to match.")
    parser.add_argument("inputs", nargs="*",
        help="Input XML files.")

    args = parser.parse_args()

    # Prepare context
    context = {}

    # Parameters passed in
    if args.params:
        for param in args.params:
            parts = param.split("=", 1)
            if len(parts) == 2:
                name = parts[0].strip()
                value = parts[1].strip()
            else:
                name = parts[0].strip()
                value = True

            context[name] = value

    # Inputs
    inputs = list(args.inputs)
    if args.walk:
        for (dir, dirs, files) in os.walk(args.root):
            extra = [os.path.join(dir, i) for i in files if fnmatch.fnmatch(i, args.walk)]
            inputs.extend(extra)

    # Create our builder
    builder = Builder(args.template, args.search)

    for input in inputs:
        # Relative path to input from root directory
        relpath = os.path.relpath(input, args.root)
        relpath = os.path.splitext(relpath)[0] + ".html"
        output = os.path.join(args.output, relpath)

        # Relative path to root from output directory
        toroot = os.path.relpath(args.output, os.path.dirname(output))
        toroot = toroot.replace(os.sep, "/")
        if not toroot.endswith("/"):
            toroot = toroot + "/"

        context["toroot"] = toroot

        if checktimes(input, output):
            builder.build(input, output, context)


if __name__ == "__main__":
    main()

