from datetime import datetime
from typing import Dict, Any
import json
from pathlib import Path

class TokenTracker:
    def __init__(self, storage_path: str = "Data/token_usage.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(exist_ok=True)
        self._load_usage_data()

    def _load_usage_data(self):
        """Load existing token usage data"""
        if self.storage_path.exists():
            with open(self.storage_path, 'r') as f:
                self.usage_data = json.load(f)
        else:
            self.usage_data = {
                "total_tokens": 0,
                "daily_usage": {},
                "provider_usage": {}
            }
            self._save_usage_data()

    def _save_usage_data(self):
        """Save token usage data to file"""
        with open(self.storage_path, 'w') as f:
            json.dump(self.usage_data, f, indent=2)

    def track_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ):
        """Track token usage for a request"""
        total_tokens = prompt_tokens + completion_tokens
        today = datetime.now().strftime("%Y-%m-%d")

        # Update total usage
        self.usage_data["total_tokens"] += total_tokens

        # Update daily usage
        if today not in self.usage_data["daily_usage"]:
            self.usage_data["daily_usage"][today] = {
                "tokens": 0
            }
        self.usage_data["daily_usage"][today]["tokens"] += total_tokens

        # Update provider usage
        if provider not in self.usage_data["provider_usage"]:
            self.usage_data["provider_usage"][provider] = {
                "total_tokens": 0,
                "models": {}
            }
        
        self.usage_data["provider_usage"][provider]["total_tokens"] += total_tokens

        # Update model usage
        if model not in self.usage_data["provider_usage"][provider]["models"]:
            self.usage_data["provider_usage"][provider]["models"][model] = {
                "total_tokens": 0
            }
        
        self.usage_data["provider_usage"][provider]["models"][model]["total_tokens"] += total_tokens

        self._save_usage_data()

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get summary of token usage"""
        return self.usage_data

    def get_daily_usage(self, days: int = 30) -> Dict[str, Any]:
        """Get daily usage for the last N days"""
        return {
            k: v for k, v in self.usage_data["daily_usage"].items()
            if (datetime.now() - datetime.strptime(k, "%Y-%m-%d")).days <= days
        } 