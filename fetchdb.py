#!/usr/bin/python3

import argparse
import sqlite3
import os, sys
from argparse import RawTextHelpFormatter


# Set up and parse command line arguments
parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description='\n'.join([
    'Allows for simple fetch commands straight from the command line to allow users to easily see the data being returned.',
    '',
    'Tables and Columns:',
    '\t- cdev [cell, temperature, state, vector, active_input, active_output, vpwr, vgnd, pin, esc, esr, leak, filename]',
    '\t- spiprof [cell, vpwr, c1, r, c2, slew1, slew2, state, vector, active_input, active_output, pin, peak, area, width, filename]',
    '\t- pgarc [cell, pin]',
    '\t- lib [cell, area, filename]',
    '',
    'Examples:',
    '\t1) To grab all data pertaining to the cell dffnrq_1x from cdev:',
    '\t$ python3 fetchdb.py "SELECT * FROM cdev WHERE cell=\'dffnrq_1x\'"',
    '',
    '\t2) To grab all unique state variations from spiprof:',
    '\t$ python3 fetchdb.py "SELECT DISTINCT state FROM spiprof ORDER BY state"',
    '',
    '\t3) To grab the cells with the highest leakage current:',
    '\t$ python3 fetchdb.py "SELECT DISTINCT cell, leak FROM cdev ORDER BY leak DESC LIMIT 25"'
]))
parser.add_argument('query', help='''SQL query to execute''')
parser.add_argument('-d', '--database', type=str, default='./redhawk.db', help='File path for the database')
args = parser.parse_args()

# Connect to the database
if not os.path.isfile(args.database):
    print('ERROR: could not to connect to database ({})'.format(args.database))
    sys.exit()
connection = sqlite3.connect(args.database)

# Execute SQL fetch
cursor = connection.execute(args.query)

# Print data
names = [description[0] for description in cursor.description]
print('Columns Names:\n{}\n'.format(names))
print('Data:')
for row in cursor:
    print(row)
