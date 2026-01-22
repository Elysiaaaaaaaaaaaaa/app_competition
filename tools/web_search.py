from tavily import TavilyClient
api = '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'
client = TavilyClient(api)

def web_search(query,cnt):
    print(f"正在搜索：{query}")
    if cnt<=6:
        response = client.search(
            query=query,
            search_depth="basic"
        )
    else:
        response = {
            "error": {
                "code": "SearchExceeded",
                "message": "搜索次数已超过6次,请根据之前返回的内容为用户回答问题",
                "type": "Exceeded"
            }
        }
    return response