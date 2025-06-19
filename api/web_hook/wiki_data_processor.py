"""
This module handles the processing and formatting of wiki data.
It includes functions for:
- Extracting XML wiki structure from AI responses.
- Parsing XML to retrieve wiki title, description, and page details.
- Cleaning and formatting text content for display.
- Generating a formatted text file (`llms.txt`) from wiki data.
"""
import re
import logging
import xml.etree.ElementTree as ET
import os
from typing import List, Tuple, Dict, Any

# Configure logger
logger = logging.getLogger(__name__)
# Basic config if not already set by another module
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

def extract_wiki_structure_xml(wiki_structure_response: str, logger_instance=None) -> str:
    """
    Clean up the AI response and extract the <wiki_structure>...</wiki_structure> XML block.
    Raises ValueError if the response is empty or no valid XML is found.

    Args:
        wiki_structure_response (str): The raw response string from the AI.
        logger_instance (logging.Logger, optional): Specific logger instance. Defaults to module logger.

    Returns:
        str: The cleaned XML text block.
    """
    if logger_instance is None:
        logger_instance = logger

    if not wiki_structure_response or str(wiki_structure_response).strip() == "":
        logger_instance.error("Wiki structure response is empty - this indicates an issue with the model call")
        raise ValueError("Wiki structure response is empty")

    wiki_structure_response = str(wiki_structure_response)
    wiki_structure_response = re.sub(r'^```(?:xml)?\s*', '', wiki_structure_response, flags=re.IGNORECASE)
    wiki_structure_response = re.sub(r'```\s*$', '', wiki_structure_response, flags=re.IGNORECASE)

    match = re.search(r"<wiki_structure>[\s\S]*?</wiki_structure>", wiki_structure_response, re.MULTILINE)

    if not match:
        logger_instance.error(f"No valid XML structure found in AI response. Response length: {len(wiki_structure_response)}")
        logger_instance.debug(f"Full response for XML extraction check: {wiki_structure_response}")
        if len(wiki_structure_response) > 500:
             logger_instance.debug(f"First 500 chars of response: {wiki_structure_response[:500]}")
        raise ValueError("No valid XML structure found in AI response")

    xml_match = match.group(0)
    xml_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', xml_match)
    return xml_text


def parse_wiki_structure(xml_text: str) -> Tuple[str, str, List[dict]]:
    """
    Parse the XML wiki structure and extract title, description, and pages.

    Args:
        xml_text (str): XML string representing the wiki structure.

    Returns:
        Tuple[str, str, List[dict]]: (title, description, pages)
                                      Each page is a dict with 'id', 'title',
                                      'description', 'importance', 'file_paths',
                                      'related_pages'.
    """
    root = ET.fromstring(xml_text)
    title = root.findtext('title', default='')
    description = root.findtext('description', default='')
    pages = []
    for page_el in root.findall('.//page'):
        page = {
            'id': page_el.get('id', ''),
            'title': page_el.findtext('title', default=''),
            'description': page_el.findtext('description', default=''),
            'importance': page_el.findtext('importance', default='medium'),
            'file_paths': [fp.text for fp in page_el.findall('.//file_path') if fp.text],
            'related_pages': [rel.text for rel in page_el.findall('.//related') if rel.text],
        }
        pages.append(page)
    return title, description, pages

def clean_and_format_content(content: str) -> str:
    """
    Cleans up HTML tags, source links, mermaid diagrams, and other patterns from content string.

    Args:
        content (str): The text content to clean.

    Returns:
        str: The cleaned text content.
    """
    if not isinstance(content, str):
        logger.warning("Content to clean is not a string. Returning as is.")
        return content

    content = re.sub(r'<details>.*?</details>', '', content, flags=re.DOTALL)
    content = re.sub(r'`Sources?: \[[^\]]*?\]\([^)]*?\)`', '', content, flags=re.IGNORECASE)
    content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
    content = re.sub(r'\[(.*?)\]\(https?://[^\s)]+\)', r'\1', content)
    content = re.sub(r'<[^>]*>', '', content)
    content = re.sub(r'```mermaid.*?```', '', content, flags=re.DOTALL)

    # Consolidate multiple spaces into a single space
    content = re.sub(r'\s+', ' ', content)

    # Clean up multiple blank lines to a maximum of two and strip leading/trailing whitespace
    content = re.sub(r'\n\s*\n', '\n\n', content).strip()
    return content

def generate_llms_txt(data: Dict[str, Dict[str, Any]], filename: str ="llms.txt") -> None:
    """
    Converts dictionary data into a formatted text file.

    Each page is formatted with its title, content (cleaned), importance,
    related pages, and file paths. The output is saved to `repo_wiki_generations/{filename}`.

    Args:
        data (Dict[str, Dict[str, Any]]): Dictionary where keys are page IDs and
                                           values are dicts of page attributes
                                           (title, content, importance, etc.).
        filename (str, optional): Name for the output text file. Defaults to "llms.txt".
    """
    try:
        output_dir = "repo_wiki_generations"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            for page_id, page_data in data.items():
                title = page_data.get('title', page_id.replace('-', ' ').title())
                content = page_data.get('content', '')
                importance = page_data.get('importance', 'N/A')
                related_pages_list = page_data.get('relatedPages', [])
                related_pages = ", ".join(related_pages_list) if isinstance(related_pages_list, list) and related_pages_list else 'None'

                file_paths_list = page_data.get('filePaths', [])
                file_paths = ", ".join(file_paths_list) if isinstance(file_paths_list, list) and file_paths_list else 'None'

                cleaned_content = clean_and_format_content(str(content))

                f.write(f"# {title}\n")
                f.write("-" * (len(title) + 2) + "\n\n")
                f.write(f"**ID:** {page_data.get('id', page_id)}\n")
                f.write(f"**Importance:** {str(importance).capitalize()}\n")
                f.write(f"**Related Pages:** {related_pages}\n")
                f.write(f"**Relevant Files:** {file_paths}\n\n")
                f.write("## Content\n")
                f.write(cleaned_content + "\n\n")
                f.write("---" * 10 + "\n\n")
        logger.info(f"Successfully generated {filename} at {filepath}")
    except Exception as e:
        logger.error(f"Error generating {filename}: {e}", exc_info=True)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Running tests for wiki_data_processor.py...")

    sample_data_llms = {
        "page-1": {
            "id": "page-1",
            "title": "Introduction to Project",
            "content": "This is the main introduction. ```mermaid\ngraph TD;\nA-->B;\n``` Some more text. <p>HTML paragraph</p> [A link](http://example.com)",
            "importance": "high",
            "relatedPages": ["page-2"],
            "filePaths": ["src/main.py", "README.md"]
        },
        "page-2": {
            "id": "page-2",
            "title": "Advanced Topics",
            "content": "Details about advanced stuff. Source: [docs](http://example.com/docs)",
            "importance": "medium",
            "relatedPages": [],
            "filePaths": ["src/advanced.py"]
        }
    }
    test_llms_filename = "test_processor_llms_output.txt" # Unique name
    generate_llms_txt(sample_data_llms, test_llms_filename)
    logger.info(f"Test '{test_llms_filename}' generated in 'repo_wiki_generations/' directory.")
    if os.path.exists(os.path.join("repo_wiki_generations", test_llms_filename)):
        logger.info(f"OK: {test_llms_filename} was created.")
    else:
        logger.error(f"FAIL: {test_llms_filename} was NOT created.")

    sample_xml_response = """
    ```xml
    <wiki_structure>
        <title>Test Wiki</title>
        <description>This is a test wiki.</description>
        <pages>
            <page id="p1">
                <title>Page 1</title>
                <description>Content for page 1.</description>
                <importance>high</importance>
                <file_path>file1.txt</file_path>
            </page>
        </pages>
    </wiki_structure>
    ```
    """
    try:
        logger.info("Testing XML extraction and parsing...")
        extracted_xml = extract_wiki_structure_xml(sample_xml_response)
        logger.info(f"Extracted XML: {extracted_xml[:100]}...")
        expected_xml_start = "<wiki_structure>"
        if extracted_xml.strip().startswith(expected_xml_start):
            logger.info("OK: XML extraction seems correct.")
        else:
            logger.error(f"FAIL: XML extraction incorrect. Expected start: '{expected_xml_start}', Got: '{extracted_xml[:50]}'")

        title, desc, pages = parse_wiki_structure(extracted_xml)
        logger.info(f"Parsed: Title='{title}', Desc='{desc}', Pages count={len(pages)}")
        if title == "Test Wiki" and len(pages) == 1 and pages[0]['title'] == "Page 1":
            logger.info("OK: XML parsing seems correct.")
        else:
            logger.error("FAIL: XML parsing produced unexpected results.")

    except ValueError as ve:
        logger.error(f"ERROR in XML processing test: {ve}")

    logger.info("Testing content cleaning...")
    dirty_text = "<details><summary>Click me</summary>Hidden details.</details>This is `Sources: [source](http://example.com)` visible. ![img](img.png) [link text](http://example.com/link)"
    cleaned_text = clean_and_format_content(dirty_text)
    expected_cleaned_text = "This is visible. link text" # Adjusted based on current regex
    logger.info(f"Cleaned text: '{cleaned_text}'")
    if cleaned_text == expected_cleaned_text:
        logger.info("OK: Content cleaning seems correct.")
    else:
        logger.error(f"FAIL: Content cleaning incorrect. Expected: '{expected_cleaned_text}', Got: '{cleaned_text}'")

    logger.info("Tests for wiki_data_processor.py finished.")
