#!/usr/bin/env python

import argparse
import datetime
import os
import subprocess

import track_results

class Summary:
    nr_commits = None
    nr_backported = None
    nr_fixed = None
    nr_fixed_unapplied = None
    nr_mentioned = None
    nr_mentioned_unapplied = None

    def __str__(self):
        return '%d\t%d\t%d\t%d\t%d\t%d' % (self.nr_commits, self.nr_backported,
                self.nr_fixed, self.nr_fixed_unapplied,
                self.nr_mentioned, self.nr_mentioned_unapplied)

def parse_summary(lines):
    """
        SUMMARY
        =======

        <N> of the <M> downstream commits are merged in the upstream.
        <O> followup fixes found (<P> are not applied downstream)
        <Q> followup mentions found (<R> are not applied downstream)
    """

    if ['SUMMARY\n', '=======\n', '\n'] != lines[:3]:
        return None

    summary = Summary()
    summary.nr_commits = int(lines[3].split()[3])
    summary.nr_backported = int(lines[3].split()[0])
    summary.nr_fixed = int(lines[4].split()[0])
    summary.nr_fixed_unapplied = int(lines[4].split()[4][1:])
    summary.nr_mentioned = int(lines[5].split()[0])
    summary.nr_mentioned_unapplied = int(lines[5].split()[4][1:])

    return summary

def commit_date(hashid, repo):
    cmd = 'git --git-dir=%s/.git log %s^..%s' % (repo, hashid, hashid)
    cmd += ' --pretty="%cd" --date=format:\'%Y-%m-%d\' | head -n 1'
    date_str = subprocess.check_output(cmd, shell=True).decode().strip()
    try:
        return datetime.datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print('Could not get the commit date of %s' % hashid)
        print('Please check whether \'--repo\' is properly provided.')
        exit(1)

def fmt_date_range(start, end):
    return '%s..%s' % (start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

def parse_pr_summary(prefix, output_lines, repo):
    results = track_results.parse_track_results(output_lines[:10], repo)
    upstream = results.upstream
    downstream = results.downstream
    hashes = results.hashids
    if not upstream or not downstream or not hashes:
        return

    up = fmt_date_range(commit_date(hashes[upstream[0]], repo),
            commit_date(hashes[upstream[1]], repo))
    dn = fmt_date_range(commit_date(hashes[downstream[0]], repo),
            commit_date(hashes[downstream[1]], repo))

    summary = parse_summary(output_lines[-6:])
    if not summary:
        return
    print('%s\t%s\t# up: %s dn: %s' % (prefix, summary, up, dn))

def pr_comments_legends(max_filename_len):
    print('# cmmt: The downstream commits')
    print('# port: The downstream commits back-ported from the upstream')
    print('# fixs: The upstream commits fixing the \'port\'')
    print('# ufix: \'fixs\' that unapplied in the downstream')
    print('# mntn: The upstream commits mentioning the \'port\'')
    print('# umnt: \'mntn\' that unapplied in the downstream')
    print('#')
    print(' ' * (max_filename_len - 4), end='')
    print('\t'.join('file cmmt port fixs ufix mntn umnt'.split()))

def set_argparser(parser):
    parser.add_argument('outputs', metavar='<file>', nargs='+',
            help='files containing output of chk-followups.py')
    parser.add_argument('--repo', metavar='<path>', default='./',
            help='path to the tracking git repo')
    parser.add_argument('--brief', action='store_true',
            help='exclude comments and legends from the output')

def main():
    parser = argparse.ArgumentParser()
    set_argparser(parser)
    args = parser.parse_args()

    filename_lengths = [len(output) for output in args.outputs]
    maxlen = max(filename_lengths)

    if not args.brief:
        pr_comments_legends(maxlen)

    for output in args.outputs:
        if not os.path.isfile(output):
            print('%s not exist' % output)
            continue
        with open(output, 'r') as f:
            parse_pr_summary(output, f.readlines(), args.repo)

if __name__ == '__main__':
    main()
