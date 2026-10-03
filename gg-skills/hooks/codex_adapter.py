#!/usr/bin/env python3
"""Codex hook wire format → 기존 공용 엔진. ask 미지원이므로 deny로 변환한다."""
import importlib.util
import json
import os
from pathlib import Path
import sys


def engine(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guardrail = engine('guardrail')
secret_guard = engine('secret_guard')


def deny(reason):
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny', 'permissionDecisionReason': reason}}


def patch_additions(patch):
    """추가/수정 줄만 검사한다. 삭제·문맥 줄은 secret 재노출로 보지 않는다."""
    path, lines = None, []
    for line in patch.splitlines():
        if line.startswith(('*** Add File: ', '*** Update File: ', '*** Delete File: ')):
            if path is not None:
                yield path, '\n'.join(lines)
            path, lines = line.split(': ', 1)[1], []
        elif line.startswith('*** Move to: '):
            path = line.split(': ', 1)[1]
        elif path is not None and line.startswith('+'):
            lines.append(line[1:])
    if path is not None:
        yield path, '\n'.join(lines)


def decide_event(event, tdd=False):
    tool = event.get('tool_name')
    if tool not in ('Bash', 'exec_command', 'apply_patch', 'Edit', 'Write', 'MultiEdit'):
        return None
    ti = event.get('tool_input')
    if not isinstance(ti, dict):
        return deny('[GG] 도구 입력을 검사할 수 없습니다.')
    if tool in ('Bash', 'exec_command'):
        command = ti.get('command', ti.get('cmd'))
        if not isinstance(command, str):
            return deny('[GG] 명령 입력을 검사할 수 없습니다.')
        decision, reason = guardrail.decide(command, guardrail.deny_common() + guardrail.ask_common())
        if decision:
            return deny('[GG] ' + reason + (' (Codex ask 미지원: 차단)' if decision == 'ask' else ''))
        return None
    if tool == 'apply_patch':
        patch = ti.get('command')
        if not isinstance(patch, str):
            return deny('[GG] patch 입력을 검사할 수 없습니다.')
        changes = patch_additions(patch)
    else:
        changes = [(ti.get('file_path', ''), secret_guard.texts_of(ti))]
    for path, text in changes:
        label = secret_guard.find_secret(path, text)
        if label:
            return deny('[GG] ' + label + ' 형식을 감지했습니다. 환경변수로 옮기세요. 값은 출력하지 않습니다.')
        if tdd and text and not os.environ.get('TDD_GUARD_DISABLE'):
            result = engine('tdd_guard').decide(path, event.get('cwd') or str(Path.cwd()), 'deny')
            if result:
                return {'hookSpecificOutput': result}
    return None


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        event = json.loads(sys.stdin.read())
        if not isinstance(event, dict):
            raise ValueError('invalid event')
        if '--stale-worktrees' in sys.argv:
            lines = engine('stale_worktrees').report(event.get('cwd') or str(Path.cwd()))
            output = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': '\n'.join(lines)}} if lines else None
        else:
            output = decide_event(event, tdd='--tdd' in sys.argv)
    except (ValueError, TypeError):
        output = deny('[GG] hook 입력을 해석할 수 없습니다.')
    if output:
        print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
