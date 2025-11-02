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
    """Parse HTML table into structured data - supports both traditional and mobile-stacked formats"""
    def __init__(self):
        super().__init__()
        self.in_tbody = False
        self.in_row = False
        self.current_row = []
        self.rows = []  # For traditional table format
        self.in_data_cell = False
        self.cell_data = []
        
        # For mobile-stacked (key-value) format
        self.current_key = None
        self.current_value = None
        self.in_key_cell = False
        self.in_value_cell = False
        self.current_claim = {}
        self.claims = []  # For mobile-stacked format
        self.current_tr_class = None  # Track current row's class
        self.in_a_tag = False  # Track if we're inside an <a> tag
        self.current_a_title = None  # Track title attribute of current <a> tag
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == 'tbody':
            self.in_tbody = True
        elif tag == 'tr':
            if self.in_tbody:
                self.in_row = True
                self.current_row = []
                # Track row class for mobile-stacked format
                self.current_tr_class = attrs_dict.get('class', '')
                # Check if this is a key-value row format (mobile-stacked)
                if 'st-key' in self.current_tr_class or 'st-val' in self.current_tr_class:
                    self.current_key = None
                    self.current_value = None
        elif tag == 'td':
            if self.in_row:
                # Check for mobile-stacked format
                cell_class = attrs_dict.get('class', '')
                if 'st-key' in cell_class:
                    self.in_key_cell = True
                    self.in_data_cell = False
                    self.cell_data = []
                elif 'st-val' in cell_class:
                    self.in_value_cell = True
                    self.in_data_cell = False
                    self.cell_data = []
                else:
                    # Traditional table format
                    self.in_data_cell = True
                    self.cell_data = []
        elif tag == 'a':
            if self.in_value_cell:
                self.in_a_tag = True
                # Extract title attribute if present
                attrs_dict = dict(attrs)
                self.current_a_title = attrs_dict.get('title', '')
                        
    def handle_endtag(self, tag):
        if tag == 'tbody':
            self.in_tbody = False
        elif tag == 'tr':
            if self.in_row:
                # Traditional table format
                if len(self.current_row) >= 6:
                    self.rows.append(self.current_row.copy())
                self.in_row = False
                self.current_row = []
                
                # Mobile-stacked format: save current key-value pair
                if self.current_key and self.current_value is not None:
                    key_lower = self.current_key.lower().strip()
                    
                    # If this is a Date field and we already have a claim with a date, save the previous claim
                    if 'date' in key_lower and 'date' in self.current_claim and self.current_claim['date']:
                        self.claims.append(self.current_claim.copy())
                        self.current_claim = {}
                    
                    # Map keys to our schema
                    if 'date' in key_lower:
                        self.current_claim['date'] = self.current_value.strip()
                    elif 'member' in key_lower:
                        self.current_claim['member'] = self.current_value.strip()
                    elif 'facility' in key_lower or 'physician' in key_lower or 'merchant' in key_lower:
                        # Only set if not already set (prefer first occurrence)
                        if 'provider' not in self.current_claim:
                            self.current_claim['provider'] = self.current_value.strip()
                    elif 'billed' in key_lower and 'amount' in key_lower:
                        self.current_claim['billed'] = self.current_value.strip()
                    elif 'plan' in key_lower and 'payment' in key_lower:
                        self.current_claim['plan_payment'] = self.current_value.strip()
                    elif 'you may owe' in key_lower or 'your cost' in key_lower:
                        self.current_claim['you_owe'] = self.current_value.strip()
                    elif 'status' in key_lower:
                        self.current_claim['status'] = self.current_value.strip()
                    elif 'eob' in key_lower or 'reference' in key_lower:
                        # EOB number is in the <a> tag's title attribute
                        # The title was captured when we saw the <a> tag in the value cell
                        # Use the stored title if available, otherwise try to extract from value text
                        eob_value = ''
                        if self.current_a_title:
                            eob_value = self.current_a_title
                        elif self.current_value:
                            # Try to extract from value text as fallback
                            eob_value = self.current_value.strip()
                        self.current_claim['eob_reference'] = eob_value
                        # Don't reset current_a_title yet - it might be used for this key-value pair
                    
                    # Check if this row indicates end of a claim (has "Details" button or extra-border class)
                    if (self.current_value and 'details' in self.current_value.lower()) or 'extra-border' in str(self.current_tr_class):
                        # Save claim if it has a date
                        if 'date' in self.current_claim and self.current_claim['date']:
                            self.claims.append(self.current_claim.copy())
                            self.current_claim = {}
                
                self.current_key = None
                self.current_value = None
                # Reset current_a_title when moving to next row
                self.current_a_title = None
        elif tag == 'td':
            if self.in_data_cell:
                # Traditional format
                text = ' '.join(self.cell_data).strip()
                text = unescape(text)
                text = re.sub(r'\s+', ' ', text)
                self.current_row.append(text)
                self.cell_data = []
                self.in_data_cell = False
            elif self.in_key_cell:
                # Mobile-stacked format: key
                self.current_key = ' '.join(self.cell_data).strip()
                self.current_key = unescape(self.current_key)
                self.current_key = re.sub(r'\s+', ' ', self.current_key)
                self.cell_data = []
                self.in_key_cell = False
            elif self.in_value_cell:
                # Mobile-stacked format: value
                text = ' '.join(self.cell_data).strip()
                text = unescape(text)
                text = re.sub(r'\s+', ' ', text)
                self.current_value = text
                self.cell_data = []
                self.in_value_cell = False
                # Reset current_a_title after processing value cell (it was captured if present)
                if self.current_a_title:
                    # Keep it for now - will be used when processing the key-value pair
                    pass
        elif tag == 'a':
            if self.in_a_tag:
                self.in_a_tag = False
                # Don't reset current_a_title here - keep it until we process the key-value pair
                # It will be reset when we process the EOB/REFERENCE key or when starting a new row
                       
    def handle_data(self, data):
        if self.in_data_cell or self.in_key_cell or self.in_value_cell:
            self.cell_data.append(data)

def parse_html_to_json(html_path):
    """Parse HTML file to JSON with standardized schema"""
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    parser = HTMLTableParser()
    parser.feed(html_content)
    
    # Save any remaining claim at end of parsing
    if parser.current_claim and 'date' in parser.current_claim and parser.current_claim['date']:
        parser.claims.append(parser.current_claim.copy())
    
    claims = []
    
    # First try mobile-stacked format (key-value pairs)
    if parser.claims:
        for claim_data in parser.claims:
            date_str = claim_data.get('date', '').strip()
            if not date_str:
                continue
            
            # Skip rows where date doesn't look like a date
            if not date_str or ('/' not in date_str and '-' not in date_str and len(date_str) < 6):
                continue
            
            formatted_date = normalize_date_to_iso(date_str)
            if not formatted_date:
                continue
            
            member_raw = claim_data.get('member', '').strip()
            provider_raw = claim_data.get('provider', '').strip()
            billed_raw = claim_data.get('billed', '').strip()
            plan_payment_raw = claim_data.get('plan_payment', '').strip()
            you_owe_raw = claim_data.get('you_owe', '').strip()
            status_raw = claim_data.get('status', '').strip()
            eob_reference_raw = claim_data.get('eob_reference', '').strip()
            
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
            # Add EOB Reference if available (for deduplication only)
            if eob_reference_raw:
                claim['EOB Reference'] = eob_reference_raw
            
            # Track whether this claim has a PDF icon (has EOB reference)
            # This will be used later to determine if claim should match PDFs
            claim['has_pdf_icon'] = bool(eob_reference_raw and eob_reference_raw.strip())
            
            claims.append(claim)
        
        # Deduplicate claims (may appear twice in HTML due to mobile/desktop views)
        # Use Date + Facility/Physician + Billed Amt + EOB Reference + Status as unique key
        # Include Status to better distinguish claims (especially refunds)
        seen = {}
        unique_claims = []
        for claim in claims:
            # Include EOB reference and Status in key to better distinguish claims
            eob = claim.get('EOB Reference', '') if 'EOB Reference' in claim else ''
            status = claim.get('Status', '')
            key = (claim.get('Date'), claim.get('Facility/Physician'), claim.get('Billed Amt'), eob, status)
            if key not in seen:
                seen[key] = True
                # Remove EOB Reference from final output (it was only used for deduplication)
                # Keep has_pdf_icon field for use in merging
                if 'EOB Reference' in claim:
                    del claim['EOB Reference']
                unique_claims.append(claim)
        
        return unique_claims
    
    # Fall back to traditional table format
    for row in parser.rows:
        # Skip rows with insufficient columns or header rows
        if len(row) < 6 or row[1] == 'Date':
            continue
        
        date_str = row[1].strip()
        # Skip rows where date doesn't look like a date (e.g., just a number or empty)
        # Dates should contain at least a slash or dash separator
        if not date_str or ('/' not in date_str and '-' not in date_str and len(date_str) < 6):
            continue
        
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
    
    # Deduplicate claims (may appear twice in HTML due to mobile/desktop views)
    # Use Date + Facility/Physician + Billed Amt as unique key
    seen = {}
    unique_claims = []
    for claim in claims:
        key = (claim.get('Date'), claim.get('Facility/Physician'), claim.get('Billed Amt'))
        if key not in seen:
            seen[key] = True
            unique_claims.append(claim)
    
    return unique_claims

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

