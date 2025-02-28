import os
import json
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from code_generator import CodeGenerator
from code_executor import CodeExecutor
from chat_handler import ChatHandler

app = FastAPI(title="Code Execution System")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize components
code_generator = CodeGenerator()
code_executor = CodeExecutor()
chat_handler = ChatHandler(code_executor, code_generator)

# Create directory for static files
os.makedirs("static", exist_ok=True)

# Create basic HTML file for original UI
with open("static/index.html", "w") as f:
    f.write("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Execution System</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        textarea {
            width: 100%;
            height: 300px;
            font-family: monospace;
            padding: 10px;
        }
        button {
            padding: 10px 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
            margin-top: 10px;
        }
        button:disabled {
            background-color: #cccccc;
        }
        #output {
            font-family: monospace;
            white-space: pre;
            padding: 10px;
            border: 1px solid #ddd;
            height: 300px;
            overflow: auto;
            background-color: #f5f5f5;
        }
        .status {
            margin-top: 10px;
            padding: 10px;
            border-radius: 4px;
        }
        .error {
            background-color: #ffdddd;
            color: #f44336;
        }
        .success {
            background-color: #ddffdd;
            color: #4CAF50;
        }
        .info {
            background-color: #e7f3fe;
            color: #2196F3;
        }
        .nav-bar {
            display: flex;
            margin-bottom: 20px;
        }
        .nav-link {
            margin-right: 20px;
            text-decoration: none;
            padding: 10px;
            background-color: #4CAF50;
            color: white;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="nav-bar">
        <a href="/" class="nav-link">Code Execution UI</a>
        <a href="/chat" class="nav-link">Interactive Chat</a>
    </div>

    <h1>Code Execution System</h1>
    
    <div class="container">
        <div>
            <h2>Prompt</h2>
            <textarea id="prompt" placeholder="Enter your prompt here..."></textarea>
            <button id="generateBtn">Generate Code</button>
            
            <h2>Code</h2>
            <textarea id="code" placeholder="Generated code will appear here..."></textarea>
            <button id="executeBtn" disabled>Execute Code</button>
            
            <div>
                <h3>Input (optional)</h3>
                <textarea id="input" placeholder="Enter input for your program..."></textarea>
            </div>
        </div>
        
        <div>
            <h2>Output</h2>
            <div id="status" class="status info">Ready</div>
            <div id="output">Output will appear here...</div>
        </div>
    </div>

    <script>
        const promptEl = document.getElementById('prompt');
        const codeEl = document.getElementById('code');
        const inputEl = document.getElementById('input');
        const outputEl = document.getElementById('output');
        const statusEl = document.getElementById('status');
        const generateBtn = document.getElementById('generateBtn');
        const executeBtn = document.getElementById('executeBtn');
        
        let socket = null;
        let executionId = null;
        
        // Generate code
        generateBtn.addEventListener('click', async () => {
            const prompt = promptEl.value.trim();
            if (!prompt) {
                setStatus('Please enter a prompt', 'error');
                return;
            }
            
            setStatus('Generating code...', 'info');
            generateBtn.disabled = true;
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        prompt: prompt
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to generate code');
                }
                
                const data = await response.json();
                codeEl.value = data.code;
                executeBtn.disabled = false;
                setStatus('Code generated successfully', 'success');
            } catch (error) {
                setStatus(`Error: ${error.message}`, 'error');
            } finally {
                generateBtn.disabled = false;
            }
        });
        
        // Execute code
        executeBtn.addEventListener('click', async () => {
            const code = codeEl.value.trim();
            if (!code) {
                setStatus('No code to execute', 'error');
                return;
            }
            
            setStatus('Executing code...', 'info');
            executeBtn.disabled = true;
            outputEl.textContent = '';
            
            try {
                console.log("Sending execution request with code:", code.substring(0, 50) + "...");
                
                const response = await fetch('/api/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        code: code,
                        input: inputEl.value
                    })
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Failed to execute code: ${errorText}`);
                }
                
                const data = await response.json();
                console.log("Received execution response:", data);
                executionId = data.execution_id;
                
                // Connect to WebSocket for real-time updates
                connectWebSocket(executionId);
            } catch (error) {
                console.error("Execution error:", error);
                setStatus(`Error: ${error.message}`, 'error');
                executeBtn.disabled = false;
            }
        });
        
        // Connect to WebSocket
        function connectWebSocket(id) {
            if (socket) {
                socket.close();
            }
            
            console.log("Connecting to WebSocket with execution ID:", id);
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            socket = new WebSocket(`${protocol}//${window.location.host}/ws/execution/${id}`);
            
            socket.onopen = () => {
                console.log('WebSocket connected');
            };
            
            socket.onmessage = (event) => {
                console.log("WebSocket message received:", event.data);
                try {
                    const data = JSON.parse(event.data);
                    
                    switch (data.status) {
                        case 'starting':
                            setStatus('Starting execution...', 'info');
                            break;
                        case 'compiling':
                            setStatus('Compiling code...', 'info');
                            break;
                        case 'running':
                            setStatus('Running program...', 'info');
                            break;
                        case 'compile_error':
                            setStatus('Compilation error', 'error');
                            outputEl.textContent = data.error;
                            executeBtn.disabled = false;
                            break;
                        case 'error':
                            setStatus(`Error: ${data.error}`, 'error');
                            executeBtn.disabled = false;
                            break;
                        case 'completed':
                            if (data.result.status_code === 0) {
                                setStatus('Execution completed successfully', 'success');
                                outputEl.textContent = data.result.output;
                            } else {
                                setStatus('Execution failed', 'error');
                                outputEl.textContent = data.result.error || data.result.output;
                            }
                            executeBtn.disabled = false;
                            break;
                        default:
                            console.log("Unknown status:", data.status);
                    }
                } catch (error) {
                    console.error("Error parsing WebSocket message:", error);
                }
            };
            
            socket.onclose = () => {
                console.log('WebSocket disconnected');
            };
            
            socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                setStatus('WebSocket error', 'error');
                executeBtn.disabled = false;
            };
        }
        
        // Set status message
        function setStatus(message, type) {
            statusEl.textContent = message;
            statusEl.className = `status ${type}`;
        }
    </script>
</body>
</html>
""")

# Create chat interface HTML file
with open("static/chat.html", "w") as f:
    f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Code Chat</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .nav-bar {
            display: flex;
            margin-bottom: 20px;
        }
        .nav-link {
            margin-right: 20px;
            text-decoration: none;
            padding: 10px;
            background-color: #4CAF50;
            color: white;
            border-radius: 4px;
        }
        .chat-container {
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            height: 70vh;
            display: flex;
            flex-direction: column;
        }
        .chat-header {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
        }
        .chat-messages {
            flex-grow: 1;
            overflow-y: auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .message {
            margin-bottom: 20px;
            max-width: 80%;
        }
        .user-message {
            margin-left: auto;
            background-color: #e7f3fe;
            padding: 10px 15px;
            border-radius: 18px 18px 0 18px;
        }
        .assistant-message {
            background-color: #f1f0f0;
            padding: 10px 15px;
            border-radius: 18px 18px 18px 0;
        }
        .code-block {
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre-wrap;
            margin: 10px 0;
            border-left: 3px solid #4CAF50;
            overflow-x: auto;
        }
        .execution-result {
            margin-top: 10px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
        }
        .execution-success {
            border-left: 3px solid #4CAF50;
        }
        .execution-error {
            border-left: 3px solid #f44336;
        }
        .chat-input {
            display: flex;
            padding: 10px;
            background-color: white;
            border-top: 1px solid #ddd;
        }
        .chat-input textarea {
            flex-grow: 1;
            height: 60px;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            resize: none;
            font-family: Arial, sans-serif;
        }
        .chat-input-row {
            display: flex;
            width: 100%;
        }
        .chat-input-column {
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }
        .chat-input button {
            margin-left: 10px;
            align-self: flex-end;
            padding: 10px 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .program-input {
            margin-top: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 5px;
            height: 30px;
            font-family: Arial, sans-serif;
        }
        .program-input-label {
            font-size: 12px;
            color: #666;
            margin-top: 3px;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(0,0,0,.1);
            border-radius: 50%;
            border-top-color: #4CAF50;
            animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="nav-bar">
        <a href="/" class="nav-link">Code Execution UI</a>
        <a href="/chat" class="nav-link">Interactive Chat</a>
    </div>

    <h1>Interactive Code Chat</h1>
    
    <div class="chat-container">
        <div class="chat-header">
            <h2>Chat with Code Execution</h2>
        </div>
        <div class="chat-messages" id="chatMessages">
            <div class="message assistant-message">
                Type your C programming request and I'll generate the code. Say "run it" to execute.
            </div>
        </div>
        <div class="chat-input">
            <div class="chat-input-column">
                <textarea id="chatInput" placeholder="Type your message here..."></textarea>
                <div>
                    <input type="text" id="programInput" class="program-input" placeholder="Program input (optional)">
                    <div class="program-input-label">Input for your program (for scanf, etc.)</div>
                </div>
            </div>
            <button id="sendBtn">Send</button>
        </div>
    </div>

    <script>
        // DOM elements
        var chatMessagesEl = document.getElementById('chatMessages');
        var chatInputEl = document.getElementById('chatInput');
        var programInputEl = document.getElementById('programInput');
        var sendBtn = document.getElementById('sendBtn');
        
        // Function to escape HTML
        function escapeHtml(text) {
            var div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Function to add message to chat
        function addChatMessage(content, sender, isHtml, id) {
            var messageDiv = document.createElement('div');
            messageDiv.className = "message " + sender + "-message";
            
            if (id) {
                messageDiv.id = id;
            }
            
            if (isHtml) {
                messageDiv.innerHTML = content;
            } else {
                messageDiv.textContent = content;
            }
            
            chatMessagesEl.appendChild(messageDiv);
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
        }
        
        // Function to remove message from chat
        function removeChatMessage(id) {
            var messageDiv = document.getElementById(id);
            if (messageDiv) {
                messageDiv.remove();
            }
        }
        
        // Function to handle code execution response
        function handleCodeExecutionResponse(data) {
            var responseHtml = "";
            responseHtml += "<div class=\\\"code-block\\\">" + escapeHtml(data.code) + "</div>";
            
            var resultClass = data.status === "success" ? "execution-success" : "execution-error";
            var resultLabel = data.status === "success" ? "Output:" : "Error:";
            
            responseHtml += "<div class=\\\"execution-result " + resultClass + "\\\">";
            responseHtml += "<strong>" + resultLabel + "</strong><br>";
            responseHtml += "<pre>" + (escapeHtml(data.content) || "(No output)") + "</pre>";
            responseHtml += "</div>";
            
            if (data.execution_time) {
                responseHtml += "<div><small>Execution time: " + data.execution_time.toFixed(2) + "s</small></div>";
            }
            
            addChatMessage(responseHtml, "assistant", true);
        }
        
        // Function to handle code generation response
        function handleCodeGenerationResponse(data) {
            var responseHtml = "";
            responseHtml += "<div class=\\\"code-block\\\">" + escapeHtml(data.content) + "</div>";
            
            addChatMessage(responseHtml, "assistant", true);
        }
        
        // Function to send chat message
        function sendChatMessage() {
            var message = chatInputEl.value.trim();
            var inputData = programInputEl.value.trim();
            
            if (!message) {
                return;
            }
            
            // Add user message to chat
            addChatMessage(message, "user", false);
            chatInputEl.value = "";
            
            // Add temporary loading message
            var loadingMsgId = "loading-" + Date.now();
            addChatMessage("<div class=\\\"loading\\\"></div> Processing...", "assistant", true, loadingMsgId);
            
            // Send message to server
            fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: message,
                    input_data: inputData
                })
            })
            .then(function(response) {
                if (!response.ok) {
                    return response.text().then(function(text) {
                        throw new Error("Server error: " + response.status + " " + text);
                    });
                }
                return response.json();
            })
            .then(function(data) {
                // Remove loading message
                removeChatMessage(loadingMsgId);
                
                // Process different response types
                if (data.type === "code_execution") {
                    handleCodeExecutionResponse(data);
                } else if (data.type === "code_generation") {
                    handleCodeGenerationResponse(data);
                } else {
                    // Simple text response
                    addChatMessage(data.content, "assistant", false);
                }
            })
            .catch(function(error) {
                console.error("Error in sendChatMessage:", error);
                
                // Remove loading message and show error
                removeChatMessage(loadingMsgId);
                addChatMessage("Sorry, there was an error: " + error.message, "assistant", false);
            });
        }
        
        // Add event listeners
        sendBtn.addEventListener("click", function() {
            sendChatMessage();
        });
        
        // Handle Enter key
        chatInputEl.addEventListener("keydown", function(e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    </script>
</body>
</html>""")

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, execution_id: str):
        await websocket.accept()
        if execution_id not in self.active_connections:
            self.active_connections[execution_id] = []
        self.active_connections[execution_id].append(websocket)
        print(f"WebSocket client connected for execution {execution_id}. Active connections: {len(self.active_connections[execution_id])}")

    def disconnect(self, websocket: WebSocket, execution_id: str):
        if execution_id in self.active_connections:
            if websocket in self.active_connections[execution_id]:
                self.active_connections[execution_id].remove(websocket)
                print(f"WebSocket client disconnected from execution {execution_id}")
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]
                print(f"No more clients for execution {execution_id}")

    async def broadcast(self, message: str, execution_id: str):
        if execution_id in self.active_connections:
            print(f"Broadcasting to {len(self.active_connections[execution_id])} clients for execution {execution_id}: {message[:50]}...")
            disconnected_websockets = []
            for connection in self.active_connections[execution_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error sending to WebSocket: {e}")
                    disconnected_websockets.append(connection)
            
            # Clean up any disconnected websockets
            for ws in disconnected_websockets:
                self.disconnect(ws, execution_id)

manager = ConnectionManager()

# Pydantic models
class PromptRequest(BaseModel):
    prompt: str
    model: str = "gpt-4o"
    language: str = "c"

class CodeResponse(BaseModel):
    code: str

class ExecuteRequest(BaseModel):
    code: str
    input: Optional[str] = ""

class ExecutionResponse(BaseModel):
    execution_id: str

class ChatRequest(BaseModel):
    message: str
    input_data: Optional[str] = ""

class ChatResponse(BaseModel):
    type: str
    content: str
    code: Optional[str] = None
    status: Optional[str] = None
    execution_time: Optional[float] = None
    execution_id: Optional[str] = None
    message: Optional[str] = None

# API endpoints
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/chat", response_class=HTMLResponse)
async def chat_interface():
    with open("static/chat.html", "r") as f:
        return f.read()

@app.post("/api/generate", response_model=CodeResponse)
async def generate_code(request: PromptRequest):
    try:
        print(f"Generating code for prompt: {request.prompt[:50]}...")
        code = await code_generator.generate_code(
            prompt=request.prompt,
            language=request.language,
            model=request.model
        )
        print("Code generated successfully")
        return {"code": code}
    except Exception as e:
        print(f"Error generating code: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/execute", response_model=ExecutionResponse)
async def execute_code(request: ExecuteRequest, background_tasks: BackgroundTasks):
    try:
        print(f"Executing code (length: {len(request.code)}) with input (length: {len(request.input or '')})...")
        execution_id = str(uuid.uuid4())
        
        # Execute code in the background
        background_tasks.add_task(
            code_executor.execute_c_code,
            code=request.code,
            input_data=request.input,
            execution_id=execution_id,
            websocket_manager=manager
        )
        
        print(f"Started execution with ID: {execution_id}")
        return {"execution_id": execution_id}
    except Exception as e:
        print(f"Error starting execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
async def process_chat_message(request: ChatRequest, client_host: Optional[str] = None):
    try:
        print(f"Processing chat message: {request.message[:50]}...")
        
        # Use client host or a default ID as session identifier
        session_id = client_host or "default"
        
        response = await chat_handler.process_message(
            request.message,
            input_data=request.input_data,
            session_id=session_id
        )
        
        print(f"Chat response type: {response['type']}")
        return response
    except Exception as e:
        print(f"Error processing chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/results/{execution_id}")
async def get_execution_results(execution_id: str):
    if execution_id not in code_executor.execution_results:
        raise HTTPException(status_code=404, detail="Execution result not found")
    
    return code_executor.execution_results[execution_id]

@app.websocket("/ws/execution/{execution_id}")
async def websocket_endpoint(websocket: WebSocket, execution_id: str):
    await manager.connect(websocket, execution_id)
    try:
        print(f"New WebSocket connection for execution ID: {execution_id}")
        
        # If execution has already completed, send the result immediately
        if execution_id in code_executor.execution_results:
            print(f"Execution {execution_id} already completed, sending result immediately")
            await websocket.send_text(json.dumps({
                "status": "completed",
                "result": code_executor.execution_results[execution_id]
            }))
        
        # Keep the connection open to receive more events
        while True:
            message = await websocket.receive_text()
            print(f"Received message from client: {message}")
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for execution {execution_id}")
        manager.disconnect(websocket, execution_id)
    except Exception as e:
        print(f"WebSocket error for execution {execution_id}: {str(e)}")
        manager.disconnect(websocket, execution_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)