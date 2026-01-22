1. 修改`director_assistant.py`中的`assistant_prompt`，将回复格式要求改为JSON格式，包含`idea`和`need_to_confirm`字段，注意强调返只能是纯json，并给出示例和各字段说明。
2. 修改`run_acps.py`中的`extract_idea`函数，使其能够解析JSON字符串并提取`idea`字段
3. 确保修改后的代码能够正常工作，不影响其他功能

