from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.package_contract import verify_entries


class PackageContractLineEndingTests(unittest.TestCase):
    def test_crlf_only_hash_mismatch_gets_diagnostic_without_passing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "scripts" / "verify_install.py"
            path.parent.mkdir()
            lf_bytes = b"print('ok')\nprint('still ok')\n"
            crlf_bytes = lf_bytes.replace(b"\n", b"\r\n")
            path.write_bytes(crlf_bytes)
            expected = hashlib.sha256(lf_bytes).hexdigest()

            missing, mismatches = verify_entries(root, [{"path": "scripts/verify_install.py", "sha256": expected}])

        self.assertEqual([], missing)
        self.assertEqual(1, len(mismatches))
        self.assertEqual("CRLF_LINE_ENDING_CONVERSION", mismatches[0]["probable_cause"])
        self.assertTrue(mismatches[0]["normalized_lf_matches"])


if __name__ == "__main__":
    unittest.main()
