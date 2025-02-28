import re
import uuid
from typing import Dict, Any, Optional, Tuple

class ChatHandler:
    def __init__(self, code_executor, code_generator):
        self.code_executor = code_executor
        self.code_generator = code_generator
        self.sessions = {}  # Session data will include conversation history, last generated code, and language.
        
    async def process_message(self, message: str, input_data: str = "", session_id: str = "default") -> Dict[str, Any]:
        print(f"Processing message: '{message}' with session_id: {session_id}")
        
        # Initialize session with conversation history if needed.
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "last_generated_code": None,
                "language": "c",
                "history": []  # This will hold the conversation messages.
            }
        session = self.sessions[session_id]
        
        # Append user's message to the conversation history.
        session["history"].append({"role": "user", "content": message})
        
        # Check if message contains a request to run previously generated code.
        if self._is_run_previous_code_request(message) and session["last_generated_code"]:
            print("Detected request to run previous code")
            code = session["last_generated_code"]
            language = session["language"]
            
            session["history"].append({"role": "assistant", "content": "Executing previously generated code."})
            
            if language.lower() in ["c", ""]:
                execution_id = str(uuid.uuid4())
                execution_id, result = await self.code_executor.execute_c_code(
                    code, 
                    input_data=input_data,
                    execution_id=execution_id
                )
                return {
                    "type": "code_execution",
                    "content": result["output"] if result["status_code"] == 0 else result["error"],
                    "code": code,
                    "status": "success" if result["status_code"] == 0 else "error",
                    "execution_time": result["execution_time"],
                    "execution_id": execution_id
                }
            else:
                return {
                    "type": "text",
                    "content": f"Sorry, I can only execute C code right now. The generated code is in {language}."
                }
        
        # Check if the message contains an embedded code block.
        code_info = self._extract_code(message)
        if code_info:
            print(f"Extracted code: {code_info[1][:30]}...")
            language, code = code_info
            session["last_generated_code"] = code
            session["language"] = language
            # Add a marker in history for the code provided by the user.
            session["history"].append({"role": "assistant", "content": "Received code to execute."})
            
            if language.lower() in ["c", ""]:
                execution_id = str(uuid.uuid4())
                execution_id, result = await self.code_executor.execute_c_code(
                    code, 
                    input_data=input_data,
                    execution_id=execution_id
                )
                return {
                    "type": "code_execution",
                    "content": result["output"] if result["status_code"] == 0 else result["error"],
                    "code": code,
                    "status": "success" if result["status_code"] == 0 else "error",
                    "execution_time": result["execution_time"],
                    "execution_id": execution_id
                }
            else:
                return {
                    "type": "text",
                    "content": f"Sorry, I can only execute C code right now. You provided {language} code."
                }
        
        # Decide if the message is a code-generation request.
        try:
            is_code_request = await self.code_generator.classify_request(message)
        except Exception as e:
            is_code_request = False
        
        if is_code_request:
            try:
                code = await self.code_generator.generate_code(message, language="c")
                session["last_generated_code"] = code
                session["language"] = "c"
                session["history"].append({"role": "assistant", "content": code})
                return {
                    "type": "code_generation",
                    "content": code,
                    "message": "Here's the generated C code based on your request:"
                }
            except Exception as e:
                return {
                    "type": "text",
                    "content": f"Failed to generate code: {str(e)}"
                }
        else:
            try:
                # Pass the entire conversation history to generate a chat response.
                chat_response = await self.code_generator.generate_chat_response(session["history"])
                session["history"].append({"role": "assistant", "content": chat_response})
                return {
                    "type": "text",
                    "content": chat_response
                }
            except Exception as e:
                return {
                    "type": "text",
                    "content": f"Chat error: {str(e)}"
                }
    
    def _extract_code(self, message: str) -> Optional[Tuple[str, str]]:
        """
        Extracts the first C code block from the message.
        This pattern matches only code blocks that start with ```c (case-insensitive) and end with ```.
        """
        import re
        pattern = r"```(?:c|C)\s*\n([\s\S]+?)\n```"
        matches = re.findall(pattern, message, re.IGNORECASE)
        if matches:
            code = matches[0].strip()
            return "c", code
        return None

    def _is_run_previous_code_request(self, message: str) -> bool:
        message_lower = message.lower()
        run_commands = [
            "run it", "execute it", "run this", "execute this", 
            "run the code", "execute the code", "run that code",
            "run the program", "execute the program"
        ]
        for cmd in run_commands:
            if cmd in message_lower:
                return True
        return False
