import json,sys
d=json.load(open(sys.argv[1])); want=set(sys.argv[2].split(','))
for t in d['tables']:
    if t['table_id'] in want:
        print('=====',t['table_id'],len(t['rows']),'x',len(t['rows'][0]))
        for i,r in enumerate(t['rows']): print(i,': '+' | '.join((x if x is not None else '∅').replace('\n','⏎') for x in r))
