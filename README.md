This directory contains tools for finding upstream commits that fixes or
mentions specific downstream commits and checking whether the followup changes
in the upstream are already in your downstream tree.

The Workflow
============

Suppose that you are developing your custom linux kernel based on the v5.4
linux kernel.  You would periodically rebase your work on latest 5.4 stable
release[1] to ensure your kernel is safe.  But, you would also back-port some
commits from v5.5.  Then, the periodic rebasing cannot ensure you have all
necessary fixes in your kernel, as the fixes for v5.5 do not land on 5.4 stable
releases.  This problem case is not only linux kernel specific but general to
many open source projects.  The tools can help you finding such commits.

[1] https://www.kernel.org/releases.html

Getting Started
===============

Let's suppose your kernel repo is at '$LINUX' and tracking the mainline
tree with a remote name 'mainline'.  Your working branch is named 'hack' and
based on v5.4.42.  Set 'PATH' to point this directory, move to your kernel
source tree and run below command:

    $ chk-followups.py --repo $LINUX \
            --downstream v5.4.42..hack --upstream v5.5..mainline/master

It will do the check for all commits in 'v5.4.42..hack' against all commits in
'v5.5..mainline/master'.

Output Format
-------------

The output of 'chk-followups.py' will classify each of the downstream commits
with a combination of below tags:

 - downstream_only: The commit is in the downstream only.  Maybe you made this
   change on your own.
 - no_followup: The upstream has no commits for the commit.
 - fixed: There are upstream commits fixing the commit.
 - mentioned: There are upstream commits mentioning the commit.  This could
   include non-fixes (e.g., merge), but would be worth to check.
 - unmerged: The followup commit is not merged in the downstream.

In case of 'fixed' or 'mentioned', the followup commits will also be listed.
For example:

    x86/unwind/orc: Prevent unwinding before ORC initialization # fixed
      fixes merged
        71c95825289f ("x86/unwind/orc: Fix error handling in __unwind_start()")
    bnxt_en: Improve AER slot reset. # fixed,unmerged
      fixes unmerged
        6e2f83884c09 ("bnxt_en: Fix AER reset logic on 57500 chips.")
    KEYS: Don't write out to userspace while holding key semaphore # mentioned,unmerged
      mentions unmerged
        4c205c84e249 ("Merge tag 'keys-fixes-20200329' of git://git.kernel.org/pub/scm/linux/kernel/git/dhowells/linux-fs")

The downstream commit titled 'x86/unwind/orc: Prevent unwinding...' is fixed by
the upstream commit 71c95825289f and already merged in the downstream (SAFE).
However, the downstream commit titled 'bnxt_en: Improve AER slot reset.' is
fixed by the upstream commit 6e2f83884c09 and not merged in the downstream.
You should carefully check the upstream commit whether it needs to be merged in
the downstream or not.

Speed Optimization
==================

Because 'chk-followups.py' should read each commits in the downstream revision
range and the upstream revision range, the runtime can be so long depending on
the size of the streams.  For example, as of 2020-08-01, tracking 4.9 stable
releases (v4.9..stable/linux-4.9.y as downstream and v4.10..linux/master as
upstream) takes more than 10 hours on some machines.  We provide a number of
ways to reduce the runtime.

Dedicated Downstream-only Commit Prefix
---------------------------------------

For each of the downstream commits, the tool first checks whether the commit is
backported from the upstream or not.  If not, it couldn't have followup and
therefore the check is finished.  The time for this increases as the number of
the upstream commits grows.  If the number of downstream-only commit is high in
your case, most of the tracking time will be used for this check.

For some reasons, some teams mark their downstream-only commits by adding a
dedicated prefix such as team name or product name in fron of the commit
titles.  If you are also using this strategy, you could let the tool know this
by using '--downstream_prefix' option of 'chk-followups.py'.  If it is given,
the tool will be able to know if a commit is downstream-only by reading the
title.

Using Previous Results as a Cache
---------------------------------

The tracking should be periodically repeated, as the upstream will keep
changing.  In that case, as the ranges of the downstream and the upstream will
only subtly changed between the iterations, the tracking could be finished
shortly if we can use the previous tracking results.  You can let the tool to
know the previous tracking results using '--prev_results' option of
'chk-followups.py'.

Ignoring Specific Followups
===========================

Some followups could be already merged in the downstream in different name, or
maybe you could manually review the followup and decided to don't merge that,
because it has only trivial fix.  For such cases, you can write down some rules
for the followups that need to be ignored in a file and give the file to
'chk-followups.py' using '--ignore_rule' option.

The rule is constructed with a number of commits.  If the first commit is in
the given downstream range, 'chk-followups' think the other commits of the rule
is already merged in the downstream.  In other words, the other commits are
ignored.  Suppose upstream commit A is fixed by upstream commit B in the
upstream and those are backported in downstream as A' and B'.  If A' has a
title same to A but B' has a title different from that of B, 'chk-followups'
will say upstream commit B is not merged in the downstream yet.  However, if
you provide a rule (B', B), the tool will say B is already merged in.  Note
that B' could be A' in some case.  Or, if you know B is not merged in
downstream but you think it is not necessary (maybe because it fixes only
trivial problem), you can provide a rule (A', B).

In the file, the commits should be placed in each line in form of:

    <hash id> [whatever]

You can put some additional info of the commit, for example, the subject of the
commit, in the [whatever] field.

If there are multiple rules, those should be separated with a blank line.
Also, lines starting with '#' are comments and thus ignored.  For example,
below rules are available:

    # the root cause commit backported with the fixes sqaushed in it
    1234567890abcd ("Implement feature A")
    234567890abcd1 ("Fix feature A implementation")
    34567890abcd12 ("Fix yet another bug of feature A")

    # multiple fixes squashed in one commit and back-ported
    1234567890abcd ("Fix A and B")
    234567890abcd1 ("Fix A")
    34567890abcd12 ("Fix B")

    # trivial fixes that don't need to be merged in the downstream
    4567890abcd123 ("Implement feature B")
    567890abcd1234 ("Fix typo in feature B documentation")
    67890abcd12345 ("Fix trivial bug in feature B")

Summarizing Repeated Tracking Results
=====================================

Users would repeatedly do the tracking, as long as the upstream is live and
keep changing.  Because the purpose of the repeated tracking is only finding
new followups, the 'chk-followups.py' outputs of each repeated runs would be
too verbose.  You can get a summary of the outputs by storing the outputs in
files and giving the list of the files to 'summary_outputs.py'.  The summary
will be something like below:

    # cmmt: The downstream commits
    # port: The downstream commits back-ported from the upstream
    # fixs: The upstream commits fixing the 'port'
    # ufix: 'fixs' that unapplied in the downstream
    # mntn: The upstream commits mentioning the 'port'
    # umnt: 'mntn' that unapplied in the downstream
    #
                 file       cmmt    port    fixs    ufix    mntn    umnt
    2020-07-16/5.4-stable   6633    4229    131     18      62      15      # up: 2020-01-26..2020-07-15 dn: 2019-11-24..2020-07-16
    2020-07-17/5.4-stable   6633    4229    132     19      62      15      # up: 2020-01-26..2020-07-17 dn: 2019-11-24..2020-07-16
    2020-07-19/5.4-stable   6633    4229    132     19      62      15      # up: 2020-01-26..2020-07-19 dn: 2019-11-24..2020-07-16
    2020-07-21/5.4-stable   6633    4229    133     20      62      15      # up: 2020-01-26..2020-07-20 dn: 2019-11-24..2020-07-16
    2020-07-23/5.4-stable   6848    4434    139     10      65      16      # up: 2020-01-26..2020-07-23 dn: 2019-11-24..2020-07-22
    2020-07-25/5.4-stable   6848    4434    145     16      66      17      # up: 2020-01-26..2020-07-25 dn: 2019-11-24..2020-07-22
    2020-07-27/5.4-stable   6848    4434    147     18      70      21      # up: 2020-01-26..2020-07-26 dn: 2019-11-24..2020-07-22

Formatting Report
=================

Every information is in the 'chk-followup.py' output.  However, the format is
mainly designed for the tool runner.  The project maintainers, who should
review the output and apply some followups on the project, might be different
people.  The maintainers could even work in different company or organization.
From their perspective, the format could seems verbose, not well organized, and
require manual repetitive instrumentations.

For such cases, 'format_report.py' receives the 'chk-followup.py' output and
reformat it as a report for the maintainer.  The report is in 'git send-email'
applicable simplified mail format.  So, the user can directly send it to the
maintainer via 'git send-email'.

You could refer to the report for 5.4.y linux stable releases, generated and
posted in the way:
https://lore.kernel.org/stable/20200828152745.10819-1-sjpark@amazon.com/

Similar Tools
=============

Because the problem case is quite general, there could be similar tools.  This
section lists those and compare the tools in this directory (stream-track)
against those, so that you can choose the right tool for your case.  The
comparison is based on only my sheer understanding of the tools only, so there
could be many wrong points.  If you find such things, please let me know.

git-fixes
---------

git-fixes[1] is a matured tool developed by Jörg Rödel.  The main job of the
tool is quite similar to that of stream-track: "finding upstream fixes for
backported commits."

The biggest difference between it and stream-fix is the language.  git-fixes is
almost written in CPP while stream-track is almost Python.  For the reason,
git-fixes would be faster in general, though stream-track also provides some
performance optimization tricks.  However, stream-track would be easier to be
modified by users for special use cases of them.

There are small differences in the usage and the fixes identification logic,
but seems those of git-fixes is optimized for SUSE kernel.  Meanwhile,
stream-track is designed for kaos (this is not a typo, but reading it as chaos
still works) rather than cleanly managed trees.

In summary, stream-track might be unmatured and slow (the design is made for
only daily tracking) but flexible and easier to apply, compared to git-fixes.

[1] https://github.com/joergroedel/git-fixes
