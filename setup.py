#!/usr/bin/env python

from setuptools import setup

setup(name='tabs-buoys',
      version='2.1',
      description='Read in TABS website (and other Texas) data',
      author='Kristen Thyng',
      author_email='kthyng@gmail.com',
      url='https://github.com/kthyng/tabs',
      py_modules=['tabs'],
      install_requires=['hydrofunctions', 'pandas', 'gsw', 're', 'traceback'],
     )
