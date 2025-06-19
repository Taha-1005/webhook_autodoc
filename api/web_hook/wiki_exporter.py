"""
This module handles the export of wiki content.
It includes functionality to:
- Take structured wiki data and generated page content.
- Post this data to an external API endpoint for export.
- Save the returned file (e.g., markdown or JSON) to a local 'downloads' directory.
"""
import os
import aiohttp
import json
import re
import logging
from typing import Dict, Any, Tuple

# Import models from the specified path
from api.web_hook.github_models import WikiStructure, WikiPageDetail, WikiSection

# Configure logger
logger = logging.getLogger(__name__)
# Basic config if not already set by another module
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

async def export_wiki_python(
    wiki_structure: WikiStructure,
    generated_pages: Dict[str, Dict[str, Any]], # Dict where key is page_id, value is dict with 'content'
    repo: str,
    repo_url: str,
    export_format: str = 'json',  # 'markdown' or 'json'
    api_base_url: str = ""
) -> Tuple[str | None, str | None]:
    """
    Exports the wiki content by calling an API and saving the result.

    Args:
        wiki_structure (WikiStructure): The structured representation of the wiki.
        generated_pages (Dict[str, Dict[str, Any]]): A dictionary where keys are page IDs
                                                     and values are dictionaries containing
                                                     at least a 'content' key.
        repo (str): The name of the repository (e.g., 'owner/repo_name').
        repo_url (str): The full URL of the repository.
        export_format (str, optional): The desired export format ('markdown' or 'json').
                                       Defaults to 'json'.
        api_base_url (str, optional): The base URL for the export API. If not provided,
                                      it's read from the "API_BASE_URL" environment
                                      variable or defaults to "http://localhost:8001".

    Returns:
        Tuple[str | None, str | None]: (error_message, file_path)
                                       Returns (None, file_path) on success.
                                       Returns (error_message, None) on failure.
    """
    logger.info(f"Exporting wiki for {repo} in {export_format} format")

    if not api_base_url:
        api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8001")

    export_error_message: str | None = None

    if not wiki_structure or not hasattr(wiki_structure, 'pages') or not wiki_structure.pages or not generated_pages:
        export_error_message = 'No wiki content to export (wiki_structure, pages, or generated_pages is empty)'
        logger.error(export_error_message)
        return export_error_message, None

    try:
        pages_to_export = []
        for page_model_instance in wiki_structure.pages:
            page_id = page_model_instance.id
            content = ""
            if page_id and page_id in generated_pages:
                # Ensure generated_pages[page_id] is a dict and has 'content'
                page_gen_data = generated_pages.get(page_id, {})
                if isinstance(page_gen_data, dict):
                    content = page_gen_data.get('content', "Content not generated")
                else:
                    logger.warning(f"generated_pages entry for {page_id} is not a dict, using default content.")
                    content = "Content not generated or invalid format"


            page_dict_for_export = page_model_instance.model_dump(exclude_none=True)
            pages_to_export.append({
                **page_dict_for_export,
                'content': content
            })

        if not pages_to_export:
            export_error_message = "Pages list is empty after processing for export."
            logger.error(export_error_message)
            return export_error_message, None

        payload = {
            'repo_url': repo_url,
            'type': 'github', # This might need to be more dynamic if other types are supported
            'pages': pages_to_export,
            'format': export_format
        }

        api_endpoint = f"{api_base_url.rstrip('/')}/export/wiki"
        logger.info(f"Posting to export API endpoint: {api_endpoint}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_endpoint,
                json=payload,
                headers={'Content-Type': 'application/json'}
            ) as response:
                if not response.ok: # response.ok is True if status_code < 400
                    error_text = "No error details available from API"
                    try:
                        error_text = await response.text()
                    except Exception as read_err:
                        logger.error(f"Could not read error response text: {read_err}")
                    raise Exception(f"Error exporting wiki (API call failed): {response.status} - {error_text}")

                content_disposition = response.headers.get('Content-Disposition')
                file_ext = 'md' if export_format == 'markdown' else 'json'
                repo_name_for_file = repo.replace("/", "_") # Sanitize repo name for filename
                filename = f"{repo_name_for_file}_wiki.{file_ext}"

                if content_disposition:
                    match = re.search(r'filename=(?:"([^"]+)"|([^;]+))', content_disposition)
                    if match:
                        extracted_filename = match.group(1) or match.group(2)
                        if extracted_filename:
                            filename = extracted_filename.strip()

                blob_data = await response.read()

                downloads_dir = "downloads"
                os.makedirs(downloads_dir, exist_ok=True)
                save_path = os.path.join(downloads_dir, filename)

                with open(save_path, 'wb') as f:
                    f.write(blob_data)

                logger.info(f"Wiki exported successfully to: {os.path.abspath(save_path)}")
                return None, os.path.abspath(save_path)

    except Exception as e:
        error_message = str(e)
        logger.error(f"Error during wiki export for repo {repo}: {error_message}", exc_info=True)
        return error_message, None
    finally:
        logger.info(f"Export process finished for repo {repo}.")

if __name__ == '__main__':
    import asyncio
    # Configure basic logging for tests
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Running tests for wiki_exporter.py...")

    async def test_export_functionality():
        logger.info("Setting up dummy data for export_wiki_python test...")
        # Create dummy WikiPageDetail instances
        dummy_page1_model = WikiPageDetail(
            id='p1',
            title='Test Page 1',
            description='Desc for P1',
            importance='high',
            file_paths=['file1.py'],
            related_pages=['p2'],
            content='Initial content for p1' # Content here is illustrative, exporter uses generated_pages
        )
        dummy_page2_model = WikiPageDetail(
            id='p2',
            title='Test Page 2',
            description='Desc for P2',
            importance='medium',
            file_paths=['file2.py'],
            related_pages=['p1'],
            content='Initial content for p2'
        )

        # Create dummy WikiSection instances
        dummy_section1_model = WikiSection(
            id='s1',
            title='Section 1',
            pages=['p1', 'p2'], # List of page IDs
            subsections=[]
        )

        dummy_wiki_structure = WikiStructure(
            id="dummy_wiki_id",
            title="Dummy Wiki Test",
            description="A test wiki structure for export_wiki_python.",
            pages=[dummy_page1_model, dummy_page2_model], # List of WikiPageDetail models
            sections=[dummy_section1_model],
            root_sections=['s1']
        )

        # Generated content that the main process would have created
        generated_content_for_pages = {
            "p1": {"content": "This is the fully generated content for page 1."},
            "p2": {"content": "This is the fully generated content for page 2."}
        }

        repo_name = "test_owner/test_repo"
        repo_full_url = "http://example.com/test_owner/test_repo"

        # Test with a mock API server if possible, or be prepared for network errors
        # For this standalone test, we'll use a common public API that might return an error,
        # or a non-existent local one to ensure the error handling path is tested.
        # Using a non-existent local URL to avoid external calls during typical testing.
        test_api_base = os.environ.get("TEST_API_BASE_URL", "http://localhost:9999") # Use a port unlikely to be in use

        logger.info(f"Attempting export to TEST API: {test_api_base} (JSON format)")
        err_json, path_json = await export_wiki_python(
            dummy_wiki_structure,
            generated_content_for_pages,
            repo_name,
            repo_full_url,
            export_format='json',
            api_base_url=test_api_base
        )

        if err_json:
            logger.info(f"OK (expected for test): JSON export failed as expected with non-existent API: {err_json}")
            # This is an expected outcome if the API endpoint isn't live.
            # For a real test, you'd mock aiohttp.ClientSession.post
        else:
            logger.info(f"UNEXPECTED SUCCESS or issue: JSON export succeeded, file at: {path_json}")
            # This case might occur if a service is accidentally running on test_api_base or if there's a logic flaw.
            if path_json and os.path.exists(path_json):
                 logger.info(f"File {path_json} was created. Please verify its contents.")
            else:
                 logger.warning(f"Export reported success but file path {path_json} is invalid or file does not exist.")


        logger.info(f"Attempting export to TEST API: {test_api_base} (Markdown format)")
        err_md, path_md = await export_wiki_python(
            dummy_wiki_structure,
            generated_content_for_pages,
            repo_name,
            repo_full_url,
            export_format='markdown',
            api_base_url=test_api_base
        )

        if err_md:
            logger.info(f"OK (expected for test): Markdown export failed as expected with non-existent API: {err_md}")
        else:
            logger.info(f"UNEXPECTED SUCCESS or issue: Markdown export succeeded, file at: {path_md}")
            if path_md and os.path.exists(path_md):
                 logger.info(f"File {path_md} was created. Please verify its contents.")
            else:
                 logger.warning(f"Export reported success but file path {path_md} is invalid or file does not exist.")

    # Running the async test function
    # In some environments, asyncio.run() might conflict if an event loop is already running.
    # If this script is run directly, asyncio.run() is appropriate.
    try:
        asyncio.run(test_export_functionality())
    except RuntimeError as e:
        if " asyncio.run() cannot be called from a running event loop" in str(e):
            logger.warning(f"Could not run test_export_functionality with asyncio.run() due to existing event loop: {e}")
            # If an event loop is already running (e.g. Jupyter, some IDEs),
            # you might need to schedule it differently, e.g. loop.create_task(test_export_functionality())
            # For this script, we'll assume it's run where asyncio.run() is fine.
        else:
            raise # Re-raise other RuntimeErrors

    logger.info("Tests for wiki_exporter.py finished.")
