#!/usr/bin/env python
#-*- coding: utf-8 -*-
###
### Program for creating a link hierarchy based on existing _le types.
### The program takes as input the file types-verbs-lex.tdl (which currently
### contains the _le types). It should be in the directory above where
### the program is when it runs. The output is written to types-link.tdl.
###
### Livnat Herzig Sheinfux (December 2014), based on Petter Haugereid
###


###
### Opening read and write files
###
le_types_file=open('../types-verb-lex.tdl','r')
ara_le_types_file=open('../ara-types-verb-lex.tdl','r')
link_h_file=open('../types-link.tdl','w')


###
### Writing initial lines of the output file
###
import time
import datetime
link_h_file.write(';;  -*- Mode: TDL; Coding: utf-8; -*- \n;;\n')
link_h_file.write(';;  Link hierarchy automatically derived from \n;;  an existing file of _le types (')
link_h_file.write(datetime.datetime.now().strftime("%d/%m/%Y") + ')\n')


###
### Reading in le-types from the general file
###
argstlists = []
le_lines = le_types_file.readlines()
le_types = []
le_types2 = []
for line in le_lines:
    argstlist = []
    if ':=' in line and '_le' in line:
        items = line.split(' := ')
        le_type = items[0]
        le_types = le_types + [le_type]
        subp = le_type.split('_')
        argst = subp[0]
        links = argst[3:]
        links2 = links.split('-')
        for link in links2:
            argstlist = argstlist + [link]
        #argstlist.sort()#this messed up our order
        if argstlist not in argstlists:
            argstlists = argstlists + [argstlist]#I moved this inside the if clause, so it won't add empty lists for empty lines.(and then made it conditional on not being there before)
                
    '''if ':=' in line:
        items = line.split(' := ')
        mytype = items[0]
        le_types2 = le_types2 + [mytype]'''#shouldn't be relevant
argstlists = argstlists + [['0']]#addition - note that currently arg0 and no-arg don't differ (they could, if any other interim types were needed)
argstlists = argstlists + [['4']]#addition - for S-FRAME of subject raising
'''argstlists = argstlists + [['0', '1']]##test
argstlists = argstlists + [['0', '2']]##test
argstlists = argstlists + [['0', '3']]##test
argstlists = argstlists + [['0', '4']]##test
argstlists = argstlists + [['0', '12', '14']]##test'''
print('argstlists with only the le-types: ' + str(argstlists))


###
### Reading in le-types from the arabic file
###
ara_le_lines = ara_le_types_file.readlines()
ara_le_types = []
ara_le_types2 = []
for line in ara_le_lines:
    argstlist = []
    if ':=' in line and '_le' in line:
        items = line.split(' := ')
        ara_le_type = items[0]
        ara_le_types = ara_le_types + [ara_le_type]
        subp = ara_le_type.split('_')
        argst = subp[0]
        links = argst[3:]
        links2 = links.split('-')
        for link in links2:
            argstlist = argstlist + [link]
        #argstlist.sort()#this messed up our order
        if argstlist not in argstlists:
            argstlists = argstlists + [argstlist]#I moved this inside the if clause, so it won't add empty lists for empty lines.(and then made it conditional on not being there before)

###
### Adding the arg constellations that 'arg1-', 'arg1+', 'arg2+', 'arg2-',
### 'arg3+', 'arg3-', 'arg4+', 'arg4-', 'arg5+', 'arg5-', 'arg6+' and 'arg6-' represent, to the list of argument
### frame constellations
###
'''argstlists = argstlists + [['0', '2', '23', '24', '234', '3', '34', '4'], ['1', '12', '13', '14', '123', '124', '134', '1234'],
             ['2', '12', '23', '24', '123', '234', '124', '1234'],['0', '1', '13', '14', '134', '3', '34', '4'],
             ['3', '13', '23', '34', '123', '234', '134', '1234'],['0', '1', '12', '14', '124', '2', '24', '4'],
             ['4', '14', '24', '34', '124', '234', '134', '1234'],['0', '1', '12', '13', '123', '2', '23', '3']]'''
argstlists = argstlists + [['0', '2', '23', '24', '25', '26', '234', '235', '236', '245', '256', '246', '2345', '2346', '2356', '2456',
              '23456','3', '34', '35', '36', '345', '356', '346', '3456', '4', '45', '46', '456', '5', '56', '6'],
             ['1', '12', '13', '14', '15', '16', '123', '134', '145', '156', '124', '125', '126', '135', '136', '146', '1234', '1345',
              '1456', '1245', '1246', '1256', '1356', '1346', '1235', '1236', '12345', '12346', '12356', '12456', '13456', '123456'],
             ['2', '12', '23', '24', '25', '26', '123', '125', '126', '234', '124', '235', '236', '245', '256', '246', '1234', '2345',
              '1235', '1236', '1246', '1245', '2346', '2356', '2456', '1256', '12345', '23456', '12456', '12356', '12346', '123456'],
             ['0', '1', '13', '14', '15', '16', '134', '145', '156', '135', '136', '146', '1345', '1456', '1356', '1346', '13456', '3',
              '34', '35', '36', '345', '356', '346', '3456', '4', '45', '46', '456', '5', '56', '6'],
             ['3', '13', '23', '34', '35', '36', '123', '135', '136', '234', '134', '235', '236', '345', '356', '346', '1234', '1235',
              '1236', '2345', '2346', '3456', '2356', '1345', '1346', '1356', '12345', '23456', '12356', '12346', '13456', '123456'],
             ['0', '1', '12', '14', '15', '16', '145', '156', '124', '125', '126', '146', '1456', '1245','1246', '1256', '12456', '2',
              '24', '25', '26', '245', '256', '246', '2456', '4', '45', '46', '456', '5', '56', '6'],
             ['4', '14', '24', '34', '45', '46', '124', '134', '145', '146', '234', '245', '246', '345', '346', '456', '1234', '1245',
              '1246', '1345', '1346', '1456', '2345', '3456', '2346', '2456', '12345', '23456', '13456', '12456', '12346', '123456'],
             ['0', '1', '12', '13', '15', '16', '123', '156', '125', '126', '135', '136', '1256', '1356', '1235', '1236', '12356', '2',
              '23', '25', '26', '235', '236', '256', '2356', '3', '35', '36', '356', '5', '56', '6'],
             ['5', '15', '25', '35', '45', '56', '125', '135', '145', '156', '235', '245', '256', '345', '356', '456', '1235', '1245',
              '1345', '1256', '1356', '1456', '2345', '3456', '2356', '2456', '12345', '23456', '12456', '13456', '12356', '123456'],
             ['0', '1', '12', '13', '14', '16', '123', '134', '126', '124', '136', '146', '1234', '1246', '1346', '1236', '12346', '2',
              '23', '24', '26', '234', '236', '246', '2346', '3', '34', '36', '346', '4', '46', '6' ],
             ['6', '16', '26', '36', '46', '56', '126', '136', '146', '156', '236', '246', '256', '346', '356', '456', '1256', '1246',
              '1236', '1456', '1346', '1356', '2346', '2356', '2456', '3456', '23456', '12346', '12356', '12456', '13456', '123456'],
             ['0', '1', '12', '13', '14', '15', '123', '134', '145', '124', '125', '135', '1234', '1345', '1245', '1235', '12345', '2',
              '23', '24', '25', '234', '235', '245', '2345', '3', '34', '35', '345', '4', '45', '5']]
argstlists2 = []
for p in argstlists:##I don't think this does anything
	if not p in argstlists2:
		argstlists2 = argstlists2 + [p]
argstlists = argstlists2
print('argstlists with the top types as well: ' + str(argstlists))


###
### Creating a type hierarchy of argument frame constellations and writing
### them to heb-types.tdl
###
typedefs = []###originally defined earlier but left untouched as far as I can see
for p in argstlists:
    if len(p) > 0 and not  p[0] == '':
        subtype = 'arg' + p[0]
        for part in p[1:]:
                subtype = subtype + '-' + part
        type2 = ' := '
        types = []
        for q in argstlists:
                if set(p) < set(q):
                        z = 1
                        for r in argstlists:
                                if set(r) < set(q) and set(p) < set(r):
                                        z = 0
                        if z == 1:
                                type2 = q[0]
                                for part in q[1:]:
                                        type2 = type2 + '-' + part
                                types = types + [type2]
                                z = 1
        typedef = subtype + ' := arg'
        if types == []:
                typedef = subtype + ' := link.'
        else:
                for item in types[:-1]:
                        typedef = typedef + item + ' & arg'
                lasttype = types[-1:][0]
                typedef = typedef + lasttype + '.'
        typedefs = typedefs + [typedef]
noarg = 'no-arg := arg1- & arg2- & arg3- & arg4- & arg5- & arg6-.'#addition
typedefs = typedefs + [noarg]#addition

###
### Replacing argument structure constellations with 'arg1+', 'arg1-', and so
### on...
###
typedefs2 = []
for type in typedefs:
	type = type.replace('arg0-2-23-24-25-26-234-235-236-245-256-246-2345-2346-2356-2456-23456-3-34-35-36-345-356-346-3456-4-45-46-456-5-56-6','arg1-')
	type = type.replace('arg1-12-13-14-15-16-123-134-145-156-124-125-126-135-136-146-1234-1345-1456-1245-1246-1256-1356-1346-1235-1236-12345-12346-12356-12456-13456-123456','arg1+')
	type = type.replace('arg2-12-23-24-25-26-123-125-126-234-124-235-236-245-256-246-1234-2345-1235-1236-1246-1245-2346-2356-2456-1256-12345-23456-12456-12356-12346-123456','arg2+')
	type = type.replace('arg0-1-13-14-15-16-134-145-156-135-136-146-1345-1456-1356-1346-13456-3-34-35-36-345-356-346-3456-4-45-46-456-5-56-6','arg2-')
	type = type.replace('arg3-13-23-34-35-36-123-135-136-234-134-235-236-345-356-346-1234-1235-1236-2345-2346-3456-2356-1345-1346-1356-12345-23456-12356-12346-13456-123456','arg3+')
	type = type.replace('arg0-1-12-14-15-16-145-156-124-125-126-146-1456-1245-1246-1256-12456-2-24-25-26-245-256-246-2456-4-45-46-456-5-56-6','arg3-')
	type = type.replace('arg4-14-24-34-45-46-124-134-145-146-234-245-246-345-346-456-1234-1245-1246-1345-1346-1456-2345-3456-2346-2456-12345-23456-13456-12456-12346-123456','arg4+')
	type = type.replace('arg0-1-12-13-15-16-123-156-125-126-135-136-1256-1356-1235-1236-12356-2-23-25-26-235-236-256-2356-3-35-36-356-5-56-6','arg4-')
	type = type.replace('arg5-15-25-35-45-56-125-135-145-156-235-245-256-345-356-456-1235-1245-1345-1256-1356-1456-2345-3456-2356-2456-12345-23456-12456-13456-12356-123456','arg5+')
	type = type.replace('arg0-1-12-13-14-16-123-134-126-124-136-146-1234-1246-1346-1236-12346-2-23-24-26-234-236-246-2346-3-34-36-346-4-46-6','arg5-')
	type = type.replace('arg6-16-26-36-46-56-126-136-146-156-236-246-256-346-356-456-1256-1246-1236-1456-1346-1356-2346-2356-2456-3456-23456-12346-12356-12456-13456-123456','arg6+')
	type = type.replace('arg0-1-12-13-14-15-123-134-145-124-125-135-1234-1345-1245-1235-12345-2-23-24-25-234-235-245-2345-3-34-35-345-4-45-5','arg6-')
	typedefs2 = typedefs2 + [type]
typedefs = typedefs2
typedefs.sort()


xx = 0
for typedef in typedefs:
	link_h_file.write(typedef + '\n')
	xx = xx+1
	
link_h_file.close()

###
### Remove files
###
import os

le_types_file.close()
ara_le_types_file.close()
