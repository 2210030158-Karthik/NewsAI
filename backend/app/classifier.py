import numpy # <-- ADDED THIS IMPORT
from transformers import pipeline
from typing import List, Dict, Union

# --- Initialize the AI Model (Classifier) ---
# ... (rest of the file remains the same) ...

print("Loading Zero-Shot-Classification model...")
# Check if CUDA is available and set the device
try:
    import torch
    if torch.cuda.is_available():
        device = 0 # Use the first GPU
        print("Device set to use CUDA (GPU)")
    else:
        device = -1 # Use CPU
        print("Device set to use cpu")
except ImportError:
    device = -1 # Use CPU if torch is not installed (should not happen with requirements)
    print("Torch not found. Device set to use cpu")


# Load the pipeline specifying the device
classifier = pipeline("zero-shot-classification",
                      model="facebook/bart-large-mnli",
                      device=device) # Specify the device
print("Model loaded successfully.")


# --- Define the Classification Function ---

def classify_article_content(content: str, topics: List[str]) -> List[Dict[str, Union[str, float]]]:
    """
    Takes a piece of text (article content) and a list of candidate topics.
    Returns a list of dictionaries with scores for each topic.
    """
    if not content or not topics:
        return []

    # Basic cleaning - remove excessive whitespace which might indicate issues
    content = ' '.join(content.split())
    if not content: # Check again after stripping whitespace
        print("Warning: Content is empty after cleaning.")
        return []


    try:
        # We set multi_label=True because an article can be about
        # "Politics" AND "Law" at the same time.
        # Add truncation to handle long articles gracefully
        result = classifier(content, topics, multi_label=True, truncation=True, max_length=512) # Added truncation

        # The result from the pipeline is a bit messy. Let's clean it up.
        classified_scores = []
        if 'labels' in result and 'scores' in result:
             for label, score in zip(result['labels'], result['scores']):
                 classified_scores.append({
                     "topic": label,
                     "score": score
                 })
        else:
             print(f"Warning: Unexpected result format from classifier for content starting with: {content[:100]}...")
             print(f"Result received: {result}")


        return classified_scores

    except ImportError as e:
         # Catch the specific error we are seeing
         print(f"FATAL: ImportError during classification: {e}")
         print("This likely means a required library (like numpy) is missing or cannot be found by the runtime.")
         # Re-raise the error to stop the process, as this is critical
         raise e
    except Exception as e:
        print(f"Error during classification: {e}")
        # Log the type of error and the beginning of the content
        print(f"Error type: {type(e)}")
        print(f"Content (start): {content[:100]}...")
        # If something else fails, return empty
        return []

# --- Example of how to use this (for testing) ---
if __name__ == "__main__":
    test_topics = ["Gaming", "Politics", "Technology", "Crimes", "International Law"]
    test_content = (
        "A new bill was passed in parliament today that restricts "
        "international trade. Lawmakers are concerned about the "
        "impact on the tech sector. Some have called it a 'crime' "
        "against free trade."
    )

    scores = classify_article_content(test_content, test_topics)
    print("\n--- Classification Test ---")
    print(f"Content: {test_content}\n")
    print("Scores:")
    if scores:
        for item in scores:
            print(f"- {item['topic']}: {item['score']:.2f}")
    else:
        print("Classification failed or returned no scores.")

