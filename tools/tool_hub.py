ark_web_search = [{
    "type": "function",
    "name": "web_search",
    "description": "联网搜索资料。当用户需要了解某个具体的信息，或用户提出的概念你不了解，以及对视频创作有不了解时，使用此工具。不能连续使用",
    "parameters": {
        "type": "object",
        "properties": {
        "query": {
            "type": "string",
            "description": "需要进行联网搜索进行确认的内容"
        }
        },
        "required": ["query"]
    },
    "strict": True
}]
