// static/js/main.js (Simplified)

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('symptomForm');
    const diagnoseBtn = document.getElementById('diagnoseBtn');
    const feedbackButtons = document.querySelectorAll('.feedback-btn');
    const mainResultSection = document.getElementById('resultSection');
    const possibleDiagnosesSection = document.getElementById('possibleDiagnosesSection');
    const inputElement = document.getElementById('symptomsInput'); // Still needed for clearing error messages

    // --- Helper Function for Feedback Messages ---
    const showFeedbackMessage = (message, type = 'info', targetSectionId = 'resultSection') => {
        const targetSection = document.getElementById(targetSectionId);
        if (!targetSection) return;

        const msgElement = document.createElement('div');
        msgElement.className = `feedback-message ${type}`;
        msgElement.textContent = message;
        
        targetSection.insertBefore(msgElement, targetSection.firstChild);
        
        setTimeout(() => {
            msgElement.remove();
        }, 3000);
    };

    // --- Feedback Handling ---
    const handleFeedback = async (event) => {
        const btn = event.target;
        if (!btn.classList.contains('feedback-btn')) return;

        const userInput = btn.dataset.input;
        const predictedDisease = btn.dataset.disease;
        const feedbackType = btn.dataset.feedback;

        if (!userInput || !predictedDisease || !feedbackType) {
            console.error("Missing data attributes for feedback.");
            return;
        }

        btn.disabled = true;
        btn.closest('.feedback-buttons').querySelectorAll('.feedback-btn').forEach(b => b.disabled = true);

        try {
            const response = await fetch('/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_input: userInput,
                    predicted_disease: predictedDisease,
                    feedback_type: feedbackType
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                showFeedbackMessage(`Thank you for your feedback! (${feedbackType})`, 'success', btn.closest('.result-container, .diagnosis-item').id);
                btn.style.backgroundColor = feedbackType === 'correct' ? '#28a745' : '#dc3545';
                btn.textContent = 'Submitted';
                btn.disabled = true;
            } else {
                showFeedbackMessage(`Error: ${result.message}`, 'error', btn.closest('.result-container, .diagnosis-item').id);
                btn.disabled = false;
                btn.closest('.feedback-buttons').querySelectorAll('.feedback-btn').forEach(b => b.disabled = false);
            }
        } catch (error) {
            console.error('Error submitting feedback:', error);
            showFeedbackMessage('Network error. Please try again.', 'error', btn.closest('.result-container, .diagnosis-item').id);
            btn.disabled = false;
            btn.closest('.feedback-buttons').querySelectorAll('.feedback-btn').forEach(b => b.disabled = false);
        }
    };

    // Attach feedback listeners
    feedbackButtons.forEach(button => {
        button.addEventListener('click', handleFeedback);
    });

    // --- Form Submission & Button State ---
    if (form) {
        form.addEventListener('submit', () => {
            diagnoseBtn.textContent = 'Diagnosing...';
            diagnoseBtn.disabled = true;
            // Clear previous results and messages immediately for better UX
            if (mainResultSection) mainResultSection.style.display = 'none';
            if (possibleDiagnosesSection) possibleDiagnosesSection.style.display = 'none';
            const errorMsgElement = document.querySelector('.error-message');
            if (errorMsgElement) errorMsgElement.textContent = '';
            
            // Page reload handled by browser after submission. Button state reset on next page load.
        });
    }
    
    // Clear error message when user starts typing again
    if (inputElement) {
        inputElement.addEventListener('input', () => {
            const errorMsgElement = document.querySelector('.error-message');
            if (errorMsgElement) {
                errorMsgElement.textContent = '';
            }
        });
    }
});