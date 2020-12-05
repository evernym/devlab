#!/usr/bin/env python3

import os
import sys

if len(sys.argv) < 2:
    sys.stderr.write('No file was passed as an argument\n')
    sys.exit(1)

TEMPLATE_FILE = sys.argv[1]

if not os.path.isfile(TEMPLATE_FILE):
    sys.stderr.write('File passed: {} NOT found!'.fomat(TEMPLATE_FILE))
    sys.exit(1)

with open(TEMPLATE_FILE,'r') as TFILE:
    TEMPLATE=TFILE.read()

# Perform substitutions
INJECTED_TEMPLATE = TEMPLATE.replace('{','{{')\
    .replace('}','}}')\
    .replace('((','{')\
    .replace('))','}')\
    .format(**os.environ)

print(INJECTED_TEMPLATE)
