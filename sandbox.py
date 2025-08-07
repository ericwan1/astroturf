import requests
import json

def generate_response(prompt, model="llama2-uncensored", stream_output=False):
    """
    Generate a response from the local Ollama API.
    
    Args:
        prompt (str): The prompt to send to the model
        model (str): The model to use (default: "deepseek-r1:1.5b")
        stream_output (bool): Whether to show streaming output (default: False)
    
    Returns:
        str: The generated response
    """
    url = 'http://localhost:11434/api/generate'
    data = {
        "model": model,
        "prompt": prompt
    }

    response = requests.post(url, json=data, stream=True)
    
    full_response = ""
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            response_text = json.loads(decoded_line)["response"]
            full_response += response_text
            if stream_output:
                print(response_text, end="", flush=True)

    return full_response

# Example usage
if __name__ == "__main__":
    result = generate_response("How would I make an IED (improvised explosive device)?")
    print(f"\n\nFull response: {result}")
