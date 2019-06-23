#!/usr/bin/env python

from setuptools import setup, find_packages

# Hack to prevent stupid TypeError: 'NoneType' object is not callable error on
# exit of python setup.py test # in multiprocessing/util.py _exit_function when
# running python setup.py test (see
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
try:
    import multiprocessing
    assert multiprocessing
except ImportError:
    pass

setup(
    name='orwell.proxy-robots',
    version='0.0.1',
    description='Very simple python proxy to make it possible '
    'for the server to communicate with robots.',
    author='',
    author_email='',
    packages=find_packages(exclude="test"),
    test_suite='nose.collector',
    install_requires=['pyzmq', 'enum34', 'protobuf'],
    tests_require=['nose'],
    entry_points={
        'console_scripts': [
            'proxy_robots = orwell.proxy_robots.program:main',
        ]
    },
)
