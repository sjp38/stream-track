#!/usr/bin/env python3

import datetime
import subprocess

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
