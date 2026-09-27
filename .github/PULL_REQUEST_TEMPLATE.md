## Summary

<!-- What changed and why. One or two paragraphs; the diff shows the how. -->

**Issue:** <!-- the issue this closes, or "none" -->

## Checklist

<!-- Strike out what does not apply and say why. -->

- [ ] `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` pass
- [ ] `cd ui && npm run check && npm run build` pass
- [ ] `uv run python scripts/check_no_cyrillic.py` passes
- [ ] The app starts (`uv run python app.py`), and the changed feature was tried by hand for
      anything touching runtime
- [ ] `CHANGELOG.md` entry added if a user would notice
- [ ] Documentation this change makes wrong is updated (`README.md`, `README.ru.md`, `CONTRIBUTING.md`)
- [ ] No existing `backend` / `steps` slot or signal signature changed, and no route, map or
      object-set file format changed
- [ ] Commits follow Conventional Commits; the branch is ready to squash-merge
