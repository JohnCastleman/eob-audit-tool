#!/usr/bin/env python3
"""
Tool 3: JSON to Markdown
Generates a markdown table from JSON claim data.

Usage:
    python json_to_md.py <input.json> [output.md] [--title TITLE] [--composite]
    
    If output.md is not specified, outputs to stdout.
    --title: Override the default title
    --composite: Add links to sub-files at bottom (if available in JSON metadata)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

def format_date_for_display(date_str):
    """Convert ISO 8601 date (YYYY-MM-DD) to MM/DD/YY display format"""
    if not date_str:
        return ''
    try:
        # Try ISO format first
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime('%m/%d/%y')
    except:
        # Fallback for already-formatted dates or empty strings
        return date_str

def format_amount_for_display(amount_str):
    """Convert numeric amount to formatted display with $ and commas"""
    if not amount_str:
        return ''
    try:
        # Try to parse as float to handle edge cases
        amount_float = float(str(amount_str))
        # Format with 2 decimal places
        return f"${amount_float:,.2f}"
    except:
        # Fallback: just return as-is
        return amount_str

def generate_markdown_from_json(json_data, title, include_source_col=False, sort_reverse=True, sub_files=None):
    """Generate markdown table from JSON data
    
    Args:
        json_data: List of claim dictionaries
        title: Title for the markdown document
        include_source_col: Whether to include the In PDF/HTML? column
        sort_reverse: Sort in reverse chronological order (newest first)
        sub_files: Optional list of file paths to reference at bottom
    """
    # Sort claims by date if sort_reverse is enabled
    if sort_reverse:
        try:
            json_data = sorted(json_data, key=lambda x: datetime.strptime(x['Date'], '%Y-%m-%d'), reverse=True)
        except (KeyError, ValueError):
            # If sorting fails, use unsorted data
            pass
    
    md_content = f"# {title}\n\n"
    
    if include_source_col:
        md_content += "| Date | Member | Facility/Physician | Service | Billed Amt | Plan Payment | You May Owe | Status | In PDF/HTML? |\n"
        md_content += "|------|--------|-------------------|---------|------------|--------------|-------------|--------|--------------|\n"
        
        for claim in json_data:
            date_display = format_date_for_display(claim.get('Date', ''))
            billed_display = format_amount_for_display(claim.get('Billed Amt', ''))
            plan_payment_display = format_amount_for_display(claim.get('Plan Payment', ''))
            you_may_owe_display = format_amount_for_display(claim.get('You May Owe', ''))
            md_content += f"| {date_display} | {claim.get('Member', '')} | {claim.get('Facility/Physician', '')} | {claim.get('Service', '')} | {billed_display} | {plan_payment_display} | {you_may_owe_display} | {claim.get('Status', '')} | {claim.get('In PDF/HTML?', '')} |\n"
    else:
        md_content += "| Date | Member | Facility/Physician | Service | Billed Amt | Plan Payment | You May Owe | Status |\n"
        md_content += "|------|--------|-------------------|---------|------------|--------------|-------------|--------|\n"
        
        for claim in json_data:
            date_display = format_date_for_display(claim.get('Date', ''))
            billed_display = format_amount_for_display(claim.get('Billed Amt', ''))
            plan_payment_display = format_amount_for_display(claim.get('Plan Payment', ''))
            you_may_owe_display = format_amount_for_display(claim.get('You May Owe', ''))
            md_content += f"| {date_display} | {claim.get('Member', '')} | {claim.get('Facility/Physician', '')} | {claim.get('Service', '')} | {billed_display} | {plan_payment_display} | {you_may_owe_display} | {claim.get('Status', '')} |\n"
    
    # Add references to sub-files if provided
    if sub_files:
        md_content += "\n## Related Files\n\n"
        for sub_file in sub_files:
            md_content += f"- [{Path(sub_file).name}]({sub_file})\n"
    
    return md_content

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python json_to_md.py <input.json> [output.md] [--title TITLE] [--composite] [--force]", file=sys.stderr)
        sys.exit(1)
    
    json_path = sys.argv[1]
    output_path = None
    title = None
    composite = False
    force = False
    
    # Parse arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--title':
            title = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--composite':
            composite = True
            i += 1
        elif sys.argv[i] == '--force':
            force = True
            i += 1
        elif not sys.argv[i].startswith('--'):
            output_path = sys.argv[i]
            i += 1
        else:
            i += 1
    
    # Load JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Determine if this is a composite JSON (has metadata)
    json_file = Path(json_path)
    claims = data if isinstance(data, list) else data.get('claims', [])
    
    # Set title
    if not title:
        if isinstance(data, dict) and 'title' in data:
            title = data['title']
        else:
            title = f"{json_file.stem} Claims Summary"
    
    # Check for composite metadata
    include_source_col = '_composite' in json_path or composite
    sub_files = data.get('sub_files', []) if isinstance(data, dict) else None
    
    # Check if output file exists and skip unless --force
    if output_path and Path(output_path).exists() and not force:
        print(f"Skipping {output_path} (already exists, use --force to overwrite)", file=sys.stderr)
        sys.exit(0)
    
    # Generate markdown
    md_content = generate_markdown_from_json(
        claims, 
        title, 
        include_source_col=include_source_col,
        sub_files=sub_files
    )
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
    else:
        print(md_content)

if __name__ == '__main__':
    main()

