XML2HTML
========

This python script is a simple HTML builder that reads XML files, applies
an XSL tranform to the XML file, and saves the result out to an HTML file.


Arguments
=========

-r <dir>
--root <dir>

    REQUIRED
    This specifies a root directory that will be used to generate relative
    names for the input and output file names.


-i <file>
--input <file>

    REQUIRED
    This specifies the input XML file to apply the transform to.


-o <file>
--output <file>

    REQUIRED
    This specifies where to save the resulting HTML file


-t <file>
--transform <file>

    REQUIRED
    This specifies the location of the XSL file that gets applied to the XML
    to generate the output.


-h <file>
--header <file>

    OPTIONAL
    This specifies a file that will be prepended to the final contents.  All
    leading and trailing whitespace will be stripped from this file when read.
    This can be used to add a DOCTYPE to the output.


-f <file>
--footer <file>

    OPTIONAL
    This specifies a file that will be appended to the final contents.  All
    leading and trailing whitespace will be stripped from the file when read.


-p <name=value>
--property <name=value>

    OPTIONAL, MULTIPLE
    This specifies a property that is used internally.  See the section on
    properties for more information.


-e <encoding>
--encoding <encoding>

    OPTIONAL, DEFAULT=utf-8
    This specifies the encoding that is used for the output file.  This is
    also the encoding used to read the input header and footer files.


-s
--strip

    OPTIONAL, DEFAULT=False
    This specifies whether the output should be stripped.  If this option
    is set, then leading spaces and blank lines will be stripped from the
    output except for preserved tags.


--selfclose [+|!]<tag>[,<tag>...]

    OPTIONAL
    This specifies a list of tags that are allowed to be self-closing.  All
    other tags that are self-closing in the output will be made to contain
    a closing tag.  This means that tags in the form of <tag /> will be
    changed to <tag></tag>, except for allowed tags.

    You can specify this option multiple times.  Each time, the following
    rules will be applied:

        If the option begins with a '+', then the specified tags will be added
        to the current self-closing tags.

        If the option begins with a '!', then the specified tags will be
        removed from the current self-closing tags.

        If the option does not begin with a '+' or '!', then the specified tags
        will replace the current self-closing tags.

    The inititial set of self-closing tags is:

        area, base, br, col, command, embed, hr, img, input, keygen, link,
        meta, param, source, track, wbr


--preserve [+|!]<tag>[,<tag>...]

    OPTIONAL
    This specifies a list of tags whose contents between the start of the tag
    and the closing tag should not be stripped when the strip option is given.
    The match is performed in such a way that the preserved tag should not
    contain the same tag nested, as the first closing tag of the same name
    marks the end of the presered region.

    You can specify this option multiple times.  Each time, the following
    rules will be applied:

        If the option begins with a '+', then the specified tags will be added
        to the current preserved tags.

        If the option begins with a '!', then the specified tags will be
        removed from the current preserved tags.

        If the option does not begin with a '+' or '!', then the specified tags
        will replace the current preserved tags.

    The initial set of preserved tags is:

        pre, textarea, script, style


<name=value>

    OPTIONAL
    The remaining arguments are treated as parameters in the form of
    "name=value" pairs.  These parameters are passed to the XSL transform
    and are also used in the header and footer.

    When applying the header and footer, any text in the files in the form of
    '@key@' is replaced by the matching parameter.  To generate a literal '@',
    use '@@' in the header and footer file.



Properties
==========

The following are the properties are used by the script.


highlight.wrap
    VALUES: yes,no
    DEFAULT: no
    If this is set to no, then "nowrap=True" is used in the Pygments
    HtmlFormatter class.  This will prevent the generated tokens from being
    wrapped even by a <pre> tag.  This allows the user to wrap the tags as
    desired.


highlight.classes
    VALUES: yes,no
    DEFAULT: yes
    If set then the <span> tags in the output will use classes.  Otherwise
    the <span> tags in the output will use inline styles.


highlight.background
    VALUES: yes,no
    DEFAULT: no
    This controls wheter the formatter will generate background color for the
    wrapping element.  This has no effect if "highlight.wrap" is "no"


highlight.cssclass
    VALUES: string
    DEFAULT: highlight
    This controls the class of the wrapping element.  This has no effect
    if "highlight.wrap" is "no"


XSL Parameters
==============

The following default parameters are available for XSL as well as for the
header and footer files.  All paths use '/' as directory separators.


root
    This is the absolute path the the specified root.


input
    This is the absolute path to the input file.


output
    This is the absolute path to the output file.


inputrelroot
    This is the relative path from the input file to the root.  This will
    consist of zero repeating '../', one for each level the input is under
    the root.


outputrelroot
    This is the relative path from the output file to the root.  This will
    consist of zero repeating '../', one for each level the output is under
    the root.


relinput
    This is the relative path from the root to the input file.


reloutput
    This is the relative path from the root to the output file.



