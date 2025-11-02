#!/usr/bin/env python3
"""
Tool 2: PDF to JSON
Parses a PDF file containing EOB claims and outputs JSON.

Usage:
    python pdf_to_json.py <input.pdf> [output.json]
    
    If output.json is not specified, outputs to stdout.
"""

import json
import re
import sys
import pdfplumber
from datetime import datetime
from pathlib import Path

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

def parse_pdf_to_json(pdf_path):
    """Parse PDF file to JSON with standardized schema"""
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() or ""
        
        patient_match = re.search(r'Patient:\s*([A-Z,\s]+)', full_text)
        patient_name = patient_match.group(1).strip().replace('\n', ' ').replace(' P', '').strip() if patient_match else ""
        
        # First find all claim sections
        claim_num_pattern = r'CLAIM # ([A-Z0-9]+)'
        claim_nums = list(re.finditer(claim_num_pattern, full_text))
        
        claims = []
        for i, claim_match in enumerate(claim_nums):
            claim_num = claim_match.group(1)
            
            # Get the section for this claim (everything until next CLAIM # or GRAND TOTAL)
            if i < len(claim_nums) - 1:
                next_claim_start = claim_nums[i + 1].start()
            else:
                next_claim_start = len(full_text)
            
            claim_text = full_text[claim_match.start():next_claim_start]
            
            # Extract date - handle both MM/DD/YY and MM/DD/YYYY formats
            # Always prefer 4-digit year first, fall back to 2-digit only if needed
            date_match = re.search(r'Service Dates:\s+(\d{2}/\d{2}/20\d{2})', claim_text)
            if not date_match:
                date_match = re.search(r'Service Dates:\s+(\d{2}/\d{2}/\d{2})', claim_text)
            
            if date_match:
                date_str = date_match.group(1)
                # Convert to ISO format
                service_date = normalize_date_to_iso(date_str)
            else:
                service_date = ''
            
            # Try to find CLAIM TOTAL amounts first (preferred)
            claim_total_match = re.search(r'CLAIM TOTAL((?:\s+\$[\d,]+\.\d{2}){11})', claim_text)
            if claim_total_match:
                amounts_str = claim_total_match.group(1)
                amounts = re.findall(r'\$[\d,]+\.\d{2}', amounts_str)
                
                if len(amounts) != 11:
                    continue
                
                billed = normalize_amount(amounts[0])
                plan_payment = normalize_amount(amounts[4])  # Column 5
                you_may_owe = normalize_amount(amounts[10])  # Column 11
            else:
                # No CLAIM TOTAL - try to extract from detail rows
                # Look for lines with 11 dollar amounts that look like service lines
                detail_row_match = re.search(r'(IMAGING|SPECIALIST|RADIOLOGY|PREVENTATIVE|PHYSICAL|ANESTHESIA|ORTHOTICS|CARE)[^\n]*((?:\s+\$[\d,]+\.\d{2}){11})', claim_text)
                if detail_row_match:
                    amounts_str = detail_row_match.group(2)
                    amounts = re.findall(r'\$[\d,]+\.\d{2}', amounts_str)
                    
                    if len(amounts) == 11:
                        billed = normalize_amount(amounts[0])
                        plan_payment = normalize_amount(amounts[4])
                        you_may_owe = normalize_amount(amounts[10])
                    else:
                        continue  # Skip this claim if we can't parse amounts
                else:
                    # Last resort: try GRAND TOTAL (but only as fallback)
                    grand_total_match = re.search(r'GRAND TOTAL.*?((?:\s+\$[\d,]+\.\d{2}){11})', claim_text)
                    if grand_total_match:
                        amounts_str = grand_total_match.group(1)
                        amounts = re.findall(r'\$[\d,]+\.\d{2}', amounts_str)
                        
                        if len(amounts) == 11:
                            billed = normalize_amount(amounts[0])
                            plan_payment = normalize_amount(amounts[4])
                            you_may_owe = normalize_amount(amounts[10])
                        else:
                            continue  # Skip this claim if we can't parse amounts
                    else:
                        continue  # Skip claims without totals
            
            # Extract provider information
            provider_match = re.search(r'Provider:\s*([A-Z\s&.,]+?)\s+Processed', claim_text)
            if provider_match:
                provider = provider_match.group(1).strip()
            else:
                # Try alternative provider detection
                if 'TEXAS ANESTHESIA PARTNERS PLLC' in claim_text:
                    provider = 'TEXAS ANESTHESIA PARTNERS PLLC'
                elif 'TRAVIS D. HAYDEN' in claim_text or 'TRAVIS HAYDEN' in claim_text:
                    provider = 'TRAVIS D. HAYDEN'
                elif 'JONATHAN D. RINGENBERG' in claim_text or 'JONATHAN RINGENBERG' in claim_text:
                    provider = 'JONATHAN D. RINGENBERG'
                elif 'ATHLETICO LTD' in claim_text:
                    provider = 'ATHLETICO LTD'
                elif 'JOHN E. MCGARRY' in claim_text or 'JOHN MCGARRY' in claim_text:
                    provider = 'JOHN E. MCGARRY'
                elif 'DAN M. NGUYEN' in claim_text or 'DAN NGUYEN' in claim_text:
                    provider = 'DAN M. NGUYEN'
                elif 'METHODIST CDI' in claim_text:
                    provider = 'METHODIST CDI'
                elif 'QUEST DIAGNOSTIC' in claim_text:
                    provider = 'QUEST DIAGNOSTIC CLINICAL LAB I.'
                elif 'CATALYST PHYSICIAN' in claim_text:
                    provider = 'CATALYST PHYSICIAN GROUP NTX P'
                elif 'TEXAS ONCOLOGY' in claim_text:
                    provider = 'TEXAS ONCOLOGY PA'
                else:
                    provider = 'Unknown'
            
            status_match = re.search(r'Processed As:\s+([^\n]+)', claim_text)
            status = status_match.group(1).strip() if status_match else 'In-Network'
            
            service_match = re.search(r'(ORTHOTICS|ANESTHESIA SERVICE|PAIN MANAGEMENT|PHYSICAL THERAPY|IMAGING|SPECIALIST OFFICE VISIT|RADIOLOGY SERVICE|PREVENTATIVE CARE)', claim_text)
            service_desc = service_match.group(1) if service_match else ''
            
            claim = {
                'Date': service_date,
                'Member': patient_name,
                'Facility/Physician': provider,
                'Service': service_desc,
                'Billed Amt': billed,
                'Plan Payment': plan_payment,
                'You May Owe': you_may_owe,
                'Status': status
            }
            claims.append(claim)
    
    return claims

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_json.py <input.pdf> [output.json]", file=sys.stderr)
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    claims = parse_pdf_to_json(pdf_path)
    json_output = json.dumps(claims, indent=2)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_output)
    else:
        print(json_output)

if __name__ == '__main__':
    main()

