#!/usr/bin/env python3
"""
CloudWatch Log Investigation Agent - Main Entry Point.

This is the main entry point for the AutoGen-based CloudWatch log investigation system.
Provides a simple, command-line interface for investigating CloudWatch logs using AI agents.
"""

from tools.aws_utils import list_log_groups
from agents.simplified_agents import create_cloudwatch_orchestrator
import os
import sys
import argparse
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Add src to path for imports
sys.path.insert(0, os.path.dirname(__file__))


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("cloudwatch_agent.log"),
        ],
    )


def check_prerequisites() -> Dict[str, bool]:
    """Check system prerequisites."""
    checks = {"aws_credentials": False, "ai_api_key": False, "autogen_installed": False}

    # Check AWS credentials
    try:
        result = list_log_groups()
        if result and "log_groups" in json.loads(result):
            checks["aws_credentials"] = True
    except Exception:
        pass

    # Check AI API keys
    ai_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "GOOGLE_API_KEY",
    ]
    checks["ai_api_key"] = any(os.getenv(key) for key in ai_keys)

    # Check AutoGen installation
    try:
        import autogen_agentchat
        import autogen_core

        checks["autogen_installed"] = True
    except ImportError:
        pass

    return checks


def print_prerequisites_status(checks: Dict[str, bool]) -> None:
    """Print prerequisite check results."""
    print("\n🔍 System Prerequisites Check:")
    print("-" * 40)

    def status_emoji(x):
        return "✅" if x else "❌"

    print(
        f"{status_emoji(checks['aws_credentials'])} AWS Credentials: {'Configured' if checks['aws_credentials'] else 'Not found'}"
    )
    print(
        f"{status_emoji(checks['ai_api_key'])} AI API Key: {'Available' if checks['ai_api_key'] else 'Not configured'}"
    )
    print(
        f"{status_emoji(checks['autogen_installed'])} AutoGen: {'Installed' if checks['autogen_installed'] else 'Not installed'}"
    )

    if not all(checks.values()):
        print("\n⚠️  Setup Required:")
        if not checks["aws_credentials"]:
            print("  • Configure AWS credentials (aws configure)")
        if not checks["ai_api_key"]:
            print("  • Set AI API key (e.g., export OPENAI_API_KEY=your-key)")
        if not checks["autogen_installed"]:
            print(
                "  • Install AutoGen: pip install autogen-agentchat autogen-core autogen-ext[openai]"
            )
    else:
        print("\n🎉 All prerequisites met!")


def investigate_interactive() -> None:
    """Interactive investigation mode."""
    print("\n🤖 CloudWatch Log Investigation Agent")
    print("=" * 50)
    print("Enter Japanese instructions for log investigation.")
    print("Type 'quit' or 'exit' to stop.")
    print("Type 'status' to check agent status.")
    print("Type 'help' for examples.")

    # Initialize orchestrator
    try:
        orchestrator = create_cloudwatch_orchestrator()
        print("✅ Agent system initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to initialize agent system: {e}")
        return

    while True:
        try:
            # Get user input
            instruction = input("\n🔍 Investigation> ").strip()

            if not instruction:
                continue

            if instruction.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye!")
                break

            if instruction.lower() == "status":
                status = orchestrator.get_agent_status()
                print(f"\n📊 Agent Status:")
                print(f"  Total Agents: {status['total_agents']}")
                print(f"  Model Client Ready: {status['model_client_ready']}")
                continue

            if instruction.lower() == "help":
                print_help_examples()
                continue

            # Perform investigation
            print(f"\n🔍 Investigating: {instruction}")
            print("⏳ Processing... (this may take a moment)")

            start_time = datetime.now()
            result = orchestrator.investigate(instruction)
            duration = (datetime.now() - start_time).total_seconds()

            print(f"\n✅ Investigation completed in {duration:.2f} seconds")
            print(f"📋 Result: {result}")

        except KeyboardInterrupt:
            print("\n\n⚠️ Interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error during investigation: {e}")
            logging.exception("Investigation failed")


def investigate_command(instruction: str, output_file: Optional[str] = None) -> None:
    """Single command investigation."""
    print(f"🔍 Investigating: {instruction}")

    try:
        orchestrator = create_cloudwatch_orchestrator()
        print("✅ Agent system initialized")

        start_time = datetime.now()
        result = orchestrator.investigate(instruction)
        duration = (datetime.now() - start_time).total_seconds()

        print(f"✅ Investigation completed in {duration:.2f} seconds")

        # Format result
        output = {
            "instruction": instruction,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration,
            "result": result,
        }

        # Save to file if specified
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"📁 Result saved to: {output_file}")
        else:
            print(f"📋 Result: {json.dumps(output, indent=2, ensure_ascii=False)}")

    except Exception as e:
        print(f"❌ Investigation failed: {e}")
        logging.exception("Investigation failed")
        sys.exit(1)


def print_help_examples() -> None:
    """Print help and example instructions."""
    print("\n💡 Example Instructions:")
    print("-" * 30)
    print(
        "• 'Lambdaファンクションでエラーが発生しています。過去1時間のログを調査してください。'"
    )
    print("• 'API Gatewayで500エラーが多発しています。原因を調査してください。'")
    print(
        "• 'データベース接続エラーが発生しています。関連するログを調査してください。'"
    )
    print("• '過去24時間のエラーログをすべて調査してください。'")
    print(
        "• 'CloudFrontでパフォーマンス問題が発生しています。ログを確認してください。'"
    )


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="CloudWatch Log Investigation Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --interactive
  %(prog)s --investigate "Lambdaファンクションでエラーが発生しています。調査してください。"
  %(prog)s --check
        """,
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Start interactive investigation mode",
    )

    parser.add_argument(
        "--investigate",
        type=str,
        help="Run single investigation with given instruction (Japanese)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file for investigation results (JSON format)",
    )

    parser.add_argument(
        "--check", "-c", action="store_true", help="Check system prerequisites"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Check prerequisites
    checks = check_prerequisites()

    if args.check:
        print_prerequisites_status(checks)
        return 0 if all(checks.values()) else 1

    # Print status if not all prerequisites are met
    if not all(checks.values()):
        print_prerequisites_status(checks)
        if not checks["aws_credentials"]:
            print("\n❌ Cannot proceed without AWS credentials")
            return 1
        if not checks["ai_api_key"]:
            print("\n⚠️ Warning: No AI API key found. Some features may not work.")

    # Run appropriate mode
    if args.interactive:
        investigate_interactive()
    elif args.investigate:
        investigate_command(args.investigate, args.output)
    else:
        # Default to interactive if no specific command
        print("No command specified. Starting interactive mode...")
        investigate_interactive()

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.exception("Unexpected error")
        sys.exit(1)
