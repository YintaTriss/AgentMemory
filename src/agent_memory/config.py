"""
AgentMemory v0.3 - Configuration Module

Environment variables and default settings for AgentMemory.
Zero external dependencies - works with folder + optional embedding model.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any


class Config:
    """Configuration class for AgentMemory v0.3"""
    
    # Default paths
    DEFAULT_MEMORY_DIR = "memory"
    DEFAULT_DATA_DIR = "data"
    
    # Embedder settings
    EMBEDDER_HASH = "hash"  # Fast, no API needed
    EMBEDDER_DASHSCOPE = "dashscope"
    EMBEDDER_OPENAI = "openai"
    EMBEDDER_LOCAL = "local"
    
    def __init__(self, memory_dir: Optional[str] = None, embedder: str = "hash"):
        """
        Initialize configuration.
        
        Args:
            memory_dir: Directory for memory storage (default: "memory")
            embedder: Embedder type - "hash", "dashscope", "openai", "local"
        """
        self.memory_dir = memory_dir or os.environ.get("AGENT_MEMORY_DIR", self.DEFAULT_MEMORY_DIR)
        self.data_dir = os.environ.get("AGENT_MEMORY_DATA_DIR", self.DEFAULT_DATA_DIR)
        valid_embedders = {self.EMBEDDER_HASH, self.EMBEDDER_DASHSCOPE,
                            self.EMBEDDER_OPENAI, self.EMBEDDER_LOCAL}
        if embedder not in valid_embedders:
            raise ValueError(f"embedder must be one of {valid_embedders}, got: {embedder}")
        self.embedder = embedder
        
        # Ensure directories exist
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        
        # Embedder configuration
        self.embedding_dims = 1536  # Default for OpenAI/hash
        self._load_embedder_config()
    
    def _load_embedder_config(self):
        """Load embedder-specific configuration from environment."""
        if self.embedder == self.EMBEDDER_HASH:
            self.embedding_dims = 1536  # HashEmbedder uses 1536-dim vectors
        elif self.embedder == self.EMBEDDER_DASHSCOPE:
            self.dashscope_api_key = os.environ.get("DASHSCOPE_API_KEY", "")
            self.embedding_dims = 1536
        elif self.embedder == self.EMBEDDER_OPENAI:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
            self.embedding_dims = 1536
        elif self.embedder == self.EMBEDDER_LOCAL:
            self.local_model_path = os.environ.get("LOCAL_EMBED_MODEL_PATH", "bge-large-zh")
            self.embedding_dims = 1024
    
    def get_memory_path(self, *parts) -> Path:
        """Get path within memory directory."""
        return Path(self.memory_dir, *parts)
    
    def get_data_path(self, *parts) -> Path:
        """Get path within data directory."""
        return Path(self.data_dir, *parts)


# Global config instance
_config: Optional[Config] = None


def get_config(memory_dir: Optional[str] = None, embedder: str = "hash") -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None or memory_dir is not None:
        _config = Config(memory_dir=memory_dir, embedder=embedder)
    return _config


def reset_config():
    """Reset global config (useful for testing)."""
    global _config
    _config = None
