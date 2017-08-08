#!/usr/bin/env python
# programmer : Daofeng

from setuptools import setup


setup (
    name='submitTaRGET',
    version='1.0.3',
    description='Bulk upload data to target dcc',
    url='https://github.com/xzhuo/TargetBulkUpload',
    author='Xiaoyu Zhuo',
    author_email='xzhuo@wustl.edu',
    license='MIT',
    install_requires=['xlrd'],
    scripts=['submitTaRGET']
)
