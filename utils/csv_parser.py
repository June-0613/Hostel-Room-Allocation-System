# utils/csv_parser.py
import csv
import io
import pandas as pd
from datetime import datetime

def parse_student_csv(file_stream, db_cursor):
    """
    Enhanced CSV parser with:
    - Better error handling
    - Data validation
    - Batch insertion for performance
    """
    try:
        # Validate file stream
        if not file_stream:
            raise ValueError("Empty file stream")

        # Read and decode the file
        file_content = file_stream.read().decode('utf-8-sig')  # Handles BOM
        if not file_content.strip():
            raise ValueError("Empty CSV file")

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(file_content))
        required_columns = {'name', 'admission_number'}
        
        # Validate CSV headers
        if not required_columns.issubset(csv_reader.fieldnames):
            missing = required_columns - set(csv_reader.fieldnames)
            raise ValueError(f"Missing columns: {missing}")

        # Prepare batch insert
        batch = []
        for row in csv_reader:
            name = row['name'].strip()
            admission_no = row['admission_number'].strip()

            # Data validation
            if not (name and admission_no):
                print(f"Skipping row with empty values: {row}")
                continue

            batch.append((name, admission_no))

        # Batch insert (avoids duplicate checks in DB)
        if batch:
            db_cursor.executemany(
                """INSERT IGNORE INTO freshers_list 
                   (name, admission_no, uploaded_on)
                   VALUES (%s, %s, %s)""",
                [(name, adm_no, datetime.now()) for name, adm_no in batch]
            )
            return True
        
        print("No valid records found in CSV")
        return False

    except csv.Error as e:
        print(f"CSV parsing error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def parse_excel_file(file_stream, db_cursor):
    try:

        # For .xlsx
        if file_stream.name.endswith('.xlsx'):
            df = pd.read_excel(file_stream, engine='openpyxl')
        # For .xls
        else:
            df = pd.read_excel(file_stream, engine='xlrd')
        # ... rest of your parsing logic ...
    except ImportError:
        raise ImportError(
            "Required Excel packages missing. "
            "Run: pip install openpyxl xlrd"
        )
    
        # Read Excel with headers
        df = pd.read_excel(file_stream)
        
        # Standardize column names (handle spaces/special chars)
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Validate required columns
        required = {'name', 'admission_number'}
        if missing := required - set(df.columns):
            return {'error': f"Missing columns: {missing}"}
        
        # Clean data
        df = df.dropna(subset=['name', 'admission_number'])
        df = df[
            df['name'].astype(str).str.strip().ne('') &
            df['admission_number'].astype(str).str.strip().ne('')
        ]
        
        if df.empty:
            return {'error': 'No valid rows after cleaning'}
            
        # Convert admission numbers to string
        df['admission_number'] = df['admission_number'].astype(str).str.strip()
        
        # Batch insert with duplicate prevention
        db_cursor.executemany(
            """INSERT INTO freshers_list (name, admission_no, uploaded_on)
               SELECT %s, %s, NOW() 
               WHERE NOT EXISTS (
                   SELECT 1 FROM freshers_list WHERE admission_no = %s
               )""",
            [(row['name'], row['admission_number'], row['admission_number']) 
             for _, row in df.iterrows()]
        )
        
        return {
            'total': len(df),
            'inserted': db_cursor.rowcount,
            'duplicates': len(df) - db_cursor.rowcount
        }
        
    except Exception as e:
        return {'error': f'Excel processing failed: {str(e)}'}
