#!/usr/bin/env python3

import argparse
import datetime
import os

import git
import track_results

"""
TODO

- Format patches
- Add recipients
"""

class Report:
    commit = None
    commit_date = None
    author = None
    fixes = None
    mentions = None
    applicable = None

    def __init__(self, commit, repo):
        self.commit = commit
        self.commit_date = git.commit_date(commit.commit_hash, repo)
        self.author = git.author(commit.commit_hash, repo)
        self.fixes = []
        self.mentions = []

    def __str__(self):
        lines = ['%s' % self.commit]
        lines.append('# commit date: %s, author: %s' %
            (self.commit_date.strftime('%Y-%m-%d'), self.author))
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

    # Check if the commits are cleanly applicable
    cwd = os.getcwd()
    os.chdir(args.repo)
    original_head = git.head_hashid()

    downstream_end = prev_res.downstream[-1]
    git.reset_hard(downstream_end)

    for report in to_report.values():
        if git.applicable(report.commit.commit_hash, downstream_end):
            report.applicable = True
        else:
            report.applicable = False

    git.reset_hard(original_head)
    os.chdir(cwd)

    # Print the report

    authors = {}
    for r in to_report.values():
        authors[r.author] = True

    print('To: %s' % ', '.join(authors))

    print("""
We found below %d commits in the '%s (upstream)' seems fixing or mentioning
commits in the '%s (downstream)' but are not merged in the 'downstream' yet.
Could you please review if those need to be merged in?

The commits are grouped as 'fixes cleanly applicable', 'fixes not cleanly
applicable (need manual backporting to be applied)', 'mentions cleanly
applicable', and 'mentions not cleanly applicable'.  Also, the commits in each
group are sorted by the commit dates (oldest first).

Both the finding of the commits and the writeup of this report is automatically
done by a little script[1].  I'm going to run the tool and post this kind of
report every couple of weeks or every month.  Any comment (e.g., regarding
posting period, new features request, bug report, ...) is welcome.

Especially, if you find some commits that don't need to be merged in the
downstream, please let me know so that I can mark those as unnecessary and
don't bother you again.

[1] https://github.com/sjp38/stream-track
""" % (len(to_report),
    '..'.join(prev_res.upstream), '..'.join(prev_res.downstream)))

    for ref in prev_res.hashids:
        print('    # %s: %s' % (ref, prev_res.hashids[ref]))
    print('\n')

    print('Fixes cleanly applicable')
    print('------------------------')
    print()
    for r in sorted(
            [r for r in to_report.values() if r.fixes and r.applicable],
            key=lambda r: r.commit_date):
        print(r)
        print()
    print('\n')

    print('Fixes not cleanly applicable')
    print('----------------------------')
    print()
    for r in sorted(
            [r for r in to_report.values() if r.fixes and not r.applicable],
            key=lambda r: r.commit_date):
        print(r)
        print()
    print('\n')

    print('Mentions cleanly applicable')
    print('---------------------------')
    print()
    for r in sorted(
            [r for r in to_report.values() if not r.fixes and r.applicable],
            key=lambda r: r.commit_date):
        print(r)
        print()
    print('\n')

    print('Mentions not cleanly applicable')
    print('-------------------------------')
    print()
    for r in sorted(
            [r for r in to_report.values() if not r.fixes and not r.applicable],
            key=lambda r: r.commit_date):
        print(r)
        print()
    print('\n')

if __name__ == '__main__':
    main()
