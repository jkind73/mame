#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Synthetic provenance failure controls; never executes the fake payload."""
import hashlib
from pathlib import Path
import tempfile
from verify_ci_artifact import BRANCH, INPUTS, STATUS, check_artifact

with tempfile.TemporaryDirectory(prefix='saturn-ci-artifact-test-') as tmp:
    d = Path(tmp)
    modes = ('good', 'running', 'failed', 'branch', 'workflow', 'commit',
             'status', 'trees', 'hash', 'filename', 'missing', 'extra-tree')
    for mode in modes:
        run = dict(status='completed', conclusion='success', headBranch=BRANCH,
                   workflowName='Saturn integration artifact', headSha='a' * 40, url='https://example.invalid/test')
        trees = ['b' * 40] * len(INPUTS)
        (d / 'source-commit.txt').write_text('a' * 40 + '\n')
        (d / 'status.txt').write_text(STATUS + '\n')
        (d / 'input-trees.txt').write_text('\n'.join(trees) + '\n')
        (d / 'saturn').write_bytes(b'synthetic payload - never executed')
        digest = hashlib.sha256((d / 'saturn').read_bytes()).hexdigest()
        (d / 'binary.sha256').write_text(digest + '  saturn\n')
        if mode == 'running': run['status'] = 'in_progress'
        if mode == 'failed': run['conclusion'] = 'failure'
        if mode == 'branch': run['headBranch'] = 'other'
        if mode == 'workflow': run['workflowName'] = 'other'
        if mode == 'commit': run['headSha'] = 'c' * 40
        if mode == 'status': (d / 'status.txt').write_text('PASS')
        if mode == 'trees': trees[0] = 'c' * 40
        if mode == 'hash': (d / 'saturn').write_bytes(b'changed payload')
        if mode == 'filename': (d / 'binary.sha256').write_text(digest + '  ../saturn\n')
        if mode == 'missing': (d / 'saturn').unlink()
        if mode == 'extra-tree': (d / 'input-trees.txt').write_text(('b' * 40 + '\n') * 7)
        try:
            check_artifact(d, run, trees)
        except (ValueError, FileNotFoundError):
            assert mode != 'good', mode
        else:
            assert mode == 'good', mode
print('12 synthetic CI artifact provenance cases passed (not native execution)')
