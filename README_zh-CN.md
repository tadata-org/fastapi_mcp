<p align="center"><a href="https://github.com/tadata-org/fastapi_mcp"><img src="https://github.com/user-attachments/assets/609d5b8b-37a1-42c4-87e2-f045b60026b1" alt="fastapi-to-mcp" height="100"/></a></p>
<h1 align="center">FastAPI-MCP</h1>
<p align="center">一个零配置工具，用于自动将FastAPI端点暴露为模型上下文协议（MCP）工具。</p>
<div align="center">

[![PyPI version](https://badge.fury.io/py/fastapi-mcp.svg)](https://pypi.org/project/fastapi-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastapi-mcp.svg)](https://pypi.org/project/fastapi-mcp/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009485.svg?logo=fastapi&logoColor=white)](#)
![](https://badge.mcpx.dev?type=dev 'MCP Dev')
[![CI](https://github.com/tadata-org/fastapi_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/tadata-org/fastapi_mcp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tadata-org/fastapi_mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/tadata-org/fastapi_mcp)

</div>

<p align="center"><a href="https://github.com/tadata-org/fastapi_mcp"><img src="https://github.com/user-attachments/assets/1cba1bf2-2fa4-46c7-93ac-1e9bb1a95257" alt="fastapi-mcp-usage" height="400"/></a></p>

## 特点

- **直接集成** - 直接将MCP服务器挂载到您的FastAPI应用
- **零配置** - 只需指向您的FastAPI应用即可工作
- **自动发现**所有FastAPI端点并转换为MCP工具
- **保留模式** - 保留您的请求模型和响应模型的模式
- **保留文档** - 保留所有端点的文档，就像在Swagger中一样
- **灵活部署** - 将MCP服务器挂载到同一应用，或单独部署

## 安装

我们推荐使用[uv](https://docs.astral.sh/uv/)，一个快速的Python包安装器：

```bash
uv add fastapi-mcp
```

或者，您可以使用pip安装：

```bash
pip install fastapi-mcp
```

## 基本用法

使用FastAPI-MCP的最简单方法是直接将MCP服务器添加到您的FastAPI应用中：

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

mcp = FastApiMCP(
    app,

    # 可选参数
    name="我的API MCP",
    description="我的API描述",
    base_url="http://localhost:8000",
)

# 直接将MCP服务器挂载到您的FastAPI应用
mcp.mount()
```

就是这样！您的自动生成的MCP服务器现在可以在`https://app.base.url/mcp`访问。

> **关于`base_url`的注意事项**：虽然`base_url`是可选的，但强烈建议您明确提供它。`base_url`告诉MCP服务器在调用工具时向何处发送API请求。如果不提供，库将尝试自动确定URL，这在部署环境中内部和外部URL不同时可能无法正确工作。

## 工具命名

FastAPI-MCP使用FastAPI路由中的`operation_id`作为MCP工具的名称。如果您不指定`operation_id`，FastAPI会自动生成一个，但这些名称可能比较晦涩。

比较以下两个端点定义：

```python
# 自动生成的operation_id（类似于"read_user_users__user_id__get"）
@app.get("/users/{user_id}")
async def read_user(user_id: int):
    return {"user_id": user_id}

# 显式operation_id（工具将被命名为"get_user_info"）
@app.get("/users/{user_id}", operation_id="get_user_info")
async def read_user(user_id: int):
    return {"user_id": user_id}
```

为了获得更清晰、更直观的工具名称，我们建议在FastAPI路由定义中添加显式的`operation_id`参数。

要了解更多信息，请阅读FastAPI官方文档中关于[路径操作的高级配置](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/)的部分。

## 高级用法

FastAPI-MCP提供了多种方式来自定义和控制MCP服务器的创建和配置。以下是一些高级用法模式：

### 自定义模式描述

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

mcp = FastApiMCP(
    app,
    name="我的API MCP",
    base_url="http://localhost:8000",
    describe_all_responses=True,     # 在工具描述中包含所有可能的响应模式
    describe_full_response_schema=True  # 在工具描述中包含完整的JSON模式
)

mcp.mount()
```

### 自定义暴露的端点

您可以使用Open API操作ID或标签来控制哪些FastAPI端点暴露为MCP工具：

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

# 仅包含特定操作
mcp = FastApiMCP(
    app,
    include_operations=["get_user", "create_user"]
)

# 排除特定操作
mcp = FastApiMCP(
    app,
    exclude_operations=["delete_user"]
)

# 仅包含具有特定标签的操作
mcp = FastApiMCP(
    app,
    include_tags=["users", "public"]
)

# 排除具有特定标签的操作
mcp = FastApiMCP(
    app,
    exclude_tags=["admin", "internal"]
)

# 结合操作ID和标签（包含模式）
mcp = FastApiMCP(
    app,
    include_operations=["user_login"],
    include_tags=["public"]
)

mcp.mount()
```

关于过滤的注意事项：
- 您不能同时使用`include_operations`和`exclude_operations`
- 您不能同时使用`include_tags`和`exclude_tags`
- 您可以将操作过滤与标签过滤结合使用（例如，使用`include_operations`和`include_tags`）
- 当结合过滤器时，将采取贪婪方法。匹配任一标准的端点都将被包含

### 与原始FastAPI应用分开部署

您不限于在创建MCP的同一个FastAPI应用上提供MCP服务。

您可以从一个FastAPI应用创建MCP服务器，并将其挂载到另一个应用上：

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# 您的API应用
api_app = FastAPI()
# ... 在api_app上定义您的API端点 ...

# 一个单独的MCP服务器应用
mcp_app = FastAPI()

# 从API应用创建MCP服务器
mcp = FastApiMCP(
    api_app,
    base_url="http://api-host:8001",  # API应用将运行的URL
)

# 将MCP服务器挂载到单独的应用
mcp.mount(mcp_app)

# 现在您可以分别运行两个应用：
# uvicorn main:api_app --host api-host --port 8001
# uvicorn main:mcp_app --host mcp-host --port 8000
```

### 在MCP服务器创建后添加端点

如果您在创建MCP服务器后向FastAPI应用添加端点，您需要刷新服务器以包含它们：

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()
# ... 定义初始端点 ...

# 创建MCP服务器
mcp = FastApiMCP(app)
mcp.mount()

# 在MCP服务器创建后添加新端点
@app.get("/new/endpoint/", operation_id="new_endpoint")
async def new_endpoint():
    return {"message": "Hello, world!"}

# 刷新MCP服务器以包含新端点
mcp.setup_server()
```

## 示例

请参阅[examples](examples)目录以获取完整示例。

## 使用SSE连接到MCP服务器

一旦您的集成了MCP的FastAPI应用运行，您可以使用任何支持SSE的MCP客户端连接到它，例如Cursor：

1. 运行您的应用。

2. 在Cursor -> 设置 -> MCP中，使用您的MCP服务器端点的URL（例如，`http://localhost:8000/mcp`）作为sse。

3. Cursor将自动发现所有可用的工具和资源。

## 使用[mcp-proxy stdio](https://github.com/sparfenyuk/mcp-proxy?tab=readme-ov-file#1-stdio-to-sse)连接到MCP服务器

如果您的MCP客户端不支持SSE，例如Claude Desktop：

1. 运行您的应用。

2. 安装[mcp-proxy](https://github.com/sparfenyuk/mcp-proxy?tab=readme-ov-file#installing-via-pypi)，例如：`uv tool install mcp-proxy`。

3. 在Claude Desktop的MCP配置文件（`claude_desktop_config.json`）中添加：

在Windows上：
```json
{
  "mcpServers": {
    "my-api-mcp-proxy": {
        "command": "mcp-proxy",
        "args": ["http://127.0.0.1:8000/mcp"]
    }
  }
}
```
在MacOS上：
```json
{
  "mcpServers": {
    "my-api-mcp-proxy": {
        "command": "/Full/Path/To/Your/Executable/mcp-proxy",
        "args": ["http://127.0.0.1:8000/mcp"]
    }
  }
}
```
通过在终端运行`which mcp-proxy`来找到mcp-proxy的路径。

4. Claude Desktop将自动发现所有可用的工具和资源

## 开发和贡献

感谢您考虑为FastAPI-MCP做出贡献！我们鼓励社区发布问题和拉取请求。

在开始之前，请参阅我们的[贡献指南](CONTRIBUTING.md)。

## 社区

加入[MCParty Slack社区](https://join.slack.com/t/themcparty/shared_invite/zt-30yxr1zdi-2FG~XjBA0xIgYSYuKe7~Xg)，与其他MCP爱好者联系，提问，并分享您使用FastAPI-MCP的经验。

## 要求

- Python 3.10+（推荐3.12）
- uv

## 许可证

MIT许可证。版权所有 (c) 2024 Tadata Inc.
