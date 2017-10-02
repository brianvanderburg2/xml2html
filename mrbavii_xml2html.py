#!/usr/bin/env python

__author__ = "Brian Allen Vanderburg II"
__version__ = "0.4"


import sys
import os
import re
import argparse
import fnmatch
import io

try:
    from codecs import open
except ImportError:
    pass # Python3 open can directly handle encoding

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from mrbaviirc import template


class XmlWrapper(template.Library):
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


class Lib(template.Library):
    """ A custom library for xml2html. """

    def __init__(self):
        template.Library.__init__(self)

    def set_fn(self, fn):
        if os.path.isdir(fn):
            self._dir = fn
        else:
            self._dir = os.path.dirname(fn)

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
        fn = os.path.join(self._dir, where)

        with open(fn, "rU") as handle:
            what = handle.read()

        return self.lib_highlight(what, syntax, classprefix)

    def lib_xml(self, what):
        root = ET.fromstring(what)
        return XmlWrapper(root)

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
        return sorted(self._tags)
        

# Reusable section below #

class Command(object):
    """ Base class for a command. """
    command_name="name_of_command"
    command_desc="What command does"

    @staticmethod
    def find_subclasses(cls=None, result=None):
        """ Find all subclasses. """
        if cls is None:
            cls = Command

        if result is None:
            result = []

        subclasses = cls.__subclasses__()
        result.extend(subclasses)

        for subclass in subclasses:
            Command.find_subclasses(subclass, result)
        
        return result

    @staticmethod
    def add_args(parser):
        """ Add arguments to the parser. """
        pass


class App(object):
    """ Represent our application object. """
    app_desc="What app does"

    @staticmethod
    def add_args(parser):
        """ Allow for adding common args before command args """
        pass

    def init(self):
        """ Perform common initialization before executing command. """
        pass

    def run(self):
        """ execute the command. """
        pass

    def cleanup(self):
        """ Perform cleanup. """
        pass

    @classmethod 
    def run_app(cls):
        """ Run the application. """

        app = cls()

        # Argument parser
        parser = argparse.ArgumentParser(description=cls.app_desc)
        app.add_args(parser)

        # Determine available commands
        cmd_classes = Command.find_subclasses()
        commands = {}

        if cmd_classes:
            subparsers = parser.add_subparsers(dest="command")
            for cmd in cmd_classes:
                cmd_parser = subparsers.add_parser(cmd.command_name,
                                                   description=cmd.command_desc)
                cmd.add_args(cmd_parser)

                commands[cmd.command_name] = cmd

        # Parse the arguments
        app.args = parser.parse_args()

        # Run the application
        app.init()

        if cmd_classes:
            cmd_class = commands[app.args.command]
            cmd_instance = cmd_class()
            cmd_instance.app = app
            cmd_instance.run()
        else:
            app.run()
        app.cleanup()

# Reusable section above #


# App

class Xml2HtmlApp(App):
    app_desc = "Build HTML output from XML files"

    @staticmethod
    def add_args(parser):
        """ Add common arguments. """
        pass

    def init(self):
        """ Perform some initial stuff. """

        # Prepare our context
        context = {}

        if self.args.params:
            for param in self.args.params:
                parts = param.split("=", 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    value = parts[1].strip()
                else:
                    name = parts[0].strip()
                    value = True

                context[name] = value

        context["lib"] = template.StdLib()
        context["xml2html"] = self._lib = Lib()

        self.context = context

        # Template
        loader = template.SearchPathLoader(self.args.search)
        self.env = template.Environment(loader=loader)

    def log(self, action, input, output=None):
        """ Write a log message. """

        if output:
            print("{0}: {2} ({1})".format(action, input, output))
        else:
            print("{0}: {1}".format(action, input))

    def build_from_data(self, input, output, context):
        """ Build from a data set. """

        args = self.args

        # Prepare data set
        our_context = dict(self.context)
        our_context.update(context)

        self._lib.set_fn(input)

        # Create renderer and load/render template
        renderer = template.StringRenderer()
        self.env.clear()
        tmpl = self.env.load_file(args.template)
        tmpl.render(renderer, our_context)

        # Save output
        outdir = os.path.dirname(output)
        if not os.path.isdir(outdir):
            os.makedirs(outdir)

        if self.checktimes(input, output):
            self.log("BUILD", input, output)
            with open(output, "wt") as handle:
                handle.write(renderer.get())
        else:
            self.log("NOCHG", input, output)

        sections = renderer.get_sections()
        for s in sections:
            if not s.startswith("file:"):
                continue

            output = s[5:]
            if '/' in output or os.sep in output:
                continue # TODO error, should not define directory, only filename

            if self.checktimes(input, output):
                output = os.path.join(outdir, output)
                self.log("BUILD", input, output)
                with open(output, "wt") as handle:
                    handle.write(renderer.get_section(s))
            else:
                self.log("NOCHG", input, output)

    def checktimes(self, input, output):
        """ Check timestamps and return true to continue, false if up to date. """
        if not os.path.isfile(output):
            return True

        stime = os.path.getmtime(input)
        ttime = os.path.getmtime(output)

        return stime > ttime

#helper

def readlines(fn):
    with io.open(fn, "rt", newline=None) as handle:
        for line in handle:
            line = line.rstrip("\n")
            if line and line[0:1] != "#":
                yield line


# Scan

class Scan(Command):
    command_name = "scan"
    command_desc = "Scan XML files to create state files."
    
    @staticmethod
    def add_args(parser):
        """ Add arguments for the scanner. """
        parser.add_argument("-o", dest="output", required=True,
            help="Output main state file.")
        parser.add_argument("-r", dest="root", required=True,
            help="Input root.")
        parser.add_argument("-t", dest="template", required=True,
            help="Template file.")
        parser.add_argument("-s", dest="search", action="append", default=None, required=False,
            help="Template search path. May be specified multiple times.")
        parser.add_argument("-D", dest="params", action="append",
            help="name=value parameters to pass")

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
        
        parser.add_argument("-f", dest="files", action="append", default=None, required=False,
            help="Filename(s) containing a list of files, one per line, to use as inputs.")
        parser.add_argument("inputs", nargs="*",
            help="Input XML files.")

    def run(self):
        """ Execute the command. """

        app = self.app
        args = app.args
        state = State(args.s_year,
                      args.s_month,
                      args.s_day,
                      args.s_title,
                      args.s_tags,
                      args.s_summary)

        inputs = []
        if args.files:
            for file in args.files:
                inputs.extend(readlines(file))
        inputs.extend(args.inputs)

        for input in inputs:
            # Determine relative path
            relpath = os.path.relpath(input, args.root)

            app.log("SCAN", input)
            xml = ET.parse(input)
            root = xml.getroot()

            state.decode(root, relpath)

        # Now we have all our states
        sorted_states = state.get()
        sorted_tags = state.tags()
        sorted_state_tags = {}
        for tag in sorted_tags:
            sorted_state_tags[tag] = filter(lambda i: tag in i["tags"], sorted_states)

        # Determine path to root
        toroot = os.path.relpath(args.root, os.path.dirname(args.output))
        toroot = toroot.replace(os.sep, "/")
        if not toroot.endswith("/"):
            toroot = toroot + "/"
        

        context = {
            "allstates": sorted_states,
            "tags": sorted_tags,
            "tagstates": sorted_state_tags,
            "toroot": toroot
        }

        app.build_from_data(args.root, args.output, context)

# Build

class Build(Command):
    command_name = "build"
    command_desc = "Build output from XML files"

    @staticmethod
    def add_args(parser):
        """ Add arguments for the parser. """
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

        parser.add_argument("-f", dest="files", action="append", default=None, required=False,
            help="Filename(s) containing a list of files, one per line, to use as inputs.")
        parser.add_argument("inputs", nargs="*",
            help="Input XML files.")

    def run(self):
        """ Execute the command. """

        app = self.app
        args = app.args

        inputs = []
        if args.files:
            for file in args.files:
                inputs.extend(readlines(file))
        inputs.extend(args.inputs)

        for input in inputs:
            # Determine relative path and root
            relpath = os.path.relpath(input, args.root)
            relpath = os.path.splitext(relpath)[0] + ".html"
            output = os.path.join(args.output, relpath)

            # Determine path to root
            toroot = os.path.relpath(args.output, os.path.dirname(output))
            toroot = toroot.replace(os.sep, "/")
            if not toroot.endswith("/"):
                toroot = toroot + "/"

            # Load XML
            app.log("PARSE", input)
            xml = ET.parse(input)
            root = xml.getroot()

            context = {
                "toroot": toroot,
                "relpath": relpath,
                "xml": XmlWrapper(root)
            }

            app.build_from_data(input, output, context)


if __name__ == "__main__":
    Xml2HtmlApp.run_app()

