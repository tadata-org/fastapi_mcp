import pytest
import json
from pathlib import Path
from fastapi_mcp.documentation_tools import (
    _get_file_priority,
    _prioritize_files,
    _collect_documentation_files,
    _read_documentation_files,
    ContentItem,
    DocumentationResponse,
    create_documentation_tools,
)
from mcp.server.fastmcp import FastMCP


def test_get_file_priority():
    """Test the file priority system"""
    llms_file = Path("llms.txt")
    readme_file = Path("README.md")
    other_file = Path("documentation.md")

    assert _get_file_priority(llms_file) == 0  # Highest priority
    assert _get_file_priority(readme_file) == 1  # Second priority
    assert _get_file_priority(other_file) == 2  # Lowest priority


def test_prioritize_files():
    """Test the file prioritization logic"""
    llms_file = Path("llms.txt")
    readme_file = Path("README.md")
    other_file = Path("documentation.md")

    # Test with mixed priority files
    files = [other_file, readme_file, llms_file]
    prioritized = _prioritize_files(files)
    assert len(prioritized) == 1
    assert prioritized[0] == llms_file

    # Test with only readme and other files
    files = [other_file, readme_file]
    prioritized = _prioritize_files(files)
    assert len(prioritized) == 1
    assert prioritized[0] == readme_file

    # Test with only other files
    files = [other_file]
    prioritized = _prioritize_files(files)
    assert len(prioritized) == 1
    assert prioritized[0] == other_file

    # Test with empty list
    assert _prioritize_files([]) == []


def test_collect_documentation_files(tmp_path):
    """Test documentation file collection using a real temporary filesystem"""
    # Create a docs directory with test files
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    # Create test files
    (docs_dir / "llms.txt").write_text("LLM documentation")
    (docs_dir / "README.md").write_text("README content")
    (docs_dir / "other.md").write_text("Other documentation")
    
    # Test directory path - should return only llms.txt due to priority
    files = _collect_documentation_files(str(docs_dir))
    assert len(files) == 1
    assert files[0].name == "llms.txt"
    
    # Test single file path
    single_file = docs_dir / "README.md"
    files = _collect_documentation_files(str(single_file))
    assert len(files) == 1
    assert files[0].name == "README.md"
    
    # Test list of files
    file_list = [
        str(docs_dir / "README.md"),
        str(docs_dir / "other.md")
    ]
    files = _collect_documentation_files(file_list)
    assert len(files) == 2
    assert {f.name for f in files} == {"README.md", "other.md"}


def test_read_documentation_files(tmp_path):
    """Test reading documentation files from filesystem"""
    # Create test files with content
    file1 = tmp_path / "test1.md"
    file2 = tmp_path / "test2.md"
    
    file1.write_text("Content 1")
    file2.write_text("Content 2")
    
    files = [file1, file2]
    content = _read_documentation_files(files)
    
    assert len(content) == 2
    assert content[0][0] == "Content 1"
    assert content[1][0] == "Content 2"
    assert content[0][1] == str(file1)
    assert content[1][1] == str(file2)


@pytest.mark.asyncio
async def test_fetch_documentation(tmp_path):
    """Test the fetch_documentation tool with real files"""
    # Create test documentation
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    test_content = "Test documentation content"
    (docs_dir / "llms.txt").write_text(test_content)
    
    # Create and test the tool
    mcp = FastMCP()
    create_documentation_tools(mcp, str(docs_dir))
    
    # Test the tool
    result = await mcp.call_tool("fetch_documentation", {})
    assert len(result) == 1
    result_dict = json.loads(result[0].text)
    assert "docs" in result_dict
    docs = result_dict["docs"]
    assert len(docs) == 1 
    assert docs[0]["text"] == test_content
    assert docs[0]["source"] == str(docs_dir / "llms.txt")



def test_documentation_response():
    """Test DocumentationResponse class"""
    # Test normal response
    docs = [ContentItem(text="test", source="test.md")]
    response = DocumentationResponse(docs=docs)
    assert response.docs == docs
    
    # Test error response
    error_response = DocumentationResponse.error()
    assert len(error_response.docs) == 1
    assert error_response.docs[0].text == "Error getting documentation"
    
    # Test to_dict
    response_dict = response.to_dict()
    assert isinstance(response_dict, dict)
    assert 'docs' in response_dict 