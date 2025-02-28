import os
import time
import json
import uuid
import tempfile
import shutil
import sys
import subprocess

class CodeExecutor:
    def __init__(self):
        # Check if gcc is installed
        try:
            subprocess.run(['gcc', '--version'], check=True, capture_output=True)
            print("Successfully found GCC compiler")
            self.gcc_available = True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            print(f"Error finding GCC compiler: {str(e)}", file=sys.stderr)
            print("\nPossible solutions:", file=sys.stderr)
            print("1. Make sure GCC is installed:", file=sys.stderr)
            print("   sudo apt-get install build-essential (on Ubuntu/Debian)", file=sys.stderr)
            print("   sudo yum install gcc (on CentOS/RHEL)", file=sys.stderr)
            self.gcc_available = False
        
        # In-memory storage for execution results
        self.execution_results = {}
        
    async def execute_c_code(self, code, input_data="", execution_id=None, websocket_manager=None):
        """Execute C code using local GCC compiler"""
        if execution_id is None:
            execution_id = str(uuid.uuid4())
            
        start_time = time.time()
        result = {
            "output": "",
            "error": "",
            "status_code": 0,
            "execution_time": 0
        }
        
        # Check if GCC is available
        if not self.gcc_available:
            error_message = "GCC compiler is not available. Please install GCC."
            result["error"] = error_message
            result["status_code"] = 1
            self.execution_results[execution_id] = result
            
            if websocket_manager:
                await websocket_manager.broadcast(
                    json.dumps({"status": "error", "error": error_message}),
                    execution_id
                )
            
            return execution_id, result
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, "program.c")
        executable_path = os.path.join(temp_dir, "program")
        
        try:
            # Send status update
            if websocket_manager:
                await websocket_manager.broadcast(
                    json.dumps({"status": "starting"}),
                    execution_id
                )
            
            # Write code to file
            with open(file_path, 'w') as f:
                f.write(code)
                
            # Send status update
            if websocket_manager:
                await websocket_manager.broadcast(
                    json.dumps({"status": "compiling"}),
                    execution_id
                )
                
            # Compile the code
            compile_process = subprocess.run(
                ['gcc', '-o', executable_path, file_path],
                capture_output=True,
                text=True
            )
            
            if compile_process.returncode != 0:
                # Compilation error
                result["error"] = compile_process.stderr
                result["status_code"] = compile_process.returncode
                
                # Send status update
                if websocket_manager:
                    await websocket_manager.broadcast(
                        json.dumps({"status": "compile_error", "error": compile_process.stderr}),
                        execution_id
                    )
            else:
                # Send status update
                if websocket_manager:
                    await websocket_manager.broadcast(
                        json.dumps({"status": "running"}),
                        execution_id
                    )
                    
                # Run the program
                try:
                    # Prepare input file if needed
                    if input_data:
                        input_file_path = os.path.join(temp_dir, "input.txt")
                        with open(input_file_path, 'w') as f:
                            f.write(input_data)
                        
                        # Run with input from file
                        with open(input_file_path, 'r') as input_file:
                            run_process = subprocess.run(
                                [executable_path],
                                stdin=input_file,
                                capture_output=True,
                                text=True,
                                timeout=10  # Timeout after 10 seconds
                            )
                    else:
                        # Run without input
                        run_process = subprocess.run(
                            [executable_path],
                            capture_output=True,
                            text=True,
                            timeout=10  # Timeout after 10 seconds
                        )
                    
                    result["output"] = run_process.stdout
                    if run_process.stderr:
                        result["error"] = run_process.stderr
                    result["status_code"] = run_process.returncode
                    
                except subprocess.TimeoutExpired:
                    result["error"] = "Execution timed out after 10 seconds"
                    result["status_code"] = 1
                except Exception as e:
                    result["error"] = f"Execution error: {str(e)}"
                    result["status_code"] = 1
                    
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["status_code"] = 1
            
            # Send status update
            if websocket_manager:
                await websocket_manager.broadcast(
                    json.dumps({"status": "error", "error": str(e)}),
                    execution_id
                )
        
        finally:
            # Clean up
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
            
            # Calculate execution time
            result["execution_time"] = time.time() - start_time
            
            # Store the result
            self.execution_results[execution_id] = result
            
            # Send final status update
            if websocket_manager:
                await websocket_manager.broadcast(
                    json.dumps({
                        "status": "completed",
                        "result": result
                    }),
                    execution_id
                )
            
            return execution_id, result