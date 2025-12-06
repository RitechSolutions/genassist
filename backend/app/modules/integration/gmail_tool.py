
from typing import Dict, Any, List, Union, Optional
import json
import logging
import aiohttp
from app.core.utils.string_utils import replace_template_vars
from app.modules.agents.workflow.base_processor import NodeProcessor
from typing import TYPE_CHECKING
from .gmail_connector import GmailConnector
if TYPE_CHECKING:
    from app.modules.agents.workflow.builder import  WorkflowContext

logger = logging.getLogger(__name__)


class GmailToolNodeProcessor(NodeProcessor):
    """Processor for Gmail tool nodes"""
    
    def __init__(self, context: 'WorkflowContext', node_id: str, node_config: Dict[str, Any]):
        super().__init__(context, node_id, node_config)
        ds_id = node_config.get("dataSourceId", None)
        self.gmail_connector = GmailConnector(ds_id)
    
    async def _send_email(self, to: str, subject: str, body: str, 
                         html_body: Optional[str] = None, cc: Optional[List[str]] = None,
                         bcc: Optional[List[str]] = None, attachments: Optional[List[str]] = None) -> Dict[str, Any]:
        """Send email via Gmail"""
        try:
            if not self.gmail_connector:
                raise Exception("Gmail connector not initialized")
            
            result = await self.gmail_connector.send_email(
                to=to,
                subject=subject,
                body=body,
                html_body=html_body,
                cc=cc,
                bcc=bcc,
                attachments=attachments
            )
            
            return {
                "status": 200,
                "data": result,
                "operation": "send_email"
            }
            
        except Exception as e:
            logger.error(f"Gmail send email failed: {str(e)}")
            return {
                "status": 500,
                "data": {"error": str(e)},
                "operation": "send_email"
            }
    
    async def _get_messages(self, query: str = '', max_results: int = 10,
                          include_spam_trash: bool = False) -> Dict[str, Any]:
        """Retrieve messages from Gmail"""
        try:
            if not self.gmail_connector:
                raise Exception("Gmail connector not initialized")
            
            messages = await self.gmail_connector.get_messages(
                query=query,
                max_results=max_results,
                include_spam_trash=include_spam_trash
            )
            
            return {
                "status": 200,
                "data": {
                    "messages": messages,
                    "count": len(messages),
                    "query": query
                },
                "operation": "get_messages"
            }
            
        except Exception as e:
            logger.error(f"Gmail get messages failed: {str(e)}")
            return {
                "status": 500,
                "data": {"error": str(e)},
                "operation": "get_messages"
            }
    
    async def _mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark message as read"""
        try:
            if not self.gmail_connector:
                raise Exception("Gmail connector not initialized")
            
            success = await self.gmail_connector.mark_as_read(message_id)
            
            return {
                "status": 200,
                "data": {
                    "success": success,
                    "message_id": message_id,
                    "action": "marked_as_read"
                },
                "operation": "mark_as_read"
            }
            
        except Exception as e:
            logger.error(f"Gmail mark as read failed: {str(e)}")
            return {
                "status": 500,
                "data": {"error": str(e)},
                "operation": "mark_as_read"
            }
    
    async def _delete_message(self, message_id: str) -> Dict[str, Any]:
        """Delete message"""
        try:
            if not self.gmail_connector:
                raise Exception("Gmail connector not initialized")
            
            success = self.gmail_connector.delete_message(message_id)
            
            return {
                "status": 200,
                "data": {
                    "success": success,
                    "message_id": message_id,
                    "action": "deleted"
                },
                "operation": "delete_message"
            }
            
        except Exception as e:
            logger.error(f"Gmail delete message failed: {str(e)}")
            return {
                "status": 500,
                "data": {"error": str(e)},
                "operation": "delete_message"
            }
    
    async def _reply_to_email(self, message_id: str, reply_body: str,
                            original_email: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Reply to an email"""
        try:
            if not self.gmail_connector:
                raise Exception("Gmail connector not initialized")
            
            # If original email not provided, get it
            if not original_email:
                messages = self.gmail_connector.get_messages(query=f"rfc822msgid:{message_id}", max_results=1)
                if not messages:
                    raise Exception(f"Original email not found: {message_id}")
                original_email = messages[0]
            
            # Extract reply information
            original_from = original_email.get('from', '')
            original_subject = original_email.get('subject', '')
            
            # Add "Re:" if not present
            reply_subject = original_subject
            if not reply_subject.startswith('Re:'):
                reply_subject = f"Re: {reply_subject}"
            
            # Send reply
            result = self.gmail_connector.send_email(
                to=original_from,
                subject=reply_subject,
                body=reply_body,
            )
            
            return {
                "status": 200,
                "data": {
                    **result,
                    "original_message_id": message_id,
                    "reply_to": original_from
                },
                "operation": "reply_to_email"
            }
            
        except Exception as e:
            logger.error(f"Gmail reply failed: {str(e)}")
            return {
                "status": 500,
                "data": {"error": str(e)},
                "operation": "reply_to_email"
            }
    
    async def _search_emails(self, search_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Advanced email search with multiple criteria"""
        try:
            if not self.gmail_connector:
                raise Exception("Gmail connector not initialized")
        
            
            messages = self.gmail_connector.search_emails(
                search_criteria=search_criteria
            )
            
            return {
                "status": 200,
                "data": {
                    "messages": messages,
                    "count": len(messages),
                    "search_criteria": search_criteria
                },
                "operation": "search_emails"
            }
            
        except Exception as e:
            logger.error(f"Gmail search failed: {str(e)}")
            return {
                "status": 500,
                "data": {"error": str(e)},
                "operation": "search_emails"
            }
    
    async def process(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process Gmail tool node with direct input reading"""
        
        if not input_data:
            input_data = {}
        
        # Read operation directly from input_data
        operation = input_data.get("operation", "")
        
        if not operation:
            error_msg = "No operation specified for Gmail tool"
            logger.error(error_msg)
            self.output = {
                "status": 400,
                "data": {"error": error_msg},
                "operation": "unknown"
            }
            return self.output
        
        try:
            # Log the operation for debugging
            logger.debug(f"Processing Gmail operation: {operation}")
            logger.debug(f"Input data keys: {list(input_data.keys())}")
            
            # Execute the appropriate Gmail operation with direct parameter reading
            if operation == "send_email":
                response = await self._send_email(
                    to=input_data.get("to", ""),
                    subject=input_data.get("subject", ""),
                    body=input_data.get("body", ""),
                    html_body=input_data.get("html_body"),
                    cc=input_data.get("cc"),
                    bcc=input_data.get("bcc"),
                    attachments=input_data.get("attachments")
                )
            
            elif operation == "get_messages":
                response = await self._get_messages(
                    query=input_data.get("query", ""),
                    max_results=input_data.get("max_results", 10),
                    include_spam_trash=input_data.get("include_spam_trash", False),
                )
            
            elif operation == "mark_as_read":
                response = await self._mark_as_read(
                    message_id=input_data.get("message_id", ""),
                )
            
            elif operation == "delete_message":
                response = await self._delete_message(
                    message_id=input_data.get("message_id", ""),
                )
            
            elif operation == "reply_to_email":
                response = await self._reply_to_email(
                    message_id=input_data.get("message_id", ""),
                    reply_body=input_data.get("reply_body", ""),
                    original_email=input_data.get("original_email"),
                )
            
            elif operation == "search_emails":
                response = await self._search_emails(
                    search_criteria=input_data.get("search_criteria", {}),
                )
            
            else:
                error_msg = f"Unsupported Gmail operation: {operation}"
                logger.error(error_msg)
                response = {
                    "status": 400,
                    "data": {"error": error_msg},
                    "operation": operation
                }
            
            #self.save_output(response)
            return response
            
        except Exception as e:
            error_msg = f"Error processing Gmail tool: {str(e)}"
            logger.error(error_msg)
            self.output = {
                "status": 500,
                "data": {"error": error_msg},
                "operation": operation
            }
            return self.output