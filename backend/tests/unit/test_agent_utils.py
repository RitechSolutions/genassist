"""
Unit tests for agent_utils parsing functions
"""
import pytest
from app.modules.workflow.agents.agent_utils import parse_json_response, extract_direct_response


class TestParseJsonResponse:
    """Tests for parse_json_response function"""
    
    def test_parse_normal_json(self):
        """Test parsing normal JSON response"""
        response = '{ "action": "tool_call", "tool_name": "search", "parameters": {"query": "test"} }'
        result = parse_json_response(response)
        
        assert result is not None
        assert result["action"] == "tool_call"
        assert result["tool_name"] == "search"
        assert result["parameters"]["query"] == "test"
    
    def test_parse_double_curly_braces(self):
        """Test parsing JSON wrapped in double curly braces (weak model behavior)"""
        response = '{{ "action": "direct_response", "response": "Hi! I\'m here to help you with information about GenAgent, a framework for building AI agents. How can I assist you today?", "reasoning": "Based on my knowledge, providing a friendly greeting and offering assistance is a common and appropriate response to a general greeting." }}'
        result = parse_json_response(response)
        
        assert result is not None
        assert result["action"] == "direct_response"
        assert "Hi! I'm here to help you" in result["response"]
        assert result["reasoning"] is not None
    
    def test_parse_json_with_extra_text(self):
        """Test parsing JSON with surrounding text"""
        response = 'Some text before { "action": "tool_call", "tool_name": "search" } some text after'
        result = parse_json_response(response)
        
        assert result is not None
        assert result["action"] == "tool_call"
        assert result["tool_name"] == "search"
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns None"""
        response = 'This is not JSON at all'
        result = parse_json_response(response)
        
        assert result is None
    
    def test_parse_empty_string(self):
        """Test parsing empty string"""
        response = ''
        result = parse_json_response(response)
        
        assert result is None


class TestExtractDirectResponse:
    """Tests for extract_direct_response function"""
    
    def test_extract_normal_direct_response(self):
        """Test extracting direct response from normal JSON"""
        response = '{ "action": "direct_response", "response": "Hello, how can I help you?" }'
        result = extract_direct_response(response)
        
        assert result == "Hello, how can I help you?"
    
    def test_extract_direct_response_with_double_curly_braces(self):
        """Test extracting direct response from JSON with double curly braces"""
        response = '{{ "action": "direct_response", "response": "Hi! I\'m here to help you with information about GenAgent, a framework for building AI agents. How can I assist you today?", "reasoning": "Based on my knowledge, providing a friendly greeting and offering assistance is a common and appropriate response to a general greeting." }}'
        result = extract_direct_response(response)
        
        assert result is not None
        assert "Hi! I'm here to help you" in result
        assert "GenAgent" in result
    
    def test_extract_direct_response_empty_response_field(self):
        """Test extracting direct response with empty response field"""
        response = '{ "action": "direct_response", "response": "" }'
        result = extract_direct_response(response)
        
        assert result == ""
    
    def test_extract_direct_response_missing_response_field(self):
        """Test extracting direct response with missing response field"""
        response = '{ "action": "direct_response" }'
        result = extract_direct_response(response)
        
        assert result == ""
    
    def test_extract_non_direct_response_json(self):
        """Test extracting from non-direct-response JSON returns None"""
        response = '{ "action": "tool_call", "tool_name": "search" }'
        result = extract_direct_response(response)
        
        assert result is None
    
    def test_extract_plain_text(self):
        """Test extracting from plain text returns the text"""
        response = 'This is just plain text without JSON'
        result = extract_direct_response(response)
        
        assert result == response
    
    def test_extract_direct_response_fallback_parsing(self):
        """Test fallback parsing with double curly braces"""
        response = '{{ "action": "direct_response", "response": "Test response" }}'
        result = extract_direct_response(response)
        
        assert result == "Test response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
