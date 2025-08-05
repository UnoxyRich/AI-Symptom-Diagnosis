# data_utils.py
import pandas as pd
import re
import os
import logging
from collections import Counter

# --- Logging Setup ---
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, 'data_utils.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler() # Also log to console
    ]
)
logger = logging.getLogger(__name__)

# --- Symptom Normalization & Keyword Extraction ---
# This map defines standardized terms and their common variations.
# Expand this significantly for better results.
COMMON_SYMPTOM_MAP = {
    # General terms
    'fever': ['fever', 'high temperature', 'raised temperature', 'feeling hot', 'hot flashes'],
    'cough': ['cough', 'coughing', 'hacking cough', 'persistent cough'],
    'headache': ['headache', 'migraine', 'head pain', 'throbbing head', 'pain in head'],
    'fatigue': ['tired', 'tiredness', 'fatigue', 'exhausted', 'weak', 'lack of energy'],
    'sore throat': ['sore throat', 'throat pain', 'pain when swallowing', 'scratchy throat'],
    'runny nose': ['runny nose', 'nasal discharge', 'dripping nose', 'rhinorrhea'],
    'nausea': ['nausea', 'feeling sick', 'sick to stomach', 'upset stomach'],
    'vomiting': ['vomit', 'vomiting', 'thrown up', 'puking'],
    'diarrhea': ['diarrhea', 'loose stools', 'frequent bowel movements', 'watery stool'],
    'shortness of breath': ['shortness of breath', 'difficulty breathing', 'breathless', 'dyspnea'],
    'chest pain': ['chest pain', 'pain in chest', 'chest discomfort', 'tightness in chest'],
    'dizziness': ['dizzy', 'dizziness', 'lightheaded', 'vertigo'],
    'rash': ['rash', 'skin rash', 'eruption', 'skin irritation', 'hives'],
    'itchy eyes': ['itchy eyes', 'gritty eyes', 'watery eyes', 'red eyes', 'conjunctivitis'],
    # More specific ones
    'dry cough': ['dry cough', 'non-productive cough', 'tickle in throat'],
    'productive cough': ['productive cough', 'cough with phlegm', 'coughing mucus', 'wet cough'],
    'muscle aches': ['muscle aches', 'myalgia', 'body aches', 'sore muscles'],
    'loss of taste': ['loss of taste', 'ageusia', 'taste disturbance'],
    'loss of smell': ['loss of smell', 'anosmia', 'smell disturbance'],
    'abdominal pain': ['abdominal pain', 'stomach ache', 'belly pain', 'pain in abdomen'],
    'joint pain': ['joint pain', 'arthralgia', 'pain in joints'],
    'chills': ['chills', 'feeling cold', 'shivering'],
    'sweating': ['sweating', 'perspiration', 'clammy skin'],
}

# Invert the map for easier lookup: symptom variation -> standardized term
STANDARDIZED_SYMPTOM_LOOKUP = {}
for std_symptom, variations in COMMON_SYMPTOM_MAP.items():
    for variation in variations:
        STANDARDIZED_SYMPTOM_LOOKUP[variation] = std_symptom

def normalize_symptoms_text_advanced(symptom_string):
    """
    Advanced symptom normalization using a predefined map.
    Extracts keywords and maps them to standardized terms.
    """
    if not isinstance(symptom_string, str):
        return "" # Return empty string for non-string inputs

    text = symptom_string.lower()
    
    # Use regex to find potential symptom phrases and replace them
    processed_text = text
    
    # Iterate through known variations, longest first, to ensure correct matching
    sorted_variations = sorted(STANDARDIZED_SYMPTOM_LOOKUP.keys(), key=len, reverse=True)
    
    for variation in sorted_variations:
        standardized_term = STANDARDIZED_SYMPTOM_LOOKUP[variation]
        # Use regex to replace whole words/phrases, ensuring it's a distinct match
        # \b matches word boundaries. re.escape handles special characters in variations.
        pattern = r'\b' + re.escape(variation) + r'\b'
        processed_text = re.sub(pattern, standardized_term, processed_text)

    # Clean up resulting string: normalize whitespace and commas
    processed_text = re.sub(r'\s*,\s*', ', ', processed_text) # Ensure comma followed by space
    processed_text = re.sub(r'\s+', ' ', processed_text).strip() # Normalize multiple spaces
    
    # Further cleanup: remove duplicate standardized symptoms
    # Example: "fever, fever, cough" -> "fever, cough"
    symptoms_list = [s.strip() for s in processed_text.split(',') if s.strip()]
    unique_symptoms = []
    seen_symptoms = set()
    for symp in symptoms_list:
        if symp not in seen_symptoms:
            unique_symptoms.append(symp)
            seen_symptoms.add(symp)
    
    return ", ".join(unique_symptoms)

def get_cleaned_disease_dataframe(input_csv_path='data/diseases.csv'):
    """
    Reads a raw disease CSV, cleans it, applies normalization, and returns a
    cleaned pandas DataFrame. Returns None on failure.
    """
    logger.info(f"Starting data cleaning process from '{input_csv_path}'...")
    
    if not os.path.exists(input_csv_path):
        logger.error(f"Input CSV file not found: {input_csv_path}")
        return None

    try:
        df = pd.read_csv(input_csv_path)
        initial_rows = len(df)
        logger.info(f"Loaded {initial_rows} rows from original CSV.")

        # --- Data Cleaning Steps ---
        required_columns = ['disease', 'symptoms', 'treatment']
        df.dropna(subset=required_columns, inplace=True)
        rows_after_dropna = len(df)
        if rows_after_dropna < initial_rows:
            logger.warning(f"Removed {initial_rows - rows_after_dropna} rows with missing critical data.")

        # Normalize disease names and remove duplicates
        df['disease_normalized'] = df['disease'].astype(str).str.lower().str.replace(r' variant \d+', '', regex=True).str.strip()
        df.drop_duplicates(subset=['disease_normalized'], keep='first', inplace=True)
        df.drop(columns=['disease_normalized'], inplace=True) # Drop the helper column
        rows_after_disease_dedup = len(df)
        if rows_after_disease_dedup < rows_after_dropna:
             logger.info(f"Removed {rows_after_dropna - rows_after_disease_dedup} duplicate disease entries.")
        
        # Apply advanced normalization to symptoms
        df['symptoms_normalized'] = df['symptoms'].apply(normalize_symptoms_text_advanced)
        
        # Further cleanup for treatments
        df['treatment'] = df['treatment'].astype(str).str.lower().str.strip()
        df['treatment'] = df['treatment'].replace('', 'Not specified') # Handle empty treatments

        # Remove rows where normalized symptoms became empty after processing
        df = df[df['symptoms_normalized'] != ""].copy()
        
        # Create a list of normalized symptoms for easier processing (e.g., keyword matching)
        df['normalized_symptoms_list'] = df['symptoms_normalized'].apply(lambda x: [s.strip() for s in x.split(',') if s.strip()])

        # Final check for empty dataframe or missing critical columns after cleaning
        if df.empty:
            logger.error("Dataframe is empty after cleaning.")
            return None
        # Re-check columns as some might have been dropped or altered
        if not all(col in df.columns for col in ['disease', 'symptoms', 'treatment', 'symptoms_normalized', 'normalized_symptoms_list']):
            logger.error("Critical columns missing after cleaning. Expected: ['disease', 'symptoms', 'treatment', 'symptoms_normalized', 'normalized_symptoms_list']")
            return None

        logger.info(f"Successfully cleaned data. DataFrame with {len(df)} rows is ready.")
        return df

    except Exception as e:
        logger.error(f"An error occurred during advanced data cleaning: {e}", exc_info=True)
        return None

# Example usage function (called if script is run directly)
if __name__ == "__main__":
    # Ensure data directory exists
    if not os.path.exists('data'): os.makedirs('data')
    
    # Create a dummy diseases.csv if it doesn't exist for testing purposes
    if not os.path.exists('data/diseases.csv'):
        dummy_data = {
            'disease': ['Flu', 'Flu Variant 2', 'Cold', 'COVID-19', 'Migraine'],
            'symptoms': ['fever, cough, body aches', 'Fever, COUGH, body aches', 'sneezing, runny nose', 'fever, dry cough, loss of taste', 'headache, nausea, sensitivity to light'],
            'treatment': ['rest, fluids', 'Rest, fluids', 'rest', 'isolation, rest, fluids', 'pain relievers, dark room']
        }
        pd.DataFrame(dummy_data).to_csv('data/diseases.csv', index=False)
        logger.info("Created dummy data/diseases.csv for demonstration.")

    # Run the cleaning process and save to a new CSV for inspection
    cleaned_df = get_cleaned_disease_dataframe()
    if cleaned_df is not None:
        output_path = 'data/cleaned_diseases_for_inspection.csv'
        cleaned_df.to_csv(output_path, index=False)
        logger.info(f"Advanced data cleaning finished. Inspected data is at: {output_path}")
    else:
        logger.error("Advanced data cleaning process failed.")