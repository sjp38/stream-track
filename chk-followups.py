#!/usr/bin/env python3

import argparse
import subprocess

from track_results import *

title_hash_maps = {}

def hash_by_title(title, revision_range, repo):
    if not revision_range in title_hash_maps:
        title_hash_maps[revision_range] = {}
    cache = title_hash_maps[revision_range]
    if title in cache:
        return cache[title]

    keyword = title.replace('\'', '\'"\'"\'')
    cmd = 'git --git-dir=%s/.git log --oneline %s --abbrev=12' % (
            repo, revision_range)
    cmd += ' | grep -F \'%s\' -m 1' % keyword
    try:
        result = subprocess.check_output(cmd, shell=True).decode()
        commit_hash = result[:12]
        grepped = result[13:].strip()
        if grepped != title:
            new_range = commit_hash + '^'
            boundaries = revision_range.split('..')
            if len(boundaries) == 2:
                new_range = '%s..%s' % (boundaries[0], new_range)
            return hash_by_title(title, new_range, repo)
        cache[title] = commit_hash
        return commit_hash
    except:
        return None

def touched_files(gitref, repo):
    git_cmd = ['git', '--git-dir=%s/.git' % repo]
    git_cmd += ['show', '%s' % gitref, '--pretty=', '--name-only']
    return subprocess.check_output(git_cmd).decode().strip().split('\n')

def hashes_in(base, to, repo, target_files):
    git_cmd = ['git', '--git-dir=%s/.git' % repo]
    git_cmd += ['log', '%s..%s' % (base, to), '--pretty=%H']
    if target_files:
        git_cmd += ['--'] + target_files.split()
    return subprocess.check_output(git_cmd).decode().strip().split('\n')

def track_commit(commit, repo, upstream, downstream, track_all_files):
    result = TrackResult(commit)

    files = ''
    if not track_all_files:
        files = ' '.join(touched_files(commit.commit_hash, repo))

    upstream_end = upstream
    upstream_boundaries = upstream.split('..')
    if len(upstream_boundaries) == 2:
        upstream_end = upstream_boundaries[1]

    to_check = hashes_in(commit.commit_hash, upstream_end, repo, files)
    for h in to_check:
        if not h:
            continue
        upstream_commit = Commit(h, repo)
        followups = [upstream_commit, None]
        if upstream_commit.is_fix_of(commit):
            result.followup_fixes.append(followups)
        elif upstream_commit.mentioned(commit):
            result.followup_mentions.append(followups)
        else:
            continue

        followups[1] = hash_by_title(upstream_commit.title, downstream, repo)

    return result

def hash_by_ref(reference, repo):
    if not repo in hash_by_ref.cache:
        hash_by_ref.cache[repo] = {}
    if reference in hash_by_ref.cache[repo]:
        return hash_by_ref.cache[repo][reference]

    cmd = 'git --git-dir=%s/.git rev-parse %s' % (repo, reference)
    hashid = subprocess.check_output(cmd, shell=True).decode().strip()
    hash_by_ref.cache[repo][reference] = hashid
    return hashid
hash_by_ref.cache = {}

def pr_streams(upstream, downstream, repo):
    print('# upstream: %s' % upstream)
    print('# downstream: %s' % downstream)

    for ref in upstream.split('..') + downstream.split('..'):
        hash_ = hash_by_ref(ref, repo)
        print('# %s: %s' % (ref, hash_))

def comm_rev_ranges(range1, range2, repo):
    "Return common part in two revision ranges"
    if len(range1) == 1:
        range1 = [''] + range1
    if len(range2) == 1:
        range2 = [''] + range2

    comm_end = None
    if range1[1] == range2[1]:
        comm_end = range1[1]
    else:
        cmd = 'git --git-dir=%s/.git merge-base %s %s' % (repo,
                range1[1], range2[1])
        comm_end = subprocess.check_output(cmd, shell=True).decode().strip()
    if not comm_end:
        return None

    comm_start = None
    if range1[0] == range2[0]:
        comm_start = range1[0]
    else:
        cmd = 'git --git-dir=%s/.git log --pretty=%%h --abbrev=12 %s^..%s' % (
                repo, range1[0], comm_end)
        cmd += ' --first-parent'
        range1_commits = subprocess.check_output(cmd, shell=True).decode().strip().split('\n')
        cmd = 'git --git-dir=%s/.git log --pretty=%%h --abbrev=12 %s^..%s' % (
                repo, range2[0], comm_end)
        cmd += ' --first-parent'
        range2_commits = subprocess.check_output(cmd, shell=True).decode().strip().split('\n')

        if len(range1_commits) == 0 or len(range2_commits) == 0:
            return None

        if len(range1_commits) > len(range2_commits):
            shorter = range2_commits
            longer = range1_commits
        else:
            shorter = range1_commits
            longer = range2_commits

        comm_start = shorter[-1]
        for idx, r in enumerate(shorter):
            if r != longer[idx]:
                comm_start = longer[idx - 1]

    return [comm_start, comm_end]

def track_from_scratch(title, repo, upstream, downstream, check_all_files):
    h = hash_by_title(title, upstream, repo)
    if not h:
        return TrackResult(None)

    c = Commit(h, repo)
    return track_commit(c, repo, upstream, downstream, check_all_files)

def do_track(title, repo, upstream, downstream, downstream_prefix,
        check_all_files, prev_results):

    if downstream_prefix and title.startswith(downstream_prefix):
        return TrackResult(None)

    if not prev_results or not title in prev_results.results:
        return track_from_scratch(title, repo, upstream, downstream,
                check_all_files)

    prev_up = [prev_results.hashids[x] for x in prev_results.upstream]
    prev_dn = [prev_results.hashids[x] for x in prev_results.downstream]
    now_up = [hash_by_ref(x, repo) for x in upstream.split('..')]
    now_dn = [hash_by_ref(x, repo) for x in downstream.split('..')]
    if prev_up == now_up and prev_dn == now_dn:
        return prev_results.results[title]

    pres = prev_results.results[title]
    if not do_track.upstreams_comm:
        do_track.upstreams_comm = comm_rev_ranges(prev_up, now_up, repo)
    comm = do_track.upstreams_comm

    # exclude track results that invalid due to changed upstream range
    exclude_ranges = ['%s..%s' % (prev_up[0], comm[0]),
            '%s..%s' % (comm[1], prev_up[1])]
    for r in exclude_ranges:
        if hash_by_title(title, r, repo):
            # it's downstream only now
            return TrackResult(None)
        filtered_followups = []
        for f in pres.followup_fixes:
            if hash_by_title(f[0].title, r, repo):
                # the followup is not in the new upstream
                continue
            filtered_followups.append(f)
        pres.followup_fixes = filtered_followups

        filtered_followups = []
        for f in pres.followup_mentions:
            if hash_by_title(f[0].title, r, repo):
                # the followup is not in the new upstream
                continue
            filtered_followups.append(f)
        pres.followup_mentions = filtered_followups

    # include new followups made due to the changed upstream range
    include_ranges = ['%s..%s' % (now_up[0], comm[0]),
            '%s..%s' % (comm[1], now_up[1])]
    for r in include_ranges:
        h = hash_by_title(title, r, repo)
        if not h:
            continue
        c = Commit(h, repo)
        pres.upstream_commit = c
        new_result = track_commit(c, repo, r, downstream, check_all_files)
        pres.followup_fixes += new_result.followup_fixes
        pres.followup_mentions += new_result.followup_mentions

    if not do_track.downstreams_comm:
        do_track.downstreams_comm = comm_rev_ranges(prev_dn, now_dn, repo)
    comm = do_track.downstreams_comm

    # exclude followup backports that invalid due to the changed downstream
    exclude_ranges = ['%s..%s' % (prev_dn[0], comm[0]),
            '%s..%s' % (comm[1], prev_dn[1])]
    for r in exclude_ranges:
        for f in pres.followup_fixes + pres.followup_mentions:
            if f[1] and hash_by_title(f[0].title, r, repo):
                # the backport of the followup is not in the current downstream
                f[1] = None

    # include followup backports that made by the changed downstream range
    include_ranges = ['%s..%s' % (now_dn[0], comm[0]), '%s..%s' % (
        comm[1], now_dn[1])]
    for r in include_ranges:
        for f in pres.followup_fixes + pres.followup_mentions:
            if not f[1]:
                f[1] = hash_by_title(f[0].title, r, repo)

    return pres
do_track.upstreams_comm = None
do_track.downstreams_comm = None

def read_ignore_rules(rules_file):
    rules = {}
    with open(rules_file, 'r') as f:
        to_ignore = None
        for line in f:
            if line.startswith('#'):
                continue
            line = line.strip()
            if line == '':
                to_ignore = None
                continue

            hashid = line.split()[0]
            if to_ignore == None:
                to_ignore = []
                rules[hashid] = to_ignore
            else:
                to_ignore.append(hashid)
    return rules

def set_argparser(parser):
    parser.add_argument('--repo', metavar='<path>', default='./',
            help='path to the kernel source git repo')
    parser.add_argument('--upstream', metavar='<revision range>',
            help='the upstream history')
    parser.add_argument('--downstream', metavar='<revision range>',
            help='the downstream history')
    parser.add_argument('--titles', metavar='<title>',
            help='the titles of the downstream commits to track for')
    parser.add_argument('--ignore_rule', metavar='<file>',
            help='ignore specific follower commits')
    parser.add_argument('--prev_results', metavar='<file>',
            help='use the previous result for speedup of the check')

    parser.add_argument('--followups_only', action='store_true',
            help='do not print commits having no followups')
    parser.add_argument('--highlight_skip_merged', action='store_true',
            help='skip merged followups in the highlight section')
    parser.add_argument('--all_files', action='store_true',
            help='track whole files, rather than touched files only')

    parser.add_argument('--downstream_prefix', metavar='<prefix>',
            help='commits having titles with the prefix are downstream only')
    parser.description='track status of followup commits in the upstream.'

def main():
    parser = argparse.ArgumentParser()
    set_argparser(parser)
    args = parser.parse_args()

    repo = args.repo

    if not args.upstream:
        print('upstream is not given')
        parser.print_help()
        exit(1)
    upstream = args.upstream

    if not args.downstream:
        cmd = 'git --git-dir=%s/.git describe --abbrev=0' % repo
        try:
            base = subprocess.check_output(cmd, shell=True).decode().strip()
        except:
            printf('failed getting the default downstream')
            exit(1)
        args.downstream = '%s..HEAD' % base
        print('# use %s as downstream' % args.downstream)
    downstream = args.downstream

    pr_streams(upstream, downstream, repo)

    prev_res = None
    if args.prev_results:
        with open(args.prev_results, 'r') as f:
            prev_res = parse_track_results(f.readlines(), repo)

    if not args.titles:
        print('# track for all downstream commits')
        if not downstream in title_hash_maps:
            title_hash_maps[downstream] = {}

        cmd = 'git --git-dir=%s/.git log --pretty="%%h %%s" --abbrev=12 %s' % (
                repo, downstream)
        try:
            results = subprocess.check_output(cmd, shell=True).decode()
            titles = []
            for r in results.strip().split('\n'):
                r = r.strip()
                hashid = r[:12]
                title = r[13:]
                title_hash_maps[downstream][title] = hashid
                titles.append(title)
        except:
            print('failed getting the downstream commits')
            exit(1)
    else:
        titles = args.titles.strip().split('\n')

    ignore_rules = {}
    if args.ignore_rule:
        ignore_rules = read_ignore_rules(args.ignore_rule)

    track_results = TrackResults()
    results = {}
    track_results.results = results

    for t in titles:
        results[t] = do_track(t, repo, upstream, downstream,
                args.downstream_prefix, args.all_files, prev_res)
        r = results[t]
        hashid = hash_by_title(t, downstream, repo)
        if hashid in ignore_rules:
            new_followup_fixes = []
            for f in r.followup_fixes:
                if f[0].commit_hash[:12] in ignore_rules[hashid]:
                    continue
                new_followup_fixes.append(f)
            r.followup_fixes = new_followup_fixes

            new_followup_mentions = []
            for m in r.followup_mentions:
                if m[0].commit_hash[:12] in ignore_rules[hashid]:
                    continue
                new_followup_mentions.append(m)
            r.followup_mentions = new_followup_mentions

        if not args.followups_only or (r.followup_fixes or r.followup_mentions):
            print('%s #' % t, results[t])

    if not args.followups_only:
        print()
        print()
        print('HIGHLIGHTS')
        print('==========')
        print()
        print('\n'.join(track_results.highlight_lines(
            args.highlight_skip_merged)))
    print()
    print()
    print('SUMMARY')
    print('=======')
    print()
    print('\n'.join(track_results.summary_lines()))

if __name__ == '__main__':
    main()
