# app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from logic import SymptomChecker
import logging
import os
import pandas as pd # Needed for data checks in __main__

# --- App Setup ---
app = Flask(__name__)
# Use a more robust secret key, perhaps from environment variables in production
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_default_fallback_secret_key_for_dev') 

# --- Logging Configuration ---
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file_app = os.path.join(log_dir, 'flask_app.log')
# Use the same formatter as logic.py for consistency if desired, or define a new one.
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Configure Flask's logger to write to a file
handler_app = logging.FileHandler(log_file_app)
handler_app.setFormatter(formatter)
app.logger.addHandler(handler_app)
app.logger.setLevel(logging.INFO) # Set Flask's logger level

# --- Initialize Symptom Checker ---
# The checker instance should be global or managed via app context for efficiency
try:
    checker = SymptomChecker()
    app.logger.info("SymptomChecker initialized successfully.")
except RuntimeError as e:
    app.logger.error(f"Failed to initialize SymptomChecker: {e}")
    checker = None # Ensure checker is None if initialization fails

# --- Global cache for symptoms (loaded once) ---
_available_symptoms = []
_symptoms_loaded = False

def load_available_symptoms():
    """Loads the list of unique normalized symptoms for autocomplete."""
    global _available_symptoms, _symptoms_loaded
    if _symptoms_loaded: return True
    
    # Access the dataframe (_df) from the initialized checker instance
    if checker and checker._df is not None: 
        try:
            all_symptoms = set()
            # Ensure 'normalized_symptoms_list' column exists
            if 'normalized_symptoms_list' in checker._df.columns:
                for symp_list in checker._df['normalized_symptoms_list']:
                    # Ensure symp_list is iterable (e.g., not NaN or None)
                    if isinstance(symp_list, list):
                        for s in symp_list:
                            if s: all_symptoms.add(s)
            else:
                app.logger.error("'normalized_symptoms_list' column not found in checker._df.")
                return False
            
            _available_symptoms = sorted(list(all_symptoms))
            _symptoms_loaded = True
            app.logger.info(f"Loaded {_available_symptoms.__len__()} unique symptoms for autocomplete.")
            return True
        except Exception as e:
            app.logger.error(f"Error loading available symptoms: {e}", exc_info=True)
            return False
    else:
        app.logger.error("SymptomChecker not initialized or its data (_df) is not available to get symptoms.")
        return False

# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    # Initialize session variables if they don't exist
    if 'user_symptoms_input' not in session:
        session['user_symptoms_input'] = ''
    if 'result' not in session:
        session['result'] = None
    if 'error_message' not in session:
        session['error_message'] = None
    if 'possible_diagnoses' not in session:
        session['possible_diagnoses'] = None

    # Retrieve data from session for rendering
    user_symptoms_input = session.get('user_symptoms_input', '')
    result = session.get('result')
    error_message = session.get('error_message')
    possible_diagnoses = session.get('possible_diagnoses')

    if request.method == 'POST':
        # Clear previous results/errors when a new diagnosis is requested
        session['result'] = None
        session['error_message'] = None
        session['possible_diagnoses'] = None

        user_symptoms_input_raw = request.form.get('symptoms', '').strip()
        session['user_symptoms_input'] = user_symptoms_input_raw # Store raw input in session

        if not user_symptoms_input_raw:
            session['error_message'] = "Please enter your symptoms."
        elif checker is None:
            session['error_message'] = "Symptom checking service is currently unavailable."
        else:
            try:
                # Get primary diagnosis and other possibilities
                disease, treatment, confidence = checker.diagnose(user_symptoms_input_raw)
                
                # Check if diagnose returned an error message or low confidence warning
                if "Could not confidently diagnose" in disease or "Could not determine a diagnosis" in disease or confidence < 45.0: # Use a confidence check here too
                    session['error_message'] = disease # Use the returned message as error
                    session['result'] = None # Ensure no primary result is shown
                    # Fetch possible diagnoses even on error to show alternatives
                    possible = checker.get_possible_diagnoses(user_symptoms_input_raw)
                    session['possible_diagnoses'] = possible if possible else None
                else:
                    session['result'] = {
                        'symptoms': user_symptoms_input_raw, 
                        'disease': disease,
                        'treatment': treatment,
                        'confidence': confidence
                    }
                    # Fetch other possible diagnoses if the primary one is good
                    possible = checker.get_possible_diagnoses(user_symptoms_input_raw)
                    # Filter out the primary result if it appears in the list
                    session['possible_diagnoses'] = [pd for pd in possible if pd['disease'] != disease] if possible else None
            
            except Exception as e:
                app.logger.error(f"Exception in POST handler for '/': {e}", exc_info=True)
                session['error_message'] = "An unexpected error occurred during diagnosis. Please try again."
                session['result'] = None
                session['possible_diagnoses'] = None
        
        # Redirect back to the same page to refresh with session data
        return redirect(url_for('index'))

    # On GET request, just render the template with current session data
    return render_template('index.html', 
                           result=session.get('result'), 
                           error_message=session.get('error_message'), 
                           user_symptoms_input=session.get('user_symptoms_input'),
                           possible_diagnoses=session.get('possible_diagnoses'))

# Endpoint to provide autocomplete data
@app.route('/get_symptoms')
def get_symptoms():
    """Endpoint to provide a list of normalized symptoms for autocomplete."""
    if not load_available_symptoms(): # Ensure symptoms are loaded
        return jsonify({"status": "error", "message": "Service unavailable or symptoms not loaded."}), 503
    
    current_input = request.args.get('q', '').lower().strip()
    
    # Filter symptoms based on user's current input
    filtered_symptoms = []
    if not current_input:
        # Return a subset if no query, to avoid sending huge lists
        filtered_symptoms = _available_symptoms[:20] 
    else:
        current_words_list = current_input.split(',')
        last_word = current_words_list[-1].strip() if current_words_list else ''

        if last_word:
            # Find symptoms starting with the last typed word, and not already fully entered
            fully_entered_symptoms = {w.strip() for w in current_words_list if w.strip()}
            filtered_symptoms = [s for s in _available_symptoms 
                                 if s.startswith(last_word) and s not in fully_entered_symptoms]
            filtered_symptoms = filtered_symptoms[:10] # Limit results

    return jsonify({"status": "success", "symptoms": filtered_symptoms})


# --- Feedback Route ---
# Note: CSRF protection is recommended for production, especially for POST requests.
# You'd typically use Flask-WTF or similar libraries.
@app.route('/feedback', methods=['POST'])
def feedback():
    try:
        data = request.get_json()
        user_input = data.get('user_input')
        predicted_disease = data.get('predicted_disease')
        feedback_type = data.get('feedback_type') # e.g., 'correct', 'incorrect'

        if not all([user_input, predicted_disease, feedback_type]):
            app.logger.warning("Incomplete feedback data received.")
            return jsonify({"status": "error", "message": "Incomplete data provided."}), 400

        if checker:
            checker.record_feedback(user_input, predicted_disease, feedback_type)
            app.logger.info(f"Feedback received: Input='{user_input}', Predicted='{predicted_disease}', Type='{feedback_type}'")
            return jsonify({"status": "success", "message": "Feedback recorded."})
        else:
            app.logger.error("Feedback received but SymptomChecker not initialized.")
            return jsonify({"status": "error", "message": "Service unavailable."}), 503

    except Exception as e:
        app.logger.error(f"Error processing feedback: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error processing feedback."}), 500

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    app.logger.warning(f"404 Error: Requested path '{request.path}' not found.")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"500 Internal Server Error: {e}", exc_info=True)
    return render_template('500.html'), 500

# --- Main Execution ---
if __name__ == '__main__':
    # Ensure initial data setup if running directly
    if not os.path.exists('data'): os.makedirs('data')
    if not os.path.exists('data/diseases.csv'):
        # Create a minimal dummy file if it's missing, for initial testing
        dummy_data = {
            'disease': ['Flu', 'Cold'],
            'symptoms': ['fever, cough, body aches', 'sneezing, runny nose'],
            'treatment': ['rest, fluids', 'rest']
        }
        try:
            pd.DataFrame(dummy_data).to_csv('data/diseases.csv', index=False)
            app.logger.warning("Created dummy data/diseases.csv as it was missing.")
        except Exception as e:
            app.logger.error(f"Failed to create dummy diseases.csv: {e}")

    # Run the app
    # debug=True is useful for development, but disable for production.
    # host='0.0.0.0' makes the server accessible on your network.
    app.run(debug=True, host='0.0.0.0')