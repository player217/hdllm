"""
WebSocket Manager for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
Description: Real-time communication via WebSocket
"""

import json
import asyncio
import logging
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect, status
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)


# =============================================================================
# WebSocket Message Types
# =============================================================================

class MessageType(str, Enum):
    """WebSocket message types"""
    # Connection management
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PING = "ping"
    PONG = "pong"
    
    # Chat/RAG
    CHAT_MESSAGE = "chat_message"
    CHAT_RESPONSE = "chat_response"
    CHAT_STREAM = "chat_stream"
    CHAT_ERROR = "chat_error"
    
    # Status updates
    STATUS_UPDATE = "status_update"
    PROGRESS_UPDATE = "progress_update"
    
    # Document operations
    DOC_UPLOAD = "doc_upload"
    DOC_PROCESS = "doc_process"
    DOC_INDEX = "doc_index"
    
    # System notifications
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"
    
    # User presence
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"
    USER_STATUS = "user_status"


@dataclass
class WebSocketMessage:
    """Standard WebSocket message format"""
    type: MessageType
    data: Any
    user_id: Optional[str] = None
    timestamp: datetime = None
    message_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        msg_dict = asdict(self)
        msg_dict['timestamp'] = self.timestamp.isoformat()
        msg_dict['type'] = self.type.value
        return json.dumps(msg_dict)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """Create message from JSON string"""
        data = json.loads(json_str)
        if 'timestamp' in data:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'type' in data:
            data['type'] = MessageType(data['type'])
        return cls(**data)


# =============================================================================
# Connection Manager
# =============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections and message routing
    
    Features:
    - Connection pooling
    - Room/channel support
    - Broadcast capabilities
    - User presence tracking
    - Message queuing
    """
    
    def __init__(self):
        # Connection storage
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        
        # Room management
        self.rooms: Dict[str, Set[str]] = {}  # room -> connection_ids
        self.user_rooms: Dict[str, Set[str]] = {}  # user_id -> rooms
        
        # User status
        self.user_status: Dict[str, str] = {}  # user_id -> status
        
        # Message queue for offline users
        self.message_queue: Dict[str, List[WebSocketMessage]] = {}
        
        # Statistics
        self.stats = {
            "total_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0
        }
    
    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: Optional[str] = None
    ):
        """
        Accept and register a new WebSocket connection
        
        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
            user_id: Optional user identifier
        """
        await websocket.accept()
        
        self.active_connections[connection_id] = websocket
        self.stats["total_connections"] += 1
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            
            # Set user online
            await self.set_user_status(user_id, "online")
            
            # Send queued messages
            await self.send_queued_messages(user_id)
            
            # Notify others about user joining
            await self.broadcast_to_all(
                WebSocketMessage(
                    type=MessageType.USER_JOIN,
                    data={"user_id": user_id, "status": "online"}
                ),
                exclude=[connection_id]
            )
        
        logger.info(f"WebSocket connected: {connection_id} (user: {user_id})")
    
    async def disconnect(self, connection_id: str):
        """
        Disconnect and cleanup a WebSocket connection
        
        Args:
            connection_id: Connection identifier to disconnect
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            
            # Find associated user
            user_id = None
            for uid, conn_ids in self.user_connections.items():
                if connection_id in conn_ids:
                    user_id = uid
                    conn_ids.remove(connection_id)
                    if not conn_ids:
                        # Last connection for this user
                        del self.user_connections[uid]
                        await self.set_user_status(uid, "offline")
                        
                        # Notify others about user leaving
                        await self.broadcast_to_all(
                            WebSocketMessage(
                                type=MessageType.USER_LEAVE,
                                data={"user_id": uid, "status": "offline"}
                            ),
                            exclude=[connection_id]
                        )
                    break
            
            # Remove from rooms
            for room, conn_ids in self.rooms.items():
                if connection_id in conn_ids:
                    conn_ids.remove(connection_id)
            
            # Close WebSocket if still open
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
            
            del self.active_connections[connection_id]
            
            logger.info(f"WebSocket disconnected: {connection_id} (user: {user_id})")
    
    async def send_personal_message(
        self,
        message: WebSocketMessage,
        connection_id: str
    ) -> bool:
        """
        Send message to specific connection
        
        Args:
            message: Message to send
            connection_id: Target connection
            
        Returns:
            True if sent successfully, False otherwise
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(message.to_json())
                self.stats["messages_sent"] += 1
                return True
            except Exception as e:
                logger.error(f"Error sending to {connection_id}: {e}")
                self.stats["errors"] += 1
                await self.disconnect(connection_id)
                return False
        return False
    
    async def send_to_user(
        self,
        message: WebSocketMessage,
        user_id: str
    ) -> int:
        """
        Send message to all connections of a user
        
        Args:
            message: Message to send
            user_id: Target user
            
        Returns:
            Number of successful sends
        """
        if user_id in self.user_connections:
            success_count = 0
            for conn_id in list(self.user_connections[user_id]):
                if await self.send_personal_message(message, conn_id):
                    success_count += 1
            return success_count
        else:
            # Queue message for offline user
            if user_id not in self.message_queue:
                self.message_queue[user_id] = []
            self.message_queue[user_id].append(message)
            return 0
    
    async def broadcast_to_room(
        self,
        message: WebSocketMessage,
        room: str,
        exclude: Optional[List[str]] = None
    ) -> int:
        """
        Broadcast message to all connections in a room
        
        Args:
            message: Message to broadcast
            room: Target room
            exclude: Connection IDs to exclude
            
        Returns:
            Number of successful sends
        """
        if room not in self.rooms:
            return 0
        
        exclude = exclude or []
        success_count = 0
        
        for conn_id in list(self.rooms[room]):
            if conn_id not in exclude:
                if await self.send_personal_message(message, conn_id):
                    success_count += 1
        
        return success_count
    
    async def broadcast_to_all(
        self,
        message: WebSocketMessage,
        exclude: Optional[List[str]] = None
    ) -> int:
        """
        Broadcast message to all active connections
        
        Args:
            message: Message to broadcast
            exclude: Connection IDs to exclude
            
        Returns:
            Number of successful sends
        """
        exclude = exclude or []
        success_count = 0
        
        for conn_id in list(self.active_connections.keys()):
            if conn_id not in exclude:
                if await self.send_personal_message(message, conn_id):
                    success_count += 1
        
        return success_count
    
    async def join_room(self, connection_id: str, room: str):
        """Add connection to a room"""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(connection_id)
        
        # Track user rooms
        for user_id, conn_ids in self.user_connections.items():
            if connection_id in conn_ids:
                if user_id not in self.user_rooms:
                    self.user_rooms[user_id] = set()
                self.user_rooms[user_id].add(room)
                break
    
    async def leave_room(self, connection_id: str, room: str):
        """Remove connection from a room"""
        if room in self.rooms and connection_id in self.rooms[room]:
            self.rooms[room].remove(connection_id)
            if not self.rooms[room]:
                del self.rooms[room]
    
    async def set_user_status(self, user_id: str, status: str):
        """Update user status"""
        self.user_status[user_id] = status
        
        # Broadcast status change
        await self.broadcast_to_all(
            WebSocketMessage(
                type=MessageType.USER_STATUS,
                data={"user_id": user_id, "status": status}
            )
        )
    
    async def send_queued_messages(self, user_id: str):
        """Send queued messages to user when they come online"""
        if user_id in self.message_queue:
            messages = self.message_queue[user_id]
            del self.message_queue[user_id]
            
            for message in messages:
                await self.send_to_user(message, user_id)
    
    def get_online_users(self) -> List[str]:
        """Get list of online users"""
        return list(self.user_connections.keys())
    
    def get_room_users(self, room: str) -> List[str]:
        """Get list of users in a room"""
        users = []
        if room in self.rooms:
            for conn_id in self.rooms[room]:
                for user_id, conn_ids in self.user_connections.items():
                    if conn_id in conn_ids:
                        users.append(user_id)
                        break
        return users
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            **self.stats,
            "active_connections": len(self.active_connections),
            "online_users": len(self.user_connections),
            "active_rooms": len(self.rooms),
            "queued_messages": sum(len(msgs) for msgs in self.message_queue.values())
        }


# =============================================================================
# WebSocket Handler
# =============================================================================

class WebSocketHandler:
    """
    Handles WebSocket message processing and routing
    """
    
    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        self.handlers = {
            MessageType.PING: self.handle_ping,
            MessageType.CHAT_MESSAGE: self.handle_chat_message,
            MessageType.STATUS_UPDATE: self.handle_status_update,
        }
    
    async def handle_message(
        self,
        message: WebSocketMessage,
        connection_id: str
    ):
        """
        Route message to appropriate handler
        
        Args:
            message: Received message
            connection_id: Source connection
        """
        handler = self.handlers.get(message.type)
        if handler:
            await handler(message, connection_id)
        else:
            logger.warning(f"No handler for message type: {message.type}")
    
    async def handle_ping(self, message: WebSocketMessage, connection_id: str):
        """Handle ping message"""
        pong = WebSocketMessage(
            type=MessageType.PONG,
            data={"timestamp": datetime.now().isoformat()}
        )
        await self.manager.send_personal_message(pong, connection_id)
    
    async def handle_chat_message(self, message: WebSocketMessage, connection_id: str):
        """Handle chat message"""
        # Process chat message (integrate with RAG pipeline)
        # This is where you'd call the RAG system
        
        # For now, echo back
        response = WebSocketMessage(
            type=MessageType.CHAT_RESPONSE,
            data={
                "echo": message.data,
                "processed_at": datetime.now().isoformat()
            }
        )
        await self.manager.send_personal_message(response, connection_id)
    
    async def handle_status_update(self, message: WebSocketMessage, connection_id: str):
        """Handle status update"""
        if message.user_id:
            status = message.data.get("status", "online")
            await self.manager.set_user_status(message.user_id, status)


# =============================================================================
# Global Manager Instance
# =============================================================================

# Create singleton manager instance
manager = ConnectionManager()
handler = WebSocketHandler(manager)


# =============================================================================
# WebSocket Endpoint
# =============================================================================

async def websocket_endpoint(
    websocket: WebSocket,
    connection_id: str,
    user_id: Optional[str] = None
):
    """
    Main WebSocket endpoint handler
    
    Args:
        websocket: WebSocket connection
        connection_id: Unique connection ID
        user_id: Optional user ID
    """
    await manager.connect(websocket, connection_id, user_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            try:
                # Parse message
                message = WebSocketMessage.from_json(data)
                message.user_id = user_id
                
                # Handle message
                await handler.handle_message(message, connection_id)
                
                manager.stats["messages_received"] += 1
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {connection_id}: {data}")
                error_msg = WebSocketMessage(
                    type=MessageType.CHAT_ERROR,
                    data={"error": "Invalid message format"}
                )
                await manager.send_personal_message(error_msg, connection_id)
            
    except WebSocketDisconnect:
        await manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
        await manager.disconnect(connection_id)