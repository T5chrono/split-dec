"""Both Python locks pin artifacts, not just version numbers.

A version pin says "fastapi 0.141.1"; a hash says *which file* that is. The
first is only as good as the index serving it, and the threat this closes is a
compromised or substituted mirror, on top of TLS.

Why a test rather than trusting the `locks` CI job: that job recompiles and
diffs, so it does notice a lock regenerated without `--generate-hashes` — but
it is deliberately **not** a required status check, while this file runs inside
`backend`, which is. And the failure mode is silent in the worst way: hashes
are all-or-nothing, so losing them does not break an install, it just quietly
stops checking anything.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCKS = ("requirements.txt", "requirements-dev.txt")

# A requirement line opens with `name==version`, optionally followed by an
# environment marker. Hashes hang off it on continuation lines.
_PIN = re.compile(r"^[A-Za-z0-9_.-]+==")


def _requirements(name: str) -> list[tuple[str, list[str]]]:
    """Each pinned requirement in a lock, with the hashes attached to it."""
    found: list[tuple[str, list[str]]] = []
    for raw in (ROOT / name).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if _PIN.match(line):
            found.append((line.split(" ")[0].rstrip("\\").strip(), []))
        elif line.startswith("--hash=") and found:
            found[-1][1].append(line.removeprefix("--hash=").rstrip("\\").strip())
    return found


def test_every_pinned_package_carries_a_hash():
    for name in LOCKS:
        requirements = _requirements(name)
        assert requirements, f"{name}: no pinned requirements found — parser is wrong"
        unhashed = [pin for pin, hashes in requirements if not hashes]
        assert not unhashed, (
            f"{name}: regenerated without --generate-hashes? Unhashed: {unhashed}"
        )


def test_every_hash_is_a_sha256():
    """Shape, not strength: `--hash=md5:...` is accepted by pip and is not a
    supply-chain control. uv only emits sha256, so anything else here was
    typed by a person."""
    for name in LOCKS:
        for pin, hashes in _requirements(name):
            for digest in hashes:
                algorithm, _, value = digest.partition(":")
                assert algorithm == "sha256", f"{name}: {pin} uses {algorithm}"
                assert re.fullmatch(r"[0-9a-f]{64}", value), f"{name}: {pin} -> {value}"


def test_the_documented_regeneration_command_matches_the_header():
    """requirements.in tells a human how to regenerate; uv records what was
    actually run. A drift between the two is how the flag gets lost — the
    person follows the instructions and produces a different file."""
    documented = (ROOT / "requirements.in").read_text(encoding="utf-8")
    for name in LOCKS:
        header = (ROOT / name).read_text(encoding="utf-8").splitlines()[1]
        command = header.lstrip("# ").strip()
        assert "--generate-hashes" in command, f"{name} header: {command}"
        assert command in documented, (
            f"{name} was generated with a command requirements.in does not document:"
            f"\n  lock: {command}"
        )
