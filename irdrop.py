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

################################################################################
# Error checking
################################################################################
def error(message):
    print('ERROR:', message)

def compare_pin_names(cdev_cells, pgarc_cells):
    for cell_name, pins in pgarc_cells.items():
        if cell_name in cdev_cells:
            for cdev_sub_cell, cdev_sub_cell_data in cdev_cells[cell_name].items():
                cdev_pins = cdev_cells[cell_name][cdev_sub_cell]['pins'].keys()
                for pin in pins:
                    if pin not in cdev_pins:
                        message = 'pin "{}" in pgarc but not in cdev for cell: "{}" and sub cell: "{}"'.format(pin, cell_name, cdev_sub_cell)
                        error(message)

################################################################################
# .cdev Parsing
################################################################################

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

    # Last cell also contains the final printed info line for the file, remove it
    cells[-1] = '\n'.join(cells[-1].splitlines()[:-1])

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

################################################################################
# .pgarc Parsing
################################################################################

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

################################################################################
# .spiprof Parsing
################################################################################

def parse_spiprof():
    '''
    Summary: splits up and extracts information for each spiprof cell
    Returns: dictionary of all cells in format <cell name> : [<pin name>]
    '''
    # First, split up pgarc file into a list of text segments for each individual cell
    with open(args.spiprof_filename,'r') as f:
        data = f.read()
        spiprof_cells = data.split('cell: ')
        del data
        spiprof_cells.pop(0) # First cell in split is empty, just delete it

    spiprof_cell_dict = {} # Result dictionary
    for spiprof_cell in spiprof_cells:
        spiprof_cell_name, spiprof_cell_data = parse_spiprof_cell(spiprof_cell)
        spiprof_cell_dict[spiprof_cell_name] = spiprof_cell_data

    return spiprof_cell_dict

def parse_spiprof_cell(cell):
    '''
    Summary: splits up a spiprof cell into subcells, each subcell consisting of one set of parameters, voltage, and data
    Returns: spiprof_cell_name: the name of the spiprof cell
             spiprof_sub_cell_dict: dictionary in format: <sub_cell parameters> : { <sub_cell voltage> : {sub_cell data}} 
    '''
    spiprof_sub_cells = cell.split('\n\n')
    spiprof_cell_name = spiprof_sub_cells[0]
    spiprof_sub_cells.pop(0)

    spiprof_sub_cell_dict = {}
    for sub_cell in spiprof_sub_cells:
        if (sub_cell != '\n'):

            # The first item in the split will contain parameters. The rest goes to a different function for more parsing
            spiprof_sub_cell_divide = sub_cell.split(';\n', 1)

            spiprof_parameters_group, spiprof_voltage_parameter, spiprof_parameters_hash, spiprof_voltage_hash = parse_spiprof_parameters(spiprof_sub_cell_divide[0])

            # Because there are mutiple entries with the same parameter hash, only create a new dictionary if one does not exist
            if spiprof_parameters_hash not in spiprof_sub_cell_dict:
                spiprof_sub_cell_dict[spiprof_parameters_hash] = {}

            for key, value in spiprof_parameters_group.items():
                spiprof_sub_cell_dict[spiprof_parameters_hash][key] = value

            spiprof_sub_cell_dict[spiprof_parameters_hash][spiprof_voltage_hash] = parse_spiprof_sub_cell(spiprof_sub_cell_divide[1])
            for key, value in spiprof_voltage_parameter.items():
                spiprof_sub_cell_dict[spiprof_parameters_hash][spiprof_voltage_hash][key] = value
        
    return spiprof_cell_name, spiprof_sub_cell_dict

def parse_spiprof_parameters(parameters):
    '''
    Summary: parses and hashes voltage and first-level parameter information.
             ie. "C1 = 0 F ; R = 0 Ohm ; C2 = 1e-15 F ; Slew1 = 1.25e-11 S ; Slew2 = 7.5e-12 S ;"
    Returns: spiprof_parameters_dict: dictionary in format: <parameter name>: <parameter value>
             spiprof_voltage_parameter: dictionary in format: <pin name> : <voltage value>
             spiprof_parameters_hash: string representing the other paramters for the subcell
             spiprof_voltage_hash: string representing the voltage parameter for the subcell
    '''
    spiprof_parameters_raw = parameters.split(' ;')
    spiprof_voltage = 0.0
    spiprof_parameters_dict = {}

    # Handling voltage separate than the other parameters because it has its own hash
    voltage_parameter_list = spiprof_parameters_raw[0].split(' = ', 1)
    voltage_name = voltage_parameter_list[0].lstrip()
    voltage_value_list = voltage_parameter_list[1].split(' ')
    spiprof_voltage = float(voltage_value_list[0])
    spiprof_voltage_parameter = {}
    spiprof_voltage_parameter[voltage_name] = spiprof_voltage
    #voltage_unit = voltage_value_list[1]
    spiprof_parameters_raw.pop(0)

    for parameter in spiprof_parameters_raw:
        parameter_list = parameter.split(' = ', 1)
        parameter_name = parameter_list[0].lstrip()
        parameter_value_list = parameter_list[1].split(' ')
        parameter_value = float(parameter_value_list[0])
        #parameter_value_unit = parameter_value_list[1]
        spiprof_parameters_dict[parameter_name] = parameter_value
        
    spiprof_parameters_hash_list = parameters.split(' ;', 1)
    spiprof_voltage_hash = spiprof_parameters_hash_list[0].lstrip()
    spiprof_parameters_hash = spiprof_parameters_hash_list[1].lstrip()
    return spiprof_parameters_dict, spiprof_voltage_parameter, spiprof_parameters_hash, spiprof_voltage_hash

def parse_spiprof_sub_cell(sub_cell):
    '''
    Summary: parses subcell data. Gets secondary parameters, data label names, and data
    Returns: spiprof_data_group_dict: dictionary in format: <parameter hash>: {<pin name>: {data label: data}}
    '''
    spiprof_data_group_dict = {}
    spiprof_data_group_list = sub_cell.split('      state = ')
    spiprof_data_group_list.pop(0)

    for data_group in spiprof_data_group_list:
        spiprof_data_dict = {}
        spiprof_data_lines = data_group.split('\n')
        spiprof_data_hash = 'state = ' + spiprof_data_lines[0]

        spiprof_data_parameters_dict = {}
        spiprof_data_parameters_raw = spiprof_data_lines[0].split(' ;')

        # because we have to split on state, and 'state = ' is erased, we need to handle it separately
        spiprof_data_parameters_dict['state'] = spiprof_data_parameters_raw[0]
        spiprof_data_parameters_raw.pop(0)

        for parameter in spiprof_data_parameters_raw:
            if parameter != '':
                parameter_list = parameter.split(' = ', 1)
                parameter_name = parameter_list[0].lstrip()
                parameter_value = parameter_list[1]
                spiprof_data_parameters_dict[parameter_name] = parameter_value 

        spiprof_data_lines.pop(0)

        # Store data labels to be used in lower dictionaries
        spiprof_data_labels = spiprof_data_lines[0].split()
        spiprof_data_labels.pop(0) # pop off empty cell

        spiprof_data_lines.pop(0)

        for spiprof_data_line in spiprof_data_lines:
            if (spiprof_data_line != 'Info: Done' and spiprof_data_line != ''):
                spiprof_data_raw = spiprof_data_line.split()
                spiprof_pin_name = spiprof_data_raw.pop(0) # pop off pin name
                spiprof_pin_data_dict = {}
                label_index = 0
                for spiprof_data_label in spiprof_data_labels:
                    spiprof_pin_data_dict[spiprof_data_label] = float(spiprof_data_raw[label_index * 2])
                    # data_unit = piprof_data_raw[label_index * 2 + 1]
                    label_index = label_index + 1
                spiprof_data_dict[spiprof_pin_name] = spiprof_pin_data_dict
        spiprof_data_group_dict[spiprof_data_hash] = spiprof_data_dict
    return spiprof_data_group_dict


cdev_cells = parse_cdev()
pgarc_cells = parse_pgarc()
spiprof_cells = parse_spiprof()

compare_pin_names(cdev_cells,  pgarc_cells)
