import logging
import sys
from importlib import metadata

# Local imports
from core.server import server
from environment import ENVIRONMENT
from os import getenv

logging.basicConfig(
    level=ENVIRONMENT.logging_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', errors='replace').decode())

def main():
    """
    Main entry point for the Google Workspace MCP server.
    Uses FastMCP's native streamable-http transport.
    """
    safe_print("🔧 Google Workspace MCP Server")
    safe_print("=" * 35)
    safe_print("📋 Server Information:")
    try:
        version = metadata.version("workspace-mcp")
    except metadata.PackageNotFoundError:
        version = "dev"
    safe_print(f"   📦 Version: {version}")
    print()

    # Import tool modules to register them with the MCP server via decorators
    tool_imports = {
        'gmail': lambda: __import__('gmail.gmail_tools'),
        'drive': lambda: __import__('gdrive.drive_tools'),
        'calendar': lambda: __import__('gcalendar.calendar_tools'),
        'docs': lambda: __import__('gdocs.docs_tools'),
        'sheets': lambda: __import__('gsheets.sheets_tools'),
        'chat': lambda: __import__('gchat.chat_tools'),
    }

    tool_icons = {
        'gmail': '📧',
        'drive': '📁',
        'calendar': '📅',
        'docs': '📄',
        'sheets': '📊',
        'chat': '💬',
    }

    # Import specified tools or all tools if none specified
    tools_to_import = tool_imports.keys()
    safe_print(f"🛠️  Loading {len(tools_to_import)} tool module{'s' if len(tools_to_import) != 1 else ''}:")
    for tool in tools_to_import:
        tool_imports[tool]()
        safe_print(f"   {tool_icons[tool]} {tool.title()} - Google {tool.title()} API integration")
    print()

    safe_print(f"📊 Configuration Summary:")
    safe_print(f"   🔧 Tools Enabled: {len(tools_to_import)}/{len(tool_imports)}")
    safe_print(f"   📝 Log Level: {logging.getLogger().getEffectiveLevel()}")
    print()


    try: 
        server.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=8000,
            path="/",
            log_level=getenv("LOGGING_LEVEL"),
        )
    except KeyboardInterrupt:
        safe_print("\n👋 Server shutdown requested")
        # Clean up OAuth callback server if running
        sys.exit(0)
    except Exception as e:
        safe_print(f"\n❌ Server error: {e}")
        logger.error(f"Unexpected error running server: {e}", exc_info=True)
        # Clean up OAuth callback server if running
        sys.exit(1)

if __name__ == "__main__":
    main()
