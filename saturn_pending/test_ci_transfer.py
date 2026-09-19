#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Synthetic API transfer identity controls, not downloaded-binary evidence."""
import base64
import hashlib

from fetch_ci_artifact import source_identity, transfer_identity, decode_blob, BRANCH

source = 'a'*40
run = dict(status='completed', conclusion='success', headBranch=BRANCH,
           workflowName='Saturn integration artifact', headSha=source)
data = b'synthetic transfer bytes, not an executable'
sha = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
release = dict(isDraft=True, targetCommitish=source,
               body='Temporary API transfer blob: '+sha+'\n')
record = dict(sha=sha, encoding='base64', size=len(data),
              content=base64.b64encode(data).decode()+'\n')
assert source_identity(run) == source
assert transfer_identity(release, source) == sha
assert decode_blob(record, sha) == data
bad = []
for key, value in [('status', 'in_progress'), ('conclusion', 'failure'),
                   ('headBranch', 'other'), ('workflowName', 'other'), ('headSha', '../bad')]:
    r = dict(run, **{key: value})
    bad.append(lambda r=r: source_identity(r))
for key, value in [('isDraft', False), ('targetCommitish', 'b'*40),
                   ('body', ''), ('body', release['body']*2)]:
    r = dict(release, **{key: value})
    bad.append(lambda r=r: transfer_identity(r, source))
for key, value in [('sha', 'b'*40), ('encoding', 'utf8'), ('size', 0),
                   ('size', 65*1024*1024), ('size', len(data)+1),
                   ('content', 'not!base64'),
                   ('content', base64.b64encode(b'x'*len(data)).decode())]:
    r = dict(record, **{key: value})
    bad.append(lambda r=r: decode_blob(r, sha))
for check in bad:
    try:
        check()
    except ValueError:
        continue
    raise AssertionError('Malformed API transfer accepted')
print(f'{len(bad)+3} synthetic transfer identity/encoding/size/content controls passed')
