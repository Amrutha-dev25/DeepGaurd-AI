from fastmcp import FastMCP

from app.forensics import analyze_ela, analyze_frames, compute_hash, extract_exif

# Initialize the MCP server with a descriptive name
mcp = FastMCP("DeepGuard Forensics MCP Server")

# Helper wrappers to match required tool names

def perform_ela(file_path: str) -> dict:
    """MCP tool: perform Error Level Analysis on the given image file.
    Returns a dict with a summary and optional diff_bbox.
    """
    return analyze_ela(file_path)

def extract_exif_tool_func(file_path: str) -> dict:
    """MCP tool: extract EXIF metadata from the given file.
    Returns a dict with a summary and exif dict.
    """
    return extract_exif(file_path)

def compute_hash_tool_func(file_path: str) -> dict:
    """MCP tool: compute SHA-256 and perceptual hash for the file.
    Returns a dict with sha256 and optional phash.
    """
    return compute_hash(file_path)

def analyze_frames_tool_func(file_path: str) -> dict:
    """MCP tool: analyze video frames (or image) for frame count and brightness.
    Returns a dict with a summary, frame_count, and average_brightness.
    """
    return analyze_frames(file_path)

# Register the tools with the server using the required names
@mcp.tool(name="perform_ela")
def perform_ela_tool(file_path: str) -> dict:
    return perform_ela(file_path)

@mcp.tool(name="extract_exif")
def extract_exif_tool(file_path: str) -> dict:
    return extract_exif_tool_func(file_path)

@mcp.tool(name="compute_hash")
def compute_hash_tool(file_path: str) -> dict:
    return compute_hash_tool_func(file_path)

@mcp.tool(name="analyze_frames")
def analyze_frames_tool(file_path: str) -> dict:
    return analyze_frames_tool_func(file_path)

# Entry point - run the MCP server when executed directly.
if __name__ == "__main__":
    # Use the default stdio transport.
    mcp.run()
