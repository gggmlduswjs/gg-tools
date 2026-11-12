import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
import os
import shutil
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageTests(unittest.TestCase):
    def test_same_published_skills_and_review(self):
        original = json.loads((ROOT / 'gg-skills/.claude-plugin/plugin.json').read_text(encoding='utf-8'))
        codex = json.loads((ROOT / 'gg-skills/.codex-plugin/plugin.json').read_text(encoding='utf-8'))
        self.assertEqual(codex['skills'], original['skills'] + ['./codex-skills/project-review'])
        for relative in codex['skills']:
            self.assertTrue((ROOT / 'gg-skills' / relative / 'SKILL.md').is_file())
        catalog = json.loads((ROOT / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
        self.assertEqual(catalog['plugins'][0]['source']['path'], './gg-skills')

    @unittest.skipUnless(shutil.which('pwsh'), 'PowerShell unavailable')
    def test_installer_accepts_explicit_codex_executable_in_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'desktop codex.exe'
            executable.write_text('not executed in DryRun')
            result = subprocess.run(['pwsh', '-NoProfile', '-File', str(ROOT / 'bootstrap-codex.ps1'),
                                     '-DryRun', '-CodexExecutable', str(executable)],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(executable), result.stdout)

    @unittest.skipUnless(shutil.which('pwsh'), 'PowerShell unavailable')
    def test_installer_prefers_desktop_bundle_over_path(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'OpenAI/Codex/bin/build/codex.exe'
            executable.parent.mkdir(parents=True)
            executable.write_text('not executed in DryRun')
            result = subprocess.run(['pwsh', '-NoProfile', '-File', str(ROOT / 'bootstrap-codex.ps1'), '-DryRun'],
                                    env=dict(os.environ, LOCALAPPDATA=directory),
                                    capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(executable), result.stdout)


class HookTests(unittest.TestCase):
    def setUp(self):
        self.hook = load('gg-skills/hooks/codex_adapter.py', 'codex_adapter')

    def test_common_deny_and_ask_fail_closed(self):
        for command in ('git add -A', 'git push --force', 'git reset --hard'):
            result = self.hook.decide_event({'tool_name': 'Bash', 'tool_input': {'command': command}})
            self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIsNone(self.hook.decide_event({'tool_name': 'Bash', 'tool_input': {'command': 'git status --short'}}))

    def test_public_django_ci_value_does_not_block_commands(self):
        for command in (
            'DJANGO_SECRET_KEY=ci-only-not-a-real-secret python manage.py test',
            "$env:DJANGO_SECRET_KEY='ci-only-not-a-real-secret'; python manage.py test",
            '$env:DJANGO_SECRET_KEY="ci-only-not-a-real-secret"; python manage.py test',
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.hook.decide_event(
                    {'tool_name': 'exec_command', 'tool_input': {'cmd': command}}))

    def test_public_ci_exception_does_not_hide_other_secrets_or_risks(self):
        for command in (
            'OTHER_SECRET_KEY=ci-only-not-a-real-secret python x.py',
            'DJANGO_SECRET_KEY=ci-only-not-a-real-secret-extra python x.py',
            "DJANGO_SECRET_KEY='ci-only-not-a-real-secret!' python x.py",
            "DJANGO_SECRET_KEY='ci-only-not-a-real-secret'actual python x.py",
            'export "DJANGO_SECRET_KEY=ci-only-not-a-real-secret;actual-private-suffix"',
            'export "DJANGO_SECRET_KEY=ci-only-not-a-real-secret actual-private-suffix"',
            "export 'DJANGO_SECRET_KEY=ci-only-not-a-real-secret;actual-private-suffix'",
            'DJANGO_SECRET_KEY=ci-only-not-a-real-secret OTHER_TOKEN=' + 'D' * 20 + ' python x.py',
            'DJANGO_SECRET_KEY=' + 'D' * 20 + ' python x.py',
            'DJANGO_SECRET_KEY=ci-only-not-a-real-secret git push --force',
            'DJANGO_SECRET_KEY=ci-only-not-a-real-secret git reset --hard',
            'DJANGO_SECRET_KEY=ci-only-not-a-real-secret psql -c "DROP TABLE orders"',
        ):
            with self.subTest(command=command):
                result = self.hook.decide_event(
                    {'tool_name': 'exec_command', 'tool_input': {'cmd': command}})
                self.assertIsNotNone(result)
                self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_patch_only_new_text_and_each_file(self):
        token = 'ghp_' + 'a' * 36
        patch = '*** Begin Patch\n*** Update File: README.md\n-' + token + '\n+removed\n*** Add File: src/config.py\n+TOKEN="' + token + '"\n*** End Patch'
        result = self.hook.decide_event({'tool_name': 'apply_patch', 'tool_input': {'command': patch}})
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertNotIn(token, json.dumps(result))
        removal = '*** Begin Patch\n*** Update File: config.py\n-' + token + '\n+use_env()\n*** End Patch'
        self.assertIsNone(self.hook.decide_event({'tool_name': 'apply_patch', 'tool_input': {'command': removal}}))

    def test_unknown_tool_ignored_malformed_known_tool_denied(self):
        self.assertIsNone(self.hook.decide_event({'tool_name': 'mcp__fs__read', 'tool_input': {}}))
        result = self.hook.decide_event({'tool_name': 'Bash', 'tool_input': {}})
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_optional_tdd_checks_new_destination_and_uses_deny(self):
        with tempfile.TemporaryDirectory() as directory:
            event = {'cwd': directory, 'tool_name': 'apply_patch', 'tool_input': {'command':
                     '*** Begin Patch\n*** Update File: src/old.py\n*** Move to: src/service.py\n+def service(): pass\n*** End Patch'}}
            self.assertIsNone(self.hook.decide_event(event))
            result = self.hook.decide_event(event, tdd=True)
            self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')
            (Path(directory) / 'test_service.py').write_text('test')
            self.assertIsNone(self.hook.decide_event(event, tdd=True))

    def test_current_openai_keys_and_removal_do_not_leak(self):
        for prefix in ('sk-proj-', 'sk-svcacct-', 'sk-'):
            token = prefix + 'aA_-' * 25
            if prefix == 'sk-':
                token = prefix + 'aA' * 25
            patch_text = '*** Begin Patch\n*** Add File: config.py\n+KEY="' + token + '"\n*** End Patch'
            result = self.hook.decide_event({'tool_name': 'apply_patch', 'tool_input': {'command': patch_text}})
            self.assertIsNotNone(result, prefix)
            self.assertNotIn(token, json.dumps(result))
            removal = '*** Begin Patch\n*** Update File: config.py\n-' + token + '\n+use_env()\n*** End Patch'
            self.assertIsNone(self.hook.decide_event({'tool_name': 'apply_patch', 'tool_input': {'command': removal}}))

    def test_explicit_tdd_disable_remains_effective(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'TDD_GUARD_DISABLE': '1'}):
            event = {'cwd': directory, 'tool_name': 'apply_patch', 'tool_input': {'command':
                     '*** Begin Patch\n*** Add File: src/service.py\n+def service(): pass\n*** End Patch'}}
            self.assertIsNone(self.hook.decide_event(event, tdd=True))


class OnboardTests(unittest.TestCase):
    def setUp(self):
        self.onboard = load('gg-skills/skills/engineering/onboard/scripts/check_setup.py', 'onboard')

    def test_codex_pc_does_not_require_claude_or_external_plugins(self):
        calls = []
        def fake_run(command, **kwargs):
            calls.append(command)
            if command[:3] == ['codex', 'plugin', 'list']:
                return 0, json.dumps({'installed': [{'pluginId': 'gg-skills@gg-tools', 'enabled': True}]})
            return 0, 'ok'
        with patch.object(self.onboard, 'run', fake_run):
            rows = self.onboard.check_pc(runtime='codex')
        self.assertIn(['codex', '--version'], calls)
        self.assertFalse(any('claude' in command for command in calls))
        self.assertTrue(any(row[1] == 'gg-skills@gg-tools' and row[2] == self.onboard.OK for row in rows))

    def test_codex_project_accepts_worktree_without_claude_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / '.git').write_text('gitdir: example')
            (p / 'AGENTS.md').write_text('rules')
            (p / 'CLAUDE.md').write_text('rules')
            (p / 'docs').mkdir()
            (p / 'docs/PRD.md').write_text('spec')
            self.assertEqual(self.onboard.check_project(directory, runtime='codex')[0][2], self.onboard.OK)


if __name__ == '__main__':
    unittest.main()
