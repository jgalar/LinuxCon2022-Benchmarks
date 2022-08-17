# Copyright (c) PLUMgrid, Inc.
# Licensed under the Apache License, Version 2.0 (the "License")
from distutils.core import setup
import os
import sys

# sdist does not support --root.
if "sdist" not in sys.argv and os.environ.get('DESTDIR'):
    sys.argv += ['--root', os.environ['DESTDIR']]

setup(name='bcc',
      version='0.25.0',
      description='BPF Loader Library',
      author='Brenden Blanco',
      author_email='bblanco@plumgrid.com',
      url='https://github.com/iovisor/bcc',
      packages=['bcc'],
      platforms=['Linux'])
