# TASK-009: PyPI Publication

**Status**: todo
**Priority**: medium

## Description
Publish pywinhello to PyPI. Name availability confirmed 2026-03-07.

## Acceptance Criteria
- [ ] LICENSE file (MIT)
- [ ] Version bump strategy decided
- [ ] `uv build` produces clean sdist + wheel
- [ ] `uv run twine upload dist/* -u __token__ -p $PYPI_TOKEN`
- [ ] `pip install pywinhello` works from PyPI
- [ ] GitHub repo created at obichan117/pywinhello
