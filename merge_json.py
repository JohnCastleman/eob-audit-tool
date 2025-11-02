#!/usr/bin/env python3
"""
Tool 4: Merge JSON files
Combines multiple JSON claim files into a single composite JSON with source tracking.

Usage:
    python merge_json.py <json1.json> <json2.json> ... [output.json] [--force]
    
    If output.json is not specified, outputs to stdout.
    --force: Overwrite existing output file.
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

def make_unique_key(claim, include_status=False):
    """Create unique key for a claim
    
    Args:
        claim: Claim dictionary
        include_status: If True, include Status in key (for HTML deduplication)
    
    Returns:
        Unique key string
    """
    key = f"{claim['Date']}|{claim['Billed Amt']}|{claim['Plan Payment']}|{claim['You May Owe']}"
    if include_status:
        status = claim.get('Status', '')
        key += f"|{status}"
    return key

def make_pdf_matching_key(claim):
    """Create 4-field key for matching PDF claims to HTML claims"""
    return f"{claim['Date']}|{claim['Billed Amt']}|{claim['Plan Payment']}|{claim['You May Owe']}"

def merge_claims(json_files, sources):
    """Merge claims from multiple JSON files with source tracking
    
    Args:
        json_files: List of JSON file paths
        sources: List of source labels ('PDF' or 'HTML')
    
    Returns:
        Tuple of (merged_claims_list, sub_files_list)
    """
    # Separate dictionaries for HTML (5-field key) and PDF (4-field key)
    html_claims_dict = {}  # Uses 5-field key (includes Status)
    pdf_claims_dict = {}  # Uses 4-field key
    all_claims_dict = {}  # Final merged results
    sub_files = []
    
    # First pass: collect all claims by source type with appropriate keys
    for json_file, source in zip(json_files, sources):
        with open(json_file, 'r', encoding='utf-8') as f:
            claims = json.load(f)
        
        # Track sub-file
        json_path = Path(json_file)
        sub_files.append(f"{json_path.stem}.md")
        
        if source == 'HTML':
            # HTML claims: use 5-field key (Date + Billed + Plan Payment + You May Owe + Status)
            for claim in claims:
                key = make_unique_key(claim, include_status=True)
                
                if key not in html_claims_dict:
                    claim_copy = claim.copy()
                    # Use "(HTML)" for HTML claims without PDF icon
                    if not claim.get('has_pdf_icon', True):
                        claim_copy['In PDF/HTML?'] = '(HTML)'
                    else:
                        claim_copy['In PDF/HTML?'] = 'HTML'
                    # Keep has_pdf_icon for now (will be used for PDF matching)
                    html_claims_dict[key] = claim_copy
                # else: duplicate within HTML (shouldn't happen after html_to_json dedup, but keep first)
        else:  # PDF
            # PDF claims: use 4-field key (Date + Billed + Plan Payment + You May Owe)
            for claim in claims:
                key = make_unique_key(claim, include_status=False)
                
                if key not in pdf_claims_dict:
                    claim_copy = claim.copy()
                    claim_copy['In PDF/HTML?'] = 'PDF'
                    pdf_claims_dict[key] = claim_copy
                # else: duplicate within PDF (shouldn't happen, but keep first)
    
    # Second pass: merge HTML and PDF, matching PDF claims to HTML claims with PDF icons
    # Use 4-field key for cross-source matching
    matched_pdf_keys = set()
    html_claims_matched_to_pdf = set()  # Track which HTML 5-field keys matched PDFs
    
    # First pass: identify all HTML claims that match PDFs (by 4-field key)
    # Build a mapping from PDF 4-field keys to lists of matching HTML 5-field keys
    pdf_to_html_matches = {}  # pdf_key_4field -> list of html_key_5field
    
    for html_key_5field, html_claim in html_claims_dict.items():
        # Only consider HTML claims with PDF icons for matching
        if not html_claim.get('has_pdf_icon', True):
            continue
        
        # Extract 4-field key for potential PDF matching
        pdf_key_4field = make_pdf_matching_key(html_claim)
        
        # Check if there's a matching PDF claim
        if pdf_key_4field in pdf_claims_dict:
            matched_pdf_keys.add(pdf_key_4field)
            if pdf_key_4field not in pdf_to_html_matches:
                pdf_to_html_matches[pdf_key_4field] = []
            pdf_to_html_matches[pdf_key_4field].append(html_key_5field)
            html_claims_matched_to_pdf.add(html_key_5field)
    
    # HTML claims are the "master" records - add all HTML claims first
    # When a PDF matches, the HTML claim becomes BOTH (HTML is authoritative)
    for html_key_5field, html_claim in html_claims_dict.items():
        pdf_key_4field = make_pdf_matching_key(html_claim)
        
        # If this HTML claim matched a PDF, mark it as BOTH
        if html_key_5field in html_claims_matched_to_pdf:
            # HTML claim matched a PDF - mark as BOTH (HTML is the master)
            claim_copy = html_claim.copy()
            claim_copy['In PDF/HTML?'] = 'BOTH'
            if 'has_pdf_icon' in claim_copy:
                del claim_copy['has_pdf_icon']
            # Use 5-field key to preserve unique Status values for HTML claims
            all_claims_dict[f"HTML_{html_key_5field}"] = claim_copy
        else:
            # Not matched to PDF, add as HTML-only
            claim_copy = html_claim.copy()
            # Remove has_pdf_icon from final output
            if 'has_pdf_icon' in claim_copy:
                del claim_copy['has_pdf_icon']
            # Determine label based on PDF icon
            if not html_claim.get('has_pdf_icon', True):
                claim_copy['In PDF/HTML?'] = '(HTML)'
            else:
                claim_copy['In PDF/HTML?'] = 'HTML'
            # Use a composite key to ensure uniqueness (5-field key prefixed)
            all_claims_dict[f"HTML_{html_key_5field}"] = claim_copy
    
    # Add unmatched PDF claims
    for pdf_key_4field, pdf_claim in pdf_claims_dict.items():
        if pdf_key_4field not in matched_pdf_keys:
            all_claims_dict[pdf_key_4field] = pdf_claim
    
    # Convert to list and sort by ISO date
    merged_claims = list(all_claims_dict.values())
    
    def sort_key(claim):
        """Get sort key for claim, handling invalid dates"""
        date_str = claim.get('Date', '')
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            # Invalid date - put at end (use a very old date)
            return datetime(1900, 1, 1)
    
    merged_claims.sort(key=sort_key, reverse=True)
    
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
    
    # Parse arguments
    force = False
    args = sys.argv[1:]
    
    # Extract --force flag
    if '--force' in args:
        force = True
        args = [arg for arg in args if arg != '--force']
    
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
    
    # Check if output file exists and skip unless --force
    if output_path and Path(output_path).exists() and not force:
        print(f"Skipping {output_path} (already exists, use --force to overwrite)", file=sys.stderr)
        sys.exit(0)
    
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

