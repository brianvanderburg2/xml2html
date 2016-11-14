#!/usr/bin/env python

__author__ = "Brian Allen Vanderburg II"


import sys
import os
import re
import argparse

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

    def lib_esc(self, what, quote=False):
        import cgi
        return cgi.escape(what, quote)


class Builder(object):
    """ A builder is responsible for building the output. """

    def __init__(self, infile, template, extra={}):
        """ Initialize a builder. """

        # Store parameters
        self._infile = infile
        self._template = template

        # Prepare default context and template
        context = {
            "lib": mrbavii_lib_template.StdLib(),
            "xml2html": Lib()
        }
        context.update(extra)
        
        loader = mrbavii_lib_template.FileSystemLoader()
        self._env = mrbavii_lib_template.Environment(
            loader = loader,
            context = context
        )

        # Default items
        self._contents = []
        self._params = {}


    def build(self):
        """ Build the output and return the result. """
        
        xml = ET.parse(self._infile)

        params = {
            "xml": XmlWrapper(xml.getroot())
        }

        renderer = mrbavii_lib_template.StringRenderer()
        template = self._env.load_file(self._template)
        template.render(renderer, params)

        return renderer.get()


def main():
    """ Run the program. """

    # Parse arguments
    parser = argparse.ArgumentParser(description="Convert XML to HTML or other text output.")
    parser.add_argument("-i", dest="input", required=True,
        help="Input XML file.")
    parser.add_argument("-o", dest="output", required=True,
        help="Output file.")
    parser.add_argument("-r", dest="root", required=True,
        help="Root directory relative to output.")
    parser.add_argument("-t", dest="template", required=True,
        help="Template file.")
    parser.add_argument("params", nargs="*",
        help="name=value parameters to pass")

    args = parser.parse_args()

    # Prepare context
    context = {}

    # Relative path to root from output directory
    toroot = os.path.relpath(args.root, os.path.dirname(args.output))
    toroot = toroot.replace(os.sep, "/")
    if not toroot.endswith("/"):
        toroot = toroot + "/"

    context["toroot"] = toroot

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

    # Create our builder and build
    builder = Builder(args.input, args.template, context)
    contents = builder.build()

    # Save our output file
    outdir = os.path.dirname(args.output)
    if not os.path.isdir(outdir):
        os.makedirs(outdir)

    with open(args.output, "wt") as handle:
        handle.write(contents)



if __name__ == "__main__":
    main()

