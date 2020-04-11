#!/usr/bin/python3

import argparse

# Set up and parse command line arguments
parser = argparse.ArgumentParser(description='''Runs an IR drop analysis comparing
    the values of .cdev, .spiprof, and .pgarc files''')
parser.add_argument('cdev_filename')
parser.add_argument('spiprof_filename')
parser.add_argument('pgarc_filename')
args = parser.parse_args()

def parse_cdev():
    '''
    Summary: splits up and extracts information for each cdev cell
    Returns: dictionary of all cells in format <cell name> : {<sub_cells>}
    '''
    # First, split up cdev file into a list of text segments for each individual cell
    with open(args.cdev_filename,'r') as f:
        data = f.read()
        cells = data.split('Info: cell=')
        cells.pop(0) # First element of the split is just the header info, delete it

    # Parse info from each cell and add it to the result cell dictionary
    cell_dict = {} # Result dictionary
    for cell in cells:
        cell_name, cell_data = parse_cdev_cell(cell)
        cell_dict[cell_name] = cell_data

    return cell_dict

def parse_cdev_cell(cell):
    '''
    Summary: parses information out of an *individual* cdev cell
    Input: string of cdev cell text
    Returns:
        1) Cell name
        2) Dictionary of information for each sub_cell configuration
    '''
    # Get cell name and (unparsed) data string
    cell_name = cell.splitlines()[0]  # Name is first line
    cell_data = cell.splitlines()[1:] # Data is everything *except* the first line

    # Split up cell into each sub-cell / parameter configuration
    sub_cells = [[]] # Initialize with an empty first sub-cell
    pin_previous = False # Was the previous line part of the pin level?
    for line in cell_data:
        pin_current = line.strip().startswith('pin = ') # Is the current line part of the pin level?
        # Check if a new sub cell was started--previous pin view was ended
        if not pin_current and pin_previous:
            sub_cells.append([]) # Start a new sub cell
        sub_cells[-1].append(line)
        pin_previous = pin_current

    # Parse individual sub cells and add each sub cell info to our result dictionary
    sub_cell_dict = {} # Result dictionary
    for sub_cell in sub_cells:
        parameter_data, pin_data = parse_cdev_sub_cell(sub_cell)
        parameter_data_hash = str(parameter_data)
        sub_cell_dict[parameter_data_hash] = parameter_data
        # Add the pin data
        sub_cell_dict[parameter_data_hash]['pins'] = pin_data


    return cell_name, sub_cell_dict

def parse_cdev_sub_cell(sub_cell):
    '''
    Summary: parses information out of an cdev sub cell
    Input: string of cdev sub cell text
    Returns:
        1) Dictionary of sub cell's parameter information (used as sub cells hash key)
        2) Dictionary of sub cell's pin information
    '''
    # Split lines up into pin lines and parameter lines
    pin_lines = []
    parameter_lines = []
    for line in sub_cell:
        if line.strip().startswith('pin = '):
            pin_lines.append(line)
        else:
            parameter_lines.append(line)

    # Get initial pin data: everything BUT voltage, we'll get that later
    pin_dict = {}
    for line in pin_lines:
        segments = line.split(',') # Data segments
        pin_name = segments[0].split(' ')[-1] # Pin name is the last word of the first data segment
        # Make a new pin entry if its not already in our pins dictionary
        if pin_name not in pin_dict:
            pin_dict[pin_name] = {}
        # Parse and add the actual data, ex: esc, esr, leakage...
        for segment in segments[1:]:
            variable = segment.split('=')[0].strip()
            value = segment.split('=')[1].strip()
            pin_dict[pin_name][variable] = value

    # Get parameter data
    parameter_dict = {}
    for line in parameter_lines:
        parameters = line.split(';') # Each parameter is seperated by a ;
        # Extract info for each parameter
        for parameter in parameters:
            if '=' in parameter:
                variable = parameter.split('=')[0].strip()
                value = parameter.split('=')[1].strip()
                parameter_dict[variable] = value
                # Check to see if it's a pin voltage parameter: add it to the pin info too
                if variable in pin_dict:
                    pin_dict[variable]['voltage'] = value

    return parameter_dict, pin_dict

print(parse_cdev())
