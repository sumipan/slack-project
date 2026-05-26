import json
import re
from unittest.mock import MagicMock, patch


from slack_project.ghdag_bridge import submit_order


class TestSubmitOrder:
    def _make_mocks(self):
        mock_adapter = MagicMock()
        mock_adapter.build_exec_record.return_value = {"type": "exec", "model": "claude-sonnet-4-6"}
        mock_state = MagicMock()
        mock_state_cls = MagicMock(return_value=mock_state)
        mock_audit = MagicMock()
        mock_audit_cls = MagicMock(return_value=mock_audit)
        return mock_adapter, mock_state, mock_state_cls, mock_audit, mock_audit_cls

    def test_result_filename_format(self, tmp_path):
        mock_adapter, mock_state, mock_state_cls, mock_audit, mock_audit_cls = self._make_mocks()

        with (
            patch("slack_project.ghdag_bridge._claude_adapter", mock_adapter),
            patch("slack_project.ghdag_bridge.PipelineState", mock_state_cls),
            patch("slack_project.ghdag_bridge.AuditContext", mock_audit_cls),
        ):
            result = submit_order("order content", queue_dir=tmp_path)

        assert re.match(r"^\d{14}-claude-result-[0-9a-f-]{36}\.md$", result)

    def test_write_order_file_called_with_content(self, tmp_path):
        mock_adapter, mock_state, mock_state_cls, mock_audit, mock_audit_cls = self._make_mocks()

        with (
            patch("slack_project.ghdag_bridge._claude_adapter", mock_adapter),
            patch("slack_project.ghdag_bridge.PipelineState", mock_state_cls),
            patch("slack_project.ghdag_bridge.AuditContext", mock_audit_cls),
        ):
            submit_order("my order content", queue_dir=tmp_path)

        mock_state.write_order_file.assert_called_once()
        call_kwargs = mock_state.write_order_file.call_args
        assert call_kwargs.kwargs.get("content") == "my order content" or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] == "my order content"
        )

    def test_append_exec_records_called(self, tmp_path):
        mock_adapter, mock_state, mock_state_cls, mock_audit, mock_audit_cls = self._make_mocks()

        with (
            patch("slack_project.ghdag_bridge._claude_adapter", mock_adapter),
            patch("slack_project.ghdag_bridge.PipelineState", mock_state_cls),
            patch("slack_project.ghdag_bridge.AuditContext", mock_audit_cls),
        ):
            submit_order("content", queue_dir=tmp_path)

        mock_state.append_exec_records.assert_called_once()

    def test_custom_model_passed_to_build_exec_record(self, tmp_path):
        mock_adapter, mock_state, mock_state_cls, mock_audit, mock_audit_cls = self._make_mocks()

        with (
            patch("slack_project.ghdag_bridge._claude_adapter", mock_adapter),
            patch("slack_project.ghdag_bridge.PipelineState", mock_state_cls),
            patch("slack_project.ghdag_bridge.AuditContext", mock_audit_cls),
        ):
            submit_order("content", model="claude-opus-4-6", queue_dir=tmp_path)

        call_kwargs = mock_adapter.build_exec_record.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"

    def test_default_model_is_claude_sonnet(self, tmp_path):
        mock_adapter, mock_state, mock_state_cls, mock_audit, mock_audit_cls = self._make_mocks()

        with (
            patch("slack_project.ghdag_bridge._claude_adapter", mock_adapter),
            patch("slack_project.ghdag_bridge.PipelineState", mock_state_cls),
            patch("slack_project.ghdag_bridge.AuditContext", mock_audit_cls),
        ):
            submit_order("content", queue_dir=tmp_path)

        call_kwargs = mock_adapter.build_exec_record.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    def test_queue_dir_created_if_missing(self, tmp_path):
        mock_adapter, mock_state, mock_state_cls, mock_audit, mock_audit_cls = self._make_mocks()
        new_dir = tmp_path / "new_jobs"

        with (
            patch("slack_project.ghdag_bridge._claude_adapter", mock_adapter),
            patch("slack_project.ghdag_bridge.PipelineState", mock_state_cls),
            patch("slack_project.ghdag_bridge.AuditContext", mock_audit_cls),
        ):
            submit_order("content", queue_dir=new_dir)

        assert new_dir.exists()

    def test_real_pipeline_state_writes_files(self, tmp_path):
        """PipelineState を実際に使い、ファイルが生成されることを検証する。"""
        state_dir = tmp_path / ".state"

        with patch("slack_project.ghdag_bridge._STATE_DIR", state_dir):
            result = submit_order("order content here", queue_dir=tmp_path)

        order_files = list(tmp_path.glob("*-claude-order-*.md"))
        assert len(order_files) == 1
        assert order_files[0].read_text() == "order content here"

        exec_jsonl = tmp_path / "exec.jsonl"
        assert exec_jsonl.exists()
        record = json.loads(exec_jsonl.read_text())
        assert "uuid" in record

        assert re.match(r"^\d{14}-claude-result-[0-9a-f-]{36}\.md$", result)
