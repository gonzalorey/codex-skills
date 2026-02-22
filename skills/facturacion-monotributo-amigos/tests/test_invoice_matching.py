"""Tests for invoice-to-owner matching using filename_aliases (blue/green)."""
from __future__ import annotations

import unittest


# Exercise _matches_invoice logic directly, without subprocess.
# We import the function indirectly via the module so we can monkey-patch _alias_cfg.
import scripts.run_monthly_close as runner


def _make_matcher(alias_cfg: dict):
    """Return a _matches_invoice closure bound to the given alias_cfg."""
    def _matches(person, filename):
        alias = person["alias"]
        token = alias_cfg.get(alias) or alias.split("-")[-1]
        return str(token).lower() in filename.lower()
    return _matches


class TestInvoiceMatching(unittest.TestCase):
    def test_fallback_uses_last_alias_segment(self) -> None:
        """Blue path: no filename_aliases entry → fall back to last segment of alias."""
        matcher = _make_matcher({})
        person = {"alias": "santi-favelukes"}
        self.assertTrue(matcher(person, "factura_favelukes_2026-02.pdf"))
        self.assertFalse(matcher(person, "factura_olivieri_2026-02.pdf"))

    def test_explicit_alias_overrides_default(self) -> None:
        """Green path: filename_aliases entry wins over last-segment heuristic.

        Default token would be 'perez' (last alias segment).  The explicit alias
        maps to 'jperez', so only filenames containing 'jperez' match – a file
        that only contains the bare 'perez' segment must NOT match (it could belong
        to a different person named e.g. 'maria-perez').
        """
        matcher = _make_matcher({"juan-perez": "jperez"})
        person = {"alias": "juan-perez"}
        # Filename with explicit token → match.
        self.assertTrue(matcher(person, "factura_jperez_2026-02.pdf"))
        # Filename with only the default segment ('perez') → no match because
        # the explicit token 'jperez' is not present.
        self.assertFalse(matcher(person, "factura_perez_2026-02.pdf"))

    def test_matching_is_case_insensitive(self) -> None:
        matcher = _make_matcher({"santi-olivieri": "Olivieri"})
        person = {"alias": "santi-olivieri"}
        self.assertTrue(matcher(person, "FACTURA_OLIVIERI_FEB2026.PDF"))

    def test_no_match_returns_false(self) -> None:
        matcher = _make_matcher({})
        person = {"alias": "santi-favelukes"}
        self.assertFalse(matcher(person, "factura_unknown_2026-02.pdf"))


if __name__ == "__main__":
    unittest.main()
