#!/usr/bin/env python3
"""
Tool 4: Merge JSON files
Combines multiple JSON claim files into a single composite JSON with source tracking.

Usage:
    python merge_json.py <json1.json> <json2.json> ... [output.json]
    
    If output.json is not specified, outputs to stdout.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

def normalize_provider(provider):
    """Normalize provider names for matching"""
    if not provider:
        return ''
    p = provider.upper()
    # Remove common suffixes and normalize
    p = re.sub(r'\s*LTD\s*$', '', p)
    p = re.sub(r'\s*PLLC\s*$', '', p)
    p = re.sub(r'\s*PA\s*$', '', p)
    p = re.sub(r'\s*INC\.?\s*$', '', p)
    p = re.sub(r'\s+D\s+', ' D ', p)
    p = re.sub(r'\.', '', p)
    p = re.sub(r'\s+', ' ', p).strip()
    return p

def make_unique_key(claim):
    """Create unique key for a claim: Date + Billed + Plan Payment + You May Owe"""
    return f"{claim['Date']}|{claim['Billed Amt']}|{claim['Plan Payment']}|{claim['You May Owe']}"

def merge_claims(json_files, sources):
    """Merge claims from multiple JSON files with source tracking
    
    Args:
        json_files: List of JSON file paths
        sources: List of source labels ('PDF' or 'HTML')
    
    Returns:
        Tuple of (merged_claims_list, sub_files_list)
    """
    all_claims_dict = {}
    sub_files = []
    
    # Process each JSON file
    for json_file, source in zip(json_files, sources):
        with open(json_file, 'r', encoding='utf-8') as f:
            claims = json.load(f)
        
        # Track sub-file
        json_path = Path(json_file)
        sub_files.append(f"{json_path.stem}.md")
        
        # Add claims with source tracking
        for claim in claims:
            key = make_unique_key(claim)
            
            if key not in all_claims_dict:
                # New unique claim
                claim_copy = claim.copy()
                claim_copy['In PDF/HTML?'] = source
                all_claims_dict[key] = claim_copy
            else:
                # Duplicate claim - mark as BOTH
                existing_claim = all_claims_dict[key]
                existing_source = existing_claim.get('In PDF/HTML?', '')
                
                if existing_source != 'BOTH':
                    if source != existing_source:
                        # Mark as BOTH
                        all_claims_dict[key]['In PDF/HTML?'] = 'BOTH'
                    # else same source duplicate, keep first occurrence
    
    # Convert to list and sort by ISO date
    merged_claims = list(all_claims_dict.values())
    merged_claims.sort(key=lambda x: datetime.strptime(x['Date'], '%Y-%m-%d'), reverse=True)
    
    return merged_claims, sub_files

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python merge_json.py <json1.json> <json2.json> ... [output.json]", file=sys.stderr)
        sys.exit(1)
    
    # Parse arguments - determine source types from filenames or assume all PDF unless HTML detected
    json_files = []
    sources = []
    output_path = None
    
    # Process args - all .json files except the last one are inputs
    args = sys.argv[1:]
    
    if not args:
        print("Error: No arguments provided", file=sys.stderr)
        sys.exit(1)
    
    if len(args) < 2:
        print("Error: Need at least 2 arguments (input JSON files and output file)", file=sys.stderr)
        sys.exit(1)
    
    # All args except the last one are input JSON files
    input_json_files = args[:-1]
    output_path = args[-1]  # Last arg is output file
    
    for arg in input_json_files:
        if Path(arg).suffix != '.json':
            print(f"Warning: Skipping non-JSON file: {arg}", file=sys.stderr)
            continue
        json_files.append(arg)
        # Determine source from filename
        # HTML files typically contain "BCBS" or ".html" in their original filename or have "claims" pattern
        filename = Path(arg).name
        if 'BCBS' in filename or filename.startswith('BCBS') or '.html' in str(arg):
            sources.append('HTML')
        else:
            sources.append('PDF')
    
    # If last arg doesn't look like output JSON, set it anyway
    if Path(output_path).suffix != '.json':
        print(f"Warning: Output path doesn't end with .json: {output_path}", file=sys.stderr)
    
    # Merge claims
    merged_claims, sub_files = merge_claims(json_files, sources)
    
    # Create output structure
    output = {
        'claims': merged_claims,
        'sub_files': sub_files,
        'title': None  # Will be set by caller
    }
    
    json_output = json.dumps(output, indent=2)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_output)
    else:
        print(json_output)

if __name__ == '__main__':
    main()

