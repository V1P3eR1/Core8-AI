import unittest
from patch_gate import PatchRejected, validate_patch


def patch_for(path='apps/demo/index.html', extra=''):
    return (f'diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-old\n+new\n{extra}').encode()


class PatchGateTests(unittest.TestCase):
    def test_accept_scoped_text(self):
        self.assertEqual(validate_patch(patch_for()).paths, ('apps/demo/index.html',))

    def test_accept_new_file(self):
        p = b'diff --git a/docs/demo.md b/docs/demo.md\nnew file mode 100644\n--- /dev/null\n+++ b/docs/demo.md\n@@ -0,0 +1 @@\n+hello\n'
        self.assertEqual(validate_patch(p).file_count, 1)

    def test_reject_outside_root(self):
        with self.assertRaises(PatchRejected): validate_patch(patch_for('.github/workflows/evil.yml'))

    def test_reject_parent(self):
        with self.assertRaises(PatchRejected): validate_patch(patch_for('apps/../.github/workflows/a.yml'))

    def test_reject_env(self):
        with self.assertRaises(PatchRejected): validate_patch(patch_for('apps/demo/.env.production'))

    def test_reject_executable_mode(self):
        with self.assertRaises(PatchRejected): validate_patch(patch_for().replace(b'100644', b'100755'))

    def test_reject_symlink(self):
        with self.assertRaises(PatchRejected): validate_patch(patch_for().replace(b'100644', b'120000'))

    def test_reject_binary(self):
        with self.assertRaises(PatchRejected): validate_patch(patch_for(extra='GIT binary patch\n'))

    def test_reject_rename(self):
        with self.assertRaises(PatchRejected): validate_patch(b'diff --git a/docs/a.md b/docs/b.md\n')

    def test_reject_mismatched_path(self):
        with self.assertRaises(PatchRejected): validate_patch(patch_for().replace(b'+++ b/apps/demo/index.html', b'+++ b/docs/secret.md'))

    def test_reject_duplicate(self):
        with self.assertRaises(PatchRejected): validate_patch(patch_for() + patch_for())

    def test_reject_oversize(self):
        with self.assertRaises(PatchRejected): validate_patch(b'x' * 300001)

    def test_reject_empty(self):
        with self.assertRaises(PatchRejected): validate_patch(b'')


if __name__ == '__main__':
    unittest.main()
