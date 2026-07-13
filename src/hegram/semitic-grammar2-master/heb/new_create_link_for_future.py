#!/usr/bin/env python
#-*- coding: utf-8 -*-
###
### Program for creating a link hierarchy based on existing _le types.
### The program takes as input the file types-verbs-lex.tdl (which currently
### contains the _le types). It should be in the directory above where
### the program is when it runs. The output is written to types-link-big.tdl.
###
### Livnat Herzig Sheinfux (December 2014), based on Petter Haugereid
###

### Update (August 2015): in order to accommodate a large, automatically created
### verbal lexicon (based on PMI_dictionary.csv and new_dinflections.csv), the code
### was enhanced. New arg types are now also taken from the lexicon (and added to
### separate files that mimic the contents of types-verb-lex and types-dep-lxm, see elaboration below).
### NOTE: This is a preliminary version of the code, in order to debug the process!!!



###
### Opening read and write files
###

le_types_file=open('../types-verb-lex.tdl','r')
ara_le_types_file=open('../ara-types-verb-lex.tdl','r')
link_h_file=open('../types-link_big.tdl','w')#the large link output file
#additions, to accomodate verbs from PMI dictionary and dinflections
blexicon_file=open('../lexicon_big.tdl','r')
dlexicon_file=open('../dummy_lexicon.tdl','r')#a dummy lexicon to add leaf types that we need for disjunctive types (135, 136, 1235, 1356, 12356)
temp_output_verbs_file=open('../temp-types-verb-auto.tdl','w')
temp_output_deps_file=open('../temp-types-deps-lxm-auto.tdl','w')

additional_le_types = []#types as they appear in types-verbs (i.e., with syntactic realization and tense_le)


#temporarily - don't include ones that are already defined in types-verb-lex
already_exist = ['arg16_p_past_le', 'arg12_p_future_le', 'arg12_n_past_le', 'arg12_p_past_le', \
                 'arg12_n_future_le', 'arg15-16-156_p_p_past_le', 'arg15_p_past_le', 'arg12_p_present_le', \
                 'arg15-16-156_p_p_present_le', 'arg12_n_present_le', 'arg12_npc_past_le', \
                 'arg12_nc_present_le', 'arg12_v_subj-cntrl_future_le', 'arg15-16-156_p_p_future_le', 'arg12_npc_present_le', \
                 'arg12_pc_future_le', 'arg12_v_subj-cntrl_present_le', 'arg12_nc_future_le', 'arg12_pc_past_le', \
                 'arg12_nc_past_le', 'arg12-123_n_p_future_le', 'arg12_npc_future_le', 'arg12_pc_present_le', \
                 'arg12_v_subj-cntrl_past_le', 'arg12-123_n_p_past_le', 'arg1-14-15-16-145-146-156-1456_njp_p_p_past_le', \
                 'arg12_v_subj-cntrl_infinitive_le', 'arg125_v_p_obj-cntrl_past_le']



nums = ['1', '2', '3', '4', '5', '6']
tenses = ['past', 'present', 'future', 'imperative', 'infinitive']

#parse the lexicon, extracting only the le type names of verbs, for now
def parse_lexicon(lexicon_file):
    lexicon_lines = lexicon_file.readlines()
    relevant_area = False
    for line in lexicon_lines:
        if line.startswith(";==="):#ignore prepositions
            if "= VERBS" in line:
                relevant_area = True
            elif "= ADJECTIVES" in line:
                relevant_area = False
        elif relevant_area:
            if ':=' in line:
                line_as_list = line.split()#This should create a list in the form: [word, :=, le_name, &]
                le_name = line_as_list[2]
                if le_name not in already_exist and le_name not in additional_le_types and not le_name.endswith('qpart-lex-item'):
                    additional_le_types.append(le_name)

parse_lexicon(blexicon_file)
parse_lexicon(dlexicon_file)

print('number of automatic verbal LE types: ' + str(len(additional_le_types)))


###
### Writing initial lines of the output files
###
import time
import datetime
link_h_file.write(';;  -*- Mode: TDL; Coding: utf-8; -*- \n;;\n')
link_h_file.write(';;  Link hierarchy automatically derived from \n;;  an existing file of _le types (')
link_h_file.write(datetime.datetime.now().strftime("%d/%m/%Y") + ')\n')

temp_output_verbs_file.write(';;  -*- Mode: TDL; Coding: utf-8; -*- \n;;\n')
temp_output_verbs_file.write(';;  Automatically derived types, that should be in types-verbs, derived from the lexicon \n;;  currently only for verbs\n;')
temp_output_verbs_file.write(datetime.datetime.now().strftime("%d/%m/%Y") + '\n')
temp_output_verbs_file.write(';=================================================\n')
temp_output_verbs_file.write(';============Mimicking types-verb-lex==============\n')
temp_output_verbs_file.write(';=================================================\n')


temp_output_deps_file.write(';;  -*- Mode: TDL; Coding: utf-8; -*- \n;;\n')
temp_output_deps_file.write(';;  Automatically derived types, that should be in types-deps, derived from the lexicon \n;;  currently only for verbs\n;')
temp_output_deps_file.write(datetime.datetime.now().strftime("%d/%m/%Y") + '\n')
temp_output_deps_file.write(';=================================================\n')
temp_output_deps_file.write(';============Mimicking types-deps-lxm==============\n')
temp_output_deps_file.write(';=================================================\n')

pure_types = []#e.g. arg126_nc_p
existing_pure_types = []
existing_full_types = []

print('the additional le_types are:\n')
for le_type in additional_le_types:
    print(le_type)
print('there are ' + str(len(additional_le_types)) + ' additional le_types')
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
        if ('_').join(subp[:-2]) not in existing_pure_types:
            existing_pure_types.append(('_').join(subp[:-2]))
        if ('_').join(subp) not in existing_full_types:
            existing_full_types.append(('_').join(subp))            
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
#print('argstlists with only the le-types: ' + str(argstlists))


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
##        if ('_').join(subp[:-2]) not in existing_pure_types:
##            existing_pure_types.append(('_').join(subp[:-2]))
##        if ('_').join(subp) not in existing_full_types:
##            existing_full_types.append(('_').join(subp))                 
        links = argst[3:]
        links2 = links.split('-')
        for link in links2:
            argstlist = argstlist + [link]
        #argstlist.sort()#this messed up our order
        if argstlist not in argstlists:
            argstlists = argstlists + [argstlist]#I moved this inside the if clause, so it won't add empty lists for empty lines.(and then made it conditional on not being there before)

###
###Create the le types (mimicking types-verb-lex)
###
#arg126_nc_p_past_le := arg126_nc_p & basic-verb-lex & past-verb-lex.
for le_type in additional_le_types:
    corrupt = False
    if 'argxc' not in le_type and 'raising' not in le_type and 'cop' not in le_type and '&' not in le_type:#these will require special treatment, so for now, the ones in types-verb will be used
        type_as_list = le_type.split('_')#['arg126', 'nc', 'p', 'past', 'le']
        print(str(type_as_list))
        pure_type = ('_').join(type_as_list[:-2])#arg126_nc_p
        if len(type_as_list) == 3 and type_as_list[1] in tenses and type_as_list[0][-1] in nums:#don't include corrupt types of the form argNUM_TENSE_le
            corrupt = True
            print('corrupt: ' + le_type)
        #if not corrupt and pure_type not in existing_pure_types:
        if not corrupt and le_type not in existing_full_types:           
            s = le_type + ' := ' + pure_type + ' & basic-verb-lex & ' + type_as_list[-2] + '-verb-lex.\n'
            temp_output_verbs_file.write(s)

###
###Create the missing pre-le types (mimicking types-deps-lxm)
###
#arg1256_n_p_p := arg1_np & arg5_pp & arg6_pp &
#  [ SYNSEM.LOCAL.CAT.VAL.R-FRAME arg1256 ].
for le_type in additional_le_types:
    corrupt = False
    if 'argxc' not in le_type and 'raising' not in le_type and 'cop' not in le_type and '&' not in le_type:#these will require special treatment, so for now, the ones in types-verb will be used
        type_as_list = le_type.split('_')#e.g. ['arg12-13-123', 'n', 'p', 'future', 'le']
        syntactic_reals = type_as_list[1:-2]
        pure_type = ('_').join(type_as_list[:-2])#e.g. 'arg12-13-123_n_p'
        r_frame_val = type_as_list[0]
        parents = []
        if len(type_as_list) == 3 and type_as_list[1] in tenses and type_as_list[0][-1] in nums:#don't include corrupt types of the form argNUM_TENSE_le
            corrupt = True
        if not corrupt and pure_type not in pure_types and pure_type not in existing_pure_types and pure_type != 'arg12_np' and pure_type not in ['arg123_v_p', 'arg123_v_n', 'arg12_v'] :#Some of the following is very specific to which types are automatically produced at the moment
            pure_types.append(pure_type)
            if '1' in r_frame_val:#assumes the verb has an arg1 subject
                parents.append('arg1_np')
            if '3' in r_frame_val:
                parents.append('arg3_pp')#there will be no automatically created arg3 np 
            if '5' in r_frame_val:
                parents.append('arg5_pp')#there will be no automatically created arg5 advp
            if '6' in r_frame_val:
                parents.append('arg6_pp')#only for hebrew
            if '2' in r_frame_val:
                if 'nc' in syntactic_reals:
                    parents.append('arg2_cp-np')
                elif 'npc' in syntactic_reals:
                    parents.append('arg2_cp-np-pp')
                elif 'pc' in syntactic_reals:
                    parents.append('arg2_cp-pp')
                elif 'np' in syntactic_reals:
                    if '4' not in r_frame_val:
                        parents.append('arg2_np-pp')
                elif 'c' in syntactic_reals:
                    parents.append('arg2_cp')
                elif 'n' in syntactic_reals:
                    if '4' not in r_frame_val:
                        parents.append('arg2_np')
                elif 'p' in syntactic_reals:
                    if '4' not in r_frame_val:
                        parents.append('arg2_pp')
            #if '4' in r_frame_val:#to expand on later (they aren't created automatically, as PMI dictionary doesn't have them, they already previously exist)
            s = pure_type + ' :='
            for parent in parents:
                s += ' ' + parent + ' &'
            s += '\n  [ SYNSEM.LOCAL.CAT.VAL.R-FRAME ' + r_frame_val + ' ].\n'
            temp_output_deps_file.write(s)
            


print('the pure types are:\n')
for ptype in pure_types:
    print(ptype)
print('there are ' + str(len(pure_types)) + ' pure types')

print('the existing pure types are:\n')
for eptype in existing_pure_types:
    print(eptype)
print('there are ' + str(len(existing_pure_types)) + ' existing pure types')



###
###Add the automatic types to the general list, so that they'll be included in types-link
###        
for additional_type in additional_le_types:
    argstlist = []
    elements = additional_type.split('_')
    numeric_type = elements[0][3:]
    links2 = numeric_type.split('-')
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
#print('argstlists with the top types as well: ' + str(argstlists))


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

blexicon_file.close()
temp_output_verbs_file.close()
temp_output_deps_file.close()
