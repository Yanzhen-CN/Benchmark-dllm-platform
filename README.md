# Benchmark-dllm Platform

`Benchmark-dllm` 的轻量化 Streamlit 展示与操作界面。

## 功能

- 按模型、变体和数据集查看评分，使用对比图和表格展示具体结果。
- 查看接受 TPS、功率、峰值显存、单样本时间、接受 token 数和能耗。
- 查看 Profiling 的计算量、阶段构成和逐步变化。
- 比较不同模型在 block 内的接受顺序、Kendall `τ` 和每次 Forward 接受量。
- 查看单样本 Trace、Accept 更新图和 Sudoku 生成动图。
- 直接生成缺失的可视化，并支持删除、回收站和恢复。
- 浏览、放大、全屏查看和复制 PNG/GIF 结果。
- 从页面选择模型、变体和数据集，生成与命令行一致的 Benchmark 任务。

平台直接读取 `Benchmark-dllm/output`，不会复制模型、数据集、评分器或可视化实现。

## 启动

```bash
python start.py
```


首次启动会自动准备平台环境。模型仍使用 `Benchmark-dllm/venv_scripts` 中各自独立的运行环境，不需要手动进入 `.venv`。

默认打开：

```text
http://127.0.0.1:8501
http://<this-device-LAN-IP>:8501
```

## 结果目录

```text
Benchmark-dllm/output/
├── model_output/          # 模型原始输出与 Trace
├── score_output/          # 数据集评分与性能汇总
└── visualization_output/  # 公共图表、Profiling 和单样本可视化
```

平台只读取和展示正式结果。临时日志、平台状态和回收站内容保存在平台自己的状态目录中。

## 自定义路径

Benchmark 或输出目录不在默认位置时，可以设置：

```text
DLLM_BENCH_ROOT=/path/to/Benchmark-dllm
DLLM_BENCH_OUTPUT_ROOT=/path/to/output
```

平台作为 Git 子模块使用时位于：

```text
Benchmark-dllm/platform/
```
