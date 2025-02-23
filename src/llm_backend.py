# llm_backend.py
import requests
import os


def get_llm_response(prompt, model="llama3:instruct", temperature=0.7, top_p=0.9, max_tokens=1000):
    """
    Sends a prompt to the LLM API and returns the generated response.
    """
    ollama_port = os.getenv("OLLAMA_PORT", "11434")
    url = f"http://ollama:{ollama_port}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=90)
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        return f"Error: Failed to get a response from the LLM API. Details: {str(e)}"


def llm_interface(prompt, model, temperature, top_p, max_tokens):
    """
    Wrapper function to call the LLM backend and return the response for Gradio.
    """
    response = get_llm_response(
        prompt=prompt,
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_tokens=int(max_tokens)
    )
    return response
