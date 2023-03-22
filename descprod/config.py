# config.py

import sys
import os

def check_config(config):
    ''''
    Check if a string is valid field, simple or compound configuration.
    Returns 0 - valid string
            1 - Invalid character
            2 - Four or mor contiguous dashes
            3 - Exactly two contiguos dashes
            4 - Not a string
    '''
    if type(config) is not str: return 4
    for char in config:
        if not char.isalpha() and char != ':' and char != '-' : return 1
    if config.find('----') >= 0: return 2
    for cfg in split_compound_config(config):
        if cfg.find('--') >= 0: return 3
    return 0

def split_config_field(field):
    return field.split(':')

def split_config(config):
    return config.split('-')

def split_compound_config(compound):
    return compound.split('---')

def split_config_field_main():
    myname = os.path.basename(sys.argv[0])
    args = sys.argv[1:]
    dohelp = len(args) != 1
    field = '-h' if dohelp else args[0]
    if field == '-h':
        print(f"Usage: {myname} [-h] CONFIG_FIELD")
        return 0
    chk = check_config(field)
    if chk: return chk
    if field.find('-') >= 0: return 5
    sout = ''
    sep = ''
    for value in split_config_field(field):
        sout += f"{sep}{value}"
        sep = ' '
    print(sout)
    return 0

def split_config_main():
    myname = os.path.basename(sys.argv[0])
    args = sys.argv[1:]
    dohelp = len(args) != 1
    config = '-h' if dohelp else args[0]
    if config == '-h':
        print(f"Usage: {myname} [-h] CONFIG")
        return 0
    chk = check_config(config)
    if chk: return chk
    sout = ''
    sep = ''
    for field in split_config(config):
        sout += f"{sep}{field}"
        sep = ' '
    print(sout)
    return 0

def split_compound_config_main():
    myname = os.path.basename(sys.argv[0])
    args = sys.argv[1:]
    dohelp = len(args) != 1
    cconfig = '-h' if dohelp else args[0]
    if cconfig == '-h':
        print(f"Usage: {myname} [-h] COMPOUND_CONFIG")
        return 0
    chk = check_config(cconfig)
    if chk: return chk
    sout = ''
    sep = ''
    for config in split_compound_config(cconfig):
        sout += f"{sep}{config}"
        sep = ' '
    print(sout)
    return 0
