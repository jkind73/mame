#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Retrieve an exported CI ZIP through GitHub's authenticated Git-blob API.

The export workflow must already have populated its unpublished draft release.
The temporary blob is only a transport: the existing unpacker independently
checks the original Actions ZIP digest/size and local source/binary provenance.
No binary execution, new Git ref, sandbox listener, or credential persistence.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from verify_ci_artifact import BRANCH, REPO, ROOT, require


def source_identity(run):
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'CI run did not succeed')
    require(run['headBranch'] == BRANCH, 'Wrong source branch')
    require(run['workflowName'] == 'Saturn integration artifact', 'Wrong workflow')
    require(re.fullmatch(r'[0-9a-f]{40}', run['headSha']), 'Malformed source identity')
    return run['headSha']


def transfer_identity(release, source):
    require(release['isDraft'] is True, 'Transfer storage must remain an unpublished draft')
    require(release['targetCommitish'] == source, 'Draft source mismatch')
    matches = re.findall(r'^Temporary API transfer blob: ([0-9a-f]{40})$', release['body'], re.M)
    require(len(matches) == 1, 'Missing or ambiguous API transfer blob; rerun the export workflow')
    return matches[0]


def decode_blob(record, expected):
    require(record['sha'] == expected and record['encoding'] == 'base64', 'Wrong Git blob identity/encoding')
    require(0 < record['size'] <= 64*1024*1024, 'Invalid transfer size')
    data = base64.b64decode(''.join(record['content'].split()), validate=True)
    require(len(data) == record['size'], 'Git blob size mismatch')
    identity = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    require(identity == expected, 'Git blob content mismatch')
    return data


def gh_json(*args):
    return json.loads(subprocess.check_output(['gh', *args], text=True))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id', type=int, required=True)
    p.add_argument('--destination', type=Path, required=True)
    a = p.parse_args()
    require(a.run_id > 0, 'Invalid run ID')
    destination = a.destination.resolve()
    require(destination != ROOT and ROOT not in destination.parents, 'Use an external destination')
    run = gh_json('run', 'view', str(a.run_id), '--repo', REPO, '--json',
                  'headSha,headBranch,workflowName,status,conclusion')
    source = source_identity(run)
    release = gh_json('release', 'view', 'arena-saturn-validation-'+source,
                      '--repo', REPO, '--json', 'isDraft,targetCommitish,body')
    blob = transfer_identity(release, source)
    record = gh_json('api', f'repos/{REPO}/git/blobs/{blob}')
    data = decode_blob(record, blob)
    with tempfile.TemporaryDirectory(prefix='saturn-ci-transfer-') as tmp:
        archive = Path(tmp)/'artifact.zip'
        archive.write_bytes(data)
        subprocess.run([sys.executable, str(Path(__file__).with_name('unpack_ci_artifact.py')),
                        str(archive), '--run-id', str(a.run_id),
                        '--destination', str(destination)], check=True)


if __name__ == '__main__':
    main()
