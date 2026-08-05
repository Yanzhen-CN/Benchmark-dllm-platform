# Benchmark-dllm Platform

`Benchmark-dllm-platform` 是 `Benchmark-dllm` 的轻量 Streamlit 调试平台。它负责浏览配置、提交任务、查看运行状态和展示结果，不复制模型、数据集、打分器或可视化实现。

## 从旧平台借鉴什么

[AI-pharmacy Molecule Property Prediction Platform](https://github.com/Yanzhen-CN/AI-pharmacy-Molecule-Property-Prediction-Platform) 中值得保留的是统一入口、YAML 注册、模型/数据集/结果平行组织，以及运行历史浏览。

| 保留 | 不照搬 |
| --- | --- |
| 模型、数据集、结果分析平行组织 | Conda 中心化环境管理 |
| YAML 注册模型和任务 | 在前端环境安装 PyTorch、scikit-learn 等重依赖 |
| 统一入口、运行状态和结果浏览 | 让 Streamlit 同时承担环境、执行、上传和分析 |

当前 Benchmark 已有更清晰的边界：`run_bench.py` 统一调度，`venv_scripts/` 管理各模型独立环境。平台只读取配置、提交命令和展示结果。

## 目录结构

```text
Benchmark-dllm-platform/
|-- app.py
|-- pages/                    # Streamlit 页面
|-- platform_core/            # 配置、命令、进程和结果适配
|-- scripts/                  # 平台环境的创建与启动
|-- docs/architecture.md      # 架构与合并边界
`-- .streamlit/config.toml
```

平台与 Benchmark 的职责边界：

- 模型：继续维护在 `Benchmark-dllm/configs/models` 和 `src/dllm_bench/models`。
- 数据集：继续维护在 `Benchmark-dllm/configs/datasets` 和 `src/dllm_bench/datasets`。
- 实验矩阵：继续维护在 `Benchmark-dllm/configs/experiments`。
- 环境：平台只使用自己的 `.venv`，模型环境由 `Benchmark-dllm/venv_scripts` 管理。
- 结果：平台只读取 `Benchmark-dllm/output`，不修改正式输出结构。

## 启动

Windows 和 Linux 使用同一个入口：

```bash
python start.py
```

入口会在首次运行时自动创建平台自己的轻量环境并安装界面依赖。模型环境仍由 Benchmark 的 `venv_scripts/` 管理，使用平台时不需要接触任何 `.venv` 路径。

默认目录结构：

```text
Benchmark/
|-- Benchmark-dllm/
`-- Benchmark-dllm-platform/
```

目录不同时可设置：

```text
DLLM_BENCH_ROOT=/path/to/Benchmark-dllm
DLLM_BENCH_OUTPUT_ROOT=/path/to/output
```

## 当前功能

- 自动发现模型、variant、数据集和实验矩阵。
- 通过 `run_bench.py` 构造任务，保持模型环境隔离。
- 默认 dry-run；真实运行前需要页面确认。
- 后台任务日志写入 `.state/runs`，不混入 Benchmark 输出。
- 浏览 score metadata 和最新可视化文件。
- 展示各模型启动器与 `.venvs/<model>` 状态。

## 合并条件

- 页面不硬编码模型或数据集名称。
- 页面任务与手工 CLI 使用同一命令路径。
- 平台环境不安装模型依赖。
- 页面不改变 generation、score 和 visualization schema。
- Windows 本地调试与 Linux 远端运行使用相同配置。
