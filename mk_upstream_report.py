#!/usr/bin/env python3

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

def main():
    print('Nice to meet you, but I need more implementation')

if __name__ == '__main__':
    main()
