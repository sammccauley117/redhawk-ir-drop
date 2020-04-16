#!/usr/bin/python3

import argparse

# Set up and parse command line arguments
parser = argparse.ArgumentParser(description='''Runs an IR drop analysis comparing
    the values of .cdev, .spiprof, and .pgarc files''')
parser.add_argument('cdev_filename')
parser.add_argument('spiprof_filename')
parser.add_argument('pgarc_filename')
args = parser.parse_args()

# Establish what the units for each cdev variable should be
CDEV_UNITS = {
    'voltage': 'V',
    'esc': 'F',
    'esr': 'ohm',
    'leak': 'A',
    'Temperature': 'C'
}

def error(message):
    print('ERROR:', message)

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
        parameter_data, pin_data = parse_cdev_sub_cell(sub_cell, cell_name)
        parameter_data_hash = str(parameter_data)
        sub_cell_dict[parameter_data_hash] = parameter_data
        # Add the pin data
        sub_cell_dict[parameter_data_hash]['pins'] = pin_data


    return cell_name, sub_cell_dict

def parse_cdev_sub_cell(sub_cell, cell_name):
    '''
    Summary: parses information out of an cdev sub cell
    Input:
        sub_cell: string of cdev sub cell text
        cell_name: string name of the cell being parsed, used for error messages
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
        parameters = line.split(',') # Pin parameters are each seperated by commas
        pin_name = parameters[0].split(' ')[-1] # Pin name is the last word of the first data segment
        # Make a new pin entry if its not already in our pins dictionary
        if pin_name not in pin_dict:
            pin_dict[pin_name] = {}
        # Parse and add the actual data, ex: esc, esr, leakage...
        for parameter in parameters[1:]:
            variable, value = parse_cdev_parameter(parameter, cell_name)
            pin_dict[pin_name][variable] = value

    # Get parameter data
    parameter_dict = {}
    for line in parameter_lines:
        parameters = line.split(';') # Each parameter is seperated by a ;
        # Extract info for each parameter
        for parameter in parameters:
            if '=' in parameter:
                variable, value = parse_cdev_parameter(parameter, cell_name, pin_dict)
                parameter_dict[variable] = value
                # Check to see if it's a pin voltage parameter: add it to the pin info too
                if variable in pin_dict:
                    pin_dict[variable]['voltage'] = value

    return parameter_dict, pin_dict

def parse_cdev_parameter(parameter_string, cell_name, pin_dict={}):
    '''
    Summary: parses a single parameter string in the form "<variable> = <value>",
        converts to float if possible, and verifies units
    Inputs:
        parameter_string: string in the form "<variable> = <value>"
        cell_name: string name of the cell being parsed, used for error messages
        pin_dict: optional dictionary containing the pin names for the scenario that a pin
            name is the variable and the unit needs to be verified that it is in V
    Returns:
        variable: string variable name
        value: value of the variable, either a string or a float
    '''
    variable = parameter_string.split('=')[0].strip()
    data = parameter_string.split('=')[1].strip().split(' ')
    has_unit = True if len(data) == 2 else False

    # If there is a unit, data[0] is assumed to be the float value and data[1] the unit
    # Check to make sure it is a valid unit
    if has_unit:
        try:
            # Try casting the variable data as a float if possible and verify the unit
            value = float(data[0])
            unit = data[1]
            if variable in CDEV_UNITS:
                if unit != CDEV_UNITS[variable]:
                    message = "Unknown unit '{}' for variable '{}' in cdev cell: {}".format(unit, variable, cell_name)
                    error(message)
            else:
                # Variable could be a pin, if not then it's unknown
                if variable not in pin_dict:
                    message = "Unknown variable '{}' for cdev cell: {}".format(variable, cell_name)
                    error(message)
            return variable, value
        except:
            # data[0] does not appear to be a float, this must be some variable we
            # haven't seen before, rejoin the variable data and return it as a string
            return variable, ' '.join(data)

    # There does not appear to be a unit, treat the value as a string
    value = parameter_string.split('=')[1].strip()
    return variable, value

def parse_pgarc():
    '''
    Summary: splits up and extracts information (pin names) for each pgarc cell
    Returns: dictionary of all cells in format <cell name> : [<pin name>]
    '''
    # First, split up pgarc file into a list of text segments for each individual cell
    with open(args.pgarc_filename,'r') as f:
        data = f.read()
        cells = data.split('cell ')
        cells.pop(0) # First cell in split is empty, just delete it

    # Parse cell name and pins from each cell and add it to the result cell dictionary
    cell_dict = {} # Result dictionary
    for cell in cells:
        # Split up cell into *just* an array of the important words: cell name and pins
        cell = cell.replace('{',' ')
        cell = cell.replace('}',' ')
        cell = cell.replace('\n',' ')
        cell_words = [word for word in cell.split(' ') if (word != '' and word != 'pgarc')]

        # Extract cell name and pin list from cell words and push it all to the result dictionary
        cell_name = cell_words[0]
        cell_pins = cell_words[1:]
        cell_dict[cell_name] = cell_pins

    return cell_dict

print(parse_cdev())
