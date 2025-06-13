#!/usr/bin/env python3
"""
Run script for CloudWatch Agent with proper path setup.
"""

from src.agents.simplified_agents import create_cloudwatch_orchestrator
import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def main():
    """Main function to run the CloudWatch investigation example."""
    print("CloudWatch Agent - Quick Test")
    print("=" * 40)

    try:
        # Create the orchestrator
        print("Creating CloudWatch orchestrator...")
        orchestrator = create_cloudwatch_orchestrator()

        # Get system status
        status = orchestrator.get_agent_status()
        print(f"✓ Initialized {status['total_agents']} agents")
        print(f"✓ Loaded {status['cloudwatch_tools']} CloudWatch tools")
        print(f"✓ Model client ready: {status['model_client_ready']}")
        print(f"✓ Team ready: {status['team_ready']}")

        if not status["model_client_ready"]:
            print("\n⚠️  Warning: No AI API key found. Set one of:")
            print("   - OPENAI_API_KEY")
            print("   - ANTHROPIC_API_KEY")
            print("   - AZURE_OPENAI_API_KEY")
            print("   - GOOGLE_API_KEY")
            print("   - MISTRAL_API_KEY")
            return

        if not status["team_ready"]:
            print("\n❌ Error: Team not ready. Check configuration.")
            return

        # Run a simple investigation
        print("\n" + "=" * 40)
        print("Running sample investigation...")
        print("=" * 40)

        instruction = "過去1時間でERRORレベルのログを調査してください。"
        print(f"Instruction: {instruction}")

        result = orchestrator.investigate(instruction)

        print(f"\nResult Status: {result.get('status')}")
        print(f"Duration: {result.get('duration_seconds', 0):.2f} seconds")

        if result.get("status") == "completed":
            print("✅ Investigation completed successfully!")
            if result.get("agent_interactions"):
                print("\nAgent Interactions:")
                for agent, count in result["agent_interactions"].items():
                    print(f"  {agent}: {count} messages")

            if result.get("messages"):
                print("\nMessages:")
                for message in result["messages"]:
                    print(f"  {message.get('agent')}: {message.get('content')}")

        else:
            print(f"❌ Investigation failed: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your configuration and dependencies.")


if __name__ == "__main__":
    main()
