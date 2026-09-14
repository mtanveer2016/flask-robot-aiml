"""
Ollama Client - Handles communication with Ollama LLM
"""

import json
import requests
from typing import Dict, Any, List, Optional, Generator
from dataclasses import dataclass, field


@dataclass
class Message:
    """Chat message structure"""
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


class OllamaClient:
    """Client for interacting with Ollama API"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.base_url = base_url
        self.model = model
        self.conversation_history: List[Message] = []
    
    def set_model(self, model: str):
        """Change the model being used"""
        self.model = model
    
    def add_message(self, role: str, content: str, tool_calls: Optional[List[Dict]] = None):
        """Add a message to conversation history"""
        self.conversation_history.append(Message(role=role, content=content, tool_calls=tool_calls))
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    def chat(self, message: str, tools: Optional[List[Dict]] = None, 
             system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a chat message to Ollama and get response.
        
        Args:
            message: User message
            tools: List of tool schemas for function calling
            system_prompt: Optional system prompt
        
        Returns:
            Dict with 'content' and 'tool_calls' if any
        """
        # Build messages
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history
        for msg in self.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        # Prepare request
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
        
        # Make request
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract response
            assistant_message = result.get("message", {})
            content = assistant_message.get("content", "")
            tool_calls = assistant_message.get("tool_calls", [])
            
            # Save to history
            self.add_message("user", message)
            self.add_message("assistant", content, tool_calls)
            
            return {
                "content": content,
                "tool_calls": tool_calls,
                "raw": result
            }
            
        except requests.exceptions.RequestException as e:
            return {"error": f"Ollama API error: {str(e)}"}
    
    def chat_stream(self, message: str, tools: Optional[List[Dict]] = None,
                    system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """
        Stream chat response from Ollama
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        for msg in self.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        
        messages.append({"role": "user", "content": message})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=60
            )
            response.raise_for_status()
            
            full_content = ""
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if "message" in chunk and "content" in chunk["message"]:
                        content = chunk["message"]["content"]
                        full_content += content
                        yield content
            
            # Save to history
            self.add_message("user", message)
            self.add_message("assistant", full_content)
            
        except requests.exceptions.RequestException as e:
            yield f"Error: {str(e)}"
    
    def check_available(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self) -> List[str]:
        """List available models in Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except:
            return []
