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

def track(commit, repo, upstream, downstream, track_all_files):
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
    cmd = 'git --git-dir=%s/.git rev-parse %s' % (repo, reference)
    return subprocess.check_output(cmd, shell=True).decode().strip()

def pr_streams(upstream, downstream, repo):
    print('# upstream: %s' % upstream)
    print('# downstream: %s' % downstream)

    for ref in upstream.split('..') + downstream.split('..'):
        hash_ = hash_by_ref(ref, repo)
        print('# %s: %s' % (ref, hash_))

def same_streams(prev_results, upstream, downstream, repo):
    prev_upstream = [prev_results.hashids[x] for x in prev_results.upstream]
    prev_dnstream = [prev_results.hashids[x] for x in prev_results.downstream]

    upstream = [hash_by_ref(r, repo) for r in upstream.split('..')]
    dnstream = [hash_by_ref(r, repo) for r in downstream.split('..')]

    return prev_upstream == upstream and prev_dnstream == dnstream

def set_argparser(parser):
    parser.add_argument('--repo', metavar='<path>', default='./',
            help='path to the kernel source git repo')
    parser.add_argument('--upstream', metavar='<revision range>',
            help='the upstream history')
    parser.add_argument('--downstream', metavar='<revision range>',
            help='the downstream history')
    parser.add_argument('--titles', metavar='<title>',
            help='the titles of the downstream commits to track for')
    parser.add_argument('--prev_results', metavar='<file>',
            help='the file containing previous result')

    parser.add_argument('--followups_only', action='store_true',
            help='do not print commits having no followups')
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

    if not args.titles:
        if args.prev_results:
            with open(args.prev_results, 'r') as f:
                prev_res = parse_track_results(f.readlines(), repo)
                if (same_streams(prev_res, upstream, downstream, repo)):
                    print(prev_res)
                    exit(0)

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

    track_results = TrackResults()
    results = {}
    track_results.results = results

    for t in titles:
        if args.downstream_prefix and t.startswith(args.downstream_prefix):
            h = None
        else:
            h = hash_by_title(t, upstream, repo)

        if not h:
            results[t] = TrackResult(None)
        else:
            c = Commit(h, repo)
            results[t] = track(c, repo, upstream, downstream, args.all_files)
        r = results[t]
        if not args.followups_only or (r.followup_fixes or r.followup_mentions):
            print('%s #' % t, results[t])

    if not args.followups_only:
        print()
        print()
        print('HIGHLIGHTS')
        print('==========')
        print()
        print('\n'.join(track_results.highlight_lines()))
    print()
    print()
    print('SUMMARY')
    print('=======')
    print()
    print('\n'.join(track_results.summary_lines()))

if __name__ == '__main__':
    main()
