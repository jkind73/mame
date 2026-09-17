#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Check CI identity, immutable input trees and executable hash before local use.

This is provenance checking, not a signed software attestation or runtime test.
Downloads are explicit: gh run download RUN --repo jkind73/mame --name
saturn-linux-SHA --dir DIRECTORY. Failed/partial jobs must not be used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = 'jkind73/mame'
BRANCH = 'arena/01a09f50-mame'
INPUTS = ('src', 'regtests/saturn', '3rdparty', 'scripts', 'makefile', 'hash')
STATUS = ('PASS: native build, configuration validation and ROM-free regression batch. '
          'No BIOS, gameplay or live save/load acceptance.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_artifact(directory, run, local_trees):
    """Pure checks, also exercised with synthetic artifacts (not binary evidence)."""
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'CI run did not succeed')
    require(run['headBranch'] == BRANCH, 'Wrong source branch')
    require(run['workflowName'] == 'Saturn integration artifact', 'Wrong workflow')
    commit = (directory / 'source-commit.txt').read_text().strip()
    require(re.fullmatch(r'[0-9a-f]{40}', commit), 'Malformed source identity')
    require(commit == run['headSha'], 'Run/artifact source mismatch')
    require((directory / 'status.txt').read_text().strip() == STATUS, 'Missing CI success record')
    trees = (directory / 'input-trees.txt').read_text().splitlines()
    require(len(trees) == len(INPUTS) and all(re.fullmatch(r'[0-9a-f]{40}', s) for s in trees), 'Malformed input tree manifest')
    require(trees == local_trees, 'Local build/test input trees differ from the CI binary')
    match = re.fullmatch(r'([0-9a-f]{64})  saturn\n?', (directory / 'binary.sha256').read_text())
    require(match, 'Malformed binary manifest')
    binary = directory / 'saturn'
    require(binary.is_file() and binary.stat().st_size > 0, 'Missing executable')
    with binary.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    require(digest == match[1], 'Executable checksum mismatch')
    return {'source_commit': commit, 'binary_sha256': digest,
            'executable': str(binary.resolve()), 'run_url': run['url']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--run-id', required=True, type=int)
    a = p.parse_args()
    require(a.run_id > 0, 'Invalid run identifier')
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    require(branch == BRANCH, 'Use the assigned session branch')
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', *INPUTS], cwd=ROOT, check=True)
    trees = subprocess.check_output(['git', 'rev-parse', *('HEAD:' + s for s in INPUTS)], cwd=ROOT, text=True).splitlines()
    run = json.loads(subprocess.check_output(['gh', 'run', 'view', str(a.run_id), '--repo', REPO,
        '--json', 'headSha,headBranch,workflowName,status,conclusion,url'], text=True))
    print(json.dumps(check_artifact(a.directory.resolve(), run, trees), indent=2))


if __name__ == '__main__':
    main()
