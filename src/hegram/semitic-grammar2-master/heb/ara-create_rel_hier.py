#!/usr/bin/env python
#-*- coding: utf-8 -*-
###
### Program for creating a rels hierarchy based on an existing lexicon.
### The program takes as input the file ara-lexicon.tdl. It
### should be in the directory above where the program is when it runs.
### The program assumes that each part of speech appears separately in
### the lexicon.
### The output is written to ara-types-rel.tdl.
###
### Livnat Herzig Sheinfux (July 2016)
###


###
### Opening read and write files
###

ara_lexicon = open('../ara-lexicon.tdl','r')
rels_file = open('../ara-types-rel.tdl','w')

###
### Writing initial lines of the output file
###
import time
import datetime
import re
rels_file.write(';;  -*- Mode: TDL; Coding: utf-8; -*- \n;;\n')
rels_file.write(';;  Rels hierarchy automatically derived from \n;;  an existing lexicon file (')
rels_file.write(datetime.datetime.now().strftime("%d/%m/%Y") + ')\n')

#The general fixed hierarchy
rels_file.write("\n\n;LHS 29/1/15: A (relatively flat) hierarchy of rels to populate LKEYS.KEYREL.PRED.\n;Prepositions' rels appear in types-prep-lex, including idiomatic ones.")
rels_file.write("\nl-or-i-rel := predsort.")
rels_file.write("\n;For idiomatic lexical items\ni-rel := l-or-i-rel.")
rels_file.write("\n;For literal lexical items (most words)\nl-rel := l-or-i-rel.\n")

###
###Parse the lexicon and store the rels
###
noun_rels = []
verb_rels = []
adj_rels = []
adv_rels = []
func_rels = []
#PRED_STRING = re.compile(r"KEYREL.PRED _[\w-]+_rel")
PRED_STRING = re.compile(r"KEYREL.PRED _[a-zA-z0-9_+-]+_rel")


def parse_lexicon(lexicon_file):
    lexicon_lines = lexicon_file.readlines()
    list_to_add = []
    for line in lexicon_lines:
        if line.startswith(";==="):#ignore prepositions
            if "= NOUNS" in line:
                list_to_add = noun_rels
            elif "= VERBS" in line:
                list_to_add = verb_rels
            elif "= ADJECTIVES" in line:
                list_to_add = adj_rels
            elif "= ADVERBS" in line:
                list_to_add = adv_rels
            elif "= FUNCTIONAL" in line:
                list_to_add = func_rels
        elif len(PRED_STRING.findall(line)) == 1 and not line.startswith(';'):#i.e., there was a match and this isn't commented out
            rel = PRED_STRING.findall(line)[0]
            rel = rel.replace("KEYREL.PRED ", "")#this is the actual rel we want
            if not rel.endswith("_p_rel") and not rel.endswith("_ip_rel") and rel not in list_to_add:#ignore prepositions
                list_to_add.append(rel)

parse_lexicon(ara_lexicon)
#noun_rels.append("arabic")
#verb_rels.append("arabic")
#parse_lexicon(ara_lexicon)

###
###Separate idiomatic from literal rels, where relevant
###
def sep_lists(orig_list, id_list, lit_list):
    for rel in orig_list:
        if rel.startswith("_i-"):
            id_list.append(rel)
        else:
            lit_list.append(rel)

            
id_noun_rels = []
lit_noun_rels = []
id_verb_rels = []
lit_verb_rels = []
sep_lists(noun_rels, id_noun_rels, lit_noun_rels)
sep_lists(verb_rels, id_verb_rels, lit_verb_rels)

###
###Write to file
###
def write_from_list(li, parent):
    for rel in li:
        rels_file.write(rel + " := " + parent + ".\n")
        #if rel != "arabic":
            #rels_file.write(rel + " := " + parent + ".\n")
        #else:#note: this is only relevant while the arabic rels are in the same file as the hebrew ones
            #rels_file.write("\n; TAG: rels from the arabic lexicon:\n")

rels_file.write(";===========================\n;========Literal============\n;===========================\n\n")
###nouns:
rels_file.write(";=============================================================================\n;================================= NOUNS =====================================\n;=============================================================================\n")
rels_file.write("_n_rel := l-rel.\n")
#literal:
write_from_list(lit_noun_rels, "_n_rel")


###verbs:
rels_file.write("\n\n;=============================================================================\n;================================= VERBS =====================================\n;=============================================================================\n")
rels_file.write("_v_rel := l-rel.\n")
#literal:
write_from_list(lit_verb_rels, "_v_rel")

###adjectives
rels_file.write("\n\n;=============================================================================\n;================================= ADJECTIVES ================================\n;=============================================================================\n")
rels_file.write("_adj_rel := l-rel.\n")
write_from_list(adj_rels, "_adj_rel")

###adverbs
rels_file.write("\n\n;=============================================================================\n;================================= ADVERBS ===================================\n;=============================================================================\n")
rels_file.write("_adv_rel := l-rel.\n")
write_from_list(adv_rels, "_adv_rel")

###function words
rels_file.write("\n\n;=============================================================================\n;================================= FUNCTIONAL ================================\n;=============================================================================\n")
rels_file.write(";Note: prepositions have a separate (language specific) hierarchy, see types-prep-lex.tdl.\n;Some other functional elements don't have semantics yet (at, e).\n")
rels_file.write(";LHS 29/1/15: aux_rel is temporarily used for ham.\n")
rels_file.write("_funct_rel := l-rel.\n")
write_from_list(func_rels, "_funct_rel")

###Idiomatic:
rels_file.write("\n\n;===========================\n;========Idiomatic==========\n;===========================\n\n")
rels_file.write(";=============================================================================\n;================================= NOUNS =====================================\n;=============================================================================\n")
rels_file.write("_i_n_rel := i-rel.\n")
write_from_list(id_noun_rels, "_i_n_rel")

rels_file.write("\n;=============================================================================\n;================================= VERBS =====================================\n;=============================================================================\n")
rels_file.write("_i_v_rel := i-rel.\n")
write_from_list(id_verb_rels, "_i_v_rel")

print('lit nouns\n' +  str(lit_noun_rels) + '\n')#sanity check
print('id nouns\n' +  str(id_noun_rels) + '\n')#sanity check
print('lit verbs\n' + str(lit_verb_rels) + '\n')#sanity check
print('id verbs\n' + str(id_verb_rels) + '\n')#sanity check
print('adjs\n' + str(adj_rels) + '\n')#sanity check
print('advs\n' + str(adv_rels) + '\n')#sanity check
print('funcs\n' + str(func_rels) + '\n')#sanity check


ara_lexicon.close()
rels_file.close()
