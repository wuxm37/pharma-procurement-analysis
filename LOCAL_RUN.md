# 本机运行与报表导出

## 在本机重新运行

在项目目录打开 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\重新生成.ps1
```

脚本使用已安装的 Codex 捆绑 Python、Pandas 与报表库，不下载数据或安装重复依赖。执行策略参数只对这一次进程生效，不更改系统设置。会更新 `outputs/demo/` 中的生成文件，原始数据保留。

如只重建分析、网页和 CSV：

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" run_project.py
```

仅运行核心测试：

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

没有 Codex 捆绑运行库的电脑，可以在自己的 Python 3.12+ 环境安装 `requirements.txt` 后执行 `python run_project.py`。分析与网页不依赖专用服务。Excel 的重建需要 `@oai/artifact-tool`；缺少此库时仍可查看已生成的 Excel 和重新生成的 CSV，但应重新导出 Excel 后再作同批结果展示，不能把旧工作簿当成新结果。

## 仅更新展示内容

修改页面措辞或报告说明后，可执行 `python run_project.py --presentation-only`。程序校验核心计算代码、参数、测试与结果哈希后复用既有结果，不重新计时。修改计算逻辑时必须完整运行。
