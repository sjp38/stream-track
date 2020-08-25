#!/usr/bin/env python3

import argparse

import track_results

"""
Hello,


We found below commits in the upstream (<range>) are mentioning or has 'Fixes:'
tag for commits in downstream (<range>) but not merged in the downstream.
Could you please review if those need to be merged in the upstream?

# <commit date> <hash id> <title>
<commit date> <hash id> <title>
# has 'Fixes:' for <hash id> <title>.
# has mentions for <hash id> <title>.
# This can be cleanly cherry-picked on the downstream.
# This cannot be cleanly cherry-picked on the downstream.

...

The commits cleanly cherry-pickable are formatted as patches:

    <patch name>
    ...

The findings and this report is almost made by tools in
https://github.com/sjp38/stream-check.


Thanks,
SeongJae Park
"""

def set_argparser(parser):
    parser.add_argument('output', metavar='<file>',
            help='file containing output of chk-followups.py')
    parser.add_argument('--repo', metavar='<path>', default='./',
            help='path to the tracking git repo')

def main():
    parser = argparse.ArgumentParser()
    set_argparser(parser)
    args = parser.parse_args()

    with open(args.output, 'r') as f:
        prev_res = track_results.parse_track_results(f.readlines(), args.repo)

    print("""
We found below commits in the '%s (upstream)' are mentioning or has 'Fixes:'
tag for commits in the '%s (downstream)' but not merged in the 'downstream'.
Could you please review if those need to be merged in the upstream?
""" % ('..'.join(prev_res.upstream), '..'.join(prev_res.downstream)))

    print('\n')

    for ref in prev_res.hashids:
        print('# %s: %s' % (ref, prev_res.hashids[ref]))
    print('\n\n')

    to_report = {}
    for t in prev_res.results:
        res = prev_res.results[t]
        if not res.upstream_commit:
            continue

        fixes_unmerged = [x[0] for x in res.followup_fixes if not x[1]]
        mentions_unmerged = [x[0] for x in res.followup_mentions if not x[1]]
        if not fixes_unmerged and not mentions_unmerged:
            continue

        for f in fixes_unmerged:
            print(f)
            print('# has \'Fixes:\' for \'%s\'' % t)

        for m in mentions_unmerged:
            print(f)
            print('# mentions \'%s\'' % t)

        print()

if __name__ == '__main__':
    main()
