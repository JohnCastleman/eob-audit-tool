#!/usr/bin/env python3
"""
Tool 5: Complete EOB Audit Processing
Orchestrates the entire EOB processing pipeline.

Usage:
    python process_eob_audit.py <directory> [--force]

Processes all HTML and PDF files in a directory, generates individual and composite outputs.
--force: Pass --force to individual tools to overwrite existing output files.
"""

import os
import sys
import subprocess
from pathlib import Path

def find_tool_path(tool_name):
    """Find the path to a tool in the same directory as this script"""
    script_dir = Path(__file__).parent
    tool_path = script_dir / tool_name
    if tool_path.exists():
        return str(tool_path)
    return tool_name  # Fallback to PATH

def process_directory(directory, force=False):
    """Process all HTML and PDF files in a directory"""
    directory = Path(directory)
    
    # Find HTML and PDF files
    html_files = list(directory.glob('*.html'))
    pdf_files = list(directory.glob('*.pdf'))
    
    print(f"Found {len(html_files)} HTML file(s) and {len(pdf_files)} PDF file(s)")
    
    # Tool paths
    html_to_json_tool = find_tool_path('html_to_json.py')
    pdf_to_json_tool = find_tool_path('pdf_to_json.py')
    json_to_md_tool = find_tool_path('json_to_md.py')
    merge_json_tool = find_tool_path('merge_json.py')
    
    # Track all JSON files for merging
    all_json_files = []
    all_md_files = []
    
    # Process HTML files
    for html_file in html_files:
        print(f"  Processing HTML: {html_file.name}")
        json_file = directory / f"{html_file.stem}.json"
        
        # Run html_to_json.py
        cmd = [sys.executable, html_to_json_tool, str(html_file), str(json_file)]
        if force:
            cmd.append('--force')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"    ERROR: {result.stderr}", file=sys.stderr)
            continue
        
        # Show skip message if output was written to stderr (skip message)
        if result.stderr and 'Skipping' in result.stderr:
            print(f"    {result.stderr.strip()}")
            continue
        
        all_json_files.append(str(json_file))
        
        # Run json_to_md.py
        md_file = directory / f"{html_file.stem}.md"
        cmd = [sys.executable, json_to_md_tool, str(json_file), str(md_file)]
        if force:
            cmd.append('--force')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"    ERROR: {result.stderr}", file=sys.stderr)
        elif result.stderr and 'Skipping' in result.stderr:
            print(f"    {result.stderr.strip()}")
        else:
            all_md_files.append(str(md_file))
            with open(json_file, 'r') as f:
                import json
                claims = json.load(f)
                print(f"    -> {len(claims)} claims -> {json_file.name}")
    
    # Process PDF files
    for pdf_file in pdf_files:
        print(f"  Processing PDF: {pdf_file.name}")
        json_file = directory / f"{pdf_file.stem}.json"
        
        # Run pdf_to_json.py
        cmd = [sys.executable, pdf_to_json_tool, str(pdf_file), str(json_file)]
        if force:
            cmd.append('--force')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"    ERROR: {result.stderr}", file=sys.stderr)
            continue
        
        # Show skip message if output was written to stderr (skip message)
        if result.stderr and 'Skipping' in result.stderr:
            print(f"    {result.stderr.strip()}")
            continue
        
        all_json_files.append(str(json_file))
        
        # Run json_to_md.py
        md_file = directory / f"{pdf_file.stem}.md"
        cmd = [sys.executable, json_to_md_tool, str(json_file), str(md_file)]
        if force:
            cmd.append('--force')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"    ERROR: {result.stderr}", file=sys.stderr)
        elif result.stderr and 'Skipping' in result.stderr:
            print(f"    {result.stderr.strip()}")
        else:
            all_md_files.append(str(md_file))
            with open(json_file, 'r') as f:
                import json
                claims = json.load(f)
                print(f"    -> {len(claims)} claims -> {json_file.name}")
    
    # Generate composite if we have any claims
    if all_json_files:
        print("\n  Generating composite markdown...")
        folder_name = directory.name
        
        # Run merge_json.py
        composite_json = directory / f"{folder_name}_composite.json"
        cmd = [sys.executable, merge_json_tool] + all_json_files + [str(composite_json)]
        if force:
            cmd.append('--force')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"    ERROR: {result.stderr}", file=sys.stderr)
        elif result.stderr and 'Skipping' in result.stderr:
            print(f"    {result.stderr.strip()}")
            return  # Can't continue without composite JSON
        else:
            # Update title in composite JSON
            import json
            with open(composite_json, 'r') as f:
                composite_data = json.load(f)
            composite_data['title'] = f"{folder_name} - Claims Summary (PDF and HTML)"
            with open(composite_json, 'w') as f:
                json.dump(composite_data, f, indent=2)
            
            # Run json_to_md.py with composite flag
            composite_md = directory / f"{folder_name}.md"
            cmd = [sys.executable, json_to_md_tool, str(composite_json), str(composite_md), '--composite']
            if force:
                cmd.append('--force')
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"    ERROR: {result.stderr}", file=sys.stderr)
            elif result.stderr and 'Skipping' in result.stderr:
                print(f"    {result.stderr.strip()}")
            else:
                print(f"    -> {len(composite_data['claims'])} total claims -> {composite_md.name}")
                print(f"       PDF only: {sum(1 for c in composite_data['claims'] if c.get('In PDF/HTML?') == 'PDF')}")
                print(f"       HTML only: {sum(1 for c in composite_data['claims'] if c.get('In PDF/HTML?') == 'HTML')}")
                print(f"       BOTH: {sum(1 for c in composite_data['claims'] if c.get('In PDF/HTML?') == 'BOTH')}")
            
            # Clean up temporary composite JSON
            composite_json.unlink()

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python process_eob_audit.py <directory> [--force]", file=sys.stderr)
        sys.exit(1)
    
    directory = sys.argv[1]
    force = '--force' in sys.argv
    
    print(f"EOB Audit Tool - Processing: {directory}")
    if force:
        print("Force mode: will overwrite existing files")
    print("=" * 60)
    
    process_directory(directory, force=force)
    
    print("=" * 60)
    print("Done!")

if __name__ == '__main__':
    main()

