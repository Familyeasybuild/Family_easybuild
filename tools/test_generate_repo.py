import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GenerateRepoTest(unittest.TestCase):
    def setUp(self):
        self.output_path = ROOT / "_test_zips"
        self.repo_addon = ROOT / "repository.familyeasybuild.repo"
        self.backup_dir = Path(tempfile.mkdtemp())
        self.repo_addon_backup = self.backup_dir / self.repo_addon.name
        if self.output_path.exists():
            shutil.rmtree(self.output_path)
        if self.repo_addon.exists():
            shutil.move(str(self.repo_addon), str(self.repo_addon_backup))

    def tearDown(self):
        if self.output_path.exists():
            shutil.rmtree(self.output_path)
        if self.repo_addon.exists():
            shutil.rmtree(self.repo_addon)
        if self.repo_addon_backup.exists():
            shutil.move(str(self.repo_addon_backup), str(self.repo_addon))
        shutil.rmtree(self.backup_dir)

    def run_generator(self):
        env = os.environ.copy()
        env.update(
            {
                "KODI_REPO_ID": "repository.familyeasybuild.repo",
                "KODI_REPO_NAME": "Family easybuild repo",
                "KODI_REPO_VERSION": "1.0.999",
                "KODI_REPO_AUTHOR": "simon",
                "KODI_REPO_OUTPUT_PATH": "_test_zips/",
                "KODI_REPO_URL": "https://Familyeasybuild.github.io/Family_easybuild_repo/",
            }
        )
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / "generate_repo.py")],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_copies_asset_paths_referenced_by_addons_xml(self):
        self.run_generator()

        addon_output = self.output_path / "plugin.program.easybuild"
        self.assertTrue((addon_output / "resources" / "icon.png").is_file())
        self.assertTrue((addon_output / "resources" / "fanart.jpg").is_file())
        self.assertTrue((addon_output / "resources" / "screenshot-01.jpg").is_file())

    def test_repository_addon_zip_contains_icon_and_fanart(self):
        self.run_generator()

        repo_zip = (
            self.output_path
            / "repository.familyeasybuild.repo"
            / "repository.familyeasybuild.repo-1.0.999.zip"
        )
        self.assertTrue(repo_zip.is_file())
        with zipfile.ZipFile(repo_zip) as zf:
            names = set(zf.namelist())

        self.assertIn("repository.familyeasybuild.repo/icon.png", names)
        self.assertIn("repository.familyeasybuild.repo/fanart.jpg", names)

    def test_addons_md5_matches_addons_xml(self):
        self.run_generator()

        addons_xml = self.output_path / "addons.xml"
        expected = (self.output_path / "addons.xml.md5").read_text().strip()
        actual = hashlib.md5(addons_xml.read_bytes()).hexdigest()
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
