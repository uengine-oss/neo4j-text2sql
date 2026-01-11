"""
MCP (Model Context Protocol) 클라이언트

ProcessGPT의 work-assistant MCP 서버와 통신하여 프로세스를 실행합니다.

MCP 설정:
{
  "mcpServers": {
    "work-assistant": {
      "command": "uvx",
      "args": ["work-assistant-mcp"],
      "env": {
        "SUPABASE_URL": "https://your-project.supabase.co",
        "SUPABASE_ANON_KEY": "your-service-key"
      }
    }
  }
}
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.smart_logger import SmartLogger
from app.config import settings


@dataclass
class MCPServerConfig:
    """MCP 서버 설정"""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class MCPTool:
    """MCP 도구 정보"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPToolResult:
    """MCP 도구 실행 결과"""
    success: bool
    content: Any
    error: Optional[str] = None


class MCPClient:
    """
    MCP 클라이언트
    
    MCP 서버와 stdio를 통해 JSON-RPC로 통신합니다.
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._connected = False
        self._tools: List[MCPTool] = []
        self._lock = asyncio.Lock()
    
    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id
    
    async def connect(self) -> bool:
        """MCP 서버에 연결"""
        if self._connected:
            return True
        
        try:
            # 환경 변수 설정
            env = os.environ.copy()
            env.update(self.config.env)
            
            # MCP 서버 프로세스 시작
            cmd = [self.config.command] + self.config.args
            
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1
            )
            
            # 초기화 요청 전송
            init_result = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "robo-analyzer-event-detection",
                    "version": "1.0.0"
                }
            })
            
            if init_result:
                self._connected = True
                
                # 사용 가능한 도구 목록 조회
                tools_result = await self._send_request("tools/list", {})
                if tools_result and "tools" in tools_result:
                    self._tools = [
                        MCPTool(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                            input_schema=t.get("inputSchema", {})
                        )
                        for t in tools_result["tools"]
                    ]
                
                SmartLogger.log(
                    "INFO",
                    f"MCP client connected to {self.config.name}",
                    category="mcp.connect",
                    params={"server": self.config.name, "tools_count": len(self._tools)}
                )
                
                return True
            
            return False
            
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                f"Failed to connect to MCP server: {e}",
                category="mcp.connect.error",
                params={"server": self.config.name, "error": str(e)}
            )
            return False
    
    async def disconnect(self):
        """MCP 서버 연결 해제"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            
            self.process = None
        
        self._connected = False
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """JSON-RPC 요청 전송"""
        if not self.process or not self.process.stdin or not self.process.stdout:
            return None
        
        async with self._lock:
            try:
                request_id = self._next_request_id()
                request = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params
                }
                
                # 요청 전송
                request_str = json.dumps(request) + "\n"
                self.process.stdin.write(request_str)
                self.process.stdin.flush()
                
                # 응답 읽기 (비동기)
                loop = asyncio.get_event_loop()
                response_str = await loop.run_in_executor(
                    None, 
                    self.process.stdout.readline
                )
                
                if response_str:
                    response = json.loads(response_str)
                    
                    if "error" in response:
                        SmartLogger.log(
                            "ERROR",
                            f"MCP error: {response['error']}",
                            category="mcp.error",
                            params={"method": method, "error": response["error"]}
                        )
                        return None
                    
                    return response.get("result")
                
                return None
                
            except Exception as e:
                SmartLogger.log(
                    "ERROR",
                    f"MCP request failed: {e}",
                    category="mcp.request.error",
                    params={"method": method, "error": str(e)}
                )
                return None
    
    def get_tools(self) -> List[MCPTool]:
        """사용 가능한 도구 목록 반환"""
        return self._tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """도구 호출"""
        if not self._connected:
            connected = await self.connect()
            if not connected:
                return MCPToolResult(
                    success=False,
                    content=None,
                    error="MCP server not connected"
                )
        
        try:
            result = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            
            if result:
                # 결과 파싱
                content = result.get("content", [])
                
                # content가 리스트인 경우 첫 번째 항목의 text 추출
                if isinstance(content, list) and len(content) > 0:
                    first_item = content[0]
                    if isinstance(first_item, dict) and "text" in first_item:
                        try:
                            parsed_content = json.loads(first_item["text"])
                            return MCPToolResult(success=True, content=parsed_content)
                        except json.JSONDecodeError:
                            return MCPToolResult(success=True, content=first_item["text"])
                
                return MCPToolResult(success=True, content=content)
            
            return MCPToolResult(
                success=False,
                content=None,
                error="No response from MCP server"
            )
            
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                f"MCP tool call failed: {e}",
                category="mcp.tool.error",
                params={"tool": tool_name, "error": str(e)}
            )
            return MCPToolResult(
                success=False,
                content=None,
                error=str(e)
            )


class WorkAssistantClient:
    """
    ProcessGPT Work Assistant MCP 클라이언트
    
    프로세스 검색 및 실행을 위한 고수준 API를 제공합니다.
    """
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None
    ):
        # 환경 변수에서 설정 읽기
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_ANON_KEY", "")
        
        self.config = MCPServerConfig(
            name="work-assistant",
            command="uvx",
            args=["work-assistant-mcp"],
            env={
                "SUPABASE_URL": self.supabase_url,
                "SUPABASE_ANON_KEY": self.supabase_key
            }
        )
        
        self._client: Optional[MCPClient] = None
    
    async def _get_client(self) -> MCPClient:
        """MCP 클라이언트 인스턴스 반환"""
        if self._client is None:
            self._client = MCPClient(self.config)
        
        if not self._client._connected:
            await self._client.connect()
        
        return self._client
    
    async def search_processes(self, query: str) -> List[Dict[str, Any]]:
        """
        프로세스 검색
        
        Args:
            query: 검색 쿼리 (프로세스 이름 또는 설명)
        
        Returns:
            일치하는 프로세스 목록
        """
        try:
            client = await self._get_client()
            
            # work-assistant가 제공하는 도구 이름에 맞게 조정
            result = await client.call_tool("search_processes", {
                "query": query
            })
            
            if result.success:
                return result.content if isinstance(result.content, list) else [result.content]
            
            SmartLogger.log(
                "WARNING",
                f"Process search failed: {result.error}",
                category="work_assistant.search.error",
                params={"query": query, "error": result.error}
            )
            return []
            
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                f"Process search error: {e}",
                category="work_assistant.search.error",
                params={"query": query, "error": str(e)}
            )
            return []
    
    async def execute_process(
        self, 
        process_name: str, 
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        프로세스 실행
        
        Args:
            process_name: 실행할 프로세스 이름
            params: 프로세스 파라미터
            context: 실행 컨텍스트 (이벤트 데이터 등)
        
        Returns:
            실행 결과
        """
        try:
            client = await self._get_client()
            
            arguments = {
                "process_name": process_name,
                "parameters": params or {},
                "context": context or {}
            }
            
            # work-assistant가 제공하는 도구 이름에 맞게 조정
            result = await client.call_tool("execute_process", arguments)
            
            if result.success:
                SmartLogger.log(
                    "INFO",
                    f"Process executed: {process_name}",
                    category="work_assistant.execute",
                    params={"process_name": process_name, "result": result.content}
                )
                return {
                    "success": True,
                    "process_name": process_name,
                    "result": result.content
                }
            
            return {
                "success": False,
                "process_name": process_name,
                "error": result.error
            }
            
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                f"Process execution error: {e}",
                category="work_assistant.execute.error",
                params={"process_name": process_name, "error": str(e)}
            )
            return {
                "success": False,
                "process_name": process_name,
                "error": str(e)
            }
    
    async def get_process_status(self, execution_id: str) -> Dict[str, Any]:
        """
        프로세스 실행 상태 조회
        
        Args:
            execution_id: 실행 ID
        
        Returns:
            실행 상태 정보
        """
        try:
            client = await self._get_client()
            
            result = await client.call_tool("get_process_status", {
                "execution_id": execution_id
            })
            
            if result.success:
                return result.content
            
            return {"error": result.error}
            
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.disconnect()
            self._client = None


# 싱글톤 인스턴스
_work_assistant_client: Optional[WorkAssistantClient] = None


def get_work_assistant_client() -> WorkAssistantClient:
    """WorkAssistant 클라이언트 싱글톤 인스턴스 반환"""
    global _work_assistant_client
    
    if _work_assistant_client is None:
        _work_assistant_client = WorkAssistantClient()
    
    return _work_assistant_client


async def execute_process_via_mcp(
    process_name: str,
    params: Optional[Dict[str, Any]] = None,
    event_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    편의 함수: MCP를 통해 프로세스 실행
    
    Args:
        process_name: 프로세스 이름
        params: 프로세스 파라미터
        event_data: 이벤트 감지 결과 데이터
    
    Returns:
        실행 결과
    """
    client = get_work_assistant_client()
    
    context = {
        "source": "event-detection",
        "event_data": event_data or {}
    }
    
    return await client.execute_process(
        process_name=process_name,
        params=params,
        context=context
    )
