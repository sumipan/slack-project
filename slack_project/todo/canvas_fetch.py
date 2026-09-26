"""
slack_project.todo.canvas_fetch — Canvas 上のチェック状態を local todo.md に反映するユーティリティ

設計:
- Canvas の markdown は parser.parse_todo_tasks_all で扱える形式（`## <セクション>`配下の
  `### <サブセクション>` + `- [ ] / - [x]` チェックリスト）に揃っている前提。
- セクションキー（`section_key`）は無視し、normalized text（末尾メタデータ除去後）を
  キーとして check 状態を取り出す。同じタスク行が複数 section に出るケースは無い前提。
- 反映方針は **Canvas-優位 check-on-only**:
    `Canvas[x] かつ local[ ]` のときだけ local を `[x]` に上書き。
    `Canvas[ ] かつ local[x]` は触らない（local 優位）。
- ローカル全文を行単位で書き換え、いずれかの `##` セクション内の task 行だけ対象
  （最初の `##` 見出しより前の行は対象外）。
"""
from __future__ import annotations

from slack_project.todo.parser import (
    RE_TASK_LINE,
    normalize_task_text,
    parse_todo_tasks_all,
)


def parse_canvas_check_states(canvas_markdown: str) -> dict[str, bool]:
    """Canvas の markdown から ``{normalized_text: completed}`` を返す。

    parse_todo_tasks_all をそのまま流用する（全 `##` セクション対象）。section_key は無視。
    重複 normalized が現れた場合は **完了 (True) を勝たせる**（Canvas 上で 1 度でも
    チェックされていれば取り込む方向）。
    """
    states: dict[str, bool] = {}
    for _raw, completed, normalized, _assignee, _due, _section, _top in parse_todo_tasks_all(
        canvas_markdown
    ):
        if not normalized:
            continue
        if states.get(normalized) is True:
            continue  # 既に True なら据え置き
        states[normalized] = completed
    return states


def apply_check_states_to_local(
    todo_text: str, canvas_states: dict[str, bool]
) -> tuple[str, list[str]]:
    """local todo.md に canvas の check 状態を反映した text を返す。

    返り値:
        (new_text, changed_normalized_keys)

    挙動:
        - いずれかの `##` セクション内の task 行だけ対象（最初の `##` より前は対象外）。
        - 各行で ``canvas_states[normalized] is True`` かつ local が ``[ ]`` のときに ``[x]`` へ書き換え。
        - 逆方向（Canvas[ ], local[x]）は触らない。
        - canvas_states に出てこないタスクは触らない。
    """
    if not todo_text:
        return "", []

    new_lines: list[str] = []
    changed: list[str] = []
    in_section = False
    for line in todo_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = True
            new_lines.append(line)
            continue

        if in_section:
            m = RE_TASK_LINE.match(line)
            if m:
                prefix, check, body = m.group(1), m.group(2), m.group(3)
                if check == " ":
                    normalized = normalize_task_text(body)
                    if normalized and canvas_states.get(normalized) is True:
                        line = f"{prefix}[x] {body}"
                        changed.append(normalized)
        new_lines.append(line)

    return "\n".join(new_lines), changed


__all__ = ["parse_canvas_check_states", "apply_check_states_to_local"]
