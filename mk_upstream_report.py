#!/usr/bin/env python3

import argparse
import datetime

import git
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

class Report:
    commit = None
    commit_date = None
    fixes = None
    mentions = None

    def __init__(self, commit, repo):
        self.commit = commit
        self.commit_date = git.commit_date(commit.commit_hash, repo)
        self.fixes = []
        self.mentions = []

    def __str__(self):
        lines = ['%s %s' % (
            self.commit_date.strftime('%Y-%m-%d'),self.commit)]
        for f in self.fixes:
            lines.append('# fixes \'%s\'' % f)
        for m in self.mentions:
            lines.append('# mentions \'%s\'' % m)
        return '\n'.join(lines)

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
            if not f.gitref in to_report:
                to_report[f.gitref] = Report(f, args.repo)
            report = to_report[f.gitref]
            report.fixes.append(t)

        for f in mentions_unmerged:
            if not f.gitref in to_report:
                to_report[f.gitref] = Report(f, args.repo)
            report = to_report[f.gitref]
            report.mentions.append(t)

    # Print the report
    print("""
Using an automated tool[1], we found below %d commits in the '%s (upstream)'
are fixing or mentioning commits in the '%s (downstream)' but not merged in the
'downstream'.  The commits are sorted by the commit date.  Could you please
review if those need to be merged in the upstream?

[1] https://github.com/sjp38/stream-track
""" %
(len(to_report),
    '..'.join(prev_res.upstream), '..'.join(prev_res.downstream)))

    for ref in prev_res.hashids:
        print('    # %s: %s' % (ref, prev_res.hashids[ref]))
    print('\n')

    # TODO: Sort by the commit date (old first), fixes first
    for report in sorted(to_report.values(), key=lambda x: x.commit_date):
        print(report)
        print()

if __name__ == '__main__':
    main()
