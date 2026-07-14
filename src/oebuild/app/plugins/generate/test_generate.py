import pathlib
import tempfile
import unittest

from oebuild.app.plugins.generate.generate import Generate


class GenerateBuildPathTest(unittest.TestCase):
    def test_accepts_build_directory_inside_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            build_root = pathlib.Path(workspace, 'build')

            self.assertTrue(
                Generate._is_build_path(build_root / 'qemu-aarch64', build_root)
            )

    def test_rejects_build_directory_outside_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            build_root = pathlib.Path(workspace, 'build')

            self.assertFalse(
                Generate._is_build_path(
                    build_root / '..' / 'escape', build_root
                )
            )


if __name__ == '__main__':
    unittest.main()
