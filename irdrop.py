#!/usr/bin/python3

import argparse, re

# Set up and parse command line arguments
parser = argparse.ArgumentParser(description='''Runs an IR drop analysis comparing
    the values of .cdev, .spiprof, and .pgarc files''')
parser.add_argument('cdev_filename')
parser.add_argument('spiprof_filename')
parser.add_argument('pgarc_filename')
args = parser.parse_args()

def parse_cdev_cell(cell):
    '''
    Summary: parses information out of individual cdev cells
    Input: string of cdev cell text
    '''
    # Get cell name: the first word in a cell
    name = cell.splitlines()[0]

    # Use regular expressions to grab parameter information like temperature, state, etc.
    # Group data is in parentheses and are in order 1, 2, 3, etc.
    param_re = r'Temperature = (.*) C; State = (.*); vector = (.*); active_input = (.*); active_output = (.*);'
    param_search = re.search(param_re, cell)
    # Make sure RegEx search actually had a result
    if param_search:
        # Strip RegEx data from groups
        temperature = param_search.group(1)
        state = param_search.group(2)
        vector = param_search.group(3)
        active_input = param_search.group(4)
        active_output = param_search.group(5)
    else:
        print('Potential error for cell:', name)

    # No return statement yet, just print out what we found
    print('Cell: {}\t Temperature: {}\t State: {}\t Vector: {}\t Active Input: {}\t Active Output: {}'.format(
        name, temperature, state, vector, active_input, active_output))

def parse_cdev():
    # First, split up cdev file into a list of text segments for each individual cell
    with open(args.cdev_filename,'r') as f:
        data = f.read()
        cells = data.split('Info: cell=')
        cells.pop(0) # First element of the split is just the header info, delete it

    # Parse info from each cell
    for cell in cells:
        parse_cdev_cell(cell)

parse_cdev()
