# CloudWatch Logs AI Agent

**Version:** 3.0  
**Language Support:** Japanese-first with English support  
**Frameworks:** Microsoft AutoGen v0.4 + Model Context Protocol (MCP)

CloudWatch ログ調査用の AI エージェントです。Cursor やその他の AI 開発ツールとの統合のための MCP サーバーと、複雑な調査のための AutoGen マルチエージェントシステムの両方を提供します。

## 🌟 主な機能

- **MCP サーバー統合**: Cursor IDE や Claude Desktop との直接連携
- **AutoGen マルチエージェント**: 複雑なログ解析用の AI エージェントシステム
- **日本語優先対応**: ネイティブな日本語処理とレポート
- **AWS CloudWatch Logs**: 直接 API 統合とセキュアな認証
- **エラー処理**: 包括的な例外管理とリトライ機能

## 📦 インストール

### 前提条件

- Python 3.8+ (3.11+ 推奨)
- AWS アカウント（CloudWatch Logs アクセス権限）
- **MCP サーバー**: AWS 認証のみ必要（AI API キー不要）
- **AutoGen エージェント**: AI API キー（OpenAI、Anthropic、Azure OpenAI、Google、Mistral、または xAI のいずれか）

### クイックセットアップ

```bash
# リポジトリをクローン
git clone https://github.com/your-org/cloudwatch-log-agent.git
cd cloudwatch-log-agent

# 仮想環境作成
python -m venv .venv
source .venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# 設定ファイルをコピー
cp .env.mcp .env

# .env ファイルを編集（AWS認証情報を設定）
```

## 🔧 使用方法

### 1. MCP サーバーとしての使用（Cursor IDE 統合）

#### グローバル MCP 設定

`~/.cursor/mcp.json` に以下を追加：

```json
{
  "mcpServers": {
    "cloudwatch-logs-ai-agent": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/cloudwatch-log-agent",
        "run",
        "python",
        "run_mcp_server.py"
      ],
      "cwd": "/path/to/your/cloudwatch-log-agent",
      "env": {
        "PYTHONPATH": "/path/to/your/cloudwatch-log-agent",
        "AWS_PROFILE": "default",
        "AWS_REGION": "ap-northeast-1",
        "LOG_LEVEL": "INFO",
        "MCP_DEBUG": "false",
        "MCP_TRANSPORT": "stdio",
        "MCP_SERVER_NAME": "CloudWatch Logs AI Agent",
        "MCP_SERVER_VERSION": "0.2.0"
      }
    }
  }
}
```

#### 利用可能な MCP ツール（8 つ）

| ツール                        | 説明                                   |
| ----------------------------- | -------------------------------------- |
| `investigate_cloudwatch_logs` | CloudWatch ログの詳細調査              |
| `list_available_log_groups`   | 利用可能なロググループの一覧表示       |
| `analyze_log_patterns`        | ログパターンとトレンドの分析           |
| `test_connection`             | CloudWatch への接続テスト              |
| `get_log_streams`             | 特定のロググループのストリーム取得     |
| `get_recent_events`           | 最近のログイベント取得                 |
| `get_request_metrics`         | MCP サーバーのリクエストメトリクス取得 |
| `get_active_requests`         | 現在アクティブなリクエストの情報取得   |

#### MCP での使用例

Cursor で以下のように使用：

```
CloudWatch ログを調査して、過去24時間のエラーを分析してください。
ロググループ: /aws/lambda/my-function
```

### 2. AutoGen エージェントとしての使用（Python スクリプト）

#### 基本的な使用方法

```python
from src.agents.simplified_agents import create_cloudwatch_orchestrator

# オーケストレーターを作成
orchestrator = create_cloudwatch_orchestrator()

# ログ調査を実行
result = orchestrator.investigate(
    "Lambdaファンクションでエラーが発生しています。過去1時間のログを調査してください。"
)

print(result)
```

#### コマンドライン実行

```bash
# インタラクティブモード
python src/main.py

# 単発調査
python src/main.py --instruction "エラーログを調査してください" --output result.json
```

#### 利用可能なメソッド

- `orchestrator.investigate(instruction)`: 日本語の指示でログ調査
- `orchestrator.get_agent_status()`: エージェントの状態確認

## ⚙️ 設定

### 環境変数

#### MCP サーバー用（AI API キー不要）

`.env` ファイルに以下を設定：

```bash
# AWS 設定
AWS_PROFILE=default
AWS_REGION=ap-northeast-1

# MCP サーバー設定
MCP_SERVER_NAME=CloudWatch Logs Direct Integration
MCP_SERVER_VERSION=0.3.0
MCP_TRANSPORT=stdio
MCP_DEBUG=false

# ログ設定
LOG_LEVEL=INFO
```

#### AutoGen エージェント用（AI API キー必要）

`.env.agent` ファイルに以下を設定：

```bash
# AWS 設定
AWS_PROFILE=default
AWS_REGION=ap-northeast-1

# AI API キー（いずれか1つ）
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# エージェント固有設定
AGENT_LOG_LEVEL=INFO
ENABLE_DEBUG_LOGGING=false
```

### AWS 認証

以下のいずれかの方法で AWS 認証を設定：

1. **AWS CLI**: `aws configure`
2. **環境変数**: `AWS_ACCESS_KEY_ID` と `AWS_SECRET_ACCESS_KEY`
3. **IAM ロール**: EC2/ECS インスタンス用

## 📁 プロジェクト構造

```
cloudwatch-log-agent/
├── src/
│   ├── agents/
│   │   └── simplified_agents.py    # メインエージェント
│   ├── tools/                      # AutoGen 用ツール
│   ├── mcp/                       # MCP サーバー機能
│   └── config/                    # 設定管理
├── run_mcp_server.py              # MCP サーバー起動スクリプト
├── requirements.txt               # 依存関係
├── .env.mcp                       # MCP設定テンプレート
└── .env.agent                     # Agent設定ファイル
```

## 🔍 トラブルシューティング

### よくある問題

1. **AWS 認証エラー**: `aws configure` または環境変数を確認
2. **MCP 接続エラー**: パスと環境変数を確認
3. **AI API エラー（AutoGen のみ）**: API キーと利用制限を確認

### ログ確認

```bash
# MCP サーバーログ
tail -f mcp_server.log

# エージェント調査ログ
tail -f cloudwatch_agent.log
```

## 📝 ライセンス

MIT License

## 🤝 コントリビューション

Issue や Pull Request を歓迎します。日本語でも英語でも対応可能です。
