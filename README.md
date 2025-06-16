# CloudWatch Logs & Metrics AI Agent

**Version:** 3.0  
**Language Support:** Japanese-first with English support  
**Frameworks:** Microsoft AutoGen v0.4 + Model Context Protocol (MCP)

CloudWatch ログ・メトリクス調査用の AI エージェントです。Cursor やその他の AI 開発ツールとの統合のための MCP サーバーと、複雑な調査のための AutoGen マルチエージェントシステムの両方を提供します。

## TODO

- [ ] MCP の環境変数を設定できる

## 🌟 主な機能

- **MCP サーバー統合**: Cursor IDE や Claude Desktop との直接連携
- **AutoGen マルチエージェント**: 複雑なログ・メトリクス解析用の AI エージェントシステム
- **日本語優先対応**: ネイティブな日本語処理とレポート
- **AWS CloudWatch Logs**: 直接 API 統合とセキュアな認証
- **AWS CloudWatch Metrics**: CPU、メモリ、ディスク、ネットワーク、API 呼び出し数、エラー率などの包括的なメトリクス調査
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
cp .env.mcp.example .env

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
      ]
    }
  }
}
```

#### 利用可能な MCP ツール（10 つ）

##### CloudWatch Logs ツール（6 つ）

| ツール                        | 説明                               |
| ----------------------------- | ---------------------------------- |
| `investigate_cloudwatch_logs` | CloudWatch ログの詳細調査          |
| `list_available_log_groups`   | 利用可能なロググループの一覧表示   |
| `analyze_log_patterns`        | ログパターンとトレンドの分析       |
| `test_connection`             | CloudWatch への接続テスト          |
| `get_log_streams`             | 特定のロググループのストリーム取得 |
| `get_recent_events`           | 最近のログイベント取得             |

##### CloudWatch Metrics ツール（2 つ）

| ツール                           | 説明                            |
| -------------------------------- | ------------------------------- |
| `investigate_cloudwatch_metrics` | CloudWatch メトリクスの詳細調査 |
| `list_available_metrics`         | 利用可能なメトリクスの一覧表示  |

##### システム管理ツール（2 つ）

| ツール                | 説明                                   |
| --------------------- | -------------------------------------- |
| `get_request_metrics` | MCP サーバーのリクエストメトリクス取得 |
| `get_active_requests` | 現在アクティブなリクエストの情報取得   |

#### MCP での使用例

##### ログ調査の例

Cursor で以下のように使用：

```
CloudWatch ログを調査して、過去24時間のエラーを分析してください。
ロググループ: /aws/lambda/my-function
```

##### メトリクス調査の例

Cursor で以下のように使用：

```
EC2インスタンス i-1234567890abcdef0 の過去1時間のCPU使用率を調査してください。
```

```
Lambda関数 my-function の過去24時間の実行時間とエラー率を分析してください。
```

```
API Gateway my-api の過去6時間のリクエスト数、レイテンシ、エラー率を調査してください。
```

##### 統合調査の例

ログとメトリクスを組み合わせた調査：

```
Lambda関数でエラーが発生しています。メトリクス（実行時間、エラー率）とログの両方を調査して、根本原因を特定してください。
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

# メトリクス調査を実行
result = orchestrator.investigate(
    "EC2インスタンスのCPU使用率が高いです。過去24時間のメトリクスを分析してください。"
)

# 統合調査を実行（ログ + メトリクス）
result = orchestrator.investigate(
    "API Gatewayでレスポンス時間が遅くなっています。メトリクスとログの両方を調査して原因を特定してください。"
)

print(result)
```

#### コマンドライン実行

```bash
# インタラクティブモード
python src/main.py

# 単発調査（ログ）
python src/main.py --instruction "エラーログを調査してください" --output result.json

# 単発調査（メトリクス）
python src/main.py --instruction "EC2のCPU使用率を調査してください" --output metrics_result.json

# 統合調査（ログ + メトリクス）
python src/main.py --instruction "Lambda関数の性能問題を調査してください" --output combined_result.json
```

#### 利用可能なメソッド

- `orchestrator.investigate(instruction)`: 日本語の指示でログ・メトリクス調査
- `orchestrator.get_agent_status()`: エージェントの状態確認

## ⚙️ 設定

### 環境変数

#### MCP サーバー用（AI API キー不要）

`.env` ファイルに以下を設定：

```bash
# AWS 設定
AWS_PROFILE=default
AWS_REGION=ap-northeast-1

# MCP サーバー設定（実際に使用される設定のみ）
MCP_SERVER__NAME=CloudWatch Logs MCP Server
MCP_SERVER__VERSION=0.3.0
# Transport options: stdio, sse, streamable-http
MCP_SERVER__TRANSPORT=stdio
MCP_SERVER__HOST=localhost    # sse/streamable-httpの場合に使用
MCP_SERVER__PORT=8000         # sse/streamable-httpの場合に使用

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

### 環境変数の優先順位

環境変数は以下の優先順位で読み込まれます（上位が優先）：

1. **外部環境変数** (最優先) - MCP サーバーの`env`セクション、システム環境変数など
2. **`.env.{profile}`ファイル** - プロファイル固有の設定
3. **`.env`ファイル** - ローカル上書き設定
4. **`.env.cloudwatch`ファイル** - ベース設定

**重要**: 外部から渡された環境変数（MCP の`env`セクションなど）は`.env`ファイルによって上書きされることはありません。

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
├── .env.mcp.example               # MCP設定テンプレート
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
