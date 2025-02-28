from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

class CodeGenerator:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        try:
            self.client = OpenAI(api_key=api_key)
        except TypeError as e:
            if 'proxies' in str(e):
                import httpx
                http_client = httpx.Client(follow_redirects=True)
                self.client = OpenAI(api_key=api_key, http_client=http_client)
            else:
                raise
    
    async def generate_code(self, prompt, language="c", model="gpt-4o"):
        language_prompt = f"Generate {language} code for the following task."
        system_message = ("You are a skilled programmer who generates clean, efficient code. "
                          "Provide only the code without explanation unless explicitly asked for comments.")
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"{language_prompt}\n\n{prompt}"}
            ]
        )
        generated_code = response.choices[0].message.content
        lines = generated_code.split('\n')
        if lines and '```' in lines[0]:
            lines = lines[1:]
        if lines and '```' in lines[-1]:
            lines = lines[:-1]
        clean_code = '\n'.join(lines)
        return clean_code
    
    async def classify_request(self, message: str, model="gpt-4o") -> bool:
        prompt = (f"Determine if the following query is asking for a C code generation task. "
                  "Answer 'yes' if it is, or 'no' if it is not.\n"
                  f"Query: {message}")
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a classifier that determines if a user query is asking for C code generation."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.choices[0].message.content.strip().lower()
        return answer == "yes"
    
    async def generate_chat_response(self, history, model="gpt-4o") -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=history
        )
        return response.choices[0].message.content
