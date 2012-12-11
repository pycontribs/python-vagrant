
import os
from setuptools import setup, find_packages

setup(
    name = 'python-vagrant',
    version = '0.2.0',
    license = 'MIT',
    description = 'Python bindings for interacting with Vagrant virtual machines.',
    long_description = open(os.path.join(os.path.dirname(__file__), 
                                         'README.md')).read(),
    keywords = 'python virtual machine box vagrant virtualbox vagrantfile',
    url = 'https://github.com/todddeluca/python-vagrant',
    author = 'Todd Francis DeLuca',
    author_email = 'todddeluca@yahoo.com',
    classifiers = ['License :: OSI Approved :: MIT License',
                   'Development Status :: 3 - Alpha',
                   'Programming Language :: Python :: 2',
                   'Programming Language :: Python :: 2.7',
                  ],
    py_modules = ['vagrant'],
)

