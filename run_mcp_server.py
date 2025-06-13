#!/usr/bin/env python3
"""
CloudWatch Logs MCP Server Launcher

シンプルなMCPサーバー起動スクリプト
テスト・開発環境での使用に最適化
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# --- Module Cache Busting ---
# To ensure code changes are loaded during development,
# explicitly remove modules from the cache before import.
modules_to_clear = [
    "src.mcp.server",
    "src.mcp.tools",
    "src.mcp.config",
    "src.mcp.validators",
    "src.mcp.request_handler",
    "src.mcp",
    "src.agents.cloudwatch_agent",
    "src.agents.instruction_agent",
    "src.agents.investigation_agent",
    "src.agents.reporting_agent",
    "src.agents.orchestrator",
]
for module in modules_to_clear:
    if module in sys.modules:
        del sys.modules[module]
# -----------------------------

# 環境変数を早期に読み込む
try:
    from dotenv import load_dotenv

    # 複数の.envファイルを順番に読み込み
    env_files = [".env.mcp", ".env.local", ".env"]
    for env_file in env_files:
        if Path(env_file).exists():
            load_dotenv(env_file, override=False)
            print(f"✅ 環境ファイルを読み込みました: {env_file}")
            break
    else:
        print("ℹ️  環境ファイルが見つかりません (.env, .env.local, .env.mcp)")
except ImportError:
    print("⚠️  dotenvが利用できません。環境変数を手動で設定してください。")

try:
    from src.mcp.server import CloudWatchMCPServer
    from src.mcp.config import load_config
except ImportError as e:
    print(f"❌ インポートエラー: {e}")
    print("必要なモジュールがインストールされていない可能性があります。")
    print("pip install -r requirements.txt を実行してください。")
    sys.exit(1)


def setup_logging():
    """ログ設定をセットアップ"""
    # デバッグモードかどうか確認
    debug_mode = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
    log_level = logging.DEBUG if debug_mode else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("mcp_server.log", encoding="utf-8"),
        ],
    )

    if debug_mode:
        print("🐛 デバッグモードが有効です")


def check_environment():
    """環境をチェック"""
    print("🔍 環境をチェックしています...")

    # Python バージョンチェック
    if sys.version_info < (3, 8):
        print("❌ Python 3.8以上が必要です")
        sys.exit(1)

    # 必要なファイルの存在確認
    required_files = [
        "src/mcp/server.py",
        "src/mcp/config.py",
        "src/mcp/tools.py",
        "requirements.txt",
    ]

    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ 必要なファイルが見つかりません: {file_path}")
            sys.exit(1)

    # .envファイルの確認（オプション）
    if Path(".env").exists():
        print("✅ .env ファイルが見つかりました")
    else:
        print("ℹ️  .env ファイルが見つかりません（オプション）")

    print("✅ 環境チェック完了")


def start_server():
    """サーバーを起動"""
    try:
        print("🚀 CloudWatch Logs MCP Server を起動しています...")

        # 設定を読み込み
        config = load_config()

        # サーバーを作成
        server = CloudWatchMCPServer(config)

        # サーバー情報を表示
        info = server.get_server_info()
        print("\n" + "=" * 60)
        print("🌩️  CloudWatch Logs MCP Server")
        print("   テスト・開発環境用シンプル版")
        print("=" * 60)
        print(f"📋 サーバー名: {info['name']}")
        print(f"📋 バージョン: {info['version']}")
        print(f"📋 ツール数: {info['tools_count']}")
        print(f"📋 AWS リージョン: {info['config']['aws_region']}")
        print(f"📋 AWS プロファイル: {info['config']['aws_profile'] or '未設定'}")
        print(f"📋 キャッシュ: 削除済み (機能を無効化)")
        print(f"📋 ログレベル: {info['config']['log_level']}")

        # 環境変数の確認
        print("\n🔍 環境変数の確認:")
        env_vars = [
            "AWS_PROFILE",
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
            "AWS_ACCESS_KEY_ID",
        ]
        for var in env_vars:
            value = os.getenv(var)
            if value:
                if "KEY" in var:
                    print(f"   {var}: {'*' * len(value)}")
                else:
                    print(f"   {var}: {value}")
            else:
                print(f"   {var}: 未設定")

        # 実際のconfig内容を表示
        print("\n📋 読み込まれた設定:")
        print(f"   AWS Profile: {config.aws.profile or '未設定'}")
        print(f"   AWS Region: {config.aws.region}")
        print(f"   AWS設定済み: {'はい' if config.aws.is_configured() else 'いいえ'}")

        # .envファイルの確認
        env_files = [".env", ".env.local", ".env.mcp"]
        print("\n📁 .envファイルの確認:")
        for env_file in env_files:
            if Path(env_file).exists():
                print(f"   ✅ {env_file}: 存在")
            else:
                print(f"   ❌ {env_file}: なし")

        print("=" * 60)
        print("🎯 サーバーが起動しました。Ctrl+C で停止できます。")
        print("=" * 60)

        # FastMCPのrun()メソッドは内部でasyncioループを管理するため、
        # 直接呼び出す（asyncio.run()は使わない）
        import asyncio

        asyncio.run(server.app.run())

    except KeyboardInterrupt:
        print("\n🛑 サーバー停止が要求されました")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main():
    """メイン関数"""
    print("=" * 60)
    print("🌩️  CloudWatch Logs MCP Server")
    print("   テスト・開発環境用シンプル版")
    print("=" * 60)

    # ログ設定
    setup_logging()

    # 環境チェック
    check_environment()

    # サーバー起動
    start_server()


if __name__ == "__main__":
    main()
