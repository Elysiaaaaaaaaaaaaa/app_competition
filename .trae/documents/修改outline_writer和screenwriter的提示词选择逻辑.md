## 修改计划

### 1. 修改 outline\_writer.py

**当前逻辑**：

* 根据 `session_data['last_id']['outline_writer']` 是否为空来选择提示词

* 为空时使用首次创作的 `outline_develop_prompt`

* 不为空时使用修改的 `outline_modify_prompt`

**修改后逻辑**：

* 根据 `session_data['material']` 中是否存在 outline 相关内容来选择提示词

* 检查 `session_data['material'].get('outline')` 是否存在且不为空

* 如果存在，使用 `outline_modify_prompt`

* 否则，使用 `outline_develop_prompt`

**修改位置**：

* `call` 方法 (第101-151行)

* init\_assistant方法

### 2. 修改 screenwriter.py

**当前逻辑**：

* 根据 `self.screen` 是否为空来选择提示词

* 为空时使用首次创作的 `screen_prompt`

* 不为空时使用修改提示词

**修改后逻辑**：

* 根据 `session_data['material']` 中是否存在 screen 相关内容来选择提示词

* 检查 `session_data['material'].get('screen')` 是否存在且不为空

* 如果存在，使用修改提示词

* 否则，使用 `screen_prompt`

**修改位置**：

* `call` 方法 (第196-256行)

* init\_assistant方法

### 3. 具体修改点

#### outline\_writer.py

* 在 `call` 和init\_assistant方法中，将条件判断从 `if not session_data['last_id']['outline_writer']` 改为基于 `session_data['material']['outline']` 的存在性

* 调整相关逻辑，确保在首次创作和修改场景下都能正确处理

#### screenwriter.py

* 在 `call` 方法中，将条件判断从 `if not self.screen` 改为基于 `session_data['material']['screen']` 的存在性

* 调整相关逻辑，确保在首次创作和修改场景下都能正确处理

### 4. 预期效果

修改完成后，两个模块将根据 `session_data['material']` 中是否已经存在对应内容来智能选择提示词，实现：

* 当 material 中没有对应内容时，使用首次创作提示词

* 当 material 中已有对应内容时，使用修改提示词

* 提高了系统的灵活性和适应性，能够更好地处理不同场景下的请求

