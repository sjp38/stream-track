#!/usr/bin/env python3

import argparse
import subprocess

class Commit:
    gitref = None
    commit_hash = None
    title = None
    msg = None

    def __init__(self, gitref, repo):
        self.gitref = gitref

        git_cmd = ['git', '--git-dir=%s/.git' % repo]
        git_cmd += ['show', '%s' % gitref, '--pretty=%H%n%B', '--quiet']
        git_log = subprocess.check_output(git_cmd).decode().strip()

        log_lines = git_log.split('\n')
        self.commit_hash = log_lines[0]
        self.title = log_lines[1]
        self.msg = '\n'.join(log_lines[2:])

    def __str__(self):
        return '%s ("%s")' % (self.commit_hash[:12], self.title)

    def is_fix_of(self, commit):
        fixes_tag = 'Fixes: %s ("%s")' % (commit.commit_hash[:12], commit.title)
        return fixes_tag in self.msg

    def mentioned(self, commit):
        if self.title.lower().startswith('merge '):
            return False
        return commit.title in self.msg or commit.commit_hash in self.msg

class TrackResult:
    upstream_commit = None
    followup_fixes = None
    followup_mentions = None

    def __init__(self, upstream_commit):
        self.upstream_commit = upstream_commit
        self.followup_fixes = []    # [[upstream commit, downstream hash] ...]
        self.followup_mentions = [] # [[upstream commit, downstream hash] ...]

    def __str__(self):
        if not self.upstream_commit:
            return 'downstream_only'

        if not self.followup_fixes and not self.followup_mentions:
            return 'no_followup'

        fixes_merged = [x[0] for x in self.followup_fixes if x[1]]
        fixes_unmerged = [x[0] for x in self.followup_fixes if not x[1]]

        mentions_merged = [x[0] for x in self.followup_mentions if x[1]]
        mentions_unmerged = [x[0] for x in self.followup_mentions if not x[1]]

        tags = []
        if fixes_merged or fixes_unmerged:
            tags.append('fixed')
        if mentions_merged or mentions_unmerged:
            tags.append('mentioned')
        if fixes_unmerged or mentions_unmerged:
            tags.append('unmerged')
        lines = [','.join(tags)]

        if fixes_unmerged:
            lines.append('  fixes unmerged')
            lines += ['    %s' % x for x in fixes_unmerged]

        if fixes_merged:
            lines.append('  fixes merged')
            lines += ['    %s' % x for x in fixes_merged]

        if mentions_unmerged:
            lines.append('  mentions unmerged')
            lines += ['    %s' % x for x in mentions_unmerged]

        if mentions_merged:
            lines.append('  mentions merged')
            lines += ['    %s' % x for x in mentions_merged]

        return '\n'.join(lines)

def hash_by_title(title, revision_range, repo):
    keyword = title.replace('\'', '\'"\'"\'')
    cmd = 'git --git-dir=%s/.git log --oneline %s | grep -F \'%s\' -m 1' % (
            repo, revision_range, keyword)
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

def pr_highlights(results):
    for title in results:
        r = results[title]
        if not r.followup_fixes and not r.followup_mentions:
            continue
        print('%s #' % title, r)

def pr_summary(results):
    print('%d of the %d downstream commits are merged in the upstream.' %
            (len([x for x in results.values() if x.upstream_commit]),
            len(results)))

    nr_fixed = 0
    nr_fixes = 0
    nr_unmerged_fixes = 0
    for r in results.values():
        if r.followup_fixes:
            nr_fixed += 1
            nr_fixes += len(r.followup_fixes)
            for f in r.followup_fixes:
                if f[1] == None:
                    nr_unmerged_fixes += 1

    print('%d followup fixes found (%d are not applied downstream)' %
            (nr_fixes, nr_unmerged_fixes))

    nr_mentioned = 0
    nr_mentions = 0
    nr_unmerged_mentions = 0
    for r in results.values():
        if r.followup_mentions:
            nr_mentioned += 1
            nr_mentions += len(r.followup_mentions)
            for f in r.followup_mentions:
                if f[1] == None:
                    nr_unmerged_mentions += 1

    print('%d followup mentions found (%d are not applied downstream)' %
            (nr_mentions, nr_unmerged_mentions))

def set_argparser(parser):
    parser.add_argument('--repo', metavar='<path>', default='./',
            help='path to the kernel source git repo')
    parser.add_argument('--upstream', metavar='<revision range>',
            help='the upstream history')
    parser.add_argument('--downstream', metavar='<revision range>',
            help='the downstream history')
    parser.add_argument('--titles', metavar='<title>',
            help='the titles of the downstream commits to track for')

    parser.add_argument('--followups_only', action='store_true',
            help='do not print commits having no followups')
    parser.add_argument('--all_files', action='store_true',
            help='track whole files, rather than touched files only')

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

    print('# upstream:', upstream)
    print('# downstream:', downstream)

    if not args.titles:
        print('# track for all downstream commits')
        cmd = 'git --git-dir=%s/.git log --pretty=%%s %s' % (repo, downstream)
        try:
            args.titles = subprocess.check_output(cmd, shell=True).decode()
        except:
            print('failed getting the downstream commits')
            exit(1)
    titles = args.titles.strip().split('\n')

    results = {}

    for t in titles:
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
        pr_highlights(results)
    print()
    print()
    print('SUMMARY')
    print('=======')
    print()
    pr_summary(results)

if __name__ == '__main__':
    main()
