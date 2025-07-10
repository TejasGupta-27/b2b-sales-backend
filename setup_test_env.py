"""
Setup script to prepare the test environment for pitch deck testing.
This creates necessary directories and sample files.
"""
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("setup_test_env")

def create_directory_structure():
    """Create the necessary directory structure for testing"""
    # Create base directories
    directories = [
        "Data/assets",
        "Data/json",
        "test_outputs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {directory}")

def create_sample_category_file():
    """Create a sample laptop.json category file"""
    category_file = Path("Data/json/laptop.json")
    
    # Only create if it doesn't exist
    if not category_file.exists():
        content = '''
{
    "name": "laptop",
    "localized": {
        "en": "Laptop",
        "ja": "ノートパソコン",
        "fr": "Ordinateur portable",
        "de": "Laptop",
        "es": "Portátil"
    },
    "keywords": ["laptop", "notebook", "portable computer"],
    "keywords_ja": ["ノートパソコン", "ラップトップ", "ノートPC"]
}
'''
        with open(category_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Created sample category file: {category_file}")

def create_sample_company_logo():
    """Create a placeholder company logo if it doesn't exist"""
    logo_path = Path("Data/assets/company_logo.png")
    
    if not logo_path.exists():
        # Create a simple text file to simulate logo
        logo_path.parent.mkdir(parents=True, exist_ok=True)
        with open(logo_path, "w") as f:
            f.write("PLACEHOLDER LOGO FILE")
        logger.info(f"Created placeholder logo file: {logo_path}")
        logger.info("Note: This is just a placeholder file, not a real image.")

def setup_environment():
    """Setup the full test environment"""
    create_directory_structure()
    create_sample_category_file()
    create_sample_company_logo()
    
    logger.info("Test environment setup complete!")

if __name__ == "__main__":
    setup_environment()
