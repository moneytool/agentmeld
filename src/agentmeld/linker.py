"""Deciding and performing the on-disk write.

Two invariants govern everything here:

1. **We never clobber a file we did not create.** A generated file carries our
   header; a linked file is a symlink or a byte-identical copy recorded in state.
   Anything else is somebody's work, reported as a conflict.
2. **Writes are atomic.** Temp file, then ``os.replace``, so an interrupted sync
   cannot leave a half-written instruction file that an agent then reads.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from .model import Action, Mirror, Strategy
from .state import Entry, State
from .transform import HEADER_TOKEN, parse_header

__all__ = [
    "probe_symlink_support",
    "resolve_mode",
    "classify",
    "apply_mirror",
    "atomic_write_bytes",
]


def probe_symlink_support(directory: Path) -> bool:
    """Can we actually create a symlink here?

    Windows needs Developer Mode or admin, and some filesystems refuse outright,
    so this attempts the real operation rather than guessing from ``os.name``.

    The probe runs inside a temporary directory that is always removed -- checking
    a capability must not leave anything behind in someone's repo.
    """
    parent = directory if directory.exists() else directory.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(parent), prefix=".agm-probe-") as tmp:
            probe = Path(tmp) / "probe.link"
            target = Path(tmp) / "probe.txt"
            target.write_bytes(b"x")
            os.symlink(str(target), str(probe))
            return probe.is_symlink()
    except (OSError, NotImplementedError, AttributeError):
        return False


def resolve_mode(mode: str, root: Path) -> str:
    """Turn the configured mode into the concrete one: ``link`` or ``copy``."""
    if mode == "copy":
        return "copy"
    if mode == "link":
        return "link"
    return "link" if probe_symlink_support(root) else "copy"


def git_symlinks_enabled(root: Path) -> Optional[bool]:
    """Read ``core.symlinks``; ``None`` when git is unavailable or unset."""
    config = root / ".git" / "config"
    if not config.is_file():
        return None
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.strip().replace(" ", "")
        if stripped.startswith("symlinks="):
            return stripped.split("=", 1)[1].lower() in ("true", "1", "yes")
    return None


def _default_file_mode() -> int:
    """0644 minus the process umask.

    ``mkstemp`` deliberately creates 0600 files. That is right for a temp file and
    wrong for the finished mirror: an instruction file has to be readable by
    whoever else works in the repo, and a 0600 file committed from one machine
    reads as a permission change in every diff.
    """
    umask = os.umask(0)
    os.umask(umask)
    return 0o644 & ~umask


def normalise_mode(path: Path) -> bool:
    """Give an existing mirror the default mode. True when it had to change.

    Files written by older versions are 0600 and stay that way: their content
    already matches, so sync classifies them as unchanged and never rewrites them.
    Fixing only newly written files would leave every existing repo broken.
    """
    if path.is_symlink() or not path.is_file():
        return False
    wanted = _default_file_mode()
    try:
        current = path.stat().st_mode & 0o777
        if current == wanted:
            return False
        os.chmod(str(path), wanted)
    except OSError:
        return False
    return True


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".agm-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        try:
            os.chmod(tmp_name, _default_file_mode())
        except OSError:
            pass  # exotic filesystem; the content matters more than the mode
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_symlink(link: Path, source: Path) -> None:
    """Create ``link`` pointing at ``source`` by a relative path.

    Relative targets are what let the repo be cloned, moved, or mounted at a
    different path and still work.
    """
    link.parent.mkdir(parents=True, exist_ok=True)
    relative = os.path.relpath(str(source), start=str(link.parent))
    tmp = link.parent / (".agm-" + link.name + ".tmp")
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(relative, str(tmp))
    os.replace(str(tmp), str(link))


def _points_at(link: Path, source: Path) -> bool:
    try:
        return link.resolve() == source.resolve()
    except OSError:
        return False


def has_canonical_symlink_parent(target: Path, canonical: Optional[Path]) -> bool:
    """True when a symlinked ancestor would route a write into the canonical tree."""
    if canonical is None:
        return False
    for parent in target.parents:
        if not parent.is_symlink():
            continue
        try:
            destination = parent.resolve()
        except OSError:
            continue
        if destination == canonical or canonical in destination.parents:
            return True
    return False


def classify(
    mirror: Mirror,
    entry: Optional[Entry],
    mode: str,
    canonical: Optional[Path] = None,
) -> Action:
    """Decide what would happen to ``mirror.target`` without writing anything."""
    target = mirror.target
    exists = target.is_symlink() or target.exists()

    if mode == "copy" and has_canonical_symlink_parent(target, canonical):
        # Reading through the stale link returns the canonical bytes, which match
        # the payload -- so a byte comparison would wrongly say "unchanged" and
        # leave a symlink behind in a mode that promises real files.
        mirror.reason = "materialising through a stale directory symlink"
        return Action.UPDATE

    if mirror.strategy is Strategy.MERGE:
        # Merged output is computed *from* the existing file, so equality means
        # there is nothing to do; there is no conflict case.
        if not exists:
            return Action.CREATE
        try:
            return (
                Action.UNCHANGED if target.read_bytes() == mirror.payload else Action.UPDATE
            )
        except OSError:
            return Action.UPDATE

    if mirror.strategy is Strategy.LINK and mode == "link":
        if target.is_symlink():
            return Action.UNCHANGED if _points_at(target, mirror.source) else Action.UPDATE
        if not exists:
            return Action.CREATE
        if mirror.dir_link and target.is_dir():
            # A real directory of somebody's files cannot become a symlink without
            # destroying them. Adoption is the intended route out of this.
            if entry is None:
                mirror.reason = (
                    "a real directory exists here; run 'agentmeld adopt {}' to take it "
                    "over".format(target.name)
                )
                return Action.CONFLICT
            return Action.UPDATE
        # A real file sits where a symlink belongs. Only replace it if we are the
        # ones who put it there (a previous copy-mode run).
        if entry is not None:
            return Action.UPDATE
        mirror.reason = "a real file already exists here and agentmeld did not create it"
        return Action.CONFLICT

    # generate / aggregate, or link degraded to copy
    if not exists:
        return Action.CREATE

    if target.is_symlink():
        # A generated file has to be a real file. This is the link -> aggregate
        # transition: a repo whose instructions were a plain symlink gains its
        # first rule, and the mirror must now carry folded-in content. Reading
        # through the link would show canonical bytes with no header of ours and
        # look, wrongly, like somebody's hand-written file.
        if entry is not None or mode == "copy":
            mirror.reason = "replacing a symlink with a generated file"
            return Action.UPDATE
        mirror.reason = "an unmanaged symlink is in the way"
        return Action.CONFLICT

    try:
        current = target.read_bytes()
    except OSError:
        return Action.UPDATE
    if current == mirror.payload:
        return Action.UNCHANGED

    from .transform import source_hash

    if mirror.strategy is Strategy.IMPORT:
        # A bare import is one line, too short to carry a header, so ownership comes
        # from state -- but *recorded as ours* is not the same as *unmodified*.
        # Comparing against what we last wrote is what distinguishes a stale mirror
        # from somebody's edit, and skipping that check would silently discard it.
        if entry is not None and entry.output_hash:
            if source_hash(current) == entry.output_hash:
                return Action.UPDATE
        elif entry is not None:
            return Action.UPDATE
        mirror.reason = (
            "this file differs from both the import we would write and the one we "
            "last wrote -- edit the source, or delete this to let agentmeld own it"
        )
        return Action.CONFLICT

    if mirror.strategy is Strategy.LINK:
        # copy-mode link: trust state, since a copy carries no header of its own
        if entry is not None:
            return Action.UPDATE
        mirror.reason = "a real file already exists here and agentmeld did not create it"
        return Action.CONFLICT

    if entry is not None and entry.output_hash and source_hash(current) == entry.output_hash:
        # Byte-for-byte what we last wrote, so the canonical source moved on and
        # this is simply stale. Safe to rewrite.
        return Action.UPDATE

    text = current.decode("utf-8", errors="replace")
    if HEADER_TOKEN in text or parse_header(text):
        # Carries our header, which says edits here do not persist. Rewriting is
        # the documented contract -- and it keeps a header-format change from
        # turning every mirror in a repo into a conflict.
        return Action.UPDATE

    # Recorded as ours or not, this content is neither ours nor headered: somebody
    # wrote it by hand. Losing that would be worse than stopping.
    mirror.reason = (
        "hand-written file without a {} header -- refusing to overwrite".format(HEADER_TOKEN)
    )
    return Action.CONFLICT


def ensure_real_parents(target: Path, canonical: Path) -> None:
    """Replace any ancestor symlink that points into the canonical tree.

    Switching from link mode to copy mode leaves directory symlinks behind; a
    write beneath one would follow it straight into the source of truth.
    """
    parts = list(target.parents)
    for parent in reversed(parts):
        if not parent.is_symlink():
            continue
        try:
            destination = parent.resolve()
        except OSError:
            continue
        if destination == canonical or canonical in destination.parents:
            parent.unlink()
            parent.mkdir(parents=True, exist_ok=True)


def apply_mirror(mirror: Mirror, mode: str, canonical: Optional[Path] = None) -> None:
    """Perform the write decided by :func:`classify`."""
    if mirror.action in (Action.UNCHANGED, Action.SKIP, Action.CONFLICT):
        return

    target = mirror.target
    if canonical is not None and mode == "copy":
        ensure_real_parents(target, canonical)
    if mirror.strategy is Strategy.LINK and mode == "link":
        if target.is_symlink():
            target.unlink()
        elif target.is_dir():
            import shutil

            shutil.rmtree(str(target))  # only reached for a directory we recorded
        elif target.exists():
            target.unlink()
        _write_symlink(target, mirror.source)
        return

    payload = mirror.payload
    if payload is None:
        payload = mirror.source.read_bytes()
    if target.is_symlink():
        target.unlink()  # replacing a link with a real file
    atomic_write_bytes(target, payload)


def state_entry_for(mirror: Mirror, payload: Optional[bytes], source_hash: str) -> Entry:
    from .transform import source_hash as _hash

    return Entry(
        adapter=mirror.adapter_id,
        kind=str(mirror.kind),
        slug=mirror.slug,
        source="",  # filled in by the planner, which knows the repo root
        strategy=str(mirror.strategy),
        output_hash=_hash(payload) if payload is not None else "",
        source_hash=source_hash,
    )
