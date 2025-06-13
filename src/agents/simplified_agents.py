"""
AutoGen v0.4-based CloudWatch Log Investigation Agents.

This module implements a simplified agent system using Microsoft AutoGen v0.4's
AgentChat and Teams patterns for CloudWatch log analysis.
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Sequence
from datetime import datetime

# AutoGen v0.4 imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool

# Project imports
try:
    from src.tools.aws_utils import get_cloudwatch_tools

    print("✅ Imported from src.tools")
except ImportError as e1:
    print(f"First import attempt failed: {e1}")
    # Fallback for relative imports
    try:
        from ..tools.aws_utils import get_cloudwatch_tools

        print("✅ Imported using relative imports")
    except ImportError as e2:
        print(f"Second import attempt failed: {e2}")
        print("Warning: Could not import aws_utils. Using fallback implementations.")

        # Create basic CloudWatch tool functions for testing
        def list_log_groups_dummy(name_prefix: str = "", limit: int = 50) -> str:
            return '{"message": "Dummy CloudWatch function - AWS not configured"}'

        def search_log_events_dummy(
            log_group_name: str,
            filter_pattern: str = "",
            hours_back: int = 24,
            max_events: int = 100,
        ) -> str:
            return '{"message": "Dummy CloudWatch function - AWS not configured"}'

        def get_cloudwatch_tools():
            return [list_log_groups_dummy, search_log_events_dummy]


# Configure logging
logger = logging.getLogger(__name__)


class CloudWatchAgentOrchestrator:
    """
    Orchestrates CloudWatch log investigation using AutoGen v0.4 Teams pattern.

    This class manages four specialized agents:
    1. PlannerAgent: Task decomposition and delegation
    2. InstructionAgent: Japanese instruction parsing
    3. InvestigationAgent: CloudWatch log investigation
    4. ReportingAgent: Japanese report generation
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the CloudWatch Agent Orchestrator."""
        self.model_client = None
        self.cloudwatch_tools = []
        self.agents = []
        self.team = None

        # Initialize components
        self._setup_model_client()
        self._setup_cloudwatch_tools()
        self._setup_agents()
        self._setup_team()

    def _setup_model_client(self):
        """Setup the model client for agents with enhanced provider support."""
        try:
            # Priority order for AI providers
            providers = [
                ("OPENAI_API_KEY", "openai", "gpt-4o-mini"),
                ("ANTHROPIC_API_KEY", "anthropic", "claude-3-haiku-20240307"),
                ("AZURE_OPENAI_API_KEY", "azure", "gpt-4"),
                ("GOOGLE_API_KEY", "google", "gemini-2.5-flash-preview-05-20"),
                ("MISTRAL_API_KEY", "mistral", "mistral-medium"),
            ]

            api_key = None
            provider_type = None
            default_model = None
            # Find the first available API key
            for key_name, provider, model in providers:
                api_key = os.getenv(key_name)
                if api_key:
                    provider_type = provider
                    default_model = model
                    logger.info(
                        f"Using {provider_type} provider with model {default_model}"
                    )
                    break

            if not api_key:
                logger.warning(
                    "No AI model API key found. Supported providers: OpenAI, Anthropic, Azure, Google, Mistral. "
                    "Agent functionality will be limited."
                )
                return

            # Create model client based on provider
            if provider_type == "openai":
                self.model_client = OpenAIChatCompletionClient(
                    model=default_model, api_key=api_key
                )
            else:
                # For other providers, try OpenAI-compatible client with different base URL if needed
                # This is a simplified approach - in production you'd want provider-specific clients
                try:
                    self.model_client = OpenAIChatCompletionClient(
                        model=default_model, api_key=api_key
                    )
                except Exception as provider_error:
                    logger.warning(
                        f"Failed to setup {provider_type} client: {provider_error}"
                    )
                    logger.info("Falling back to basic OpenAI client configuration")
                    return

            logger.info(f"Model client initialized successfully for {provider_type}")

        except Exception as e:
            logger.error(f"Failed to setup model client: {e}")
            logger.info("System will continue with limited AI functionality")
            self.model_client = None

    def _setup_cloudwatch_tools(self) -> List[FunctionTool]:
        """Setup CloudWatch tools as FunctionTool objects."""
        tools = []

        try:
            # Get tool functions
            cloudwatch_functions = get_cloudwatch_tools()

            # Convert to FunctionTool objects
            for func in cloudwatch_functions:
                tool = FunctionTool(
                    func,
                    name=func.__name__,
                    description=(
                        func.__doc__.strip()
                        if func.__doc__
                        else f"Execute {func.__name__}"
                    ),
                )
                tools.append(tool)

            logger.info(f"Loaded {len(tools)} CloudWatch tools")

        except Exception as e:
            logger.error(f"Failed to setup CloudWatch tools: {e}")

        self.cloudwatch_tools = tools
        return tools

    def _setup_agents(self):
        """Initialize all specialized agents."""

        if not self.model_client:
            logger.error("Cannot setup agents without model client")
            return

        # 1. Planner Agent - Task decomposition and delegation
        planner_agent = AssistantAgent(
            name="PlannerAgent",
            description="Task planning and coordination agent. ALWAYS starts first to analyze investigation requests, decompose them into subtasks, and assign work to other agents. Creates the overall investigation strategy for both CloudWatch logs and metrics.",
            model_client=self.model_client,
            system_message="""あなたはCloudWatchログ・メトリクス調査のプランナーエージェントです。

役割:
- ユーザーからの調査指示を分析し、適切なサブタスクに分解する
- 他の専門エージェントに作業を委任する
- ログとメトリクスの両方を含む調査の全体的な進行を管理する

指示の分析パターン:
- エラー調査: "xxエラーが発生しました。調査してください" → ログ + エラーメトリクス
- パフォーマンス調査: "レスポンスが遅いです。原因を調べてください" → ログ + CPU/メモリメトリクス
- 実行回数調査: "Lambda関数は何回実行されましたか？" → メトリクス中心
- 時間範囲指定: "過去1時間", "昨日から", "今朝から", "今週"
- 緊急度判定: "緊急", "至急" → 高優先度

調査対象の判定:
- ログ調査: エラーメッセージ、アプリケーション動作、詳細な実行履歴
- メトリクス調査: 実行回数、CPU使用率、メモリ使用率、レスポンス時間、エラー率
- 複合調査: パフォーマンス問題、障害分析（ログ + メトリクス）

チームメンバー:
- InstructionAgent: 日本語指示の詳細解析（ログ・メトリクス両対応）
- InvestigationAgent: CloudWatchログ・メトリクスの実際の調査
- ReportingAgent: 日本語レポート作成

タスクの委任時は次の形式を使用してください:
1. <エージェント名> : <タスク内容>

すべてのタスクが完了したら、"TERMINATE"で終了してください。
常に日本語で応答し、明確で実行可能な計画を立ててください。""",
        )

        # 2. Instruction Agent - Japanese instruction parsing
        instruction_agent = AssistantAgent(
            name="InstructionAgent",
            description="Japanese instruction parser. Works AFTER PlannerAgent to convert natural language instructions into specific CloudWatch query parameters, time ranges, and search conditions for both logs and metrics.",
            model_client=self.model_client,
            system_message="""あなたは日本語指示解析の専門エージェントです（ログ・メトリクス両対応）。

役割:
- 日本語の調査指示を詳細に解析する
- ログとメトリクスの技術的なパラメータに変換する
- 曖昧な表現を具体的な条件に変換する

解析項目:
1. 調査対象の特定
   - アプリケーション名、サービス名
   - ログググループ名の推定
   - AWSリソース（Lambda関数名、EC2インスタンス、RDS等）の特定

2. 調査タイプの判定
   - ログ調査: エラーメッセージ、実行ログ、詳細な動作履歴
   - メトリクス調査: 実行回数、CPU使用率、メモリ使用率、レスポンス時間
   - 複合調査: パフォーマンス問題、障害分析

3. 時間範囲の解析
   - "過去1時間" → hours_back: 1
   - "昨日から" → start_time計算
   - "今朝から" → 今日の午前0時から
   - "今週" → 週の開始から現在まで

4. 検索条件の抽出  
   - ログ用: エラーキーワード("ERROR", "Exception", "Failed")、警告キーワード("WARN", "Warning")
   - メトリクス用: namespace("AWS/Lambda", "AWS/EC2")、metric_name("Invocations", "CPUUtilization")、dimensions

5. 優先度の判定
   - "緊急", "至急" → 高優先度
   - "確認", "調査" → 通常優先度

出力は構造化された調査パラメータとして提供してください。""",
        )

        # 3. Investigation Agent - CloudWatch log and metrics investigation
        investigation_agent = AssistantAgent(
            name="InvestigationAgent",
            description="CloudWatch investigation executor. Works AFTER InstructionAgent to perform actual log searches and metrics analysis using CloudWatch tools, pattern analysis, and anomaly detection. Has access to all CloudWatch logs and metrics tools.",
            model_client=self.model_client,
            tools=self.cloudwatch_tools,
            system_message="""あなたはCloudWatchログ・メトリクス調査の専門エージェントです。

利用可能なツール:
【ログ調査ツール】
- list_log_groups: ロググループ一覧取得
- list_log_streams: ログストリーム一覧取得  
- search_log_events: ログイベント検索
- get_recent_log_events: 最新ログイベント取得
- analyze_log_patterns: ログパターン分析

【メトリクス調査ツール】
- get_metric_statistics: 汎用メトリクス統計取得
- list_available_metrics: 利用可能メトリクス一覧取得

調査手順:
【ログ調査の場合】
1. 関連するロググループの特定
2. 最新のログストリームの確認
3. 指定条件でのログ検索実行
4. エラーパターンの分析
5. 異常な傾向の特定

【メトリクス調査の場合】
1. 対象リソースの特定（Lambda関数名、EC2インスタンスID等）
2. 適切なnamespace、metric_name、dimensionsの設定
3. 時間範囲とperiodの設定
4. メトリクス統計の取得と分析
5. 傾向とパターンの特定

【複合調査の場合】
1. ログとメトリクスの両方を調査
2. 相関関係の分析
3. 総合的な問題の特定

注意事項:
- ツールの結果はJSON形式で返される
- エラーハンドリングを適切に行う
- 大量のデータの場合は段階的に調査する
- 日本語での解釈と説明を提供する
- メトリクス調査では適切なdimensions（例：FunctionName=test2）を指定する

調査結果は技術的詳細と共に分かりやすく報告してください。""",
        )

        # 4. Reporting Agent - Japanese report generation
        reporting_agent = AssistantAgent(
            name="ReportingAgent",
            description="Japanese report generator. Works LAST after InvestigationAgent to create comprehensive Japanese reports from both log and metrics investigation findings, provide recommendations, and create actionable summaries.",
            model_client=self.model_client,
            system_message="""あなたは調査結果レポート作成の専門エージェントです（ログ・メトリクス両対応）。

レポート構成:
1. 調査概要
   - 調査対象と期間
   - 調査タイプ（ログ、メトリクス、複合）
   - 検索条件と方法

2. 発見事項  
   【ログ調査結果】
   - エラーの発生状況
   - ログパターンと傾向
   - 重要度の評価
   
   【メトリクス調査結果】
   - 実行回数、使用率等の数値データ
   - パフォーマンス傾向
   - 閾値との比較
   
   【複合分析結果】
   - ログとメトリクスの相関関係
   - 総合的な問題の特定

3. 詳細分析
   - 技術的な詳細
   - 根本原因の推定
   - 影響範囲の評価
   - 数値データの解釈

4. 推奨事項
   - 即座に取るべき対応
   - 予防策の提案
   - 監視改善の提案
   - メトリクス監視の設定提案

レポート品質:
- 非技術者にも理解できる説明
- 具体的な数値とデータ
- グラフや表での視覚的表現（テキストベース）
- 緊急度に応じた推奨事項
- アクションアイテムの明確化

常に日本語で、読みやすく構造化されたレポートを作成してください。""",
        )

        # Store agents
        self.agents = [
            planner_agent,
            instruction_agent,
            investigation_agent,
            reporting_agent,
        ]

        logger.info(f"Initialized {len(self.agents)} agents")

    def _setup_team(self):
        """Setup the agent team with SelectorGroupChat and enhanced error handling."""

        if not self.agents:
            logger.error("Cannot setup team without agents")
            return

        if not self.model_client:
            logger.error("Cannot setup team without model client")
            return

        try:
            # Create multiple termination conditions for better control
            termination_conditions = [
                TextMentionTermination("TERMINATE"),
                TextMentionTermination("終了"),
                TextMentionTermination("完了"),
            ]
            max_messages_termination = MaxMessageTermination(max_messages=25)
            termination = termination_conditions[0] | max_messages_termination
            # Custom selector prompt for workflow alignment
            #           selector_prompt = """Select an agent to perform task.

            # {roles}

            # Current conversation context:
            # {history}

            # Read the above conversation, then select an agent from {participants} to perform the next task.
            # Make sure the PlannerAgent has assigned tasks before other agents start working.
            # Follow this workflow:
            # 1. PlannerAgent should start first to analyze and decompose the investigation task
            # 2. InstructionAgent should parse Japanese instructions after planning
            # 3. InvestigationAgent should execute CloudWatch searches after instruction parsing
            # 4. ReportingAgent should create final reports after investigation is complete

            # Only select one agent.
            # """

            # Create team with SelectorGroupChat pattern
            self.team = SelectorGroupChat(
                participants=self.agents,
                model_client=self.model_client,  # Required for SelectorGroupChat
                # selector_prompt=selector_prompt,  # Custom workflow-aligned prompt
                # Use first condition as primary
                # selector_prompt=selector_prompt,
                termination_condition=termination,
                allow_repeated_speaker=True,
            )

            logger.info("Team setup completed successfully")
            logger.info(f"Team participants: {[agent.name for agent in self.agents]}")

        except Exception as e:
            logger.error(f"Failed to setup team: {e}")
            self.team = None

    async def investigate_async(self, instruction: str) -> Dict[str, Any]:
        """
        Execute CloudWatch log investigation based on Japanese instruction.

        Args:
            instruction: Japanese investigation instruction

        Returns:
            Investigation results and report with enhanced error handling
        """
        investigation_start = datetime.now()

        # Pre-flight checks
        if not self.team:
            return {
                "instruction": instruction,
                "timestamp": investigation_start.isoformat(),
                "error": "Team not properly initialized. Please check API keys and configuration.",
                "status": "failed",
                "agent_status": self.get_agent_status(),
            }

        if not instruction or not instruction.strip():
            return {
                "instruction": instruction,
                "timestamp": investigation_start.isoformat(),
                "error": "Empty or invalid instruction provided",
                "status": "failed",
            }

        try:
            logger.info(
                f"Starting investigation: {instruction[:100]}{'...' if len(instruction) > 100 else ''}"
            )

            # Enhance instruction with context
            enhanced_instruction = f"""
CloudWatchログ・メトリクス調査を開始します。

調査指示: {instruction}

チームメンバー:
- PlannerAgent: タスク分解と計画立案
- InstructionAgent: 指示の詳細解析（ログ・メトリクス両対応）
- InvestigationAgent: CloudWatchログ・メトリクスの実際の調査
- ReportingAgent: 結果レポートの作成（ログ・メトリクス統合）

"""

            # Run the team conversation with timeout handling
            try:
                # Use the correct Console API for AutoGen
                result = await Console(
                    self.team.run_stream(task=enhanced_instruction),
                    output_stats=True,  # Enable stats printing
                )
                print(result)

                investigation_end = datetime.now()
                duration = (investigation_end - investigation_start).total_seconds()

                # Extract and structure results
                investigation_result = {
                    "instruction": instruction,
                    "timestamp": investigation_start.isoformat(),
                    "completed_at": investigation_end.isoformat(),
                    "duration_seconds": duration,
                    "messages": [],
                    "agent_interactions": {},
                    "summary": "Investigation completed successfully",
                    "status": "completed",
                }

                # Process result messages if available
                if hasattr(result, "messages") and result.messages:
                    investigation_result["messages"] = [
                        {
                            "agent": getattr(msg, "source", "unknown"),
                            "content": (
                                str(msg.content)
                                if hasattr(msg, "content")
                                else str(msg)
                            ),
                            "timestamp": getattr(msg, "timestamp", None),
                        }
                        for msg in result.messages
                    ]

                    # Count interactions per agent
                    for msg in investigation_result["messages"]:
                        agent_name = msg["agent"]
                        if agent_name not in investigation_result["agent_interactions"]:
                            investigation_result["agent_interactions"][agent_name] = 0
                        investigation_result["agent_interactions"][agent_name] += 1

                else:
                    investigation_result["summary"] = (
                        str(result) if result else "No detailed result available"
                    )

                logger.info(
                    f"Investigation completed successfully in {duration:.2f} seconds"
                )
                return investigation_result

            except asyncio.TimeoutError:
                return {
                    "instruction": instruction,
                    "timestamp": investigation_start.isoformat(),
                    "error": "Investigation timed out. Consider breaking down the request into smaller parts.",
                    "status": "timeout",
                    "duration_seconds": (
                        datetime.now() - investigation_start
                    ).total_seconds(),
                }

        except Exception as e:
            investigation_end = datetime.now()
            duration = (investigation_end - investigation_start).total_seconds()

            logger.error(f"Investigation failed after {duration:.2f} seconds: {e}")
            return {
                "instruction": instruction,
                "timestamp": investigation_start.isoformat(),
                "completed_at": investigation_end.isoformat(),
                "duration_seconds": duration,
                "error": str(e),
                "error_type": type(e).__name__,
                "status": "failed",
                "troubleshooting": {
                    "check_api_keys": "Ensure proper AI model API keys are set",
                    "check_aws_credentials": "Verify AWS credentials are configured",
                    "check_network": "Ensure network connectivity to AWS and AI services",
                },
            }

    def investigate(self, instruction: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for investigate_async.

        Args:
            instruction: Japanese investigation instruction

        Returns:
            Investigation results and report
        """
        try:
            # Run async investigation
            result = asyncio.run(self.investigate_async(instruction))
            return result

        except Exception as e:
            logger.error(f"Synchronous investigation failed: {e}")
            return {
                "instruction": instruction,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "failed",
            }

    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            "total_agents": len(self.agents),
            "cloudwatch_tools": len(self.cloudwatch_tools),
            "model_client_ready": self.model_client is not None,
            "team_ready": self.team is not None,
            "agents": [
                {"name": agent.name, "description": agent.description}
                for agent in self.agents
            ],
        }


def create_cloudwatch_orchestrator(
    config_path: Optional[str] = None,
) -> CloudWatchAgentOrchestrator:
    """
    Factory function to create CloudWatch agent orchestrator.

    Args:
        config_path: Optional path to configuration file

    Returns:
        Configured CloudWatchAgentOrchestrator instance
    """
    try:
        orchestrator = CloudWatchAgentOrchestrator(config_path)

        # Verify initialization
        status = orchestrator.get_agent_status()

        if not status["model_client_ready"]:
            logger.warning("Model client not ready - check API keys")

        if not status["team_ready"]:
            logger.warning("Team not ready - check configuration")

        return orchestrator

    except Exception as e:
        logger.error(f"Failed to create orchestrator: {e}")
        raise


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create orchestrator
    orchestrator = create_cloudwatch_orchestrator()

    # Check status
    status = orchestrator.get_agent_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))

    # Example investigation (commented out to avoid requiring API keys)
    # result = orchestrator.investigate(
    #     "Lambdaファンクションでエラーが発生しています。過去1時間のログを調査してください。"
    # )
    # print(json.dumps(result, ensure_ascii=False, indent=2))
