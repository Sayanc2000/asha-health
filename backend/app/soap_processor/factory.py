from typing import Dict, Any
import os
from .default_processor import DefaultSOAPProcessor
from .mock_processor import MockSOAPProcessor
from .base import BaseSOAPProcessor
from loguru import logger
from ..config import get_settings

# Get settings for configuration
settings = get_settings()

def get_soap_processor(provider: str = "default", **kwargs) -> BaseSOAPProcessor:
    """
    Factory method to return an instance of a SOAP processor.
    Switching providers later is as simple as adding another branch here.
    
    Args:
        provider: The provider to use for SOAP processing
        **kwargs: Additional arguments to pass to the processor
        
    Returns:
        An instance of a BaseSOAPProcessor implementation
        
    Raises:
        ValueError: If the provider is unknown
    """
    # Use settings or environment variables if not explicitly provided
    endpoint = kwargs.get("endpoint") or settings.SOAP_API_ENDPOINT
    api_key = kwargs.get("api_key") or settings.SOAP_API_KEY
    
    if not api_key:
        logger.warning("No SOAP API key provided, using empty string")
        api_key = ""
    
    logger.debug(f"Creating SOAP processor with provider: {provider}")
    
    if provider == "default":
        return DefaultSOAPProcessor(endpoint=endpoint, api_key=api_key)
    elif provider == "mock":
        return MockSOAPProcessor(endpoint=endpoint, api_key=api_key)
    else:
        raise ValueError(f"Unknown SOAP processor provider: {provider}") 
