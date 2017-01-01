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


class ProgData(object):
    """ A generic wrapper for certain program data. """

    def __init__(self):
        self.cmdline = None


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

    def __bool__(self):
        return True

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

    def lib_str(self):
        return ET.tostring(self._node)


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

    def lib_xml(self, what):
        root = ET.fromstring(what)
        return XmlWrapper(root)


class Builder(object):
    """ A builder is responsible for building the output. """

    def __init__(self, progdata):
        """ Initialize a builder. """

        # Store parameters
        self._build_template = progdata.cmdline.template
        self._state_template = progdata.cmdline.s_template

        if self._state_template:
            self._state = State(progdata.cmdline.s_year,
                                progdata.cmdline.s_month,
                                progdata.cmdline.s_day,
                                progdata.cmdline.s_title,
                                progdata.cmdline.s_tags,
                                progdata.cmdline.s_summary)
        else:
            self._state = None

        # Prepare default context and template
        self._lib = Lib()

        self._context = {
            "lib": mrbavii_lib_template.StdLib(),
            "xml2html": self._lib
        }
        
        loader = mrbavii_lib_template.FileSystemLoader(progdata.cmdline.search)
        self._env = mrbavii_lib_template.Environment(
            loader = loader
        )

    def log(self, action, input, output=None):
        """ Write a log message. """

        if output:
            print("{0}: {2} ({1})".format(action, input, output))
        else:
            print("{0}: {1}".format(action, input))


    def build(self, input, output, params, generate):
        """ Build the output and return the result. """
        
        self.log("PARSE", input)
        xml = ET.parse(input)
        root = xml.getroot()

        if self._state:
            self._state.decode(root, params["relpath"])

        if not generate:
            return

        our_params = {
            "xml": XmlWrapper(root)
        }
        our_params.update(params)
        self.build_from_data(self._build_template, input, output, our_params)

    def build_state(self, input, output, params):
        """ Build the state file. """

        if not self._state:
            return

        sorted_states = self._state.get()
        tags = sorted(self._state.tags())

        sorted_state_tags = {}
        for tag in tags:
            sorted_state_tags[tag] = filter(lambda i: tag in i["tags"], sorted_states)

        our_params = {
            "allstates": sorted_states,
            "tags": tags,
            "tagstates": sorted_state_tags
        }
        our_params.update(params)

        self.build_from_data(self._state_template, input, output, our_params)

    def build_from_data(self, template, input, output, params):
        """ Build from a data set. """

        our_params = dict(self._context)
        our_params.update(params)

        self._lib.set_fn(input)

        renderer = mrbavii_lib_template.StringRenderer()
        self._env.clear()
        tmpl = self._env.load_file(template)
        tmpl.render(renderer, our_params)

        outdir = os.path.dirname(output)
        if not os.path.isdir(outdir):
            os.makedirs(outdir)

        self.log("BUILD", input, output)
        with open(output, "wt") as handle:
            handle.write(renderer.get())

        sections = renderer.get_sections()
        for s in sections:
            if not s.startswith("file:"):
                continue

            output = s[5:]
            if '/' in output or os.sep in output:
                continue # TODO error, should not define directory, only filename

            output = os.path.join(outdir, output)
            self.log("BUILD", input, output)
            with open(output, "wt") as handle:
                handle.write(renderer.get_section(s))


class State(object):
    """ Keep track of item states. """

    def __init__(self, xpyear, xpmonth, xpday, xptitle, xptags, xpsummary):
        self._states = []
        self._xpyear = xpyear
        self._xpmonth = xpmonth
        self._xpday = xpday
        self._xptitle = xptitle
        self._xptags = xptags
        self._xpsummary = xpsummary

        self._tags = set()

    def decode(self, root, relpath):
        """ Read the state from the input. """

        year = 0
        if self._xpyear:
            el = root.find(self._xpyear)
            if not el is None:
                year = int(el.text) if el.text else 0

        month = 0
        if self._xpmonth:
            el = root.find(self._xpmonth)
            if not el is None:
                month = int(el.text) if el.text else 0

        day = 0
        if self._xpday:
            el = root.find(self._xpday)
            if not el is None:
                day = int(el.text) if el.text else 0

        title = None
        if self._xptitle:
            el = root.find(self._xptitle)
            if not el is None:
                title = "".join(el.itertext())

        tags = set()
        if self._xptags:
            el = root.find(self._xptags)
            if not el is None:
                tags = set(el.text.split() if el.text else [])
        self._tags.update(tags)

        summary = None
        if self._xpsummary:
            el = root.find(self._xpsummary)
            if not el is None:
                summary = XmlWrapper(el)

        if year == 0 or month == 0 or day == 0 or title is None:
            return

        result = {
            "relpath": relpath,
            "year": year,
            "month": month,
            "day": day,
            "title": title,
            "tags": tags,
            "summary": summary
        }

        self._states.append(result)

    def get(self):
        """ Return the sorted list of states. """
        import operator

        return sorted(self._states, key=operator.itemgetter("year", "month", "day"), reverse=True)

    def tags(self):
        """ Return all tags. """
        return self._tags


def checktimes(source, target):
    """ Check timestamps and return true to continue, false if up to date. """
    if not os.path.isfile(target):
        return True

    stime = os.path.getmtime(source)
    ttime = os.path.getmtime(target)

    return stime > ttime

def main():
    """ Run the program. """
    progdata = ProgData()


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

    parser.add_argument("--state-year", dest="s_year",
        help="XPATH to year element")
    parser.add_argument("--state-month", dest="s_month",
        help="XPATH to month element (valid value of element is 1-12)")
    parser.add_argument("--state-day", dest="s_day",
        help="XPATH to day element (value value of element is 1-31)")
    parser.add_argument("--state-title", dest="s_title",
        help="XPATH to title element")
    parser.add_argument("--state-tags", dest="s_tags",
        help="XPATH to tags element")
    parser.add_argument("--state-summary",dest="s_summary",
        help="XPATH to summary element")
    parser.add_argument("--state-template", dest="s_template",
        help="XPATH to state template.")
    parser.add_argument("--state-file", dest="s_file",
        help="Pseudo-file for the state.  This file does not get generated. "
             "It is used to determine the relative path to the root.")

    args = parser.parse_args()
    progdata.cmdline = args

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

    if args.s_file: # Add pseudo-input for state file
        inputs.append(args.s_file)

    # Create our builder
    builder = Builder(progdata)

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

        # Set up our data
        context["toroot"] = toroot
        context["relpath"] = relpath

        if args.s_file and input == args.s_file:
            builder.build_state(input, output, context)
        else:
            realbuild = checktimes(input, output)
            builder.build(input, output, context, realbuild)


if __name__ == "__main__":
    main()

