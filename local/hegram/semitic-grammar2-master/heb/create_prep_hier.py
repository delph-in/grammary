#!/usr/bin/env python
#-*- encoding: utf-8 -*-

import sys

i = open('../ara-types-prep-lex.tdl','w')

import time
import datetime
i.write(';;  -*- Mode: TDL; Coding: utf-8; -*- \n;;\n')
i.write(';;  Type file for particle predicates automatically derived from a list of particles\n;; (')
i.write(datetime.datetime.now().strftime("%d/%m/%Y") + ') with \'create_prep_hier.py\'\n;;\n\n\n')


###
### Creating a type hierarchy of particle constellations and writing them to
### ara-types-prep-lex.tdl
###
typedefs = []
preplists2 = []
# This is the place to add all the combinations we want:
preplists = [ ['1la'], ['b'], ['fi'], ['l'], ['mn'], ['yla'], ['yn'], ['my'], ['ynd'], ['1la', 'l', 'fi'], ['b', 'fi'], ['l', 'yla' ], ['1la', 'l'], ['yla', 'yn'], ['yn', 'yla', 'fi', 'b'], ['yn', 'yla', 'b' ], ['yla', 'b', 'fi' ], ['1la', 'l', 'yla'], ['b', 'fi', 'yla', 'ynd' ],['1la', 'l', 'fi', 'yla', 'ynd'], ['1la', 'b', 'fi', 'l', 'mn', 'yla', 'yn', 'my', 'yla', 'ynd' ]]
for p in preplists:
    if not p in preplists2:
        preplists2 = preplists2 + [p]
#        print p
preplists = preplists2
for p in preplists:
   if not p[0][0] == '\'' and not p[0][0] == '-':
    if len(p) > 1:
        subtype = p[0]
        for prep in p[1:]:
            subtype = subtype + '-' + prep
        subtype = subtype + '-p'
    elif len(p) == 1:
        subtype = p[0]
        subtype = '_' + subtype + '_p_rel'
    type2 = ' := '
    types = []
    for q in preplists:
        if set(p) < set(q):
            z = 1
            for r in preplists:
                if set(r) < set(q) and set(p) < set(r):
                    z = 0
            if z == 1:
                type2 = q[0]
                for prep in q[1:]:
                    type2 = type2 + '-' + prep
                types = types + [type2]
                z = 1
    typedef = subtype + ' := '
    if types == []:
        typedef = typedef + 'prep-p-l.'
    else:
        if len(types[:-1]) > 19:
            typedef1 = subtype + '-1 := '
            for suptype in types[:17]:
                typedef1 = typedef1 + suptype + '-p & '
            typedef1 = typedef1 + types[18] + '-p.'
            typedef2 = subtype + '-2 := '
            for suptype in types[19:][:-1]:
                typedef2 = typedef2 + suptype + '-p & '
            typedef2 = typedef2 + types[-1] + '-p.'
            typedef = subtype + ' := ' + subtype + '-1 & ' + subtype + '-2.'
            typedefs = typedefs + [typedef1,typedef2]
        else:
            for item in types[:-1]:
                typedef = typedef + item + '-p & '
            lasttype = types[-1:][0]
            typedef = typedef + lasttype + '-p.'
    typedefs = typedefs + [typedef]

typedefs.sort()

xx = 0
typedeflen = len(typedefs)
for typedef in typedefs:
    i.write(typedef + '\n')
    xx = xx+1
	
i.close()

