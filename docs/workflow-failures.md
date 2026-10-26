# 工作流失败反馈

工作流执行失败时，运行记录保存失败节点的 `node_id`、`task_name`、错误代码、异常类型和原因。每次运行最多保存 8 条失败信息，每条消息最多 1500 个字符。`error_task` 保留供旧记录和旧调用方使用。并行层等待已经启动的节点结束后统一保存结果；同层成功节点的输出和耗时保留，后续层不再执行。

运行面板、历史运行记录和聊天中的工作流失败消息显示相同的诊断信息。没有新诊断字段的旧记录仍可显示原有失败任务。聊天工作流失败使用 `Z` 状态；聊天消息更新失败不会撤销已经保存的失败运行记录。

Python 节点默认因异常失败，原因保留具体异常类型和消息。只有显式开启“发生 Python 错误后继续执行”时，节点才将错误作为 `error_msg` 输出交给下游处理。子工作流调用、选择器和循环中的失败会向外层传播，并保留子工作流的失败证据。

API 和 CLI 的失败结果包含：

```json
{
  "error": "WORKFLOW_FAILED",
  "rid": "运行记录 ID",
  "status": "FAILED",
  "failures": [{
    "node_id": "失败节点 ID",
    "task_name": "tools.programming_function",
    "code": "NODE_EXECUTION_FAILED",
    "exception_type": "ValueError",
    "message": "人工验收：输入格式不正确"
  }],
  "next_action": "inspect_error",
  "replay_safety": "unknown"
}
```

已明确识别为节点输入问题的错误使用 `INVALID_ARGUMENT`；其他执行错误使用 `NODE_EXECUTION_FAILED`。失败结果不会承诺重新运行安全，也不会自动重新执行可能已经产生外部影响的节点。CLI 的 `workflow run` 在失败时返回退出码 1；`workflow status RUN_ID` 返回已保存的状态和诊断。

诊断消息会遮盖工作流和设置中识别出的凭据值，以及常见认证消息中的凭据。工作流定义、代码、原始输入和普通输出仍属于运行快照；不要在用于分享或导出的工作流中放入真实密钥。

## 在独立目录启动手工验收

先按 [开发说明](../README_zh.md#项目开发) 安装依赖，并在当前检出的代码中运行 `python backend/build.py -t f`，生成桌面窗口使用的 `backend/web`。该命令会重新生成当前检出目录的前端静态文件。

以下 PowerShell 命令从仓库根目录执行。`$pythonExe` 应指向已经安装项目依赖的 Python；虚拟环境在别处时，将它改为该环境解释器的绝对路径。

```powershell
$repositoryRoot = (Get-Location).Path
$pythonExe = Join-Path $repositoryRoot 'backend/.venv/Scripts/python.exe'
$acceptanceRoot = Join-Path $env:TEMP ('vector-vein-failure-check-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $acceptanceRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $acceptanceRoot 'output') | Out-Null
@{
    data_path = './data'
    api = @{ host = '127.0.0.1'; port = 0 }
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $acceptanceRoot 'config.json') -Encoding utf8
Remove-Item Env:VITE_LOCAL -ErrorAction SilentlyContinue
Remove-Item Env:VECTORVEIN_LLM_SETTINGS_FILE -ErrorAction SilentlyContinue
$env:VECTORVEIN_OUTPUT_DIR = Join-Path $acceptanceRoot 'output'
Set-Location -LiteralPath $acceptanceRoot
& $pythonExe (Join-Path $repositoryRoot 'backend/main.py')
```

配置、数据库、日志和测试输出写入新的验收目录。窗口打开后使用 Python 节点即可验证以下场景，无需配置模型或真实凭据。

1. 新建一个工作流，添加 Python 编程函数节点，代码为：

   ```python
   def main():
       raise ValueError('人工验收：输入格式不正确')
   ```

   保持“发生 Python 错误后继续执行”关闭。运行后应显示失败状态、对应节点、`ValueError` 和中文原因。打开同一条历史记录、关闭后重新打开，信息应保持一致。

2. 添加一个无依赖的成功同层节点，代码为 `def main(): return '同层节点已完成'`；再添加一个无依赖的失败同层节点，代码为 `def main(): raise LookupError('人工验收：缺少数据行')`。重新运行，应同时显示两条失败原因，并保留成功节点输出。接在失败节点后面的节点应没有执行。

3. 将失败代码改为 `def main(): return '输入有效'` 后重新运行。新记录应为完成并正常显示输出，之前的失败记录应保留原有诊断。

4. 将失败工作流作为子工作流通过工作流调用、选择器或循环执行。外层应显示失败，并能看到子工作流的具体失败信息。若通过聊天调用，聊天消息应显示失败；点击对应记录应能查看原因。

5. 查看一条更新前已经失败的历史记录。即使没有 `failures` 字段，也应正常显示旧的失败任务信息。用合成测试值验证凭据遮盖时，只检查诊断文字，不使用真实密钥。

## 自动化验证

在空的临时工作目录中，使用已安装依赖的解释器运行以下绝对路径对应的测试文件：

```text
python -m pytest <仓库>/backend/tests/test_workflow_failures.py <仓库>/backend/tests/test_workflow_failure_entrypoints.py <仓库>/backend/tests/test_workflow_failure_integration.py -q
```

集成测试通过实际 CLI 创建并执行工作流，再启动新进程读取状态，检查并行失败持久化、合成凭据遮盖、同层成功输出、下游停止及修复后成功运行。测试使用临时数据库，不请求模型服务。
