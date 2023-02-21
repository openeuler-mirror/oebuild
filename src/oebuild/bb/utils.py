# Copyright (C) 2004 Michael Lauer
#
# SPDX-License-Identifier: GPL-2.0-only
#

import os
import re

def preserved_envvars_exported():
    """Variables which are taken from the environment and placed in and exported
    from the metadata"""
    return [
        'BB_TASKHASH',
        'HOME',
        'LOGNAME',
        'PATH',
        'PWD',
        'SHELL',
        'USER',
        'LC_ALL',
        'BBSERVER',
    ]

def preserved_envvars():
    """Variables which are taken from the environment and placed in the metadata"""
    v = [
        'BBPATH',
        'BB_PRESERVE_ENV',
        'BB_ENV_WHITELIST',
        'BB_ENV_EXTRAWHITE',
    ]
    return v + preserved_envvars_exported()

def approved_variables():
    """
    Determine and return the list of whitelisted variables which are approved
    to remain in the environment.
    """
    if 'BB_PRESERVE_ENV' in os.environ:
        return os.environ.keys()
    approved = []
    if 'BB_ENV_WHITELIST' in os.environ:
        approved = os.environ['BB_ENV_WHITELIST'].split()
        approved.extend(['BB_ENV_WHITELIST'])
    else:
        approved = preserved_envvars()
    if 'BB_ENV_EXTRAWHITE' in os.environ:
        approved.extend(os.environ['BB_ENV_EXTRAWHITE'].split())
        if 'BB_ENV_EXTRAWHITE' not in approved:
            approved.extend(['BB_ENV_EXTRAWHITE'])
    return approved

def edit_metadata(meta_lines, variables, varfunc, match_overrides=False):
    """Edit lines from a recipe or config file and modify one or more
    specified variable values set in the file using a specified callback
    function. Lines are expected to have trailing newlines.
    Parameters:
        meta_lines: lines from the file; can be a list or an iterable
            (e.g. file pointer)
        variables: a list of variable names to look for. Functions
            may also be specified, but must be specified with '()' at
            the end of the name. Note that the function doesn't have
            any intrinsic understanding of _append, _prepend, _remove,
            or overrides, so these are considered as part of the name.
            These values go into a regular expression, so regular
            expression syntax is allowed.
        varfunc: callback function called for every variable matching
            one of the entries in the variables parameter. The function
            should take four arguments:
                varname: name of variable matched
                origvalue: current value in file
                op: the operator (e.g. '+=')
                newlines: list of lines up to this point. You can use
                    this to prepend lines before this variable setting
                    if you wish.
            and should return a four-element tuple:
                newvalue: new value to substitute in, or None to drop
                    the variable setting entirely. (If the removal
                    results in two consecutive blank lines, one of the
                    blank lines will also be dropped).
                newop: the operator to use - if you specify None here,
                    the original operation will be used.
                indent: number of spaces to indent multi-line entries,
                    or -1 to indent up to the level of the assignment
                    and opening quote, or a string to use as the indent.
                minbreak: True to allow the first element of a
                    multi-line value to continue on the same line as
                    the assignment, False to indent before the first
                    element.
            To clarify, if you wish not to change the value, then you
            would return like this: return origvalue, None, 0, True
        match_overrides: True to match items with _overrides on the end,
            False otherwise
    Returns a tuple:
        updated:
            True if changes were made, False otherwise.
        newlines:
            Lines after processing
    """

    var_res = {}
    if match_overrides:
        override_re = r'(_[a-zA-Z0-9-_$(){}]+)?'
    else:
        override_re = ''
    for var in variables:
        if var.endswith('()'):
            var_res[var] = re.compile(r'^(%s%s)[ \\t]*\([ \\t]*\)[ \\t]*{' % (var[:-2].rstrip(), override_re))
        else:
            var_res[var] = re.compile(r'^(%s%s)[ \\t]*[?+:.]*=[+.]*[ \\t]*(["\'])' % (var, override_re))

    updated = False
    varset_start = ''
    varlines = []
    newlines = []
    in_var = None
    full_value = ''
    var_end = ''

    def handle_var_end():
        prerun_newlines = newlines[:]
        op = varset_start[len(in_var):].strip()
        (newvalue, newop, indent, minbreak) = varfunc(in_var, full_value, op, newlines)
        changed = (prerun_newlines != newlines)

        if newvalue is None:
            # Drop the value
            return True
        elif newvalue != full_value or (newop not in [None, op]):
            if newop not in [None, op]:
                # Callback changed the operator
                varset_new = "%s %s" % (in_var, newop)
            else:
                varset_new = varset_start

            if isinstance(indent, int):
                if indent == -1:
                    indentspc = ' ' * (len(varset_new) + 2)
                else:
                    indentspc = ' ' * indent
            else:
                indentspc = indent
            if in_var.endswith('()'):
                # A function definition
                if isinstance(newvalue, list):
                    newlines.append('%s {\n%s%s\n}\n' % (varset_new, indentspc, ('\n%s' % indentspc).join(newvalue)))
                else:
                    if not newvalue.startswith('\n'):
                        newvalue = '\n' + newvalue
                    if not newvalue.endswith('\n'):
                        newvalue = newvalue + '\n'
                    newlines.append('%s {%s}\n' % (varset_new, newvalue))
            else:
                # Normal variable
                if isinstance(newvalue, list):
                    if not newvalue:
                        # Empty list -> empty string
                        newlines.append('%s ""\n' % varset_new)
                    elif minbreak:
                        # First item on first line
                        if len(newvalue) == 1:
                            newlines.append('%s "%s"\n' % (varset_new, newvalue[0]))
                        else:
                            newlines.append('%s "%s \\\n' % (varset_new, newvalue[0]))
                            for item in newvalue[1:]:
                                newlines.append('%s%s \\\n' % (indentspc, item))
                            newlines.append('%s"\n' % indentspc)
                    else:
                        # No item on first line
                        newlines.append('%s " \\\n' % varset_new)
                        for item in newvalue:
                            newlines.append('%s%s \\\n' % (indentspc, item))
                        newlines.append('%s"\n' % indentspc)
                else:
                    newlines.append('%s "%s"\n' % (varset_new, newvalue))
            return True
        else:
            # Put the old lines back where they were
            newlines.extend(varlines)
            # If newlines was touched by the function, we'll need to return True
            return changed

    checkspc = False

    for line in meta_lines:
        if in_var:
            value = line.rstrip()
            varlines.append(line)
            if in_var.endswith('()'):
                full_value += '\n' + value
            else:
                full_value += value[:-1]
            if value.endswith(var_end):
                if in_var.endswith('()'):
                    if full_value.count('{') - full_value.count('}') >= 0:
                        continue
                    full_value = full_value[:-1]
                if handle_var_end():
                    updated = True
                    checkspc = True
                in_var = None
        else:
            skip = False
            for (varname, var_re) in var_res.items():
                res = var_re.match(line)
                if res:
                    isfunc = varname.endswith('()')
                    if isfunc:
                        splitvalue = line.split('{', 1)
                        var_end = '}'
                    else:
                        var_end = res.groups()[-1]
                        splitvalue = line.split(var_end, 1)
                    varset_start = splitvalue[0].rstrip()
                    value = splitvalue[1].rstrip()
                    if not isfunc and value.endswith('\\'):
                        value = value[:-1]
                    full_value = value
                    varlines = [line]
                    in_var = res.group(1)
                    if isfunc:
                        in_var += '()'
                    if value.endswith(var_end):
                        full_value = full_value[:-1]
                        if handle_var_end():
                            updated = True
                            checkspc = True
                        in_var = None
                    skip = True
                    break
            if not skip:
                if checkspc:
                    checkspc = False
                    if newlines and newlines[-1] == '\n' and line == '\n':
                        # Squash blank line if there are two consecutive blanks after a removal
                        continue
                newlines.append(line)
    return (updated, newlines)

def edit_bblayers_conf(bblayers_conf, add, remove, edit_cb=None):
    """Edit bblayers.conf, adding and/or removing layers
    Parameters:
        bblayers_conf: path to bblayers.conf file to edit
        add: layer path (or list of layer paths) to add; None or empty
            list to add nothing
        remove: layer path (or list of layer paths) to remove; None or
            empty list to remove nothing
        edit_cb: optional callback function that will be called after
            processing adds/removes once per existing entry.
    Returns a tuple:
        notadded: list of layers specified to be added but weren't
            (because they were already in the list)
        notremoved: list of layers that were specified to be removed
            but weren't (because they weren't in the list)
    """

    import fnmatch

    def remove_trailing_sep(pth):
        if pth and pth[-1] == os.sep:
            pth = pth[:-1]
        return pth

    approved = approved_variables()
    def canonicalise_path(pth):
        pth = remove_trailing_sep(pth)
        if 'HOME' in approved and '~' in pth:
            pth = os.path.expanduser(pth)
        return pth

    def layerlist_param(value):
        if not value:
            return []
        elif isinstance(value, list):
            return [remove_trailing_sep(x) for x in value]
        else:
            return [remove_trailing_sep(value)]

    addlayers = layerlist_param(add)
    removelayers = layerlist_param(remove)

    # Need to use a list here because we can't set non-local variables from a callback in python 2.x
    bblayercalls = []
    removed = []
    plusequals = False
    orig_bblayers = []

    def handle_bblayers_firstpass(varname, origvalue, op, newlines):
        bblayercalls.append(op)
        if op == '=':
            del orig_bblayers[:]
        orig_bblayers.extend([canonicalise_path(x) for x in origvalue.split()])
        return (origvalue, None, 2, False)

    def handle_bblayers(varname, origvalue, op, newlines):
        updated = False
        bblayers = [remove_trailing_sep(x) for x in origvalue.split()]
        if removelayers:
            for removelayer in removelayers:
                for layer in bblayers:
                    if fnmatch.fnmatch(canonicalise_path(layer), canonicalise_path(removelayer)):
                        updated = True
                        bblayers.remove(layer)
                        removed.append(removelayer)
                        break
        if addlayers and not plusequals:
            for addlayer in addlayers:
                if addlayer not in bblayers:
                    updated = True
                    bblayers.append(addlayer)
            del addlayers[:]

        if edit_cb:
            newlist = []
            for layer in bblayers:
                res = edit_cb(layer, canonicalise_path(layer))
                if res != layer:
                    newlist.append(res)
                    updated = True
                else:
                    newlist.append(layer)
            bblayers = newlist

        if updated:
            if op == '+=' and not bblayers:
                bblayers = None
            return (bblayers, None, 2, False)
        else:
            return (origvalue, None, 2, False)

    with open(bblayers_conf, 'r') as f:
        (_, newlines) = edit_metadata(f, ['BBLAYERS'], handle_bblayers_firstpass)

    if not bblayercalls:
        raise Exception('Unable to find BBLAYERS in %s' % bblayers_conf)

    # Try to do the "smart" thing depending on how the user has laid out
    # their bblayers.conf file
    if bblayercalls.count('+=') > 1:
        plusequals = True

    removelayers_canon = [canonicalise_path(layer) for layer in removelayers]
    notadded = []
    for layer in addlayers:
        layer_canon = canonicalise_path(layer)
        if layer_canon in orig_bblayers and not layer_canon in removelayers_canon:
            notadded.append(layer)
    notadded_canon = [canonicalise_path(layer) for layer in notadded]
    addlayers[:] = [layer for layer in addlayers if canonicalise_path(layer) not in notadded_canon]

    (updated, newlines) = edit_metadata(newlines, ['BBLAYERS'], handle_bblayers)
    if addlayers:
        # Still need to add these
        for addlayer in addlayers:
            newlines.append('BBLAYERS += "%s"\n' % addlayer)
        updated = True

    if updated:
        with open(bblayers_conf, 'w') as f:
            f.writelines(newlines)

    notremoved = list(set(removelayers) - set(removed))

    return (notadded, notremoved)
