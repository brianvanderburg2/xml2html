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

try:
    from ConfigParser import SafeConfigParser
except ImportError:
    from configparser import SafeConfigParser


import mrbavii_lib_template


def split_tag(tag):
    """ A helper function get split a tag into namespace and tag parts. """

    if tag[0] == "{":
        end = tag.find("}")
        if end < 0:
            pass # TODO: error

        ns = tag[1:end]
        tag = tag[end + 1:]
    else:
        ns = ""

    return (ns, tag)


class ControlEntry(object):
    """ This class represents an entry in a control file. """

    def __init__(self):
        self._pre_template = None
        self._post_template = None
        self._template = None
        self._control_file = None
        self._control_prefix = ""
        self._text = None


class ControlFile(object):
    """ This class represents the content of a control file. """

    def __init__(self, filename):
        """ Load a control file. """
        self._controls = {}
        self._namespaces = {}

        ini = SafeConfigParser()
        ini.read(filename)

        for section in ini.sections():
            if section == ":namespaces:":
                pass

            entry = ControlEntry()
            self._controls[section.strip()] = entry

            if ini.has_option(section, "pre-template"):
                entry._pre_template = ini.get(section, "pre-template").strip()

            if ini.has_option(section, "post-template"):
                entry._post_template = ini.get(section, "post-template").strip()

            if ini.has_option(section, "template"):
                entry._template = ini.get(section, "template").strip()

            if ini.has_option(section, "control-file"):
                entry._control_file = ini.get(section, "control-file").strip()

            if ini.has_option(section, "control-prefix"):
                entry._control_prefix = ini.get(section, "control-prefix").strip()

            if ini.has_option(section, "text"):
                entry._text = (ini.get(section, "text").strip().lower() == "emit")

        if ini.has_section(":namespaces:"):
            for (name, value) in ini.items(":namespaces:"):
                self._namespaces[value.strip()] = name.strip()

    def find(self, tag, control_prefix):
        """ Return the spec entry for the specified tag. """

        if control_prefix and not control_prefix.endswith("/"):
            control_prefix += "/"

        (ns, tagname) = split_tag(tag)
        if ns:
            if ns in self._namespaces:
                token = control_prefix + self._namespaces[ns] + ":" + tagname
            else:
                token = control_prefix + "{" + ns + "}" + tagname
        else:
            token = control_prefix + tagname

        return self._controls.get(token, None)


class XmlWrapper(mrbavii_lib_template.Library):
    """ Class to wrap an XML node for the template engine. """

    def __init__(self, node):
        """ Init the wrapper. """
        self._node = node
        (self._ns, self._tagname) = split_tag(node.tag)

    def call_tag(self):
        return self._node.tag

    def call_ns(self):
        return self._ns

    def call_tagname(self):
        return self._tagname

    def call_text(self):
        return self._node.text

    def call_tail(self):
        return self._node.tail

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
        if child:
            child = XmlWrapper(child)

        return child


class Lib(mrbavii_lib_template.Library):
    """ A custom library for xml2html. """

    def lib_esc(self, what, quote=False):
        import cgi
        return cgi.escape(what, quote)


class Builder(object):
    """ A builder is responsible for building the output. """

    def __init__(self, infile, control_file, extra={}):
        """ Initialize a builder. """

        # Store parameters
        self._infile = infile
        self._control_file = control_file

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
        self._text_emit_stack = [False]

        self._control_files = {}
        self._contents = []

        self._params = {}


    def build(self):
        """ Build the output and return the result. """
        
        xml = ET.parse(self._infile)
        self._params["xml"] = XmlWrapper(xml.getroot())

        self.process_node(xml.getroot(), self._control_file, "")

        return "".join(self._contents)


    def get_control_file(self, filename):
        """ Return a control file to use. """
        filename = os.path.abspath(filename)
        if not filename in self._control_files:
            self._control_files[filename] = ControlFile(filename)

        return self._control_files[filename]
        

    def process_node(self, node, filename, control_prefix):
        """ Process a given node. """

        control = self.get_control_file(filename)
        entry = control.find(node.tag, control_prefix)

        if entry:
            params = dict(self._params)
            params["node"] = XmlWrapper(node)

            if not entry._text is None:
                self._text_emit_stack.append(entry._text)

            try:

                if entry._pre_template:
                    self.render_template(
                        os.path.join(
                            os.path.dirname(filename),
                            entry._pre_template
                        ),
                        params
                    )

                if entry._template:
                    self.render_template(
                        os.path.join(
                            os.path.dirname(filename),
                            entry._template
                        ),
                        params
                    )
                elif entry._control_file:
                    self.process_subnode(
                        node,
                        os.path.join(
                            os.path.dirname(filename),
                            entry._control_file
                        ),
                        entry._control_prefix
                    )
                else:
                    self.process_subnode(
                        node,
                        filename,
                        entry._control_prefix
                    )

                if entry._post_template:
                    self.render_template(
                        os.path.join(
                            os.path.dirname(filename),
                            entry._post_template
                        ),
                        params
                    )

            finally:

                if not entry._text is None:
                    self._text_emit_stack.pop()


    def process_subnode(self, node, filename, control_prefix):
        """ Process a given node's subitems using the specfile. """

        if node.text and self._text_emit_stack[-1]:
            self._contents.append(node.text)

        for child in node:
            self.process_node(child, filename, control_prefix)
            if child.tail and self._text_emit_stack[-1]:
                self._contents.append(child.tail)


    def render_template(self, filename, context):
        """ Render a given template and append to the result. """
        renderer = mrbavii_lib_template.StringRenderer()
        template = self._env.load_file(filename)
        template.render(renderer, context)

        self._contents.append(renderer.get())


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
    parser.add_argument("-c", dest="control", required=True,
        help="Control file.")
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
    builder = Builder(args.input, args.control, context)
    contents = builder.build()

    # Save our output file
    outdir = os.path.dirname(args.output)
    if not os.path.isdir(outdir):
        os.makedirs(outdir)

    with open(args.output, "wt") as handle:
        handle.write(contents)



if __name__ == "__main__":
    main()

