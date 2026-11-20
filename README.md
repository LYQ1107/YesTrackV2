# YesTrack V2：复现、诊断与研究接续

本项目研究：在固定候选与公平推理预算下，如何减少 YesTrack V2 的 referring 语义错误，并以实际候选上的 HOTA 验证改进。此目录接续 A800 聊天“诊断 YesTrack V2 提升空间”，于 2026-11-20 从 NAS 恢复到 A100。

## 阅读入口

- [完整研究历程 TXT](YesTrackV2_研究全历程与方法进展_20261120.txt)：从最初目标、逐步验证与失败，到现有方法、结论和下一步计划。
- [当前状态与研究目标](CURRENT_STATE.md)：已完成工作、证据、缺失项与接续目标。
- 历史报告：[总诊断](yestrack_diagnosis_20261101/analysis/REPORT.md)、[时序验证](yestrack_diagnosis_20261101/analysis/REPORT_round3.md)、[R56 错误分解](yestrack_diagnosis_20261101/analysis/REPORT_R56.md)、[R58 概率检验](yestrack_diagnosis_20261101/analysis/REPORT_R58.md)。
- [实验日志](yestrack_diagnosis_20261101/analysis/research_log.md)、[运行记录](yestrack_diagnosis_20261101/analysis/runs.md)和[冻结方案](yestrack_diagnosis_20261101/analysis/plans/)。

网页版 ChatGPT 可从本公开仓库的 README、当前状态和 TXT 开始阅读，再查看对应代码及报告。原始聊天记录仅保留在恢复工作区。

## 已验证的结论

| 项目 | 结果与边界 |
|---|---|
| 本地 YesTrack V2 基线 | HOTA **40.427**，发布权重推荐 γ=0.6；论文设置 γ=0.4 的本地复现为 40.132。 |
| 实际候选 referring oracle | **51.946**，相对基线空间 **11.519**；这是指定匹配规则下的 oracle。 |
| 相同 Δ10 预算的实际候选验证 | 原生去 TCP **41.211**；固定 HMM 41.087，LOSO HMM 40.149。 |
| R56 | 主要改进空间集中在语义判断；长度/面积 LOSO 过滤仅 **+0.083 HOTA**。 |
| R58 | 在 train 上完成六模型、77,184 请求的 P1–P6 检验；没有模型通过全部冻结标准。Qwen3-VL-2B 单属性校准较好，属性概率相乘和问法稳定性仍有问题。 |

下一步先完成标签人工审计，再在 train 上冻结新方案，验证属性合取、帧级无目标拒绝和独立时序证据；用实际候选对比 40.427 基线与 41.211 去 TCP 对照。目前尚未完成一个经过端到端验证的新 referring 方法。

## 代码入口

分析目录为 [`yestrack_diagnosis_20261101/analysis/`](yestrack_diagnosis_20261101/analysis/)。

| 内容 | 入口 |
|---|---|
| 复现与 oracle 分解 | `prepare_reproduction.py`、`prepare_oracles.py`、`decompose.py` |
| 上下文与联合打分 | `context_probe.py`、`som_probe.py`、`analyze_context.py`、`analyze_som.py` |
| TCP 与实际候选时序验证 | `round3.py`、`actual_temporal_replay.py`、`notcp_actual_replay.py`、`gamma_loso_control.py` |
| R56 | `r56_error_oracles.py`、`validate_r56.py` |
| R58 数据、冻结与推理 | `r58_data.py`、`r58_protocol.py`、`r58_gpu.py`、`plans/r58.json` |
| R58 统计与报告 | `r58_metrics.py`、`r58_analyze.py`、`r58_report.py`、`validate_r58.py` |
| A100 恢复与核验 | [`recovery/`](recovery/) |

官方 YesTrack、TrackEval 和 OneJev 的版本与许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 克隆与 A100 运行

```bash
git clone --recurse-submodules https://github.com/LYQ1107/YesTrackV2.git
```

仓库包含源码、配置、冻结方案、小型注释及研究报告。数据集、checkpoint、大型缓存与运行输出保留在 NAS，克隆后需要按 [`recovery/runtime_paths.json`](recovery/runtime_paths.json) 配置存储和 Python 环境。当前路径表及恢复脚本记录的是已恢复的 A100 部署。

源码、配置和小型报告在 A100；大型数据、模型权重与缓存由 `assets/` 及分析目录中的符号链接访问 NAS。不要对这些链接执行会递归改写源数据的命令。

```bash
cd /data3/liuyeqiang/YesTrackV2
source env.sh

# 读取已有详细指标和六模型原始概率，重新核对结果；不进行模型推理。
"$YESTRACK_PYTHON" recovery/verify.py

# 历史分析脚本的通用启动方式：在进程内转换旧 A800 路径。
# 新实验须使用新编号和新输出目录，避免覆盖历史结果。
"$YESTRACK_PYTHON" recovery/run.py analysis/SCRIPT.py [arguments]

# 在明确指定的空闲 GPU 上复核两候选、单帧 YesTrack 推理。
# 权重从 NAS 连续读取到匿名 RAM，避免 FUSE mmap 随机读取；不写本地磁盘。
CUDA_VISIBLE_DEVICES=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  "$YESTRACK_PYTHON" recovery/gpu_smoke.py
```

`recovery/run.py` 仅转换 `recovery/runtime_paths.json` 中列出的文件系统前缀，保留分析源码、冻结 JSON 和既有数值结果的原始字节。官方模型推理代码保持原样。

R58 专用 GPU 环境及五组当时明确暂缓备份的公开大模型权重尚未恢复；已有六模型 CPU 结果与原始概率可完整读取。详细边界与检查证据见 [恢复状态](CURRENT_STATE.md)。
