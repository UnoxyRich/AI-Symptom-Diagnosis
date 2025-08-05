# logic.py
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch
import logging
import os
from data_utils import get_cleaned_disease_dataframe, normalize_symptoms_text_advanced

# --- Logging Setup ---
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, 'symptom_checker.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler() # Also log to console
    ]
)
logger = logging.getLogger(__name__)

# --- Global variables for model, embeddings, and DataFrame ---
# This ensures resources are loaded only once for efficiency.
_model = None
_embeddings = None
_df = None # DataFrame holding cleaned disease data
_is_loaded = False # Flag to check if resources are loaded

# --- Resource Loading Function ---
def load_symptom_checker_resources(
    json_path='data/diseases.json', 
    raw_csv_path='data/diseases.csv', 
    model_name='all-MiniLM-L6-v2'
):
    """
    Loads the CSV data and the sentence transformer model.
    This function is called once when the application starts or when the checker is first used.
    """
    global _model, _embeddings, _df, _is_loaded
    
    if _is_loaded:
        logger.info("Resources already loaded. Skipping reload.")
        return True

    logger.info("Attempting to load symptom checker resources...")
    
    # --- Load Data ---
    try:
        df = None
        # Prioritize loading from the processed JSON file for speed and reliability
        if os.path.exists(json_path):
            logger.info(f"Found processed JSON file. Loading from '{json_path}'...")
            df = pd.read_json(json_path, orient='records')
        else:
            # If JSON doesn't exist, create it from the raw CSV
            logger.warning(f"Processed JSON file '{json_path}' not found. Building from '{raw_csv_path}'...")
            df = get_cleaned_disease_dataframe(raw_csv_path)
            if df is not None and not df.empty:
                # Save the cleaned DataFrame to JSON for future runs
                df.to_json(json_path, orient='records', indent=4)
                logger.info(f"Successfully created and saved processed data to '{json_path}'.")
            else:
                logger.error(f"Failed to create DataFrame from '{raw_csv_path}'. Cannot proceed.")
                return False

        if df.empty:
            raise ValueError("Cleaned CSV file is empty.")
        
        # Check for essential columns needed by the checker
        required_columns = ['disease', 'symptoms', 'treatment', 'symptoms_normalized', 'normalized_symptoms_list']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"Cleaned CSV must contain columns: {required_columns}")
        
        _df = df  # Store the loaded DataFrame globally
        logger.info(f"Successfully loaded {_df.shape[0]} disease entries.")

        # --- Load Sentence Transformer Model ---
        logger.info(f"Loading Sentence Transformer model: {model_name}")
        _model = SentenceTransformer(model_name)
        
        # --- Encode Symptoms ---
        logger.info("Encoding normalized disease symptoms. This may take a moment...")
        # Use the normalized symptoms for embedding generation
        symptom_list = _df['symptoms_normalized'].tolist()
        _embeddings = _model.encode(symptom_list, convert_to_tensor=True, show_progress_bar=True)
        logger.info("Model and embeddings loaded successfully.")
        
        _is_loaded = True # Set the flag indicating resources are ready
        return True

    except FileNotFoundError as fnf:
        logger.error(f"File Error during resource loading: {fnf}")
        return False
    except ValueError as ve:
        logger.error(f"Data Error during resource loading: {ve}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during resource loading: {e}", exc_info=True)
        return False

# --- SymptomChecker Class ---
class SymptomChecker:
    def __init__(self):
        # Ensure resources are loaded when an instance is created.
        # If loading fails, raise an error to prevent the app from running incorrectly.
        if not _is_loaded:
            if not load_symptom_checker_resources():
                raise RuntimeError("Failed to initialize SymptomChecker resources. Please check logs.")

    def _get_top_matches(self, user_input, top_n=5):
        """
        Helper method to find the top N most similar disease symptom descriptions
        to the user's input using sentence embeddings.
        Returns a list of dictionaries, each containing disease info and confidence.
        """
        if _model is None or _embeddings is None or _df is None:
            logger.error("Model or data not loaded. Cannot perform similarity search.")
            return []

        try:
            # Normalize the user's input using the same advanced function
            sanitized_input = normalize_symptoms_text_advanced(user_input)
            if not sanitized_input:
                logger.warning("User input resulted in empty normalized string.")
                return []
            
            logger.debug(f"Encoding user symptoms for matching: '{sanitized_input}'")
            user_embedding = _model.encode(sanitized_input, convert_to_tensor=True)
            
            logger.debug("Calculating embedding similarities...")
            # Calculate cosine similarity between user input and all disease embeddings
            similarities = util.cos_sim(user_embedding, _embeddings)[0]
            
            # Get the indices and scores for the top N most similar results
            top_k = torch.topk(similarities, top_n)
            top_indices = top_k.indices.tolist()
            top_scores = top_k.values.tolist()

            matches = []
            # Filter out matches with very low similarity and format results
            for idx, score in zip(top_indices, top_scores):
                if score > 0.1: # A minimal threshold for relevance
                    row = _df.iloc[idx]
                    matches.append({
                        'disease': row['disease'],
                        'treatment': row['treatment'],
                        'confidence': round(float(score) * 100, 2), # Store as percentage
                        'normalized_symptoms': row['symptoms_normalized'] # Include for context
                    })
            return matches
        
        except Exception as e:
            logger.error(f"Error in _get_top_matches for input '{user_input}': {e}", exc_info=True)
            return []

    def _calculate_keyword_overlap(self, user_input):
        """
        Calculates keyword overlap score between user input and disease symptoms.
        Uses the normalized symptom lists for comparison.
        Returns a dictionary mapping disease names to their overlap score.
        """
        if _df is None or 'normalized_symptoms_list' not in _df.columns:
            logger.error("DataFrame or 'normalized_symptoms_list' column missing for keyword overlap calculation.")
            return {}

        try:
            # Normalize user input to get a set of their symptoms
            user_symptoms_norm = normalize_symptoms_text_advanced(user_input)
            user_symptom_set = set(s.strip() for s in user_symptoms_norm.split(',') if s.strip())

            if not user_symptom_set:
                return {} # Return empty if no symptoms identified from user input

            overlap_scores = {}
            # Iterate through each disease in the DataFrame
            for index, row in _df.iterrows():
                disease = row['disease']
                # Get the set of normalized symptoms for the current disease
                disease_symptom_set = set(row['normalized_symptoms_list'])
                
                if not disease_symptom_set:
                    continue # Skip if disease has no normalized symptoms listed

                # Calculate overlap: number of common symptoms
                intersection = len(user_symptom_set.intersection(disease_symptom_set))
                
                # Store the raw count of overlapping symptoms
                overlap_scores[disease] = intersection
            
            return overlap_scores

        except Exception as e:
            logger.error(f"Error calculating keyword overlap: {e}", exc_info=True)
            return {}

    def diagnose(self, user_input, confidence_threshold=45.0, keyword_weight=0.3):
        """
        Diagnoses a disease by combining semantic similarity (embeddings) and keyword overlap.
        Returns the best diagnosis, treatment, and a combined confidence score.
        If confidence is below the threshold, it returns a general advisory message.
        
        Args:
            user_input (str): The symptoms entered by the user.
            confidence_threshold (float): Minimum combined score (0-100) to consider a diagnosis valid.
            keyword_weight (float): The weight given to keyword overlap vs. semantic similarity (0.0 to 1.0).
                                    0.0 = only embeddings, 1.0 = only keyword overlap.
        """
        # First, get top matches based on embeddings
        top_n_matches = self._get_top_matches(user_input, top_n=5) # Fetch a few initial candidates

        if not top_n_matches:
            # If no matches found by embeddings, return advisory message
            return "Could not determine a diagnosis. Please try rephrasing your symptoms or consult a doctor.", "N/A", 0.0

        # Calculate keyword overlap scores
        keyword_scores = self._calculate_keyword_overlap(user_input)
        
        # Determine the maximum possible keyword score for normalization
        max_keyword_score = 1.0 # Default if no keywords overlap or keyword_scores is empty
        if keyword_scores:
             max_keyword_score = max(keyword_scores.values()) if keyword_scores else 1.0

        combined_scores = {}
        # Combine scores for each top matching disease
        for match in top_n_matches:
            disease = match['disease']
            embedding_score = match['confidence'] / 100.0 # Convert confidence to a 0-1 scale
            
            # Get keyword score for this disease, default to 0 if not found
            kw_score_raw = keyword_scores.get(disease, 0)
            # Normalize keyword score to be between 0 and 1
            normalized_kw_score = (kw_score_raw / max_keyword_score) if max_keyword_score > 0 else 0
            
            # Calculate the final combined score using the specified weight
            combined_score = (1 - keyword_weight) * embedding_score + keyword_weight * normalized_kw_score
            
            combined_scores[disease] = {
                'score': combined_score,
                'embedding_score': embedding_score, # Store individual scores for logging/debugging
                'keyword_score': normalized_kw_score,
                'treatment': match['treatment'] # Keep the treatment associated
            }

        # Sort diseases by their combined score in descending order
        sorted_combined = sorted(combined_scores.items(), key=lambda item: item[1]['score'], reverse=True)

        if not sorted_combined:
            # This case should ideally not happen if top_n_matches was not empty, but as a safeguard:
            return "Could not determine a diagnosis. Please try rephrasing your symptoms or consult a doctor.", "N/A", 0.0

        # Get the top diagnosis after combining scores
        best_match_disease, best_match_data = sorted_combined[0]
        final_confidence_percentage = best_match_data['score'] * 100
        
        # Log the diagnostic result with detailed scores
        log_level = logging.INFO if final_confidence_percentage >= confidence_threshold else logging.WARNING
        logger.log(log_level, 
                   f"Diagnosis attempt: Input='{user_input[:50]}...' -> Predicted='{best_match_disease}' "
                   f"Confidence={final_confidence_percentage:.1f}% (Emb={best_match_data['embedding_score']*100:.1f}%, KW={best_match_data['keyword_score']*100:.1f}%)")

        # Apply the confidence threshold
        if final_confidence_percentage < confidence_threshold:
            # Return a general advisory message if confidence is too low
            return (f"Could not confidently diagnose. The symptoms provided do not strongly match known conditions. "
                    f"Confidence: {final_confidence_percentage:.1f}%. Please consult a medical professional."), \
                   "N/A", \
                   final_confidence_percentage
        
        # Return the details of the best diagnosis
        return best_match_disease, best_match_data['treatment'], round(final_confidence_percentage, 2)

    def get_possible_diagnoses(self, user_input, top_n=5, confidence_threshold=30.0):
        """
        Retrieves a list of possible diagnoses, ranked by combined confidence score.
        Filters results based on a secondary confidence threshold.
        
        Args:
            user_input (str): The symptoms entered by the user.
            top_n (int): The number of top potential diagnoses to consider.
            confidence_threshold (float): Minimum combined score (0-100) for a diagnosis to be included.
        
        Returns:
            list: A list of dictionaries, each representing a possible diagnosis.
        """
        # Get top matches based on embeddings first
        matches = self._get_top_matches(user_input, top_n=top_n)
        
        if not matches: 
            return [] # Return empty list if no initial matches

        # Calculate keyword overlap scores
        keyword_scores = self._calculate_keyword_overlap(user_input)
        max_keyword_score = max(keyword_scores.values()) if keyword_scores else 1.0
        keyword_weight = 0.3 # Use the same weight as in diagnose()

        combined_diagnoses = []
        # Calculate combined scores for each match
        for match in matches:
            disease = match['disease']
            embedding_score = match['confidence'] / 100.0
            kw_score_raw = keyword_scores.get(disease, 0)
            normalized_kw_score = (kw_score_raw / max_keyword_score) if max_keyword_score > 0 else 0
            
            combined_score = (1 - keyword_weight) * embedding_score + keyword_weight * normalized_kw_score
            
            # Only include diagnoses that meet the secondary confidence threshold
            if combined_score * 100 >= confidence_threshold:
                combined_diagnoses.append({
                    'disease': disease,
                    'treatment': match['treatment'],
                    'confidence': round(combined_score * 100, 2),
                    'normalized_symptoms': match['normalized_symptoms']
                })
        
        # Sort the results by the combined confidence score
        return sorted(combined_diagnoses, key=lambda item: item['confidence'], reverse=True)

    # --- Feedback Mechanism ---
    def record_feedback(self, user_input, predicted_disease, feedback_type):
        """
        Logs user feedback. In a real application, this data would be stored
        in a database for analysis and potential model retraining.
        """
        log_message = f"Feedback received: Input='{user_input[:50]}...', Predicted='{predicted_disease}', Feedback='{feedback_type}'"
        
        if feedback_type == 'correct':
            logger.info(log_message + " (Confirmation)")
            # TODO: Implement logic to potentially boost this disease for these symptoms
            # if using a more adaptive model or retrieval system.
        elif feedback_type == 'incorrect':
            logger.warning(log_message + " (Correction needed)")
            # TODO: Implement logic to store this feedback for model retraining or data improvement.
            # This might involve saving the user input, predicted disease, correct disease (if provided), etc.
        else:
            logger.info(log_message + " (Neutral/Other)")