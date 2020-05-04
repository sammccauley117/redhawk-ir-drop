#!/usr/bin/python3

import sqlite3
import os.path
import matplotlib.pyplot as plt
import numpy as np

def peak_vpwr_vary_state(connection):
    cursor = connection.cursor()

    # Query State, VPWR, and Peak Current for only the first 7 sections of dffnrq_1x cell
    data_query = '''SELECT DISTINCT state, vpwr, peak
    FROM spiprof
    WHERE cell = 'dffnrq_1x'
    AND pin = 'VPWR'
    AND c1 = 0
    AND r = 0
    AND c2 = 1.0e-15
    AND slew1 = 1.25e-11
    AND slew2 = 7.5e-12
    ORDER BY vpwr
    '''
    cursor.execute(data_query)
    db_data = np.array(cursor.fetchall())

    # Query states from spiprof
    state_query = '''SELECT DISTINCT state
    FROM spiprof'''
    cursor.execute(state_query)
    db_states = np.array(cursor.fetchall())

    # Extract VPWR and Peak Current for each state
    extracted_data = db_data[:, [1, 2]].astype(float)

    plt.figure(figsize = (10, 10))
    for row in db_states:
        series = extracted_data[db_data[:,0] == row, :]
        plt.plot(series[:,0], series[:,1], label = ''.join(row))

    plt.grid(True)
    plt.legend()
    plt.title('Peak vs VPWR - Varying states\ndffnrq_1x: c2 = 1.0e-15 F, slew1 = 1.25e-11 S, slew = 7.5e-12 S')
    plt.xlabel('VPWR (V)')
    plt.ylabel('Peak (A)')
    plt.savefig('graphs/peak_vs_pwr.png')
    # plt.show()

def area_vpwr_vary_parameters(connection):
    cursor = connection.cursor()

    # Query c2, slew1, slew2, vpwr, and area for dffnrq_1x cell
    data_query = '''SELECT DISTINCT c2, slew1, slew2, vpwr, area
    FROM spiprof
    WHERE cell = 'dffnrq_1x'
    AND pin = 'VPWR'
    AND state = 'output_fall'
    ORDER BY vpwr'''
    cursor.execute(data_query)
    db_data = np.array(cursor.fetchall())

    extracted_data = db_data[:, [3, 4]].astype(float)

    # Query parameter variation for dffnrq_1x cell
    parameter_query = '''SELECT DISTINCT c2, slew1, slew2
    FROM spiprof
    WHERE cell = 'dffnrq_1x'
    AND pin = 'VPWR'
    AND state = 'output_fall' '''
    cursor.execute(parameter_query)
    db_parameters = np.array(cursor.fetchall())

    # for row in db_parameters:
    #     series = extracted_data[(db_data[:,0] == row[0]) & (db_data[:,1] == row[1]) & (db_data[:,2] == row[2]), :]
    #     plt.plot(series[:,0], series[:,1], label = 'c2 = {} F, slew1 = {} S, slew2 = {} S'.format(row[0], row[1], row[2]))

    # Extract VPWR and area for several parameter variation
    series1 = extracted_data[(db_data[:,0] == 1e-15) & (db_data[:,1] == 1.25e-11) & (db_data[:,2] == 7.5e-12), :]
    series2 = extracted_data[(db_data[:,0] == 5e-15) & (db_data[:,1] == 1.25e-11) & (db_data[:,2] == 7.5e-12), :]
    series3 = extracted_data[(db_data[:,0] == 1e-14) & (db_data[:,1] == 1.25e-11) & (db_data[:,2] == 7.5e-12), :]
    series4 = extracted_data[(db_data[:,0] == 1e-15) & (db_data[:,1] == 3.8085e-11) & (db_data[:,2] == 2.2851e-11), :]
    series5 = extracted_data[(db_data[:,0] == 5e-15) & (db_data[:,1] == 3.8085e-11) & (db_data[:,2] == 2.2851e-11), :]

    # Plot the data
    plt.figure(figsize = (10, 10))
    plt.plot(series1[:,0], series1[:,1], label = 'c2 = 1e-15 F, slew1 = 1.25e-11 F, slew2 = 7.5e-12 F')
    plt.plot(series2[:,0], series2[:,1], label = 'c2 = 5e-15 F, slew1 = 1.25e-11 F, slew2 = 7.5e-12 F')
    plt.plot(series3[:,0], series3[:,1], label = 'c2 = 1e-14 F, slew1 = 1.25e-11 F, slew2 = 7.5e-12 F')
    plt.plot(series4[:,0], series4[:,1], label = 'c2 = 1e-15 F, slew1 = 3.8085e-11 F, slew2 = 2.2851e-11 F')
    plt.plot(series5[:,0], series5[:,1], label = 'c2 = 5e-15 F, slew1 = 3.8085e-11 F, slew2 = 2.2851e-11 F')

    plt.grid(True)
    plt.legend()
    plt.title('Area vs VPWR - Varying parameters (c2, slew1, slew2)\ndffnrq_1x: state = output_fall, pin = VPWR')
    plt.xlabel('VPWR (V)')
    plt.ylabel('Area (C)')
    plt.savefig('graphs/area_vs_pwr.png')
    # plt.show()

# Check if database exists already
if(os.path.isfile('redhawk.db')):
    connection = sqlite3.connect('redhawk.db')

    if(os.path.isdir('graphs') == False):
        os.mkdir('graphs')

    peak_vpwr_vary_state(connection)
    area_vpwr_vary_parameters(connection)
else:
    # If not, print an error
    print('ERROR: redhawk.db not found')
