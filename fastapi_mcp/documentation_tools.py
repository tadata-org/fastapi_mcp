from pathlib import Path
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Union, List, Optional
from dataclasses import dataclass, asdict
from .logger import logger

@dataclass
class ContentItem:
    type: str = "text"
    text: str = ""
    source: Optional[str] = None

@dataclass
class DocumentationResponse:
    docs: List[ContentItem]

    @classmethod
    def error(cls) -> "DocumentationResponse":
        return cls(docs=[ContentItem(text="Error getting documentation")], file_used=None)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def _get_file_priority(file):
    name = file.name.lower()
    if name == 'llms.txt':
        return 0  # Highest priority
    elif name.startswith('readme'):
        return 1  # Second priority
    else:
        return 2  # Lowest priority

def _prioritize_files(files: List[Path]) -> List[Path]:
    """
    Return only the highest priority files available.
    If priority 0 files exist, return only those.
    If not, return priority 1 files.
    If neither exist, return priority 2 files.
    
    Args:
        files: List of files to prioritize
        
    Returns:
        List of files with the highest available priority
    """
    if not files:
        return []
        
    # Group files by priority
    priority_groups = {0: [], 1: [], 2: []}
    for file in files:
        priority = _get_file_priority(file)
        priority_groups[priority].append(file)
    
    # Return the highest priority group that has files
    for priority in [0, 1, 2]:
        if priority_groups[priority]:
            logger.info(f"Found {len(priority_groups[priority])} files with priority {priority}")
            return priority_groups[priority]
    
    return []  # Should never reach here if files is non-empty

def _collect_documentation_files(docs_path: Union[str, List[str]]) -> List[Path]:
    """
    Collect documentation files from the given path(s).
    
    Args:
        docs_path: Can be one of:
            - A single path to a documentation file (str)
            - A list of paths to documentation files (List[str])
            - A path to a directory containing documentation files (str)
            
    Returns:
        List of Path objects representing the documentation files
    """
    # Handle list of file paths
    if isinstance(docs_path, list):
        files = []
        for path_str in docs_path:
            path = Path(path_str)
            if path.exists():
                files.append(path)
        return files

    path = Path(docs_path)  

    # If it's a directory, find all markdown files and llms.txt files
    if path.is_dir():
        md_files = list(path.rglob('*.md'))
        llms_txt_files = list(path.rglob('llms.txt'))
        return _prioritize_files(llms_txt_files + md_files)

    # If it's a single file, return it
    return [path]
            

def _read_documentation_files(files: List[Path]) -> List[tuple[str, str]]:
    all_content = []
    for file in files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                all_content.append((content, str(file)))
        except Exception as e:
            logger.error(f"Error reading documentation file {file}: {e}")
    return all_content
    

def create_documentation_tools(mcp_server: FastMCP, docs_path: Union[str, List[str]]) -> None:
    """
    Create MCP tools that serve the documentation to an AI Agent and allows searching through documentation files.
    
    Args:
        mcp_server: The MCP server to add the tool to
        docs_path: Can be one of:
            - A single path to a documentation file (str)
            - A list of paths to documentation files (List[str])
            - A path to a directory containing documentation files (str)
    """
    @mcp_server.tool()
    async def fetch_documentation() -> Dict[str, Any]:
        """
        Fetch the contents of documentation files.
        
        Returns:
            A dictionary containing the file content and metadata
        """
        files = _collect_documentation_files(docs_path)
        if not files:
            logger.error(f"No documentation files found at {docs_path}")
            return DocumentationResponse.error().to_dict()
        
        all_content = _read_documentation_files(files)
        if not all_content:
            logger.error(f"No content found in documentation files at {docs_path}")
            return DocumentationResponse.error().to_dict()
        
        return DocumentationResponse(
                docs=[ContentItem(text=content, source=source) for content, source in all_content],
            ).to_dict()

    # TODO: Add tool to search documentation