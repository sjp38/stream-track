#!/usr/bin/env python3

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

class TrackResults:
    downstream = None
    upstream = None
    hashids = {}
    results = {}

    def __str__(self):
        lines = []
        lines.append('# upstream: %s' % self.upstream)
        lines.append('# downstream: %s' % self.downstream)
        for ref in self.hashids:
            lines.append('# %s: %s' % (ref, self.hashids[ref]))

        for t in self.results:
            lines.append('%s # %s' % (t, self.results[t]))

        return '\n'.join(lines)

def parse_track_results(results_lines, repo):
    parsed = TrackResults()
    results = parsed.results

    result = None
    for line in results_lines:
        if line == '':
            break
        if line.startswith('# upstream: '):
            parsed.upstream = line[len('# upstream: '):].split('..')
            continue
        if line.startswith('# downstream: '):
            parsed.downstream = line[len('# downstream: '):].split('..')
            continue
        if line.startswith('# '):
            fields = line[2:].split(': ')
            if (len(fields) == 2 and
                        fields[0] in parsed.upstream + parsed.downstream):
                    parsed.hashids[fields[0]] = fields[1]
            continue

        if result:
            if line in ['  mentions merged', '  mentions unmerged',
                    '  fixes merged', '  fixes unmerged']:
                type_ = line.strip().split()
                continue
            if line.startswith('    '):
                line = line.strip()
                hashid = line[:12]
                title = line[15:-2]
                upstream_commit = Commit(hashid, repo)
                if type_[1] == 'merged':
                    down_hash = True
                elif type_[1] == 'unmerged':
                    down_hash = None
                followup = [upstream_commit, down_hash]
                if type_[0] == 'mentions':
                    result.followup_mentions.append(followup)
                elif type_[0] == 'fixes':
                    result.followup_fixes.append(followup)
            else:
                result = None
        else:
            comments_start = line.rfind(' # ')
            title = line[:comments_start]
            comment = line[comments_start + 3:]
            if comment == 'downstream_only':
                results[title] = TrackResult(None)
            else:
                upstream_commit = True
                results[title] = TrackResult(upstream_commit)
            if comment not in ['downstream_only', 'no_followup']:
                result = results[title]
    return parsed

