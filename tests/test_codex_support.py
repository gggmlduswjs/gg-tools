import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
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


class HookTests(unittest.TestCase):
    def setUp(self):
        self.hook = load('gg-skills/hooks/codex_adapter.py', 'codex_adapter')

    def test_common_deny_and_ask_fail_closed(self):
        for command in ('git add -A', 'git push --force', 'git reset --hard'):
            result = self.hook.decide_event({'tool_name': 'Bash', 'tool_input': {'command': command}})
            self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIsNone(self.hook.decide_event({'tool_name': 'Bash', 'tool_input': {'command': 'git status --short'}}))

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
