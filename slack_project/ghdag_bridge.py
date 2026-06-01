from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ghdag.pipeline.audit import AuditContext
from ghdag.pipeline.state import PipelineState
from ghdag.workflow.engine import get_adapter

_TZ = ZoneInfo("Asia/Tokyo")

_claude_adapter = get_adapter("claude")


def submit_order(
    order_content: str,
    *,
    model: str = "claude-sonnet-4-6",
    queue_dir: Path,
) -> str:
    """order ファイルを書き出し exec.jsonl に追記する。

    order_content: order ファイルの内容
    model: Claude モデル名
    queue_dir: jobs ディレクトリ（必須）
    Returns: 結果ファイル名 "{ts}-claude-result-{uuid}.md"
    """
    exec_jsonl = queue_dir / "exec.jsonl"
    state_dir = queue_dir.parent / ".pipeline-state"

    ts = datetime.now(_TZ).strftime("%Y%m%d%H%M%S")
    order_uuid = str(uuid.uuid4())
    result_filename = f"{ts}-claude-result-{order_uuid}.md"
    order_filename = f"{ts}-claude-order-{order_uuid}.md"

    record = _claude_adapter.build_exec_record(
        uuid=order_uuid,
        order_path=f"jobs/{order_filename}",
        result_path=f"jobs/{result_filename}",
        prompt="受け取った内容を実行して",
        model=model,
        depends=[],
    )

    queue_dir.mkdir(parents=True, exist_ok=True)
    state = PipelineState(str(state_dir), str(exec_jsonl))
    state.write_order_file(
        ts=ts,
        order_uuid=order_uuid,
        content=order_content,
        queue_dir=str(queue_dir),
    )
    audit_ctx = AuditContext(source="ghdag-bridge", correlation_id=order_uuid)
    state.append_exec_records([record], audit_context=audit_ctx)

    return result_filename
