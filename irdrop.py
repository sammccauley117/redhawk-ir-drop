#!/usr/bin/python3

import argparse

# Set up and parse command line arguments
parser = argparse.ArgumentParser(description='''Runs an IR drop analysis comparing
    the values of .cdev, .spiprof, and .pgarc files''')
parser.add_argument('cdev_filename')
parser.add_argument('spiprof_filename')
parser.add_argument('pgarc_filename')
args = parser.parse_args()

print('cdev file:\t', args.cdev_filename)
print('spiprof file:\t', args.spiprof_filename)
print('pgarc file:\t', args.pgarc_filename)
