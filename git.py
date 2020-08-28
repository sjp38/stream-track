#!/usr/bin/env python3

import datetime
import subprocess
import traceback

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

def author(hashid, repo):
    cmd = 'git --git-dir=%s/.git log %s^..%s' % (repo, hashid, hashid)
    cmd += ' --pretty="%aN <%aE>" | head -n 1'
    return subprocess.check_output(cmd, shell=True).decode().strip()

def head_hashid(repo=None):
    git_cmd = 'git '
    if repo:
        git_cmd += '--git-dir=%s/.git ' % repo
    cmd = git_cmd + 'show --pretty=%H --quiet'
    return subprocess.check_output(cmd, shell=True).decode().strip()

def reset_hard(ref):
    cmd = 'git reset --hard %s' % ref
    subprocess.check_output(cmd, shell=True)

# NOTE: working directory should be the repo
def applicable(hashid, base):
    original_hashid = head_hashid()

    reset_hard(base)

    cmd = 'git cherry-pick %s' % hashid
    try:
        subprocess.check_output(cmd, shell=True).decode().strip()
    except subprocess.CalledProcessError as e:
        try:
            cmd = 'git cherry-pick --abort'
            subprocess.check_output(cmd, shell=True)
        except Exception as e:
            print('failed aborting cherry-pick!', e)
            exit(1)
        reset_hard(original_hashid)
        return False

    reset_hard(original_hashid)
    return True
