# EOB Audit Tools

A modular suite of composable tools for parsing, merging, and analyzing EOB (Explanation of Benefits) documents from BCBS.

## Tools Overview

### 1. `html_to_json.py` - HTML Parser

Parses HTML claim files into standardized JSON format.

**Usage:**

```bash
python html_to_json.py <input.html> [output.json]
```

**Features:**

- Extracts claims from BCBS HTML tables
- Handles paginated results
- Outputs JSON with standardized schema

### 2. `pdf_to_json.py` - PDF Parser

Parses PDF EOB statements into standardized JSON format.

**Usage:**

```bash
python pdf_to_json.py <input.pdf> [output.json]
```

**Features:**

- Handles multiple claims per PDF
- Extracts from CLAIM TOTAL lines (preferred)
- Falls back to detail rows if CLAIM TOTAL missing
- Handles GRAND TOTAL as last resort
- Supports various provider formats
- Correctly parses both MM/DD/YY and MM/DD/YYYY date formats (prefers 4-digit year)

**Known Limitations:**

- Requires structured EOB format with CLAIM # headers
- Provider names are normalized but may need manual adjustment for unusual formats

### 3. `json_to_md.py` - Markdown Generator

Converts JSON claim files to markdown tables.

**Usage:**

```bash
python json_to_md.py <input.json> [output.md] [--composite]
```

**Flags:**

- `--composite`: Include "In PDF/HTML?" column and add Related Files section

**Features:**

- Sorts claims in reverse chronological order
- Supports individual and composite JSON formats
- Adds related file links for composite views

### 4. `merge_json.py` - Claims Merger

Merges multiple JSON claim files with source tracking.

**Usage:**

```bash
python merge_json.py <input1.json> <input2.json> ... <output.json>
```

**Features:**

- Deduplicates claims using composite key: Date, Billed Amt, Plan Payment, You May Owe
- Tracks source (HTML, PDF, or BOTH)
- Normalizes provider names for better matching
- Sorts output by date

**Matching Logic:**

- Primary key: Date + Billed Amt + Plan Payment + You May Owe
- Provider/Member fields are hints only, not blocking
- Normalizes common suffixes (LTD, PLLC, PA, INC, etc.)

### 5. `process_eob_audit.py` - Orchestrator

Main entry point that chains all tools together.

**Usage:**

```bash
python process_eob_audit.py <directory>
```

**Features:**

- Discovers all HTML and PDF files in directory
- Generates individual JSON and MD files for each source
- Creates composite JSON and MD files
- Uses folder name for composite output filename
- Provides summary statistics

## Workflow

1. **Discovery**: Find all HTML and PDF files in target directory
2. **Parsing**: Convert each HTML/PDF to JSON
3. **Individual MD**: Generate markdown for each JSON
4. **Merge**: Combine all JSONs with source tracking
5. **Composite MD**: Generate final summary with references

## Standard Schema

All JSON files use this schema (with normalized formats):

```json
{
  "Date": "YYYY-MM-DD",
  "Member": "Patient Name",
  "Facility/Physician": "Provider Name",
  "Service": "Service Type",
  "Billed Amt": "375.00",
  "Plan Payment": "0.00",
  "You May Owe": "0.00",
  "Status": "Status"
}
```

Composite JSON files add:

```json
{
  "In PDF/HTML?": "HTML|PDF|BOTH"
}
```

**Note:** Dates are stored in ISO 8601 format (YYYY-MM-DD), and amounts are stored as plain numbers (no $ or commas). The markdown generator converts these back to display formats (MM/DD/YY for dates, $X,XXX.XX for amounts).

## Work Directory

All project-specific EOB work (input PDFs, HTML files, and generated outputs) should be placed in the `work/` directory. This directory is excluded from version control via `.gitignore` to prevent committing sensitive patient data or large files. Each audit project should be placed in its own subdirectory within `work/`.

Example structure:

```plaintext
work/
├── BCBS - EOBs - 2025 - Lindsey/
│   ├── BCBS - claims - 2025-11-01.html
│   ├── EOB - 2025-02-14 - ... .pdf
│   └── ... (other EOB files)
└── Another Project/
    └── ... (files for another audit)
```

## Example

```bash
# Process an EOB directory from work folder
python process_eob_audit.py "work/BCBS - EOBs - 2025 - Lindsey"

# Manual pipeline example
python html_to_json.py claims.html claims.json
python pdf_to_json.py eob.pdf eob.json
python json_to_md.py claims.json claims.md
python merge_json.py claims.json eob.json composite.json
python json_to_md.py composite.json composite.md --composite
```

## Dependencies

- Python 3.x
- `pdfplumber` for PDF parsing
- Standard library: `json`, `re`, `sys`, `pathlib`, `datetime`, `subprocess`

Install dependencies:

```bash
pip install -r requirements.txt
```
