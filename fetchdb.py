#!/usr/bin/python3

import argparse
import sqlite3
import os, sys

# Set up and parse command line arguments
parser = argparse.ArgumentParser(description='''Runs an IR drop analysis comparing
    the values of .cdev, .spiprof, and .pgarc files''')
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
