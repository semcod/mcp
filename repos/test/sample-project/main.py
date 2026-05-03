"""Sample project for testing MCP Skills"""
import os
import sys
import json
import logging
from typing import Dict, List

class DataProcessor:
    """Main data processor class"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def process(self, data: List[Dict]) -> List[Dict]:
        results = []
        for item in data:
            processed = self._transform(item)
            results.append(processed)
        return results

    def _transform(self, item: Dict) -> Dict:
        return {k: v.upper() if isinstance(v, str) else v for k, v in item.items()}

def main():
    processor = DataProcessor({"debug": True})
    data = [{"name": "test", "value": 123}]
    results = processor.process(data)
    print(json.dumps(results))

if __name__ == "__main__":
    main()
