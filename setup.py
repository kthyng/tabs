#!/usr/bin/env python

from distutils.core import setup

setup(name='tabs',
      version='2.0',
      description='Read in TABS website (and other Texas) data',
      author='Kristen Thyng',
      author_email='kthyng@gmail.com',
      url='https://github.com/kthyng/tabs',
      py_modules=['tabs'],
      install_requires=['hydrofunctions', 'pandas', 'gsw', 're', 'traceback'],
     )
