#!/usr/bin/env python3
"""
Tool 1: HTML to JSON
Parses an HTML file containing an EOB claims table and outputs JSON.

Usage:
    python html_to_json.py <input.html> [output.json]
    
    If output.json is not specified, outputs to stdout.
"""

import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from html import unescape
from pathlib import Path

def normalize_provider(provider):
    """Normalize provider names for consistency"""
    if not provider:
        return ''
    p = provider.strip()
    if '<br' in p.lower():
        p = p.split('<br')[0]
    p = re.sub(r'\s*physicians?\s*&\s*facilities?\s*$', '', p, flags=re.IGNORECASE)
    p = re.sub(r'\s*hospital\s*$', '', p, flags=re.IGNORECASE)
    return p.strip()

def normalize_date_to_iso(date_str):
    """Convert date to ISO 8601 format (YYYY-MM-DD)"""
    if not date_str:
        return ''
    try:
        # Try MM/DD/YYYY format first
        date_obj = datetime.strptime(date_str, '%m/%d/%Y')
        return date_obj.strftime('%Y-%m-%d')
    except:
        try:
            # Try MM/DD/YY format
            date_obj = datetime.strptime(date_str, '%m/%d/%y')
            return date_obj.strftime('%Y-%m-%d')
        except:
            try:
                # Try YYYY-MM-DD format (already ISO)
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_str
            except:
                return date_str

def normalize_amount(amount_str):
    """Convert dollar amount to plain number (remove $ and commas)"""
    if not amount_str:
        return ''
    # Remove $, spaces, and commas
    normalized = re.sub(r'[\$,\s]', '', str(amount_str))
    # Return as string to preserve decimal precision
    return normalized

class HTMLTableParser(HTMLParser):
    """Parse HTML table into structured data"""
    def __init__(self):
        super().__init__()
        self.in_tbody = False
        self.in_row = False
        self.current_row = []
        self.rows = []
        self.in_data_cell = False
        self.cell_data = []
        
    def handle_starttag(self, tag, attrs):
        if tag == 'tbody':
            self.in_tbody = True
        elif tag == 'tr' and self.in_tbody:
            self.in_row = True
            self.current_row = []
        elif tag == 'td' and self.in_row:
            self.in_data_cell = True
            self.cell_data = []
            
    def handle_endtag(self, tag):
        if tag == 'tbody':
            self.in_tbody = False
        elif tag == 'tr' and self.in_row:
            if len(self.current_row) >= 6:
                self.rows.append(self.current_row.copy())
            self.in_row = False
            self.current_row = []
        elif tag == 'td' and self.in_data_cell:
            text = ' '.join(self.cell_data).strip()
            text = unescape(text)
            text = re.sub(r'\s+', ' ', text)
            self.current_row.append(text)
            self.cell_data = []
            self.in_data_cell = False
            
    def handle_data(self, data):
        if self.in_data_cell:
            self.cell_data.append(data)

def parse_html_to_json(html_path):
    """Parse HTML file to JSON with standardized schema"""
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    parser = HTMLTableParser()
    parser.feed(html_content)
    
    claims = []
    for row in parser.rows:
        # Skip rows with insufficient columns or header rows
        if len(row) < 6 or row[1] == 'Date':
            continue
        
        date_str = row[1].strip()
        member_raw = row[2].strip() if len(row) > 2 else ''
        provider_raw = row[3].strip() if len(row) > 3 else ''
        billed_raw = row[4].strip() if len(row) > 4 else ''
        plan_payment_raw = row[5].strip() if len(row) > 5 else ''
        you_owe_raw = row[6].strip() if len(row) > 6 else ''
        status_raw = row[7].strip() if len(row) > 7 else ''
        
        formatted_date = normalize_date_to_iso(date_str)
        if not formatted_date:
            continue
        
        provider = normalize_provider(provider_raw)
        member = member_raw.title().strip() if member_raw else ''
        
        claim = {
            'Date': formatted_date,
            'Member': member,
            'Facility/Physician': provider,
            'Service': '',
            'Billed Amt': normalize_amount(billed_raw),
            'Plan Payment': normalize_amount(plan_payment_raw),
            'You May Owe': normalize_amount(you_owe_raw),
            'Status': status_raw
        }
        claims.append(claim)
    
    return claims

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python html_to_json.py <input.html> [output.json] [--force]", file=sys.stderr)
        sys.exit(1)
    
    html_path = sys.argv[1]
    output_path = None
    force = False
    
    # Parse arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--force':
            force = True
            i += 1
        elif not sys.argv[i].startswith('--'):
            output_path = sys.argv[i]
            i += 1
        else:
            i += 1
    
    # Check if output file exists and skip unless --force
    if output_path and Path(output_path).exists() and not force:
        print(f"Skipping {output_path} (already exists, use --force to overwrite)", file=sys.stderr)
        sys.exit(0)
    
    claims = parse_html_to_json(html_path)
    json_output = json.dumps(claims, indent=2)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_output)
    else:
        print(json_output)

if __name__ == '__main__':
    main()

