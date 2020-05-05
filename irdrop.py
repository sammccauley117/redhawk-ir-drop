#!/usr/bin/python3

import argparse
import sqlite3
import os
import re
import matplotlib
import numpy as np

# Set up and parse command line arguments
parser = argparse.ArgumentParser(description='''Runs an IR drop analysis comparing
    the values of .cdev, .spiprof, and .pgarc files''')
parser.add_argument('input_file', help=''''Name of the file containing
    all the Redhawk views (.cdev, .pgarc, .spiprof, and .lib files)''')
parser.add_argument('-e', '--errorfile', type=str, default='./error.log', help='Name of the output error file')
parser.add_argument('-d', '--database', type=str, default='./redhawk.db', help='File path for the database')
args = parser.parse_args()

# Load the list of files
with open(args.input_file) as f:
    files = f.readlines()
files = [file.strip() for file in files]

# Establish what the units for each cdev variable should be
CDEV_UNITS = {
    'voltage': 'V',
    'esc': 'F',
    'esr': 'ohm',
    'leak': 'A',
    'Temperature': 'C'
}

SPIPROF_UNITS = {
    'VPWR': 'V',
    'C1': 'F',
    'R': 'Ohm',
    'C2': 'F',
    'Slew1': 'S',
    'Slew2': 'S',
    'peak': 'A',
    'area': 'C',
    'width': 'S'
}

error_set = set()

################################################################################
# Database creation
################################################################################

def create_tables(connection):
    cursor = connection.cursor()

    # Create cdev table
    cursor.execute('''
    CREATE TABLE cdev
    (cell, temperature, state, vector, active_input, active_output,
    vpwr, vgnd, pin, esc, esr, leak, filename)
    ''')

    # Create spiprof table
    cursor.execute('''
    CREATE TABLE spiprof
    (cell, vpwr, c1, r, c2, slew1, slew2, state, vector, active_input, active_output,
    pin, peak, area, width)
    ''')

    # Create pgarc table
    cursor.execute('''
    CREATE TABLE pgarc
    (cell, pin)
    ''')

    # Create liberty file table
    cursor.execute('''
    CREATE TABLE lib
    (cell, area, filename)
    ''')

    # Save changes
    connection.commit()


################################################################################
# Error checking
################################################################################
def error(message):
    '''
    Summary: adds an error message to the error set
    Input:
        message: string of the error message
    '''
    if message not in error_set:
        error_set.add('ERROR: ' + message)

def output_errors(filename):
    '''
    Summary: writes all the errors in the error set to the error file
    Input:
        filename: path of the error file
    '''
    if (len(error_set) == 0):
        print('No errors found.')
    else:
        print('Errors found. Please refer to ' + filename)
        with open(filename, 'w') as error_file:
            for error in error_set:
                error_file.write(error + '\n')

def compare_pin_names(connection):
    cursor = connection.cursor()

    # Query pin names for each view
    pgarc_pin_names_query = '''SELECT DISTINCT cell, pin FROM pgarc'''
    cursor.execute(pgarc_pin_names_query)
    pgarc_pin_names = np.array(cursor.fetchall())

    cdev_pin_names_query = '''SELECT DISTINCT cell, pin FROM cdev'''
    cursor.execute(cdev_pin_names_query)
    cdev_pin_names = np.array(cursor.fetchall())

    spiprof_pin_names_query = '''SELECT DISTINCT cell, pin FROM spiprof'''
    cursor.execute(spiprof_pin_names_query)
    spiprof_pin_names = np.array(cursor.fetchall())

    # Compare cdev and spiprof pins against pgarc pins
    for cell in pgarc_pin_names:
        cell_name = cell[0]
        pin_name = cell[1]

        # Extract pin names from views
        extracted_cdev_cell = cdev_pin_names[np.where(cdev_pin_names[:,0] == cell_name),:].squeeze(axis = 0)
        extracted_cdev_pins = extracted_cdev_cell[:,1]
        extracted_spiprof_cell = spiprof_pin_names[np.where(spiprof_pin_names[:,0] == cell_name),:].squeeze(axis = 0)
        extracted_spiprof_pins = extracted_spiprof_cell[:,1]

        if len(extracted_cdev_pins) != 0:
            if pin_name not in extracted_cdev_pins:
                message = 'pin {pin} mismatch between pgarc and cdev for cell {cell}'.format(pin = pin_name, cell = cell_name)
                error(message)

        if len(extracted_spiprof_pins) != 0:
            if pin_name not in extracted_spiprof_pins:
                message = 'pin {pin} mismatch between pgarc and spiprof for cell {cell}'.format(pin = pin_name, cell = cell_name)
                error(message)

def compare_cell_names(connection):
    # Query cdev and spiprof cells that aren't in pgarc
    cdev_query = '''SELECT cell FROM pgarc WHERE cell NOT IN (SELECT cell FROM cdev)'''
    spiprof_query = '''SELECT cell FROM pgarc WHERE cell NOT IN (SELECT cell from spiprof)'''

    cursor = connection.cursor()

    for cell in cursor.execute(cdev_query):
        message = 'cell {} in pgarc but not in cdev'.format(str(cell).replace('(\'','').replace('\',)',''))
        error(message)

    for cell in cursor.execute(spiprof_query):
        message = 'cell {} in pgarc but not in spiprof'.format(str(cell).replace('(\'','').replace('\',)',''))
        error(message)

def check_voltage_variations(connection):
    cursor = connection.cursor()

    # Extract nominal voltage from cdev view
    nominal_voltage_query = '''SELECT DISTINCT cell, vpwr FROM cdev'''
    cursor.execute(nominal_voltage_query)
    nominal_voltages = np.array(cursor.fetchall())

    # Extract voltage variations from spiprof view
    spiprof_voltage_query = '''SELECT DISTINCT cell, vpwr FROM spiprof'''
    cursor.execute(spiprof_voltage_query)
    spiprof_voltages = np.array(cursor.fetchall())

    variation_percentages = np.array([0.88, 0.92, 0.96, 1.00, 1.05, 1.10, 1.15])

    for cell in nominal_voltages:
        # Extract cell name and nominal value
        cell_name = cell[0]
        nominal_value = cell[1]

        # Calculate expected voltage variations
        voltage_variations = np.around(variation_percentages * float(nominal_value), decimals = 4)

        # Find matching cell name from spiprof view and extract voltages
        extracted_cell = spiprof_voltages[np.where(spiprof_voltages[:,0] == cell_name),:].squeeze(axis = 0)
        extracted_voltages = extracted_cell[:,1].astype(float)

        # Check if voltages match
        if len(extracted_voltages) != 0:
            for voltage in voltage_variations:
                if voltage not in extracted_voltages:
                    message = 'voltage {voltage} expected in cell {cell} but not found'.format(voltage = voltage, cell = cell_name)
                    error(message)

################################################################################
# .cdev Parsing
################################################################################
def insert_cdev(filename, connection):
    '''
    Summary: takes a cdev file, parses it, and inserts it into the cdev database table
    Input:
        filename: filename of the cdev file to be inserted
        connection: sqllite connection object
    '''
    # Parse the cdev file into JSON format
    cells = parse_cdev(filename)

    # Iterate through all the JSON cells, parameter variations, and pins. Push each unit of data
    # to the database table
    for cell, parameters_variations in cells.items():
        for parameters in parameters_variations.values():
            for pin, pin_data in parameters['pins'].items():
                query = '''INSERT INTO cdev VALUES ("{cell}", {temperature}, "{state}", "{vector}", "{active_input}",
                    "{active_output}", {vpwr}, {vgnd}, "{pin}", {esc}, {esr}, {leak}, "{filename}")'''.format(cell=cell,
                    temperature=parameters['Temperature'], state=parameters['State'], vector=parameters['vector'],
                    active_input=parameters['active_input'], active_output=parameters['active_output'],
                    vpwr=parameters['VPWR'], vgnd=parameters['VGND'], pin=pin, esc=pin_data['esc'], esr=pin_data['esr'],
                    leak=pin_data['leak'], filename=filename)
                cursor = connection.cursor()
                cursor.execute(query)

    # Commit/save the changes to the database table
    connection.commit()

def parse_cdev(filename):
    '''
    Summary: splits up and extracts information for each cdev cell
    Input: cdev filename
    Returns: dictionary of all cells in format <cell name> : {<sub_cells>}
    '''
    # First, split up cdev file into a list of text segments for each individual cell
    with open(filename,'r') as f:
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

def parse_pgarc(filename, connection):
    '''
    Summary: splits up and extracts information (pin names) for each pgarc cell
    Returns: dictionary of all cells in format <cell name> : [<pin name>]
    '''
    # First, split up pgarc file into a list of text segments for each individual cell
    with open(filename,'r') as f:
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
        cursor = connection.cursor()
        for pin in cell_pins:
            query = "INSERT INTO pgarc VALUES (\"{cell}\", \"{pin}\")".format(cell = cell_name, pin = pin)
            cursor.execute(query)

    connection.commit()
    return cell_dict

################################################################################
# .spiprof Parsing
################################################################################

def parse_spiprof(file, connection):
    '''
    Summary: splits up and extracts information for each spiprof cell
    Returns: dictionary of all cells in format <cell name> : [<pin name>]
    '''
    # First, split up pgarc file into a list of text segments for each individual cell
    with open(file,'r') as f:
        data = f.read()
        spiprof_cells = data.split('cell: ')
        del data
        spiprof_cells.pop(0) # First cell in split is empty, just delete it

    spiprof_cell_dict = {} # Result dictionary
    for spiprof_cell in spiprof_cells:
        parse_spiprof_cell(spiprof_cell, connection)
        connection.commit()

def parse_spiprof_cell(cell, connection):
    '''
    Summary: splits up a spiprof cell into subcells, each subcell consisting of one set of parameters, voltage, and data
    Calls helper functions that will add to the redhawk db
    '''
    spiprof_sub_cells = cell.split('\n\n')
    spiprof_cell_name = spiprof_sub_cells[0].split()[0]
    spiprof_sub_cells.pop(0)

    spiprof_sub_cell_dict = {}
    for sub_cell in spiprof_sub_cells:
        if (sub_cell != '\n'):

            # The first item in the split will contain parameters. The rest goes to a different function for more parsing
            spiprof_sub_cell_divide = sub_cell.split(';\n', 1)

            spiprof_parameters_group, spiprof_voltage_parameter = parse_spiprof_parameters(spiprof_cell_name, spiprof_sub_cell_divide[0])

            # Because there are mutiple entries with the same parameter hash, only create a new dictionary if one does not exist
            parse_spiprof_sub_cell(spiprof_cell_name, spiprof_voltage_parameter, spiprof_parameters_group, spiprof_sub_cell_divide[1], connection)


def parse_spiprof_parameters(cell_name, parameters):
    '''
    Summary: parses and hashes voltage and first-level parameter information.
             ie. "C1 = 0 F ; R = 0 Ohm ; C2 = 1e-15 F ; Slew1 = 1.25e-11 S ; Slew2 = 7.5e-12 S ;"
    Returns: spiprof_parameters_dict: dictionary in format: <parameter name>: <parameter value>
             spiprof_voltage_parameter: dictionary in format: <pin name> : <voltage value>
    '''
    spiprof_parameters_raw = parameters.split(' ;')
    spiprof_voltage = 0.0
    spiprof_parameters_dict = {}

    # Handling voltage separate than the other parameters because it has its own hash
    voltage_parameter_list = spiprof_parameters_raw[0].split(' = ', 1)
    voltage_name = voltage_parameter_list[0].lstrip()
    voltage_value_list = voltage_parameter_list[1].split(' ')
    spiprof_voltage = float(voltage_value_list[0])
    spiprof_voltage_parameter = (voltage_name, spiprof_voltage)
    voltage_unit = voltage_value_list[1]
    if (voltage_unit != SPIPROF_UNITS['VPWR']):
        error("Cell " + cell_name + " has incorrect voltage units. Expected \"" + SPIPROF_UNITS['VPWR'] + "\" but found \"" + voltage_unit + "\".")
    spiprof_parameters_raw.pop(0)

    for parameter in spiprof_parameters_raw:
        parameter_list = parameter.split(' = ', 1)
        parameter_name = parameter_list[0].lstrip()
        parameter_value_list = parameter_list[1].split(' ')
        parameter_value = float(parameter_value_list[0])
        parameter_value_unit = parameter_value_list[1].strip()
        if (parameter_value_unit != SPIPROF_UNITS[parameter_name]):
            error("Cell " + cell_name + " has incorrect " + parameter_name + " units. Expected \"" + SPIPROF_UNITS[parameter_name] + "\" but found \"" + parameter_value_unit + "\".")
        spiprof_parameters_dict[parameter_name] = parameter_value

    return spiprof_parameters_dict, spiprof_voltage_parameter

def parse_spiprof_sub_cell(cell_name, voltage_parameter, cell_parameters, sub_cell, connection):
    '''
    Summary: parses subcell data. Gets secondary parameters, data label names, and data
    Checks if sequential cells have 4 states, and that combinational cells have 2 states. Uses name of cell.
    Inserts cell data into the database.
    '''
    spiprof_data_group_dict = {}
    spiprof_data_group_list = sub_cell.split('      state = ')
    spiprof_data_group_list.pop(0)

    if (cell_name.startswith('dff') or cell_name.startswith('sdff') or cell_name.startswith('latch')):
        if (len(spiprof_data_group_list) != 4):
            error("Cell " + cell_name + " is probably sequential, so it should have 4 states. Instead, it has " + str(len(spiprof_data_group_list)) + " states.")
    else:
        if (len(spiprof_data_group_list) != 2):
            error("Cell " + cell_name + " is probably combinational, so it should have 2 states. Instead, it has " + str(len(spiprof_data_group_list)) + " states.")

    for data_group in spiprof_data_group_list:
        spiprof_data_dict = {}
        spiprof_data_lines = data_group.split('\n')

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
                    data_unit = spiprof_data_raw[label_index * 2 + 1]
                    if (data_unit != SPIPROF_UNITS[spiprof_data_label]):
                        error("Cell " + cell_name + " has incorrect " + spiprof_data_label + " units. Expected \"" + SPIPROF_UNITS[spiprof_data_label] + "\" but found \"" + data_unit + "\".")
                    label_index = label_index + 1
                spiprof_data_dict[spiprof_pin_name] = spiprof_pin_data_dict
                query = "INSERT INTO spiprof VALUES (\"{cell}\", {vpwr}, {c1}, {r}, {c2}, {slew1}, {slew2}, \"{state}\", \"{vector}\", \"{active_input}\", \"{active_output}\", \"{pin}\", {peak}, {area}, {width})".format(cell=cell_name, vpwr=voltage_parameter[1], c1=cell_parameters["C1"], r=cell_parameters["R"], c2=cell_parameters["C2"], slew1=cell_parameters["Slew1"], slew2=cell_parameters["Slew2"], state=spiprof_data_parameters_dict['state'], vector=spiprof_data_parameters_dict['vector'], active_input=spiprof_data_parameters_dict['active_input'], active_output=spiprof_data_parameters_dict['active_output'], pin=spiprof_pin_name, peak=spiprof_pin_data_dict['peak'], area=spiprof_pin_data_dict['area'], width=spiprof_pin_data_dict['width'])
                #print(query)
                cursor = connection.cursor()
                cursor.execute(query)

################################################################################
# .lib Parsing
################################################################################
def insert_lib(filename, connection):
    '''
    Summary: reads a liberty file, extracts the name and area of a cell, and inserts
        it into a database
    Input:
        filename: liberty filename
        connection: sqllite connection object
    '''
    # First, split up lib file into a list of raw text segments for each individual cell
    with open(filename,'r') as f:
        data = f.read()
    cells_raw = re.compile("[^_]cell \(").split(data)
    cells_raw.pop(0) # First index of the split is header info, throw it out

    # Iterate through each cell, grab its name and area, and insert it into the database
    for cell_raw in cells_raw:
        # Get name
        name = cell_raw.split(')')[0]
        if name.startswith("\""):
            name = name[1:]
        if name.endswith("\""):
            name = name[:-1]

        # Get area
        for line in cell_raw.splitlines():
            if line.strip().startswith('area : '):
                area = line.strip().split('area : ')[-1]
                if area[-1] == ';': area = area[:-1]
                area = float(area)
                break

        # Insert into database
        query = 'INSERT INTO lib VALUES ("{cell}", {area}, "{filename}")'.format(cell=name, area=area, filename=filename)
        cursor = connection.cursor()
        cursor.execute(query)

    connection.commit() # Save database changes

################################################################################
# Main script
################################################################################

# Check if db already exists: if so, delete it to allow for a fresh one to be made
if(os.path.isfile(args.database)):
    os.remove(args.database)

# Initialize database
connection = sqlite3.connect(args.database)
create_tables(connection)

# Insert the file data into the database
for file in files:
    print("Parsing: " + file, flush=True)
    if file.endswith('.cdev'):
        insert_cdev(file, connection)
    elif file.endswith('.spiprof'):
        parse_spiprof(file, connection)
    elif file.endswith('.lib'):
        insert_lib(file, connection)
    elif file.endswith('.pgarc'):
        parse_pgarc(file, connection)

# Print sample data
print('cdev sample:')
for row in connection.execute('SELECT * FROM cdev LIMIT 10'):
    print(row)
print('\nspiprof sample:')
for row in connection.execute('SELECT * FROM spiprof LIMIT 10'):
    print(row)
print('\npgarc sample:')
for row in connection.execute('SELECT * FROM pgarc LIMIT 10'):
    print(row)
print('\nlib sample:')
for row in connection.execute('SELECT * FROM lib LIMIT 10'):
    print(row)
print()

# Run additional QA
compare_cell_names(connection)
check_voltage_variations(connection)
compare_pin_names(connection)

# Log errors
output_errors(args.errorfile)
