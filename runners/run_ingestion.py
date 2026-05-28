import argparse
import sys
from pathlib import Path
from tools.csv_tools import detect_csv_category, propose_and_preview_mapping, prompt_user_approval, ingest_csv_data

def main():
    parser = argparse.ArgumentParser(description="Test CSV parsing and BigQuery upload.")
    parser.add_argument("file_path", type=str, help="Path to the CSV file to ingest.")
    parser.add_argument("--category", type=str, default=None, help="Clinical category (e.g. patients, medications, conditions, observations).")
    parser.add_argument("--yes", action="store_true", help="Auto-approve mapping and bypass interactive prompt.")
    
    args = parser.parse_args()
    file_path = Path(args.file_path)
    
    if not file_path.exists():
        print(f"Error: File not found at '{file_path}'")
        sys.exit(1)
        
    print(f"Processing file: {file_path}")
    
    # 1. Detect Category
    category = args.category
    if not category:
        category = detect_csv_category(file_path)
        print(f"Auto-detected category: '{category}'")
    else:
        print(f"Using specified category: '{category}'")
        
    # 2. Propose Mapping
    print("Generating schema mapping proposal...")
    preview_markdown = propose_and_preview_mapping(file_path)
    
    # 3. Handle Approval
    approved = True
    if not args.yes:
        approved = prompt_user_approval(preview_markdown)
    else:
        print("\n[AI Proposed CSV Schema Mapping Preview (Auto-Approved)]")
        print(preview_markdown)
        print("\n")
        
    # 4. Execute Ingestion
    print(f"Executing ingestion for category '{category}'...")
    result = ingest_csv_data(file_path, category, approved)
    
    if result.get("success"):
        print(f"\nSUCCESS: {result.get('message')}")
    else:
        print(f"\nFAILURE: {result.get('error') or result.get('message')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
